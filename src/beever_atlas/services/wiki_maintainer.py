"""WikiMaintainer service.

Karpathy-style LLM Wiki bookkeeping. Replaces the
``cache.mark_all_stale(channel_id)`` invocation at
``services/consolidation.py:130-139`` — that was a single boolean
\"refresh everything\" hammer; the maintainer routes new facts to the
specific pages they affect and rewrites only those pages' affected
sections.

Flow when WIKI_MAINTENANCE_MODE=auto:
  1. ExtractionWorker emits on_extraction_done(channel_id, fact_ids).
  2. Maintainer's plan_updates() routes fact_ids → affected page_ids
     deterministically (cluster_id → topic page, entity_tags → entity
     pages, fact_type → role pages). NO LLM call here.
  3. For each affected page, apply_update() invokes ONE per-page LLM
     call that rewrites only the affected sections. Title, slug, and
     unaffected sections are preserved byte-identical so page voice
     does not drift.
  4. Page version bumps; last_facts_seen records the new fact_ids.

When WIKI_MAINTENANCE_MODE=manual, step 1 marks the affected pages
``is_dirty=True`` but does NOT call apply_update() — the user clicks
``Maintain Wiki`` to drain the dirty queue on demand.

Spec: ``openspec/changes/oss-pipeline-and-wiki-redesign/specs/wiki-maintainer/``
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from beever_atlas.models.persistence import WikiPage, WikiPageSection
from beever_atlas.wiki.page_store import WikiPageStore

logger = logging.getLogger(__name__)


def _slug_for_topic(cluster_id: str) -> str:
    """Convert a cluster id into a stable topic page id.

    The cluster_id is opaque to consumers but uses ``/`` as a hierarchy
    separator. We sanitize to ASCII-safe slugs and prefix with
    ``topic:`` so the page namespace is unambiguous from entity /
    decisions / faq pages.
    """
    safe = (cluster_id or "unspecified").replace("/", "-")
    return f"topic:{safe}"


def _slug_for_entity(entity_name: str) -> str:
    safe = (entity_name or "").strip().lower().replace(" ", "-")
    return f"entity:{safe}" if safe else ""


def _slug_for_fact_type(fact_type: str) -> str | None:
    """Map fact_type → page slug for role-based pages.

    Returns None for fact_types that don't have a dedicated page
    (``observation``, ``opinion`` are not surfaced as their own pages
    — they belong on topic / entity pages alongside their cluster).
    """
    role_map = {
        "decision": "decisions",
        "question": "faq",
        "action_item": "action-items",
    }
    return role_map.get(fact_type)


# Upper bound on the per-channel fact scan in ``_load_facts(channel_id, None)``.
# Hitting it produces a structured warning so we can revisit during soak. The
# main path is the explicit-id branch; the channel-wide path only runs from
# ``maintain_now`` (the manual-mode UI button), where bounded latency matters
# more than completeness on a 50k-fact channel.
_CHANNEL_FACT_LOAD_CAP = 5000


def _atomic_fact_to_routing_dict(fact: Any) -> dict[str, Any]:
    """Convert an ``AtomicFact`` Pydantic record into the dict shape
    ``plan_updates`` consumes. Defensive against missing attributes so
    monkeypatched tests can hand in plain dicts too.
    """
    if isinstance(fact, dict):
        return {
            "id": str(fact.get("id") or fact.get("fact_id") or ""),
            "cluster_id": fact.get("cluster_id"),
            "entity_tags": list(fact.get("entity_tags") or []),
            "fact_type": fact.get("fact_type") or "",
            "memory_text": fact.get("memory_text") or "",
            "source_message_id": fact.get("source_message_id") or "",
        }
    return {
        "id": str(getattr(fact, "id", "") or ""),
        "cluster_id": getattr(fact, "cluster_id", None),
        "entity_tags": list(getattr(fact, "entity_tags", []) or []),
        "fact_type": getattr(fact, "fact_type", "") or "",
        "memory_text": getattr(fact, "memory_text", "") or "",
        "source_message_id": getattr(fact, "source_message_id", "") or "",
    }


_APPLY_UPDATE_SYSTEM_PROMPT = (
    "You are the wiki maintainer for an in-app personal-intelligence wiki. "
    "Your job is to integrate one or more new facts into ONE existing wiki "
    "page. You MUST:\n"
    " 1. Return ONLY the sections that need to change — never the whole page.\n"
    " 2. Preserve the page title, slug, and overall voice / tone / person.\n"
    " 3. Leave unaffected sections untouched (caller will keep them "
    "byte-identical).\n"
    " 4. Use the same markdown style + heading depth as the existing "
    "section content.\n"
    " 5. Cite each new fact inline as [fact_id] so the QA agent can resolve "
    "the source message later.\n"
    " 6. If a section truly does not exist yet but the new fact warrants "
    "one, return a NEW section (id, title, content_md). Otherwise keep the "
    "existing section ids stable.\n"
    "Output a single JSON object: "
    '{"affected_sections": [{"id": str, "title": str, "content_md": str}], '
    '"reason": str}.'
)


def _render_apply_update_prompt(
    page: "WikiPage",
    new_facts: list[dict[str, Any]],
    *,
    target_lang: str = "en",
) -> str:
    """Build the apply_update prompt mirroring WikiCompiler's structure.

    The prompt is a single string (system + JSON user payload). Gemini's
    ``response_mime_type="application/json"`` nudge is set on the call site;
    here we just make the input deterministic + parseable.
    """
    import json

    payload: dict[str, Any] = {
        "page": {
            "page_id": page.page_id,
            "title": page.title,
            "slug": page.slug,
            "page_voice_seed": page.page_voice_seed or "",
            "target_lang": target_lang,
            "last_facts_seen": list(page.last_facts_seen),
            "sections": [
                {
                    "id": s.id,
                    "title": s.title,
                    "content_md": s.content_md,
                }
                for s in page.sections
            ],
        },
        "new_facts": [
            {
                "id": f.get("id", ""),
                "memory_text": f.get("memory_text", ""),
                "cluster_id": f.get("cluster_id"),
                "entity_tags": list(f.get("entity_tags") or []),
                "fact_type": f.get("fact_type", ""),
                "source_message_id": f.get("source_message_id", ""),
            }
            for f in new_facts
        ],
    }
    return (
        _APPLY_UPDATE_SYSTEM_PROMPT
        + "\n\n--- INPUT ---\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\n--- OUTPUT (JSON only) ---\n"
    )


def _parse_apply_update_response(raw: str) -> list["WikiPageSection"]:
    """Parse the LLM response into a list of ``WikiPageSection``.

    Returns an empty list on any parse error so the caller treats the
    response as "do nothing" rather than corrupting the page.
    """
    import json

    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "event=wiki_maintainer_response_parse_failed raw_len=%d",
            len(raw),
        )
        return []

    if not isinstance(parsed, dict):
        return []
    affected_raw = parsed.get("affected_sections")
    if not isinstance(affected_raw, list):
        return []

    out: list[WikiPageSection] = []
    for entry in affected_raw:
        if not isinstance(entry, dict):
            continue
        section_id = str(entry.get("id", "")).strip()
        content_md = str(entry.get("content_md", "")).strip()
        if not section_id or not content_md:
            continue
        title = str(entry.get("title", "")).strip() or section_id.title()
        out.append(
            WikiPageSection(
                id=section_id,
                title=title,
                content_md=content_md,
            )
        )
    return out


def _slug_to_title_fallback(page_id: str) -> str:
    """Convert a page_id slug into a human-friendly title.

    Used as the universal fallback when the cluster / entity registry
    lookup wired in §4 doesn't yield a better answer.
    """
    if not page_id:
        return "Untitled"
    bare = page_id.split(":", 1)[-1]
    parts = [p for p in bare.replace("_", "-").split("-") if p]
    if not parts:
        return page_id
    return " ".join(p.capitalize() for p in parts)


# Role pages have fixed human-readable titles. Role page_ids are NOT
# prefixed with ``topic:`` or ``entity:`` — they are flat slugs that
# match the literal `_slug_for_fact_type` returns.
_ROLE_PAGE_TITLES: dict[str, str] = {
    "decisions": "Decisions",
    "faq": "Frequently Asked Questions",
    "action-items": "Action Items",
}


def _split_page_id(page_id: str) -> list[tuple[str, str]]:
    """Classify a ``page_id`` into ``(kind, identifier)`` tuples.

    Returns a list because callers iterate it (the iteration is a single
    classification pass; structuring as a list keeps the call site
    branchless). ``kind`` is one of ``"topic"``, ``"entity"``, ``"role"``,
    or ``"unknown"``.
    """
    if not page_id:
        return [("unknown", "")]
    if page_id.startswith("topic:"):
        return [("topic", page_id.split(":", 1)[1])]
    if page_id.startswith("entity:"):
        return [("entity", page_id.split(":", 1)[1])]
    if page_id in _ROLE_PAGE_TITLES:
        return [("role", page_id)]
    return [("unknown", page_id)]


class WikiMaintainer:
    """Subscribes to ExtractionWorker events and incrementally maintains
    the per-page wiki documents.

    Stateless — every call recomputes the routing from the freshly
    extracted facts. The only state is in ``WikiPageStore`` (per-page
    docs) and ``WikiCache`` (legacy, soon to be deprecated).
    """

    def __init__(
        self,
        page_store: WikiPageStore,
        llm_provider: Any | None = None,
    ) -> None:
        self._page_store = page_store
        # ``llm_provider`` is only required for ``apply_update`` —
        # routing (``plan_updates``) MUST NOT call any LLM. Tests
        # leave it None to lock in that invariant.
        self._llm_provider = llm_provider

    # ------------------------------------------------------------------
    # Deterministic routing — no LLM call
    # ------------------------------------------------------------------

    def plan_updates(self, facts: list[dict[str, Any]]) -> dict[str, list[str]]:
        """Group fact ids by the page_id they affect.

        Routing rules (deterministic):
          * ``fact.cluster_id`` → topic page (``topic:<safe-cluster-id>``)
          * each ``fact.entity_tags[i]`` → entity page (``entity:<name>``)
          * ``fact.fact_type=="decision"`` → ``decisions`` page
          * ``fact.fact_type=="question"`` → ``faq`` page
          * ``fact.fact_type=="action_item"`` → ``action-items`` page

        Same input always yields the same routing — invariant under
        retry. Empty entity_tags / cluster_id are tolerated; the fact
        contributes only to the role page (if any).

        Returns ``{page_id: [fact_id, ...]}``. Order within each list
        matches the input order so subsequent rewrites are stable.
        """
        plan: dict[str, list[str]] = {}

        def _add(page_id: str, fact_id: str) -> None:
            if not page_id or not fact_id:
                return
            plan.setdefault(page_id, []).append(fact_id)

        for fact in facts:
            fact_id = str(fact.get("id") or fact.get("fact_id") or "")
            if not fact_id:
                continue
            cluster_id = fact.get("cluster_id")
            if cluster_id:
                _add(_slug_for_topic(str(cluster_id)), fact_id)
            for entity in fact.get("entity_tags", []) or []:
                entity_slug = _slug_for_entity(str(entity))
                if entity_slug:
                    _add(entity_slug, fact_id)
            fact_type = str(fact.get("fact_type") or "")
            role_slug = _slug_for_fact_type(fact_type)
            if role_slug:
                _add(role_slug, fact_id)
        return plan

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_extraction_done(
        self,
        channel_id: str,
        fact_ids: list[str],
        *,
        target_lang: str = "en",
        mode: str = "manual",
    ) -> dict[str, Any]:
        """Hook invoked from ExtractionWorker after a successful batch.

        ``mode`` toggles between ``auto`` (call apply_update on every
        affected page right now) and ``manual`` (mark pages dirty;
        user processes them later via the Maintain Wiki button).

        ``fact_ids`` are the newly extracted facts. The maintainer
        loads their full records from Weaviate via the LLM provider
        wiring (deferred — for now the routing operates on the
        fact_ids alone via ``plan_updates_from_ids``, which fetches
        cluster + entity tags from the knowledge stores).

        Returns a counters dict for observability:
            {
                "affected_pages": int,
                "marked_dirty": int,
                "rewritten": int,
            }
        """
        counters: dict[str, int] = {
            "affected_pages": 0,
            "marked_dirty": 0,
            "rewritten": 0,
        }
        if not fact_ids:
            return counters

        # In a real deployment, plan_updates would fetch fact records
        # from Weaviate. The routing function is the testable seam;
        # the fetch + apply layer is a separate close-out task. On the
        # integration boundary we call
        # ``_load_facts(channel_id, fact_ids)`` which production wires
        # to the Weaviate store; tests stub it.
        facts = await self._load_facts(channel_id, fact_ids)
        plan = self.plan_updates(facts)
        counters["affected_pages"] = len(plan)

        if mode == "manual":
            modified = await self._page_store.mark_dirty(
                channel_id, list(plan.keys()), target_lang=target_lang
            )
            counters["marked_dirty"] = modified
            logger.info(
                "wiki_maintainer.on_extraction_done channel=%s mode=manual "
                "affected=%d marked_dirty=%d",
                channel_id,
                counters["affected_pages"],
                counters["marked_dirty"],
            )
            return counters

        # auto mode — apply per-page LLM rewrite for each affected page
        for page_id, page_fact_ids in plan.items():
            try:
                applied = await self.apply_update(
                    channel_id=channel_id,
                    page_id=page_id,
                    new_fact_ids=page_fact_ids,
                    target_lang=target_lang,
                )
                if applied:
                    counters["rewritten"] += 1
            except Exception:  # noqa: BLE001 — one bad page must not stall others
                logger.exception(
                    "wiki_maintainer.apply_update failed channel=%s page=%s fact_count=%d",
                    channel_id,
                    page_id,
                    len(page_fact_ids),
                )
        logger.info(
            "wiki_maintainer.on_extraction_done channel=%s mode=auto affected=%d rewritten=%d",
            channel_id,
            counters["affected_pages"],
            counters["rewritten"],
        )
        return counters

    async def on_consolidation_complete(
        self,
        channel_id: str,
        fact_ids: list[str],
        *,
        target_lang: str = "en",
        mode: str = "manual",
    ) -> dict[str, Any]:
        """Hook invoked after consolidation finishes for a channel.

        Replaces the legacy ``WikiCache.mark_all_stale(channel_id)`` hammer:
        instead of marking the entire wiki stale, the maintainer routes the
        consolidation's touched fact ids to the specific pages they affect.
        Behaviour mirrors :meth:`on_extraction_done` exactly — non-empty
        ``fact_ids`` routes to affected pages (auto fires LLM rewrites,
        manual marks them dirty); empty ``fact_ids`` is a no-op (the worker
        path's per-batch fan-out already covered any new facts during
        consolidation).
        """
        return await self.on_extraction_done(
            channel_id, fact_ids, target_lang=target_lang, mode=mode
        )

    async def maintain_now(self, channel_id: str, target_lang: str = "en") -> dict[str, int]:
        """Drain the dirty page queue for one channel — used by the
        manual-mode ``Maintain Wiki`` button.

        Returns ``{rewritten, errors}`` counters.
        """
        counters: dict[str, int] = {"rewritten": 0, "errors": 0}
        pages = await self._page_store.list_pages(channel_id, target_lang)
        dirty = [p for p in pages if p.is_dirty]
        for page in dirty:
            try:
                # The maintainer doesn't know which facts triggered
                # the dirty flag — it processes whatever the page's
                # last_facts_seen has missed. Production wires
                # ``_load_facts`` to fetch the channel's full fact
                # set; tests stub it to a fixed list.
                channel_facts = await self._load_facts(channel_id, None)
                already_seen = set(page.last_facts_seen)
                new_fact_ids = [
                    str(f.get("id") or "")
                    for f in channel_facts
                    if str(f.get("id") or "") not in already_seen
                ]
                applied = await self.apply_update(
                    channel_id=channel_id,
                    page_id=page.page_id,
                    new_fact_ids=new_fact_ids,
                    target_lang=target_lang,
                )
                if applied:
                    counters["rewritten"] += 1
            except Exception:  # noqa: BLE001
                logger.exception(
                    "wiki_maintainer.maintain_now failed channel=%s page=%s",
                    channel_id,
                    page.page_id,
                )
                counters["errors"] += 1
        return counters

    # ------------------------------------------------------------------
    # Per-page LLM rewrite (the actual maintainer)
    # ------------------------------------------------------------------

    async def apply_update(
        self,
        channel_id: str,
        page_id: str,
        new_fact_ids: list[str],
        *,
        target_lang: str = "en",
    ) -> bool:
        """Invoke ONE per-page LLM call to integrate ``new_fact_ids``
        into the affected sections of one wiki page.

        Preserves: title, slug, page_voice_seed, and unaffected
        sections (byte-identical). Bumps version. Clears is_dirty.

        Returns True if the page was rewritten; False if there was
        nothing to do (e.g. all ``new_fact_ids`` were already in
        ``last_facts_seen``) or the LLM call failed (in which case the
        page is left unchanged and a structured error is logged).
        """
        page = await self._page_store.get_page(channel_id, page_id, target_lang=target_lang)
        already_seen = set(page.last_facts_seen) if page else set()
        truly_new = [fid for fid in new_fact_ids if fid not in already_seen]
        if not truly_new:
            return False

        # Load full fact records for the prompt. ``fetch_by_ids`` is the
        # cheap path (one Weaviate object lookup per id); even when
        # ``_load_facts`` is monkeypatched in tests, calling it here keeps
        # the production wiring honest.
        new_facts = await self._load_facts(channel_id, truly_new)
        if not new_facts:
            # No fact records resolved — likely a test that didn't seed
            # the loader, or a Weaviate hiccup. Don't write a placeholder
            # page; let the caller retry on the next event.
            logger.warning(
                "event=wiki_maintainer_apply_update_no_facts channel_id=%s page_id=%s requested=%d",
                channel_id,
                page_id,
                len(truly_new),
            )
            return False

        if page is None:
            page = WikiPage(
                channel_id=channel_id,
                target_lang=target_lang,
                page_id=page_id,
                title=await self._resolve_first_touch_title(page_id, channel_id),
                slug=page_id.replace(":", "-"),
                sections=[
                    WikiPageSection(
                        id="overview",
                        title="Overview",
                        content_md="",
                    )
                ],
            )

        prompt = _render_apply_update_prompt(page, new_facts, target_lang=target_lang)
        try:
            raw = await self._invoke_apply_update_llm(prompt)
        except Exception as exc:  # noqa: BLE001 — leave page unchanged on any LLM error
            logger.exception(
                "event=wiki_maintainer_apply_update_llm_failed channel_id=%s page_id=%s err=%s",
                channel_id,
                page_id,
                exc,
            )
            return False

        affected_sections = _parse_apply_update_response(raw)
        if not affected_sections:
            logger.warning(
                "event=wiki_maintainer_apply_update_no_affected_sections channel_id=%s "
                "page_id=%s raw_len=%d",
                channel_id,
                page_id,
                len(raw or ""),
            )
            return False

        # Merge in place so each updated section keeps its original
        # position; only genuinely new sections (ids not already on the
        # page) are appended at the end. This preserves layout across
        # repeated rewrites — without this, an LLM update on the
        # ``"overview"`` section would shift it from the top of the page
        # to the bottom, and the order would drift unpredictably as
        # different sections get touched on different batches.
        affected_map: dict[str, WikiPageSection] = {s.id: s for s in affected_sections}
        merged: list[WikiPageSection] = [affected_map.pop(s.id, s) for s in page.sections]
        # Anything left in ``affected_map`` is a genuinely new section the
        # LLM added (id not already on the page). Append in the order the
        # LLM emitted them (dict insertion order is preserved in 3.7+).
        merged.extend(affected_map.values())

        page.sections = merged
        page.last_facts_seen = sorted(set(page.last_facts_seen) | set(truly_new))
        page.is_dirty = False
        page.updated_at = datetime.now(tz=UTC)
        # title, slug, page_voice_seed are intentionally NOT touched here —
        # the LLM contract returns ONLY affected sections, and the merge
        # path only rewrites sections by id. Voice preservation is a
        # structural invariant.
        await self._page_store.save_page(page)
        return True

    async def _invoke_apply_update_llm(self, prompt: str) -> str:
        """Single LLM call for ``apply_update``. Override in tests.

        Production path: resolve the ``wiki_maintainer`` model via
        ``LLMProvider``, then issue an ``application/json``-typed
        ``generate_content`` request mirroring the WikiCompiler call shape.
        Returns the raw JSON text (parsed by the caller).
        """
        from beever_atlas.llm.provider import get_llm_provider
        from google.genai import types

        provider = self._llm_provider or get_llm_provider()
        model_name = provider.get_model_string("wiki_maintainer")

        client = self._get_genai_client()
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=4096,
            temperature=0.2,
        )
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        return response.text or "{}"

    def _get_genai_client(self) -> Any:
        """Lazy-init + cache the Google GenAI client on the instance.

        The Google AI client is intended to be reused. In auto mode an
        extraction batch can fan out to N affected pages; constructing a
        fresh client per page would burn a connection pool slot each time.
        The client is created on first use rather than at ``__init__`` so
        unit tests that don't exercise the LLM path never touch the SDK.
        """
        cached = getattr(self, "_genai_client", None)
        if cached is None:
            from google import genai

            cached = genai.Client()
            self._genai_client = cached
        return cached

    async def _resolve_first_touch_title(self, page_id: str, channel_id: str) -> str:
        """Look up the human-friendly title for a brand-new page.

        Resolution order:
        1. ``topic:<cluster_id>`` → ``WeaviateStore.get_cluster(cluster_id).title``
        2. ``entity:<slug>`` → entity registry canonical name (capitalized)
        3. Role page (``decisions``, ``faq``, ``action-items``) → fixed constant
        4. Fallback → title-cased slug

        Any lookup failure quietly falls through to the next strategy so a
        Weaviate hiccup never blocks page creation.
        """
        for kind, ident in _split_page_id(page_id):
            if kind == "topic":
                title = await self._lookup_cluster_title(channel_id, ident)
                if title:
                    return title
                return _slug_to_title_fallback(ident)
            if kind == "entity":
                title = await self._lookup_entity_display_name(ident)
                if title:
                    return title
                return _slug_to_title_fallback(ident)
            if kind == "role":
                return _ROLE_PAGE_TITLES.get(ident, _slug_to_title_fallback(ident))
        return _slug_to_title_fallback(page_id)

    async def _lookup_cluster_title(self, channel_id: str, cluster_id: str) -> str | None:
        try:
            from beever_atlas.stores import get_stores

            stores = get_stores()
            weaviate = getattr(stores, "weaviate", None)
            if weaviate is None:
                return None
            cluster = await weaviate.get_cluster(cluster_id)
            title = getattr(cluster, "title", None) if cluster else None
            return title or None
        except Exception:  # noqa: BLE001 — title is best-effort, never blocks page creation
            logger.debug("cluster title lookup failed for %s", cluster_id, exc_info=True)
            return None

    async def _lookup_entity_display_name(self, entity_slug: str) -> str | None:
        try:
            from beever_atlas.stores import get_stores

            stores = get_stores()
            registry = getattr(stores, "entity_registry", None)
            if registry is None:
                return None
            # ``entity_slug`` already lowercased + dashed; entity registry
            # keys are canonical names (mixed case + spaces). Try the
            # un-slugified form first, then the slug verbatim as fallback.
            unslug = entity_slug.replace("-", " ")
            canonical = await registry.get_canonical(unslug)
            if canonical:
                return canonical
            canonical = await registry.get_canonical(entity_slug)
            if canonical:
                return canonical
            return None
        except Exception:  # noqa: BLE001
            logger.debug("entity display lookup failed for %s", entity_slug, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Internal — fact loader (overridden in tests)
    # ------------------------------------------------------------------

    async def _load_facts(
        self, channel_id: str, fact_ids: list[str] | None
    ) -> list[dict[str, Any]]:
        """Fetch fact records by id or by channel from Weaviate.

        When ``fact_ids`` is provided, batch-loads exactly those facts via
        ``WeaviateStore.fetch_by_ids`` (one cheap object lookup per id, no
        full scan). When ``fact_ids is None`` (the ``maintain_now``
        channel-wide path), pages through ``list_facts`` 500 at a time and
        caps the total at ``_CHANNEL_FACT_LOAD_CAP`` (5000) to avoid an
        unbounded scan on a high-traffic channel; when the cap is hit, an
        explicit ``wiki_maintainer_fact_load_truncated`` warning is emitted
        so we know to revisit during soak.

        Returns dicts in the shape ``plan_updates`` expects:
        ``{"id", "cluster_id", "entity_tags", "fact_type"}``. Tests may
        still subclass / monkeypatch this method to inject a synthetic
        fact set without touching Weaviate.
        """
        from beever_atlas.models.api import MemoryFilters
        from beever_atlas.stores import get_stores

        stores = get_stores()
        weaviate = getattr(stores, "weaviate", None)
        if weaviate is None:
            return []

        if fact_ids:
            facts = await weaviate.fetch_by_ids(list(fact_ids))
            return [_atomic_fact_to_routing_dict(f) for f in facts]

        out: list[dict[str, Any]] = []
        empty_filters = MemoryFilters()
        page_size = 500
        page = 1
        while len(out) < _CHANNEL_FACT_LOAD_CAP:
            paginated = await weaviate.list_facts(
                channel_id, empty_filters, page=page, limit=page_size
            )
            if not paginated.memories:
                break
            for f in paginated.memories:
                out.append(_atomic_fact_to_routing_dict(f))
                if len(out) >= _CHANNEL_FACT_LOAD_CAP:
                    break
            if page >= paginated.pages:
                break
            page += 1

        if len(out) >= _CHANNEL_FACT_LOAD_CAP:
            logger.warning(
                "event=wiki_maintainer_fact_load_truncated channel_id=%s total_returned=%d cap=%d",
                channel_id,
                _CHANNEL_FACT_LOAD_CAP,
                _CHANNEL_FACT_LOAD_CAP,
            )
        return out


def _hash_fact_ids(fact_ids: list[str]) -> str:
    import hashlib

    joined = "\x00".join(sorted(fact_ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


# ----------------------------------------------------------------------
# Singleton wiring (init by the FastAPI lifespan; subscribers wire to it)
# ----------------------------------------------------------------------

_maintainer_instance: WikiMaintainer | None = None


def init_wiki_maintainer(maintainer: WikiMaintainer) -> None:
    global _maintainer_instance
    _maintainer_instance = maintainer


def get_wiki_maintainer() -> WikiMaintainer | None:
    return _maintainer_instance
