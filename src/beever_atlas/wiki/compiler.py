"""LLM-based wiki page compiler — converts gathered data into WikiPage objects."""

from __future__ import annotations

import asyncio
import json
import logging
import re

from beever_atlas.llm import get_llm_provider
from beever_atlas.models.domain import AtomicFact, WikiCitation, WikiPage, WikiPageNode, WikiStructure
from beever_atlas.wiki.prompts import (
    ACTIVITY_PROMPT,
    DECISIONS_PROMPT,
    FAQ_PROMPT,
    GLOSSARY_PROMPT,
    OVERVIEW_PROMPT,
    PEOPLE_PROMPT,
    TOPIC_PROMPT,
)
from beever_atlas.wiki.schemas import CompiledPageContent

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug.strip())
    return slug[:80]


def _build_permalink(fact: AtomicFact) -> str:
    """Build a best-effort permalink to the original message."""
    if not fact.source_message_id and not fact.message_ts:
        return ""
    # For Slack: https://slack.com/archives/{channel}/{message_ts}
    if fact.platform == "slack" and fact.channel_id:
        ts = fact.message_ts.replace(".", "p") if fact.message_ts else ""
        if ts:
            return f"https://app.slack.com/archives/{fact.channel_id}/{ts}"
    return ""


def _build_citations(facts: list[AtomicFact]) -> list[WikiCitation]:
    citations = []
    for i, fact in enumerate(facts, 1):
        media_type = fact.source_media_type or None
        media_name = fact.source_media_names[0] if fact.source_media_names else None
        citations.append(
            WikiCitation(
                id=f"[{i}]",
                author=fact.author_name,
                timestamp=fact.message_ts,
                text_excerpt=fact.memory_text[:100],
                permalink=_build_permalink(fact),
                media_type=media_type if media_type else None,
                media_name=media_name,
            )
        )
    return citations


def _build_media_data(facts: list[AtomicFact]) -> list[dict]:
    """Extract media references from facts for the LLM prompt."""
    media: list[dict] = []
    seen_urls: set[str] = set()
    for fact in facts:
        for i, url in enumerate(fact.source_media_urls):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            name = fact.source_media_names[i] if i < len(fact.source_media_names) else url.split("/")[-1]
            media.append({
                "url": url,
                "type": fact.source_media_type or "file",
                "name": name,
                "author": fact.author_name,
                "context": fact.memory_text[:80],
            })
        for j, url in enumerate(fact.source_link_urls):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            title = fact.source_link_titles[j] if j < len(fact.source_link_titles) else url
            media.append({
                "url": url,
                "type": "link",
                "name": title,
                "author": fact.author_name,
                "context": fact.memory_text[:80],
            })
    return media


def _format_relationship_edges(persons: list[dict]) -> list[dict]:
    """Extract relationship edges from person entities for the People prompt."""
    edges: list[dict] = []
    for person_data in persons:
        entity = person_data.get("entity")
        if not entity:
            continue
        person_name = entity.name if hasattr(entity, "name") else str(entity)
        for edge_type in ["decided", "works_on", "uses"]:
            for target in person_data.get(edge_type, []):
                edges.append({
                    "source": person_name,
                    "relationship": edge_type.upper().replace("_", " "),
                    "target": target,
                })
    return edges


class WikiCompiler:
    """Compiles gathered channel data into WikiPage objects using the LLM."""

    def __init__(self) -> None:
        provider = get_llm_provider()
        self._model_name: str = provider.get_model_string("wiki_compiler")

    async def _call_llm(self, prompt: str) -> CompiledPageContent:
        from google import genai
        from google.genai import types

        client = genai.Client()
        response = await client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        raw = response.text or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("WikiCompiler: failed to parse LLM JSON, using empty page")
            data = {}
        return CompiledPageContent(
            content=data.get("content", ""),
            summary=data.get("summary", ""),
        )

    async def _compile_overview(self, gathered: dict) -> WikiPage:
        summary = gathered["channel_summary"]
        clusters = gathered["clusters"]
        clusters_data = [
            {"id": c.id, "title": c.title, "member_count": c.member_count, "topic_tags": c.topic_tags}
            for c in clusters
        ]
        # Build media data from media_facts
        media_data = _build_media_data(gathered["media_facts"])
        # Build graph entity data
        tech_data = [{"name": t["entity"].name, "used_by": t.get("used_by", [])} for t in gathered.get("technologies", [])]
        project_data = [{"name": p["entity"].name, "deps": p.get("dependencies", []), "owners": p.get("owners", [])} for p in gathered.get("projects", [])]

        # Aggregate key entities and relationships from all clusters
        all_key_entities: list[dict] = []
        all_key_relationships: list[dict] = []
        for c in clusters:
            all_key_entities.extend(c.key_entities[:5])
            all_key_relationships.extend(c.key_relationships[:5])

        # Glossary preview and FAQ count
        glossary_preview = summary.glossary_terms[:5] if summary.glossary_terms else []
        faq_count = sum(len(c.faq_candidates) for c in clusters)

        prompt = OVERVIEW_PROMPT.format(
            channel_name=summary.channel_name,
            description=summary.description,
            text=summary.text,
            themes=summary.themes,
            momentum=summary.momentum,
            team_dynamics=summary.team_dynamics,
            decisions_count=len(summary.top_decisions),
            people_count=len(summary.top_people),
            projects_count=len(summary.active_projects),
            tech_count=len(summary.tech_stack),
            media_count=summary.media_count,
            clusters_json=json.dumps(clusters_data, default=str),
            topic_graph_edges_json=json.dumps(summary.topic_graph_edges, default=str),
            recent_activity_json=json.dumps(summary.recent_activity_summary, default=str),
            top_people_json=json.dumps(summary.top_people, default=str),
            top_decisions_json=json.dumps(summary.top_decisions, default=str),
            technologies_json=json.dumps(tech_data, default=str),
            projects_json=json.dumps(project_data, default=str),
            key_entities_json=json.dumps(all_key_entities, default=str),
            key_relationships_json=json.dumps(all_key_relationships, default=str),
            media_json=json.dumps(media_data, default=str),
            glossary_preview_json=json.dumps(glossary_preview, default=str),
            faq_count=faq_count,
        )
        result = await self._call_llm(prompt)
        all_facts = gathered["recent_facts"] + gathered["media_facts"]
        return WikiPage(
            id="overview",
            slug="overview",
            title="Overview",
            page_type="fixed",
            section_number="1",
            content=result.content,
            summary=result.summary,
            memory_count=gathered["total_facts"],
            citations=_build_citations(all_facts[:20]),
        )

    async def _compile_topic_page(self, cluster, gathered: dict) -> WikiPage:
        member_facts: list[AtomicFact] = gathered["cluster_facts"].get(cluster.id, [])
        sorted_facts = sorted(member_facts, key=lambda f: f.quality_score, reverse=True)
        facts_data = [
            {
                "memory_text": f.memory_text,
                "author_name": f.author_name,
                "quality_score": f.quality_score,
                "fact_type": f.fact_type,
                "importance": f.importance,
                "message_ts": f.message_ts,
            }
            for f in sorted_facts[:30]
        ]
        # Collect media from member facts
        media_data = _build_media_data(member_facts)

        prompt = TOPIC_PROMPT.format(
            title=cluster.title,
            summary=cluster.summary,
            current_state=cluster.current_state,
            open_questions=cluster.open_questions,
            impact_note=cluster.impact_note,
            topic_tags=", ".join(cluster.topic_tags),
            date_range_start=cluster.date_range_start,
            date_range_end=cluster.date_range_end,
            authors=", ".join(cluster.authors),
            key_facts_json=json.dumps(cluster.key_facts, default=str),
            decisions_json=json.dumps(cluster.decisions, default=str),
            people_json=json.dumps(cluster.people, default=str),
            technologies_json=json.dumps(cluster.technologies, default=str),
            projects_json=json.dumps(cluster.projects, default=str),
            key_entities_json=json.dumps(cluster.key_entities, default=str),
            key_relationships_json=json.dumps(cluster.key_relationships, default=str),
            member_facts_json=json.dumps(facts_data, default=str),
            media_json=json.dumps(media_data, default=str),
        )
        result = await self._call_llm(prompt)
        slug = _slugify(cluster.title) or cluster.id
        return WikiPage(
            id=f"topic-{slug}",
            slug=slug,
            title=cluster.title,
            page_type="topic",
            content=result.content,
            summary=result.summary,
            memory_count=cluster.member_count,
            citations=_build_citations(sorted_facts[:20]),
        )

    async def _compile_people(self, gathered: dict) -> WikiPage:
        channel_summary = gathered["channel_summary"]
        relationship_edges = _format_relationship_edges(gathered["persons"])
        prompt = PEOPLE_PROMPT.format(
            persons_json=json.dumps(gathered["persons"], default=str),
            top_people_json=json.dumps(channel_summary.top_people, default=str),
            relationship_edges_json=json.dumps(relationship_edges, default=str),
        )
        result = await self._call_llm(prompt)
        return WikiPage(
            id="people",
            slug="people",
            title="People & Experts",
            page_type="fixed",
            content=result.content,
            summary=result.summary,
            memory_count=len(gathered["persons"]),
        )

    async def _compile_decisions(self, gathered: dict) -> WikiPage:
        channel_summary = gathered["channel_summary"]
        prompt = DECISIONS_PROMPT.format(
            decisions_json=json.dumps(gathered["decisions"], default=str),
            top_decisions_json=json.dumps(channel_summary.top_decisions, default=str),
        )
        result = await self._call_llm(prompt)
        return WikiPage(
            id="decisions",
            slug="decisions",
            title="Decisions",
            page_type="fixed",
            content=result.content,
            summary=result.summary,
            memory_count=len(gathered["decisions"]),
        )

    async def _compile_faq(self, gathered: dict) -> WikiPage:
        """Compile FAQ page from aggregated faq_candidates across all TopicClusters."""
        clusters = gathered["clusters"]
        # Aggregate faq_candidates grouped by topic
        faq_by_topic: list[dict] = []
        topic_names: list[str] = []
        for cluster in clusters:
            if cluster.faq_candidates:
                faq_by_topic.append({
                    "topic": cluster.title,
                    "questions": cluster.faq_candidates,
                })
                topic_names.append(cluster.title)

        prompt = FAQ_PROMPT.format(
            faq_candidates_json=json.dumps(faq_by_topic, default=str),
            topic_names_json=json.dumps(topic_names, default=str),
        )
        result = await self._call_llm(prompt)
        return WikiPage(
            id="faq",
            slug="faq",
            title="FAQ",
            page_type="fixed",
            content=result.content,
            summary=result.summary,
            memory_count=sum(len(c.faq_candidates) for c in clusters),
        )

    async def _compile_glossary(self, gathered: dict) -> WikiPage:
        """Compile Glossary page from ChannelSummary glossary_terms."""
        channel_summary = gathered["channel_summary"]
        glossary_terms = channel_summary.glossary_terms or []

        prompt = GLOSSARY_PROMPT.format(
            glossary_terms_json=json.dumps(glossary_terms, default=str),
            channel_description=channel_summary.description or channel_summary.channel_name,
        )
        result = await self._call_llm(prompt)
        return WikiPage(
            id="glossary",
            slug="glossary",
            title="Glossary",
            page_type="fixed",
            content=result.content,
            summary=result.summary,
            memory_count=len(glossary_terms),
        )

    async def _compile_activity(self, gathered: dict) -> WikiPage:
        channel_summary = gathered["channel_summary"]
        recent_data = [
            {
                "memory_text": f.memory_text,
                "author_name": f.author_name,
                "message_ts": f.message_ts,
                "fact_type": f.fact_type,
                "source_media_type": f.source_media_type,
            }
            for f in gathered["recent_facts"]
        ]
        # Include recent media
        recent_media = _build_media_data(gathered["recent_facts"])

        prompt = ACTIVITY_PROMPT.format(
            recent_facts_json=json.dumps(recent_data, default=str),
            recent_activity_json=json.dumps(channel_summary.recent_activity_summary, default=str),
            recent_media_json=json.dumps(recent_media, default=str),
        )
        result = await self._call_llm(prompt)
        return WikiPage(
            id="activity",
            slug="activity",
            title="Recent Activity",
            page_type="fixed",
            content=result.content,
            summary=result.summary,
            memory_count=len(gathered["recent_facts"]),
        )

    async def compile(self, gathered: dict) -> dict[str, WikiPage]:
        """Compile all pages from gathered data in parallel."""
        clusters = gathered["clusters"]

        topic_tasks = [self._compile_topic_page(c, gathered) for c in clusters]

        results = await asyncio.gather(
            self._compile_overview(gathered),
            self._compile_people(gathered),
            self._compile_decisions(gathered),
            self._compile_faq(gathered),
            self._compile_glossary(gathered),
            self._compile_activity(gathered),
            *topic_tasks,
            return_exceptions=True,
        )

        pages: dict[str, WikiPage] = {}

        fixed_keys = ["overview", "people", "decisions", "faq", "glossary", "activity"]
        for key, res in zip(fixed_keys, results[:6]):
            if isinstance(res, BaseException):
                logger.error("WikiCompiler: failed to compile %s: %s", key, res, exc_info=res)
            else:
                page: WikiPage = res
                pages[page.id] = page

        for cluster, res in zip(clusters, results[6:]):
            if isinstance(res, BaseException):
                logger.error(
                    "WikiCompiler: failed to compile topic %s: %s", cluster.id, res, exc_info=res
                )
            else:
                page = res
                pages[page.id] = page

        return pages

    def build_structure(
        self,
        channel_id: str,
        channel_name: str,
        platform: str,
        pages: dict[str, WikiPage],
    ) -> WikiStructure:
        nodes: list[WikiPageNode] = []

        # 1. Overview
        if "overview" in pages:
            p = pages["overview"]
            nodes.append(
                WikiPageNode(
                    id="overview",
                    title="Overview",
                    slug="overview",
                    section_number="1",
                    page_type="fixed",
                    memory_count=p.memory_count,
                )
            )

        # 2.x Topics
        topic_pages = sorted(
            [p for p in pages.values() if p.page_type == "topic"],
            key=lambda p: p.title,
        )
        for i, tp in enumerate(topic_pages, 1):
            tp.section_number = f"2.{i}"
            nodes.append(
                WikiPageNode(
                    id=tp.id,
                    title=tp.title,
                    slug=tp.slug,
                    section_number=f"2.{i}",
                    page_type="topic",
                    memory_count=tp.memory_count,
                )
            )

        # 3. People & Experts
        if "people" in pages:
            p = pages["people"]
            nodes.append(
                WikiPageNode(
                    id="people",
                    title="People & Experts",
                    slug="people",
                    section_number="3",
                    page_type="fixed",
                    memory_count=p.memory_count,
                )
            )

        # 4. Decisions
        if "decisions" in pages:
            p = pages["decisions"]
            nodes.append(
                WikiPageNode(
                    id="decisions",
                    title="Decisions",
                    slug="decisions",
                    section_number="4",
                    page_type="fixed",
                    memory_count=p.memory_count,
                )
            )

        # 5. FAQ
        if "faq" in pages:
            p = pages["faq"]
            nodes.append(
                WikiPageNode(
                    id="faq",
                    title="FAQ",
                    slug="faq",
                    section_number="5",
                    page_type="fixed",
                    memory_count=p.memory_count,
                )
            )

        # 6. Glossary
        if "glossary" in pages:
            p = pages["glossary"]
            nodes.append(
                WikiPageNode(
                    id="glossary",
                    title="Glossary",
                    slug="glossary",
                    section_number="6",
                    page_type="fixed",
                    memory_count=p.memory_count,
                )
            )

        # 7. Recent Activity
        if "activity" in pages:
            p = pages["activity"]
            nodes.append(
                WikiPageNode(
                    id="activity",
                    title="Recent Activity",
                    slug="activity",
                    section_number="7",
                    page_type="fixed",
                    memory_count=p.memory_count,
                )
            )

        return WikiStructure(
            channel_id=channel_id,
            channel_name=channel_name,
            platform=platform,
            pages=nodes,
        )
