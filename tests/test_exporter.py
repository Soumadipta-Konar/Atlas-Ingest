"""Unit tests for DataExporter._flatten — deterministic, no network required."""
import pytest
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
