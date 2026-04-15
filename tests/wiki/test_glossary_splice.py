"""Tests for deterministic Glossary section splicing.

Glossary generation sometimes emits only the relationship mermaid diagram
and drops the Terms table + Introduction. The splicer fills those gaps so
readers always see definitions, not just a diagram.
"""

from types import SimpleNamespace

from beever_atlas.wiki.compiler import (
    _collect_glossary_entries,
    _render_glossary_terms_table,
    _splice_glossary_sections,
)


def _cluster(title, entities):
    return SimpleNamespace(title=title, key_entities=entities, key_facts=[])


def test_collect_merges_dict_terms_with_cluster_entities():
    glossary = [
        {"term": "Beever", "definition": "Memory system",
         "first_mentioned_by": "Alice", "related_topics": ["Arch"]},
        "MCP",
    ]
    clusters = [
        _cluster("Arch", [{"name": "Beever", "description": "extra"}]),
        _cluster("Integration", [{"name": "MCP", "description": "Protocol"}]),
    ]
    rows = _collect_glossary_entries(glossary, clusters)
    names = [r["term"] for r in rows]
    assert names == ["Beever", "MCP"]
    beever = next(r for r in rows if r["term"] == "Beever")
    assert beever["definition"] == "Memory system"  # dict definition wins
    assert "Arch" in beever["related_topics"]
    mcp = next(r for r in rows if r["term"] == "MCP")
    assert mcp["definition"] == "Protocol"
    assert "Integration" in mcp["related_topics"]


def test_render_terms_table_escapes_pipes_and_falls_back():
    rows = [
        {"term": "X|Y", "definition": "", "first_mentioned_by": "",
         "related_topics": []},
    ]
    table = _render_glossary_terms_table(rows)
    assert "X\\|Y" in table
    assert "Referenced in this channel." in table
    assert "| — |" in table  # first_mentioned_by fallback


def test_splice_adds_both_missing_sections():
    diagram_only = "## Relationship diagram\n```mermaid\ngraph TD\nA-->B\n```\n"
    glossary = [{"term": "Beever", "definition": "Memory sys",
                 "first_mentioned_by": "Alice", "related_topics": ["Arch"]}]
    clusters = []
    out = _splice_glossary_sections(diagram_only, glossary, clusters)
    assert "## Introduction" in out
    assert "## Terms" in out
    assert "| Beever | Memory sys | Alice | Arch |" in out


def test_splice_respects_existing_sections():
    existing = (
        "## Relationship diagram\n```mermaid\ngraph TD\nA-->B\n```\n\n"
        "## Introduction\n\nHello.\n\n"
        "## Terms\n\n| T | D | — | — |\n|---|---|---|---|\n| X | y | — | — |\n"
    )
    out = _splice_glossary_sections(existing, [{"term": "X"}], [])
    assert out.count("## Introduction") == 1
    assert out.count("## Terms") == 1


def test_splice_noop_on_empty_content():
    assert _splice_glossary_sections("", [], []) == ""


def test_splice_skips_terms_when_no_data():
    diagram_only = "## Relationship diagram\n```mermaid\ngraph TD\nA-->B\n```\n"
    out = _splice_glossary_sections(diagram_only, [], [])
    # Introduction always rendered, Terms skipped when no entries
    assert "## Introduction" in out
    assert "## Terms" not in out
