"""LiteLLM model routing configuration for ADK agents.

Two tiers:
  - fast: query routing, fact extraction, entity extraction, classification
  - quality: response generation, wiki synthesis
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelTier:
    """Primary + fallback model for an agent tier."""

    primary: str
    fallback: str


FAST_TIER = ModelTier(
    primary="gemini/gemini-2.0-flash-lite",
    fallback="anthropic/claude-haiku-4-5",
)

QUALITY_TIER = ModelTier(
    primary="gemini/gemini-2.0-flash",
    fallback="anthropic/claude-sonnet-4-6",
)

# Maps agent purpose to its tier
AGENT_MODEL_MAP: dict[str, ModelTier] = {
    "query_routing": FAST_TIER,
    "fact_extraction": FAST_TIER,
    "entity_extraction": FAST_TIER,
    "classification": FAST_TIER,
    "semantic_retrieval": FAST_TIER,
    "graph_retrieval": FAST_TIER,
    "cluster_assignment": FAST_TIER,
    "health_check": FAST_TIER,
    "response_generation": QUALITY_TIER,
    "wiki_synthesis": QUALITY_TIER,
}


def get_model(tier: str) -> str:
    """Return the primary LiteLLM model string for a tier ('fast' or 'quality')."""
    if tier == "fast":
        return FAST_TIER.primary
    if tier == "quality":
        return QUALITY_TIER.primary
    raise ValueError(f"Unknown tier: {tier!r}. Use 'fast' or 'quality'.")


def get_model_for_agent(agent_purpose: str) -> str:
    """Return the primary model string for a specific agent purpose."""
    tier = AGENT_MODEL_MAP.get(agent_purpose)
    if tier is None:
        raise ValueError(
            f"Unknown agent purpose: {agent_purpose!r}. "
            f"Available: {list(AGENT_MODEL_MAP.keys())}"
        )
    return tier.primary


def get_fallback_for_agent(agent_purpose: str) -> str:
    """Return the fallback model string for a specific agent purpose."""
    tier = AGENT_MODEL_MAP.get(agent_purpose)
    if tier is None:
        raise ValueError(f"Unknown agent purpose: {agent_purpose!r}")
    return tier.fallback
