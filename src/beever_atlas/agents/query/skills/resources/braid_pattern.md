# Source Braid Pattern

Use when the question benefits from BOTH internal team knowledge AND external context. Braid the two; do not mix them.

## Format

```
**From your knowledge base:** <one-liner synthesizing internal findings> [src:src_xxx] [src:src_xxx]

**External context:** <one-liner from external_knowledge, attributed> [src:src_xxx]

**Synthesis:** <one-liner tying them together with the specific answer to the user>.
```

## Rules

- Exactly three labelled lines. Each label is bold. Each line is a single sentence.
- Internal line must cite ≥ 1 `[src:...]` tag from `search_channel_facts`.
- External line must cite ≥ 1 `[src:...]` tag from `search_external_knowledge`.
- Synthesis line carries no citations — it is the bridge.
- If external retrieval returned nothing, omit the External line and the Synthesis line; only emit the internal line.
- Do NOT prefix with meta phrases like "Here is the braid" — emit the three lines directly.

## Example

```
**From your knowledge base:** Your team chose Clerk over Auth0 because of flat-tier pricing above 10k MAU. [src:src_aaa1111111] [src:src_bbb2222222]

**External context:** Industry benchmarks show Auth0 is typically 2-3× more expensive at 50k MAU than flat-tier competitors. [src:src_ccc3333333]

**Synthesis:** Your team's Clerk decision aligns with the broader cost pattern in the market for mid-scale SaaS auth.
```
