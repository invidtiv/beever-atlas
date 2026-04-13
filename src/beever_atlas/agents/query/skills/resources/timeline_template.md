# Decision-Trace Timeline Template

Render a decision history as a vertical timeline. Each step is a pinned event; the final line points to the outcome.

## Format

```
## Decision trace: <topic>

- 📌 **YYYY-MM-DD** — **@actor** — <one-line rationale or action> [src:src_xxx]
- 📌 **YYYY-MM-DD** — **@actor** — <one-line rationale or action> [src:src_xxx]
- 📌 **YYYY-MM-DD** — **@actor** — <one-line rationale or action> [src:src_xxx]

→ **Outcome:** <final state or current decision> [src:src_xxx]
```

## Rules

- One bullet per step, oldest first.
- Always include date (YYYY-MM-DD), actor handle (prefix `@`), and the `[src:...]` tag from the tool result.
- Keep each rationale ≤ 100 characters.
- The final arrow line (`→ **Outcome:** ...`) is required and summarizes the latest committed decision.
- Do NOT include steps without a citation. If the tool returned an `_empty: true` row, render a single bullet noting "no recorded history" instead of fabricating steps.

## Example

```
## Decision trace: auth provider

- 📌 **2025-08-14** — **@alice** — proposed Auth0 for speed of rollout [src:src_aaa1111111]
- 📌 **2025-09-02** — **@bob** — flagged pricing concern above 10k MAU [src:src_bbb2222222]
- 📌 **2025-09-11** — **@alice** — switched proposal to Clerk; cost model fits [src:src_ccc3333333]

→ **Outcome:** Team adopted Clerk on 2025-09-18. [src:src_ddd4444444]
```
