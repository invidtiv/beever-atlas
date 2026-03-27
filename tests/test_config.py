"""Tests for config system and LiteLLM model routing."""

import os

import pytest


class TestSettings:
    def test_config_loads_defaults(self):
        from beever_atlas.infra.config import Settings

        settings = Settings()
        assert settings.weaviate_url == "http://localhost:8080"
        assert settings.neo4j_uri == "bolt://localhost:7687"
        assert settings.mongodb_uri == "mongodb://localhost:27017/beever_atlas"
        assert settings.redis_url == "redis://localhost:6379"

    def test_config_loads_from_env(self, monkeypatch):
        from beever_atlas.infra.config import Settings

        monkeypatch.setenv("WEAVIATE_URL", "http://weaviate:9999")
        monkeypatch.setenv("NEO4J_URI", "bolt://neo4j:7777")
        settings = Settings()
        assert settings.weaviate_url == "http://weaviate:9999"
        assert settings.neo4j_uri == "bolt://neo4j:7777"

    def test_neo4j_user_password_parsing(self):
        from beever_atlas.infra.config import Settings

        settings = Settings(neo4j_auth="admin/secretpass")
        assert settings.neo4j_user == "admin"
        assert settings.neo4j_password == "secretpass"

    def test_all_api_key_fields_exist(self):
        from beever_atlas.infra.config import Settings

        settings = Settings()
        assert hasattr(settings, "google_api_key")
        assert hasattr(settings, "anthropic_api_key")
        assert hasattr(settings, "jina_api_key")
        assert hasattr(settings, "tavily_api_key")


class TestLiteLLMConfig:
    def test_fast_tier_model(self):
        from beever_atlas.infra.litellm_config import get_model

        model = get_model("fast")
        assert model == "gemini/gemini-2.0-flash-lite"

    def test_quality_tier_model(self):
        from beever_atlas.infra.litellm_config import get_model

        model = get_model("quality")
        assert model == "gemini/gemini-2.0-flash"

    def test_unknown_tier_raises(self):
        from beever_atlas.infra.litellm_config import get_model

        with pytest.raises(ValueError, match="Unknown tier"):
            get_model("unknown")

    def test_fast_tier_fallback(self):
        from beever_atlas.infra.litellm_config import get_fallback_for_agent

        fallback = get_fallback_for_agent("query_routing")
        assert fallback == "anthropic/claude-haiku-4-5"

    def test_quality_tier_fallback(self):
        from beever_atlas.infra.litellm_config import get_fallback_for_agent

        fallback = get_fallback_for_agent("response_generation")
        assert fallback == "anthropic/claude-sonnet-4-6"

    def test_agent_model_mapping(self):
        from beever_atlas.infra.litellm_config import get_model_for_agent

        assert get_model_for_agent("query_routing") == "gemini/gemini-2.0-flash-lite"
        assert get_model_for_agent("response_generation") == "gemini/gemini-2.0-flash"

    def test_unknown_agent_purpose_raises(self):
        from beever_atlas.infra.litellm_config import get_model_for_agent

        with pytest.raises(ValueError, match="Unknown agent purpose"):
            get_model_for_agent("nonexistent")
