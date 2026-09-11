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


class TestDeduplicateBatch:
    """Tests for Fix #10: pairwise dedup within scraped batches."""

    def test_near_duplicates_get_merged(self, resolver):
        """Two similar unknown names should be merged to the same canonical."""
        names = ["Acme AI Solutions", "Acme AI Solution"]
        mapping = resolver.deduplicate_batch(names)
        # Both should map to the same canonical name
        assert mapping["Acme AI Solutions"] == mapping["Acme AI Solution"]

    def test_known_entities_resolve_to_seed(self, resolver):
        """Known entities should still resolve to their seed list match."""
        names = ["OpenAI", "openai", "Anthropic AI"]
        mapping = resolver.deduplicate_batch(names)
        assert mapping["OpenAI"] == "OpenAI"
        assert mapping["openai"] == "OpenAI"
        assert mapping["Anthropic AI"] == "Anthropic"

    def test_distinct_unknowns_stay_separate(self, resolver):
        """Completely different unknown names should NOT be merged."""
        names = ["Quantum Computing Labs Alpha", "BioTech Ventures Omega"]
        mapping = resolver.deduplicate_batch(names)
        assert mapping["Quantum Computing Labs Alpha"] != mapping["BioTech Ventures Omega"]

    def test_empty_batch(self, resolver):
        """Empty input should return empty mapping."""
        mapping = resolver.deduplicate_batch([])
        assert mapping == {}

    def test_single_item_batch(self, resolver):
        """Single-item batch should pass through unchanged."""
        mapping = resolver.deduplicate_batch(["Some Random Startup XYZ"])
        assert mapping["Some Random Startup XYZ"] == "Some Random Startup XYZ"

    def test_mixed_known_and_unknown_duplicates(self, resolver):
        """Mix of known and unknown entities with near-duplicates among unknowns."""
        names = [
            "OpenAI",
            "TechFlow AI Platform",
            "TechFlow AI Platforms",
            "Anthropic"
        ]
        mapping = resolver.deduplicate_batch(names)
        assert mapping["OpenAI"] == "OpenAI"
        assert mapping["Anthropic"] == "Anthropic"
        # Near-duplicate unknowns should merge
        assert mapping["TechFlow AI Platform"] == mapping["TechFlow AI Platforms"]

