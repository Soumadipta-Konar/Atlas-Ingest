"""Unit tests for EntityResolver — deterministic, no network required."""
import pytest
from src.resolution.resolver import EntityResolver, DEFAULT_SEED_ENTITIES


@pytest.fixture
def resolver():
    return EntityResolver()


class TestCanonicalizeKnownAliases:
    def test_exact_match(self, resolver):
        assert resolver.canonicalize("OpenAI") == "OpenAI"

    def test_case_insensitive_match(self, resolver):
        # "openai" should resolve to "OpenAI" at high confidence
        result = resolver.canonicalize("openai")
        assert result == "OpenAI"

    def test_common_alias_anthropic(self, resolver):
        result = resolver.canonicalize("Anthropic AI")
        assert result == "Anthropic"

    def test_hugging_face_variant(self, resolver):
        result = resolver.canonicalize("HuggingFace")
        assert result == "Hugging Face"

    def test_deepmind_variant(self, resolver):
        result = resolver.canonicalize("Google DeepMind")
        # Should match DeepMind or Google AI (both valid) — just confirm it resolves to something in the list
        assert result in DEFAULT_SEED_ENTITIES


class TestCanonicalizeUnknownsPassThrough:
    def test_unknown_entity_passes_through(self, resolver):
        raw = "Totally Unknown Startup XYZ 12345"
        result = resolver.canonicalize(raw)
        assert result == raw

    def test_gibberish_passes_through(self, resolver):
        raw = "asdfghjklqwerty"
        result = resolver.canonicalize(raw)
        assert result == raw


class TestMappingLog:
    def test_log_populated_after_canonicalize(self, resolver):
        resolver.canonicalize("OpenAI")
        log = resolver.get_mapping_log()
        assert len(log) == 1
        assert log[0]["Raw Name"] == "OpenAI"

    def test_log_grows_with_each_call(self, resolver):
        resolver.canonicalize("OpenAI")
        resolver.canonicalize("SomeUnknownThing999")
        assert len(resolver.get_mapping_log()) == 2


class TestSeedListSize:
    def test_default_seed_list_has_50_entries(self):
        assert len(DEFAULT_SEED_ENTITIES) == 50
