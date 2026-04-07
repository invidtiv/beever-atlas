"""Tests for truncated JSON recovery utilities."""

from __future__ import annotations

import json

import pytest

from beever_atlas.services.json_recovery import (
    recover_entities_from_truncated,
    recover_facts_from_truncated,
    recover_truncated_json,
)


class TestRecoverTruncatedJson:
    def test_valid_json_passes_through(self):
        data = {"facts": [{"text": "Alice built Atlas", "quality_score": 0.9}]}
        result = recover_truncated_json(json.dumps(data))
        assert result == data

    def test_truncated_mid_object_recovers(self):
        # Two complete fact objects followed by a truncated third
        text = '{"facts": [{"id": 1, "text": "fact one"}, {"id": 2, "text": "fact two"}, {"id": 3, "tex'
        result = recover_truncated_json(text)
        assert result is not None
        assert isinstance(result, dict)
        facts = result.get("facts", [])
        assert len(facts) == 2
        assert facts[0]["id"] == 1
        assert facts[1]["id"] == 2

    def test_truncated_before_any_object_returns_none(self):
        # No complete object boundary exists
        text = '{"facts": [{"id": 1, "tex'
        result = recover_truncated_json(text)
        assert result is None

    def test_malformed_input_returns_none(self):
        result = recover_truncated_json("this is not json at all")
        assert result is None

    def test_empty_string_returns_none(self):
        assert recover_truncated_json("") is None
        assert recover_truncated_json("   ") is None

    def test_valid_list_passes_through(self):
        data = [1, 2, 3]
        result = recover_truncated_json(json.dumps(data))
        assert result == data


class TestRecoverFacts:
    def test_recovers_complete_facts(self):
        # Two complete facts, third truncated
        text = '{"facts": [{"text": "Alice built Atlas", "quality_score": 0.9}, {"text": "Bob joined later", "quality_score": 0.8}, {"text": "Carol was trun'
        result = recover_facts_from_truncated(text)
        assert result is not None
        assert "facts" in result
        assert len(result["facts"]) == 2
        assert result["facts"][0]["text"] == "Alice built Atlas"

    def test_empty_facts_array(self):
        text = json.dumps({"facts": []})
        result = recover_facts_from_truncated(text)
        assert result is not None
        assert result["facts"] == []

    def test_returns_none_on_garbage(self):
        result = recover_facts_from_truncated("not json")
        assert result is None

    def test_non_dict_top_level_returns_none(self):
        result = recover_facts_from_truncated(json.dumps([1, 2, 3]))
        assert result is None

    def test_missing_facts_key_returns_empty_list(self):
        text = json.dumps({"other_key": "value"})
        result = recover_facts_from_truncated(text)
        assert result is not None
        assert result["facts"] == []


class TestRecoverEntities:
    def test_recovers_entities_and_relationships(self):
        data = {
            "entities": [
                {"name": "Alice", "type": "person", "scope": "global"},
                {"name": "Atlas", "type": "project", "scope": "global"},
            ],
            "relationships": [
                {"source": "Alice", "target": "Atlas", "type": "built", "confidence": 0.95}
            ],
        }
        result = recover_entities_from_truncated(json.dumps(data))
        assert result is not None
        assert len(result["entities"]) == 2
        assert len(result["relationships"]) == 1

    def test_truncated_entities_recovers_complete_ones(self):
        text = '{"entities": [{"name": "Alice", "type": "person"}, {"name": "Bob", "type": "person"}, {"name": "Trun'
        result = recover_entities_from_truncated(text)
        assert result is not None
        assert len(result["entities"]) == 2
        assert result["relationships"] == []

    def test_returns_none_on_garbage(self):
        result = recover_entities_from_truncated("not json")
        assert result is None

    def test_non_dict_top_level_returns_none(self):
        result = recover_entities_from_truncated(json.dumps([1, 2, 3]))
        assert result is None

    def test_empty_entities_and_relationships(self):
        text = json.dumps({"entities": [], "relationships": []})
        result = recover_entities_from_truncated(text)
        assert result is not None
        assert result["entities"] == []
        assert result["relationships"] == []

    def test_missing_keys_default_to_empty(self):
        text = json.dumps({"other": "value"})
        result = recover_entities_from_truncated(text)
        assert result is not None
        assert result["entities"] == []
        assert result["relationships"] == []
