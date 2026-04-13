# Mermaid Cheat Sheet

Use fenced ` ```mermaid ` blocks when a diagram clarifies relationships, flow, or evolution over time.

## When to use
- Flow / process → `flowchart`
- Evolution over time → `timeline`
- Entity relationships → `graph LR`

## Syntax basics

### Flowchart
```mermaid
flowchart TD
    A[Start] --> B{Has cache?}
    B -- yes --> C[Return cached]
    B -- no --> D[Fetch + store]
    D --> C
```

### Timeline
```mermaid
timeline
    title Auth provider decision
    2025-08 : Proposed Auth0
    2025-09 : Pricing concern raised
    2025-09 : Switched to Clerk
    2025-10 : Clerk adopted
```

### Relationship graph (LR = left-to-right)
```mermaid
graph LR
    Alice -->|owns| AuthService
    Bob -->|reviews| AuthService
    AuthService -->|depends on| Clerk
```

## Rules
- Keep diagrams ≤ 12 nodes. Larger graphs hurt readability.
- Label every edge in `graph`/`flowchart`.
- Do NOT put `[src:...]` tags inside the mermaid block — place them in the surrounding prose.
- Always put the fenced block on its own paragraph; never inside a list item.
