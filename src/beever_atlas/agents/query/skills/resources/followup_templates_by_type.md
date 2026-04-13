# Typed Follow-Up Templates

Generate 2-3 follow-up question suggestions keyed to the query type. Pass them to `suggest_follow_ups`.

## Templates by type

### people
- "What has @<handle> worked on recently?"
- "Who else works with @<handle> on <topic>?"
- "What decisions has @<handle> driven in #<channel>?"

### decision
- "What alternatives were considered before <decision>?"
- "Who pushed back on <decision> and why?"
- "What changed after <decision> shipped?"

### definition
- "How is <term> used in #<channel>?"
- "Who introduced <term> to the team?"
- "What replaced <term> or preceded it?"

### comparison
- "Which option did the team ultimately pick, and why?"
- "Has this comparison been revisited since the decision?"
- "Are there internal benchmarks for <A> vs <B>?"

### general
- "Can you trace the history of <topic>?"
- "Who are the experts on <topic>?"
- "What recent activity touches <topic>?"

## Rules

- Emit 2 or 3 suggestions (never 1, never > 3).
- Each suggestion is a plain string — no bullets, no numbering, no markdown formatting inside the string.
- Substitute `<handle>`, `<topic>`, `<decision>`, etc. with concrete values from the just-answered question.
- Suggestions must be in the user's language (match the answer language).
- Do NOT suggest anything the user literally just asked.
- Classify the query type from the question phrasing; if unclear, use the `general` template.
