"""Truncated JSON recovery utilities.

When an LLM response is cut off due to max_output_tokens, the JSON payload
is incomplete. This module attempts to salvage as many complete objects as
possible from the partial text rather than discarding the entire response.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def recover_truncated_json(text: str) -> dict | list | None:
    """Attempt to parse JSON, recovering partial data if the text is truncated.

    Algorithm:
    1. Try a straight ``json.loads`` — return immediately if it succeeds.
    2. Search backwards for the last complete object boundary (``},`` or ``}]``).
    3. Truncate at that boundary and close any open arrays/objects.
    4. Try ``json.loads`` on the repaired text.
    5. Return ``None`` if recovery fails.

    Args:
        text: Raw text that may contain truncated JSON.

    Returns:
        Parsed JSON value (dict or list), or ``None`` on failure.
    """
    if not text or not text.strip():
        return None

    stripped = text.strip()

    # Fast path — text is already valid JSON.
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Find the last complete object boundary.
    recovered = _find_last_complete_boundary(stripped)
    if recovered is None:
        logger.debug("json_recovery: no object boundary found, cannot recover")
        return None

    # Close any unmatched opening brackets/braces.
    closed = _close_open_structures(recovered)

    try:
        result = json.loads(closed)
        logger.debug("json_recovery: successfully recovered truncated JSON")
        return result
    except json.JSONDecodeError as exc:
        logger.debug("json_recovery: recovery attempt failed: %s", exc)
        return None


def recover_facts_from_truncated(text: str) -> dict | None:
    """Recover a ``{"facts": [...]}`` response that may be truncated.

    Parses as much of the ``facts`` list as possible and returns a dict
    with the complete fact objects that were found.

    Args:
        text: Raw LLM output, possibly truncated mid-JSON.

    Returns:
        ``{"facts": [<complete fact objects>]}`` or ``None`` if nothing
        could be recovered.
    """
    result = recover_truncated_json(text)
    if result is None:
        logger.warning(
            "json_recovery: could not recover any facts from truncated JSON"
        )
        return None

    if not isinstance(result, dict):
        logger.warning(
            "json_recovery: expected dict at top level, got %s", type(result).__name__
        )
        return None

    facts = result.get("facts", [])
    if not isinstance(facts, list):
        facts = []

    count = len(facts)
    if count > 0:
        logger.warning(
            "json_recovery: Recovered %d facts from truncated JSON "
            "(original had partial data)",
            count,
        )

    return {"facts": facts}


def recover_entities_from_truncated(text: str) -> dict | None:
    """Recover a ``{"entities": [...], "relationships": [...]}`` response.

    Parses as much of the ``entities`` and ``relationships`` lists as
    possible from a potentially truncated response.

    Args:
        text: Raw LLM output, possibly truncated mid-JSON.

    Returns:
        ``{"entities": [...], "relationships": [...]}`` with whatever
        complete objects were found, or ``None`` if nothing could be
        recovered.
    """
    result = recover_truncated_json(text)
    if result is None:
        logger.warning(
            "json_recovery: could not recover any entities from truncated JSON"
        )
        return None

    if not isinstance(result, dict):
        logger.warning(
            "json_recovery: expected dict at top level, got %s", type(result).__name__
        )
        return None

    entities = result.get("entities", [])
    relationships = result.get("relationships", [])
    if not isinstance(entities, list):
        entities = []
    if not isinstance(relationships, list):
        relationships = []

    total = len(entities) + len(relationships)
    if total > 0:
        logger.warning(
            "json_recovery: Recovered %d entities and %d relationships from "
            "truncated JSON (original had partial data)",
            len(entities),
            len(relationships),
        )

    return {"entities": entities, "relationships": relationships}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_last_complete_boundary(text: str) -> str | None:
    """Return text truncated at the last ``},`` or ``}]`` boundary.

    Searches from the end of the string towards the beginning so that we
    keep the maximum number of complete objects.
    """
    # Walk backwards looking for }, or }]
    for i in range(len(text) - 1, 0, -1):
        ch = text[i]
        prev = text[i - 1]
        if prev == "}" and ch in (",", "]"):
            # Include the ``}`` but not the trailing comma (if any).
            # Keep the ``]`` so arrays close naturally.
            if ch == "]":
                return text[: i + 1]
            else:  # ch == ","
                return text[:i]  # drop the comma; caller will close structures

    return None


def _close_open_structures(text: str) -> str:
    """Append the minimum closing brackets/braces to make ``text`` valid JSON.

    Counts unmatched ``[`` and ``{`` (ignoring characters inside strings) and
    appends the corresponding ``]`` / ``}`` tokens in reverse order.
    """
    closers: list[str] = []
    in_string = False
    escape_next = False

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            closers.append("}")
        elif ch == "[":
            closers.append("]")
        elif ch in ("}", "]"):
            if closers and closers[-1] == ch:
                closers.pop()

    return text + "".join(reversed(closers))
