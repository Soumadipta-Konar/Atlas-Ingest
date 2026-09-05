import logging
import asyncio
from typing import Type, TypeVar, Any, Optional
from pydantic import BaseModel
import litellm
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class LLMOrchestrator:
    """Multi-tier LLM fallback chain with schema enforcement."""
    
    # Fallback chain prioritizing cost/speed to complex reasoning
    MODELS = [
        "gemini/gemini-1.5-flash",
        "groq/llama3-8b-8192",
        "deepseek/deepseek-chat"
    ]

    def __init__(self):
        litellm.drop_params = True
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(litellm.RateLimitError),
        reraise=True
    )
    async def _call_model(self, model: str, prompt: str, schema: Type[T]) -> T:
        """Internal call with 429 exponential backoff handling."""
        logger.debug(f"Attempting extraction with {model}")
        try:
            # Using instructor/litellm structure for schema extraction
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format=schema,
            )
            return schema.model_validate_json(response.choices[0].message.content)
        except Exception as e:
            logger.warning(f"Model {model} failed: {str(e)}")
            raise

    async def extract_entity(self, text_chunk: str, schema: Type[T]) -> Optional[T]:
        """Executes the fallback chain to extract structured data."""
        prompt = f"Extract the following text into the exact JSON schema provided.\nText:\n{text_chunk}"
        
        for model in self.MODELS:
            try:
                return await self._call_model(model, prompt, schema)
            except litellm.RateLimitError:
                # Handled by tenacity, if it bubbles up, all retries failed
                logger.error(f"Rate limit exhausted for {model}")
                continue
            except Exception as e:
                logger.error(f"Extraction error with {model}: {e}")
                continue
                
        logger.error("All models in the fallback chain failed.")
        return None
