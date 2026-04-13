# Channel Digest Template

Render a channel overview using `get_topic_overview` + `get_recent_activity`.

## Format

```
## <channel_name> digest

### Topics
- **<topic>** — <one-line summary> [src:src_xxx]
- **<topic>** — <one-line summary> [src:src_xxx]

### Decisions
- **<decision>** — <outcome> [src:src_xxx]
- **<decision>** — <outcome> [src:src_xxx]

### People
- **@<handle>** — <role or focus> [src:src_xxx]
- **@<handle>** — <role or focus> [src:src_xxx]

### Open threads
- <question or unresolved thread> [src:src_xxx]
- <question or unresolved thread> [src:src_xxx]
```

## Rules

- All four sections (`Topics`, `Decisions`, `People`, `Open threads`) are required headings.
- If a section has no evidence, write a single bullet: "No items found." — do not omit the heading.
- Each bullet ≤ 120 characters.
- Bold the key entity (topic name, decision title, handle) in each bullet.
- Cap each section at 5 bullets; if more exist, prefer recency.

## Example

```
## #auth-platform digest

### Topics
- **Clerk migration** — in progress, 70% feature parity. [src:src_aaa1111111]
- **SAML rollout** — scoped for Q3. [src:src_bbb2222222]

### Decisions
- **Adopt Clerk** — shipped 2025-09-18. [src:src_ccc3333333]

### People
- **@alice** — migration lead. [src:src_ddd4444444]
- **@bob** — pricing review. [src:src_eee5555555]

### Open threads
- Who owns the Auth0 deprovisioning? [src:src_fff6666666]
```
