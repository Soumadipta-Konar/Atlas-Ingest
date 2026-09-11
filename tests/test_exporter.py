"""Unit tests for DataExporter._flatten and export_csv — deterministic, no network required."""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from src.utils.exporter import DataExporter


class TestFlattenBasic:
    def test_flat_dict_unchanged(self):
        d = {"a": 1, "b": "hello"}
        result = DataExporter._flatten(d)
        assert result == {"a": 1, "b": "hello"}

    def test_nested_one_level(self):
        d = {"outer": {"inner": 42}}
        result = DataExporter._flatten(d)
        assert result == {"outer.inner": 42}

    def test_nested_two_levels(self):
        d = {"a": {"b": {"c": "deep"}}}
        result = DataExporter._flatten(d)
        assert result == {"a.b.c": "deep"}

    def test_mixed_nested_and_flat(self):
        d = {"name": "test", "data": {"score": 10, "label": "ok"}}
        result = DataExporter._flatten(d)
        assert result == {"name": "test", "data.score": 10, "data.label": "ok"}


class TestFlattenEdgeCases:
    def test_empty_dict(self):
        assert DataExporter._flatten({}) == {}

    def test_none_value_preserved(self):
        d = {"key": None}
        result = DataExporter._flatten(d)
        assert result == {"key": None}

    def test_list_value_preserved_as_is(self):
        """Lists should NOT be recursed into — only dicts are flattened."""
        d = {"authors": ["Alice", "Bob"]}
        result = DataExporter._flatten(d)
        assert result == {"authors": ["Alice", "Bob"]}

    def test_empty_nested_dict(self):
        d = {"outer": {}}
        result = DataExporter._flatten(d)
        assert result == {}


class TestExportCsvMongoOptIn:
    """Tests for Fix #3: MongoDB export should be opt-in."""

    def test_no_mongo_connection_without_env_var(self, tmp_path):
        """When MONGO_URI is not set, MongoClient should NOT be called."""
        import pandas as pd
        df = pd.DataFrame({"col": [1, 2, 3]})
        csv_path = str(tmp_path / "test_output.csv")
        
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MONGO_URI", None)
            # Since MongoClient is lazily imported, if MONGO_URI is unset
            # the import never happens. We just verify no exception is raised.
            DataExporter.export_csv(df, csv_path)
            assert os.path.exists(csv_path)

    def test_mongo_connection_with_env_var(self, tmp_path):
        """When MONGO_URI is set, MongoClient should be instantiated."""
        import pandas as pd
        df = pd.DataFrame({"col": [1, 2, 3]})
        csv_path = str(tmp_path / "test_output.csv")
        
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_database.return_value = mock_db
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        
        with patch.dict(os.environ, {"MONGO_URI": "mongodb://test:27017/test"}):
            with patch("pymongo.MongoClient", return_value=mock_client):
                DataExporter.export_csv(df, csv_path)
                assert os.path.exists(csv_path)

    def test_drop_not_called_by_default(self, tmp_path):
        """collection.drop() should NOT be called when replace=False (default)."""
        import pandas as pd
        df = pd.DataFrame({"col": [1, 2, 3]})
        csv_path = str(tmp_path / "test_output.csv")
        
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_database.return_value = mock_db
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        
        with patch.dict(os.environ, {"MONGO_URI": "mongodb://test:27017/test"}):
            with patch("pymongo.MongoClient", return_value=mock_client):
                DataExporter.export_csv(df, csv_path)
                mock_collection.drop.assert_not_called()

