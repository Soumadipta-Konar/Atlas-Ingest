import logging
from typing import List, Optional
from thefuzz import process

logger = logging.getLogger(__name__)

class EntityResolver:
    """Deterministic Entity Resolution using fuzzy matching against a seed list."""
    
    def __init__(self, seed_entities: List[str] = None):
        # Mock database of known AI startups (Phase IV requirement)
        self.seed_entities = seed_entities or [
            "OpenAI",
            "Anthropic",
            "DeepMind",
            "Mistral AI",
            "Cohere",
            "Hugging Face",
            "Perplexity",
            "Scale AI",
            "Midjourney",
            "Stability AI"
        ]
        self.mapping_log = []

    def canonicalize(self, raw_name: str, threshold: int = 85) -> str:
        """Maps a raw extracted entity to the canonical list if above threshold."""
        # Clean basic punctuation
        clean_raw = raw_name.replace(",", "").replace(".", "").strip()
        
        result = process.extractOne(clean_raw, self.seed_entities)
        
        if result and result[1] >= threshold:
            canonical = result[0]
            logger.debug(f"Resolved '{raw_name}' -> '{canonical}' (Score: {result[1]})")
            self._log_mapping(raw_name, canonical, result[1])
            return canonical
            
        logger.debug(f"No strong match for '{raw_name}'. Keeping raw.")
        self._log_mapping(raw_name, raw_name, 0)
        return raw_name

    def _log_mapping(self, raw: str, canonical: str, score: int):
        self.mapping_log.append({
            "Raw Name": raw,
            "Canonical Name": canonical,
            "Match Score": score
        })

    def get_mapping_log(self) -> List[dict]:
        return self.mapping_log
