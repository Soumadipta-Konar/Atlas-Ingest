"""Unit tests for LLMOrchestrator — fallback chain logic with mocked litellm."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.llm.orchestrator import LLMOrchestrator
from pydantic import BaseModel

pytestmark = pytest.mark.asyncio(loop_scope="function")


class DummyEntity(BaseModel):
    name: str
    value: int = 0


class TestFallbackChain:
    @pytest.mark.asyncio
    async def test_first_model_success_skips_fallbacks(self):
        """If the first model succeeds, no other models are tried."""
        orch = LLMOrchestrator()
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "test", "value": 42}'
        
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_call:
            result = await orch.extract_entity("some text", DummyEntity)
            
            assert result is not None
            assert result.name == "test"
            assert result.value == 42
            # Should only call the first model
            assert mock_call.call_count == 1
            assert mock_call.call_args[1]["model"] == "gemini/gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_fallback_to_second_model_on_failure(self):
        """If the first model fails, the second model is tried."""
        orch = LLMOrchestrator()
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "fallback", "value": 99}'
        
        call_count = 0
        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Model 1 failed")
            return mock_response
        
        with patch("litellm.acompletion", side_effect=side_effect):
            result = await orch.extract_entity("some text", DummyEntity)
            
            assert result is not None
            assert result.name == "fallback"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_models_fail_returns_none(self):
        """If all models in the chain fail, extract_entity returns None."""
        orch = LLMOrchestrator()
        
        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=Exception("fail")):
            result = await orch.extract_entity("some text", DummyEntity)
            assert result is None

    def test_models_list_uses_current_defaults(self):
        """Verify the model list contains current (not retired) model IDs."""
        orch = LLMOrchestrator()
        assert "gemini/gemini-2.5-flash" in orch.models
        assert "groq/llama-3.3-70b-versatile" in orch.models
        assert "deepseek/deepseek-chat" in orch.models
        # Ensure retired models are NOT in the list
        assert "gemini/gemini-1.5-flash-002" not in orch.models
        assert "groq/llama-3.1-8b-instant" not in orch.models


class TestVerifyModels:
    @pytest.mark.asyncio
    async def test_verify_removes_dead_models(self):
        """verify_models() should remove models that fail the health check."""
        orch = LLMOrchestrator()
        
        call_count = 0
        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            model = kwargs.get("model", "")
            if "gemini" in model:
                raise Exception("dead")
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "OK"
            return mock_resp
        
        with patch("litellm.acompletion", side_effect=side_effect):
            alive = await orch.verify_models()
            
            assert "gemini/gemini-2.5-flash" not in alive
            assert len(alive) == 2
            assert orch.models == alive

    @pytest.mark.asyncio
    async def test_verify_keeps_defaults_if_all_fail(self):
        """If all models fail health check, keep defaults as last resort."""
        orch = LLMOrchestrator()
        original_models = list(orch.models)
        
        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=Exception("all dead")):
            alive = await orch.verify_models()
            
            assert alive == []
            # Should keep original models as fallback
            assert orch.models == original_models
