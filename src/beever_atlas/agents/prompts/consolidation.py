"""Consolidation agent prompts for topic cluster and channel summarization."""

CLUSTER_SUMMARY_INSTRUCTION = """\
Summarize this topic from a team channel (2-3 sentences). \
Include key decisions, actions, and who was involved.

{context}

Return a JSON object:
{{"summary_text": "your summary here"}}
"""

CHANNEL_SUMMARY_INSTRUCTION = """\
Generate a brief channel overview (3-5 sentences) from these topic summaries. \
Highlight the main themes and key information.

{context}

Return a JSON object:
{{"summary_text": "your summary here"}}
"""
