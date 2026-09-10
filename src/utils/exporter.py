import pandas as pd
import logging
from typing import List
from pydantic import BaseModel
import os
from pymongo import MongoClient

logger = logging.getLogger(__name__)

class DataExporter:

    @staticmethod
    def _flatten(d: dict, parent_key: str = "") -> dict:
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
        if not entities:
            return pd.DataFrame()
        return pd.DataFrame([DataExporter._flatten(e.model_dump()) for e in entities])

    @staticmethod
    def export_csv(df: pd.DataFrame, filename: str):
        df.to_csv(filename, index=False)
        logger.info(f"Exported {len(df)} rows to {filename}")
        
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/atlas_ingest")
        if mongo_uri:
            try:
                client = MongoClient(mongo_uri)
                db = client.get_database("atlas_ingest")
                collection_name = filename.split("/")[-1].split(".")[0]
                collection = db[collection_name]
                collection.drop()
                records = df.to_dict("records")
                if records:
                    collection.insert_many(records)
            except Exception as e:
                logger.error(f"Mongo error: {e}")

    @staticmethod
    def export_mapping_log(log_data: List[dict], filename: str):
        df = pd.DataFrame(log_data)
        df.to_csv(filename, index=False)
        logger.info(f"Exported Mapping Log to {filename}")
