import logging
import json
from typing import List, Dict, Optional
from thefuzz import process, fuzz

logger = logging.getLogger(__name__)

DEFAULT_SEED_ENTITIES = [
    "OpenAI",
    "Anthropic",
    "DeepMind",
    "Mistral AI",
    "Cohere",
    "Hugging Face",
    "Perplexity",
    "Scale AI",
    "Midjourney",
    "Stability AI",
    "Meta AI",
    "Google AI",
    "xAI",
    "Inflection AI",
    "Databricks",
    "Runway",
    "Jasper AI",
    "Adept AI",
    "Character AI",
    "Together AI",
    "Replicate",
    "Anyscale",
    "Weights & Biases",
    "LangChain",
    "Pinecone",
    "Weaviate",
    "Galileo AI",
    "Snorkel AI",
    "Mosaic ML",
    "Lightning AI",
    "Aleph Alpha",
    "AI21 Labs",
    "Imbue",
    "Contextual AI",
    "Descript",
    "ElevenLabs",
    "Pika Labs",
    "Luma AI",
    "Synthesia",
    "Twelve Labs",
    "Tome",
    "Glean",
    "Vectara",
    "Qdrant",
    "Chroma",
    "LlamaIndex",
    "Fixie AI",
    "Dust",
    "Comet ML",
    "Superagent"
]

class EntityResolver:
    """Deterministic Entity Resolution using fuzzy matching against a seed list
    and pairwise deduplication within scraped batches."""
    
    def __init__(self, seed_entities: List[str] = None, seed_file: str = None):
        if seed_file:
            try:
                with open(seed_file, 'r') as f:
                    self.seed_entities = json.load(f)
                logger.info(f"Loaded {len(self.seed_entities)} seed entities from {seed_file}")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to load seed file '{seed_file}': {e}. Using defaults.")
                self.seed_entities = DEFAULT_SEED_ENTITIES
        else:
            self.seed_entities = seed_entities or DEFAULT_SEED_ENTITIES
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

    def deduplicate_batch(self, names: List[str], threshold: int = 85) -> Dict[str, str]:
        """Deduplicates a batch of names using pairwise fuzzy comparison.
        
        First canonicalizes each name against the seed list, then merges
        near-duplicates within the unresolved set (names that didn't match
        any seed entity) so long-tail entities get properly merged.
        
        Returns a mapping {original_name: canonical_name}.
        """
        mapping: Dict[str, str] = {}
        
        # Step 1: Canonicalize against seed list
        unresolved = []
        for name in names:
            canonical = self.canonicalize(name, threshold)
            mapping[name] = canonical
            if canonical == name:
                # Didn't match any seed — mark as unresolved for pairwise dedup
                unresolved.append(name)
        
        # Step 2: Pairwise dedup among unresolved names
        if len(unresolved) > 1:
            canonical_groups: List[str] = []  # first-seen representative for each cluster
            
            for name in unresolved:
                clean = name.replace(",", "").replace(".", "").strip()
                matched = False
                
                for representative in canonical_groups:
                    score = fuzz.WRatio(clean, representative.replace(",", "").replace(".", "").strip())
                    if score >= threshold:
                        mapping[name] = representative
                        self._log_mapping(name, representative, score)
                        matched = True
                        break
                
                if not matched:
                    canonical_groups.append(name)
                    # mapping[name] already == name from step 1
        
        return mapping

    def _log_mapping(self, raw: str, canonical: str, score: int):
        self.mapping_log.append({
            "Raw Name": raw,
            "Canonical Name": canonical,
            "Match Score": score
        })

    def get_mapping_log(self) -> List[dict]:
        return self.mapping_log

