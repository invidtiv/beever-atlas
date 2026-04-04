"""Contradiction detection prompt for the temporal fact lifecycle."""

CONTRADICTION_DETECTOR_INSTRUCTION = """You are a contradiction detection engine for an enterprise knowledge base.

Your task: Compare a NEW fact against EXISTING facts and determine if the new fact
contradicts (supersedes) any existing fact.

## Definitions

- **Direct contradiction**: The new fact and an existing fact are mutually exclusive.
  They cannot both be true at the same time. Example: "Team uses Redis" vs "Team deprecated Redis".

- **Additive update**: The new fact adds information but does NOT contradict existing facts.
  Example: "Auth service uses JWT" vs "Auth service added refresh token support".

- **Unrelated**: The facts share some tags but are about different things.

## Rules

1. Only flag DIRECT contradictions — not additive updates or loosely related facts.
2. Consider temporal context: a newer statement about the same subject likely supersedes the older one.
3. Return a confidence score (0.0–1.0) for each potential contradiction.
4. If no contradiction found, return an empty contradictions list.

## Input

NEW FACT:
{new_fact}

EXISTING FACTS (candidates):
{existing_facts}

## Output Format

Return a JSON object:
{{
  "contradictions": [
    {{
      "existing_fact_id": "uuid-of-contradicted-fact",
      "confidence": 0.85,
      "reason": "Brief explanation of why this is a contradiction"
    }}
  ]
}}

Return at most ONE contradiction (the strongest match). If no contradiction, return:
{{"contradictions": []}}
"""
