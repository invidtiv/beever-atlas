"""Prompt templates for each wiki page type.

Design philosophy: STRUCTURE FIRST — diagrams, tables, bullet points, then supporting text.
Domain-agnostic — works for tech, community, research, personal, and enterprise channels.
"""

from __future__ import annotations

OVERVIEW_PROMPT = """You are a knowledge wiki compiler. Create an **Overview** page for this channel.

Return JSON: {{"content": "markdown string", "summary": "1-2 sentence summary"}}

## Content structure (follow this order strictly)
1. **Brief intro** — 2-3 sentences describing what this channel is about and its purpose
2. **Concept map** — ```mermaid flowchart showing how the main topics/themes relate to each other. Use the topic relationships data to build accurate connections.
3. **Key Highlights table** — GFM table summarizing: total topics, decisions made, key contributors, resources shared, active period
4. **Topics at a glance** — bullet list of each topic with 1-line description and memory count
5. **Key contributors** — bullet list of most active people and their roles/expertise
6. **Tools & resources** — if technologies or tools data exists, show as bullet list or GFM table. Skip this section entirely if no tools/technologies are relevant.
7. **Recent momentum** — 2-3 sentences on what's currently active or changing. Reference the activity summary data.

## Adaptive instructions
- Adapt your language to match the channel's domain. If the data is technical, use technical terms. If it's a community or personal channel, use appropriate casual language.
- The concept map should reflect the actual relationships in the data — don't force a technical "architecture" if the channel discusses non-technical topics.
- Only include sections where data exists. If there are no technologies, skip "Tools & resources". If there are no decisions, don't mention them prominently.

## Rules
- Do NOT start with a # heading (title rendered separately)
- Each numbered section above MUST be a ## heading (e.g. `## Concept Map`, `## Key Highlights`). Use ### for sub-sections within them. This creates a navigable table of contents.
- Use ```mermaid for diagrams. Keep syntax SIMPLE — use only `graph TD` with `A[Label] --> B[Label]` edges. Do NOT use subgraph, do NOT use `--` edge labels, do NOT use parentheses inside brackets. Example: `graph TD\n    A[Data Sources] --> B[Processing]\n    B --> C[Storage]`
- Use ```chart for data charts with exact JSON: {{"type":"donut","title":"...","data":[{{"name":"X","value":N}}],"xKey":"name","series":["value"]}}
- Use GFM tables for structured data
- Use bullet points over paragraphs when listing facts
- Add [N] citation markers on factual claims (use actual numbers: [1], [2], [3])
- Do NOT use @, #, or $ prefixes for entity names — just write names normally
- If media (images/PDFs/links) exist, embed important ones as ![desc](url) for images or [name](url) for docs/links

## Channel data
Channel: {channel_name}
Description: {description}
Summary: {text}
Themes: {themes}
Momentum: {momentum}
Contributor dynamics: {team_dynamics}
Decisions: {decisions_count} | Contributors: {people_count} | Projects: {projects_count} | Tools/Tech: {tech_count} | Media: {media_count}

Topics: {clusters_json}
Topic relationships: {topic_graph_edges_json}
Recent activity: {recent_activity_json}
Key contributors: {top_people_json}
Key decisions: {top_decisions_json}
Technologies/Tools: {technologies_json}
Projects/Initiatives: {projects_json}
Key entities from knowledge graph: {key_entities_json}
Entity relationships from knowledge graph: {key_relationships_json}
Media: {media_json}
Glossary preview (first 5 terms): {glossary_preview_json}
FAQ count across topics: {faq_count}
"""

TOPIC_PROMPT = """You are a knowledge wiki compiler. Create a **Topic** page for the cluster below.

Return JSON: {{"content": "markdown string", "summary": "1-2 sentence summary"}}

## Content structure (follow this order strictly)
1. **Overview** — 2-3 sentences summarizing this topic: what it covers, why it matters, and its current state
2. **Concept diagram** — ```mermaid diagram showing how the key entities (people, decisions, concepts) relate within this topic. Use the entity relationships data to build accurate connections.
3. **Key Facts** — GFM table with columns: Fact, Source, Type, Importance — showing the most important facts with [N] citations
4. **Decisions & outcomes** — if decisions exist, show as GFM table with columns: Decision, Status, Made By, Date. Use status badges: ✅ active, ❌ superseded, ⏳ pending. Skip if no decisions.
5. **Contributors** — bullet list of people involved with their roles (decision maker, contributor, expert, mentioned)
6. **Tools & resources** — if technologies/tools exist, bullet list. Skip if none.
7. **Current state & open questions** — what's resolved vs. still open. Use bullet points.
8. **Media & Resources** — if media exists, embed relevant images as ![desc](url), documents as [name](url). Skip if none.

## Adaptive instructions
- The concept diagram should reflect actual entities and relationships from this topic — not a generic template
- If this topic is about a technical system, show system relationships. If about a community event, show event logistics. If about research, show methodology flow. Adapt to the content.
- Prioritize showing high-quality, high-importance facts in the Key Facts table
- Every factual claim MUST have a [N] citation marker

## Rules
- Do NOT start with a # heading (title rendered separately)
- Each numbered section above MUST be a ## heading (e.g. `## Concept Diagram`, `## Key Facts`). Use ### for sub-sections. This creates a navigable table of contents.
- ALWAYS include at least one ```mermaid diagram. Keep syntax SIMPLE — use only `graph TD` with `A[Label] --> B[Label]` edges. No subgraph, no `--` edge labels, no parentheses in brackets
- Use ```chart for quantitative data with JSON: {{"type":"bar","title":"...","data":[...],"xKey":"name","series":["value"]}}
- Prefer tables and bullet points over long paragraphs
- Add [N] citation markers (actual numbers) on every factual claim
- Do NOT use @, #, or $ prefixes — write entity names normally
- If media exists, embed: ![desc](url) for images, [name](url) for docs/links

## Topic data
Title: {title}
Summary: {summary}
Current state: {current_state}
Open questions: {open_questions}
Impact: {impact_note}
Tags: {topic_tags}
Period: {date_range_start} – {date_range_end}
Authors: {authors}

Key facts: {key_facts_json}
Decisions: {decisions_json}
People: {people_json}
Technologies: {technologies_json}
Projects: {projects_json}

Knowledge graph entities in this topic: {key_entities_json}
Knowledge graph relationships in this topic: {key_relationships_json}

All facts (for citation sourcing): {member_facts_json}
Media: {media_json}
"""

PEOPLE_PROMPT = """You are a knowledge wiki compiler. Create a **People & Experts** page.

Return JSON: {{"content": "markdown string", "summary": "1-2 sentence summary"}}

## Content structure (follow this order strictly)
1. **Overview** — 1-2 sentences describing the contributor landscape in this channel
2. **Contributor network** — ```mermaid diagram showing key people and their connections. Use relationship edges to show who collaborates with whom, who made which decisions, and expertise areas.
3. **Activity chart** — ```chart bar chart showing contribution level per person
4. **Contributors table** — GFM table with columns: Name, Role/Expertise, Topics Active In, Key Contributions, Decisions Made
5. **Collaboration patterns** — bullet points on notable collaboration patterns, expertise clusters, and knowledge areas

## Adaptive instructions
- Use "Contributors" and "Experts" language rather than "Team members" — this works for open communities, research groups, and enterprise teams alike
- The mermaid diagram should show actual relationships from the edge data: who DECIDED what, who WORKS_ON what, who USES which tools
- If the channel has few people (1-3), keep the diagram simple. For larger groups (5+), focus on the most active contributors.

## Rules
- Do NOT start with a # heading
- Each numbered section above MUST be a ## heading (e.g. `## Contributor Network`, `## Contributors Table`). Use ### for sub-sections. This creates a navigable table of contents.
- MUST include a ```mermaid diagram. Keep syntax SIMPLE — `graph TD` with `A[Label] --> B[Label]`. No subgraph, no parentheses in brackets
- Use GFM tables, not prose paragraphs, for listing people
- Add [N] citation markers on factual claims
- Do NOT use @, #, $ prefixes — write names normally
- Activity chart JSON: {{"type":"bar","title":"Contributor Activity","data":[{{"name":"Alice","contributions":15}}],"xKey":"name","series":["contributions"]}}

## Data
People (with relationship edges): {persons_json}
Contributor context: {top_people_json}
Relationship edges (from knowledge graph): {relationship_edges_json}
"""

DECISIONS_PROMPT = """You are a knowledge wiki compiler. Create a **Decisions** page.

Return JSON: {{"content": "markdown string", "summary": "1-2 sentence summary"}}

## Content structure (follow this order strictly)
1. **Summary** — 1-2 sentences on the decision landscape: how many decisions, how many active vs. superseded
2. **Decision flow** — ```mermaid flowchart showing decision relationships and supersession chains. Show active decisions in a different style than superseded ones.
3. **Decision timeline** — GFM table with columns: Date, Decision, Status, Made By, Context, Supersedes
4. **Impact analysis** — bullet points on what each active decision affects and its significance

## Adaptive instructions
- "Decisions" applies broadly: technical architecture choices, community governance decisions, research methodology selections, project direction changes, policy updates
- If no decisions exist, produce a brief note: "No formal decisions have been recorded in this channel yet." with a simple placeholder diagram
- If there are supersession chains, make them visually clear in the mermaid diagram
- Include context/rationale for each decision where available

## Rules
- Do NOT start with a # heading
- Each numbered section above MUST be a ## heading (e.g. `## Decision Flow`, `## Decision Timeline`). Use ### for sub-sections. This creates a navigable table of contents.
- MUST include a ```mermaid flowchart. Keep syntax SIMPLE — `graph TD` with `A[Label] --> B[Label]`. No subgraph, no parentheses in brackets
- Status badges: ✅ active, ❌ superseded, ⏳ pending
- Use tables for the timeline, not paragraphs
- Add [N] citation markers on factual claims
- Do NOT use @, #, $ prefixes

## Data
Decisions (with supersession chains): {decisions_json}
Decision context: {top_decisions_json}
"""

ACTIVITY_PROMPT = """You are a knowledge wiki compiler. Create a **Recent Activity** page.

Return JSON: {{"content": "markdown string", "summary": "1-2 sentence summary"}}

## Content structure (follow this order strictly)
1. **Summary** — 1-2 sentences on recent activity: what happened in the last 7 days, key highlights
2. **Activity chart** — ```chart area chart showing knowledge captured per day over the last 7 days
3. **Daily breakdown** — for each day with activity, a section with:
   - Date as ### heading
   - Bullet list of key facts, decisions, and contributions added
   - Any media shared that day (embed images, link to docs)
4. **Highlights** — if there are standout events (major decisions, new topics, significant media), call them out

## Adaptive instructions
- Activity means different things in different channels: code discussions, community events, research findings, project updates. Adapt language accordingly.
- If no recent activity exists, produce a brief note: "No activity recorded in the last 7 days." Skip the chart.
- If media was shared recently, embed or link it in the daily breakdown
- Group related facts within each day for readability

## Rules
- Do NOT start with a # heading
- Each numbered section above MUST be a ## heading (e.g. `## Activity Chart`, `## Daily Breakdown`). Use ### for sub-sections (e.g. each day as ### heading). This creates a navigable table of contents.
- Activity chart JSON: {{"type":"area","title":"Knowledge Growth","data":[{{"date":"Apr 01","facts":5,"decisions":1}}],"xKey":"date","series":["facts","decisions"]}}
- Use bullet points, not paragraphs
- Add [N] citation markers where applicable
- Do NOT use @, #, $ prefixes
- If no recent activity, just say so briefly (no empty charts)

## Data
Recent facts (last 7 days): {recent_facts_json}
Activity summary: {recent_activity_json}
Media shared recently: {recent_media_json}
"""

FAQ_PROMPT = """You are a knowledge wiki compiler. Create a **FAQ** (Frequently Asked Questions) page.

Return JSON: {{"content": "markdown string", "summary": "1-2 sentence summary"}}

## Content structure (follow this order strictly)
1. **Introduction** — 1 sentence: "Common questions and answers that have emerged from discussions in this channel."
2. **Topic distribution** — if FAQs come from 3+ topics, include a ```chart donut chart showing how many FAQs per topic
3. **Q&A sections** — group questions by topic. For each topic group:
   - Use ## heading with topic name
   - List each Q&A as:
     - **Q: [question text]**
     - A: [answer text] [N] (with citation)
4. **Related pages** — bullet list suggesting which wiki pages have more detail on each topic

## Adaptive instructions
- These Q&A pairs were extracted from actual channel discussions — they represent real questions people asked and answers that emerged
- Deduplicate similar questions — if two topics generated nearly identical questions, merge them and cite both sources
- If no FAQ candidates exist at all, produce: "No frequently asked questions have emerged from channel discussions yet. As more conversations happen, common questions and their answers will appear here."
- Order questions within each topic by relevance/importance, not chronologically

## Rules
- Do NOT start with a # heading (title rendered separately)
- Each topic group MUST be a ## heading. Individual Q&A pairs use ### or bold formatting. This creates a navigable table of contents.
- Use ```chart for the topic distribution with JSON: {{"type":"donut","title":"FAQ by Topic","data":[{{"name":"Topic A","value":3}}],"xKey":"name","series":["value"]}}
- Add [N] citation markers on answers to trace back to source discussions
- Do NOT use @, #, $ prefixes — write names normally
- Keep answers concise but complete — 1-3 sentences each

## Data
FAQ candidates (grouped by topic): {faq_candidates_json}
Topic names for reference: {topic_names_json}
"""

GLOSSARY_PROMPT = """You are a knowledge wiki compiler. Create a **Glossary** page.

Return JSON: {{"content": "markdown string", "summary": "1-2 sentence summary"}}

## Content structure (follow this order strictly)
1. **Introduction** — 1 sentence: "Key terms, acronyms, and concepts used in this channel."
2. **Terms table** — GFM table with columns: Term, Definition, First Mentioned By, Related Topics. Sort alphabetically.
3. **Relationship diagram** — if 5+ terms exist, include a ```mermaid diagram showing how terms relate to each other (which terms are used together, which are sub-concepts of others)
4. **Category breakdown** — if terms naturally group into categories (e.g., technical terms, process terms, domain terms), add a brief categorized list after the table

## Adaptive instructions
- Glossary terms can be anything channel-specific: technical jargon, project codenames, acronyms, community slang, research terminology, business terms
- Enrich definitions where the provided data is thin — add context about how the term is used in this channel specifically
- If no glossary terms exist, produce: "No channel-specific terms have been identified yet. As more specialized vocabulary emerges in discussions, it will be cataloged here."
- Cross-reference related topics where possible

## Rules
- Do NOT start with a # heading (title rendered separately)
- Each numbered section above MUST be a ## heading (e.g. `## Terms`, `## Relationship Diagram`). Use ### for sub-sections or categories. This creates a navigable table of contents.
- Use GFM tables for the main term list — this is the primary content
- Use ```mermaid for the relationship diagram. Keep syntax SIMPLE — `graph TD` with `A[Label] --> B[Label]`. No subgraph, no parentheses in brackets
- Do NOT use @, #, $ prefixes — write names normally

## Data
Glossary terms: {glossary_terms_json}
Channel context: {channel_description}
"""
