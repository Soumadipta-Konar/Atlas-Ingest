import pandas as pd
import logging
from typing import List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class DataExporter:
    """Exports structured entities to pandas DataFrames and CSVs."""
    
    @staticmethod
    def _flatten(d: dict, parent_key: str = "") -> dict:
        """Recursively flattens an arbitrarily-nested dict using dot notation."""
        items = {}
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(DataExporter._flatten(v, new_key))
            else:
                items[new_key] = v
        return items

    @staticmethod
    def entities_to_df(entities: List[BaseModel]) -> pd.DataFrame:
        """Flattens nested pydantic models (at any depth) into a 2D dataframe."""
        if not entities:
            return pd.DataFrame()
        return pd.DataFrame([DataExporter._flatten(e.model_dump()) for e in entities])

    @staticmethod
    def export_csv(df: pd.DataFrame, filename: str):
        """Exports dataframe to a CSV file."""
        df.to_csv(filename, index=False)
        logger.info(f"Exported {len(df)} rows to {filename}")

    @staticmethod
    def export_mapping_log(log_data: List[dict], filename: str):
        """Exports the entity mapping log."""
        df = pd.DataFrame(log_data)
        df.to_csv(filename, index=False)
        logger.info(f"Exported Mapping Log to {filename}")
