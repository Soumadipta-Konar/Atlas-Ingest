import pandas as pd
import logging
from typing import List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class DataExporter:
    """Exports structured entities to pandas DataFrames and CSVs."""
    
    @staticmethod
    def entities_to_df(entities: List[BaseModel]) -> pd.DataFrame:
        """Flattens nested pydantic models into a 2D dataframe."""
        if not entities:
            return pd.DataFrame()
            
        # Convert to dict and flatten nested 'source' and 'content' keys
        flattened_data = []
        for entity in entities:
            raw_dict = entity.model_dump()
            flat_dict = {}
            for k, v in raw_dict.items():
                if isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        # Flatten with dot notation e.g., 'content.entityName'
                        flat_dict[f"{k}.{sub_k}"] = sub_v
                else:
                    flat_dict[k] = v
            flattened_data.append(flat_dict)
            
        return pd.DataFrame(flattened_data)

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
