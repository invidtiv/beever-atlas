"""Query decomposer: classifies questions as simple or complex and decomposes them."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field

from beever_atlas.agents.query.prompts import DECOMPOSITION_PROMPT

logger = logging.getLogger(__name__)

# Patterns signaling a complex multi-part question
_COMPLEX_PATTERNS = re.compile(
    r"\b(and|vs\.?|versus|compare|also|additionally|furthermore|"
    r"as well as|not only|but also|both|between|difference between|"
    r"still|anymore|currently|nowadays|is it still|should we)\b",
    re.IGNORECASE,
)


@dataclass
class SubQuery:
    query: str
    focus: str
    is_external: bool = False


@dataclass
class QueryPlan:
    original: str
    is_simple: bool
    internal_queries: list[SubQuery] = field(default_factory=list)
    external_queries: list[SubQuery] = field(default_factory=list)


def _is_simple(question: str) -> bool:
    """Fast-path heuristic: returns True if question can skip decomposition.

    Simple questions: single entity/topic, no conjunctions, short.
    Cost: $0 (no LLM call).
    """
    if _COMPLEX_PATTERNS.search(question):
        return False
    if len(question.split()) > 15:
        return False
    return True


async def decompose(question: str) -> QueryPlan:
    """Classify a question and optionally decompose it into parallel sub-queries.

    Simple questions → fast path (no LLM call, $0 cost).
    Complex questions → decompose via qa_router (Flash Lite).
    Failure → fall back to original question as a single internal query.
    """
    if _is_simple(question):
        logger.debug("QueryDecomposer: fast path for %r", question[:60])
        return QueryPlan(
            original=question,
            is_simple=True,
            internal_queries=[SubQuery(query=question, focus="main")],
        )

    return await _decompose_complex(question)


async def _decompose_complex(question: str) -> QueryPlan:
    """LLM-based decomposition for complex questions."""
    try:
        from beever_atlas.llm.provider import get_llm_provider

        provider = get_llm_provider()
        model_name = provider.resolve_model("qa_router")

        # Ollama models return a LiteLlm object — fall back to single query
        if not isinstance(model_name, str):
            logger.debug("QueryDecomposer: Ollama model, skipping LLM decomposition")
            return QueryPlan(
                original=question,
                is_simple=False,
                internal_queries=[SubQuery(query=question, focus="main")],
            )

        import google.generativeai as genai  # type: ignore[import]

        prompt = DECOMPOSITION_PROMPT.format(question=question)
        model = genai.GenerativeModel(model_name)

        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt),
            timeout=10.0,
        )
        text = response.text.strip()

        # Strip markdown fences if present
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

        data = json.loads(text)

        internal_queries = [
            SubQuery(query=q["query"], focus=q.get("focus", ""), is_external=False)
            for q in data.get("internal_queries", [])[:4]  # max 4
        ]
        external_queries = [
            SubQuery(query=q["query"], focus=q.get("focus", ""), is_external=True)
            for q in data.get("external_queries", [])[:2]  # max 2
        ]

        if not internal_queries:
            internal_queries = [SubQuery(query=question, focus="main")]

        logger.debug(
            "QueryDecomposer: %d internal + %d external sub-queries for %r",
            len(internal_queries),
            len(external_queries),
            question[:60],
        )

        return QueryPlan(
            original=question,
            is_simple=False,
            internal_queries=internal_queries,
            external_queries=external_queries,
        )

    except (TimeoutError, asyncio.TimeoutError):
        logger.warning("QueryDecomposer: decomposition timed out, using single query")
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("QueryDecomposer: JSON parse failed (%s), using single query", exc)
    except Exception:
        logger.warning("QueryDecomposer: unexpected error, using single query", exc_info=True)

    # Fallback: single internal query, no decomposition error surfaced to user
    return QueryPlan(
        original=question,
        is_simple=False,
        internal_queries=[SubQuery(query=question, focus="main")],
    )
