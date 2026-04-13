# Comparison Table Template

Compare 2 or more entities across 2 or more dimensions using a markdown table.

## Format

```
## Comparison: <Entity A> vs <Entity B>

| Dimension | <Entity A> | <Entity B> |
|---|---|---|
| <dim 1> | <cited value> [src:src_xxx] | <cited value> [src:src_xxx] |
| <dim 2> | <cited value> [src:src_xxx] | <cited value> [src:src_xxx] |
| <dim 3> | <cited value> [src:src_xxx] | <cited value> [src:src_xxx] |

**Summary:** <2-3 sentence synthesis highlighting the key trade-off>.
```

## Rules

- Rows = dimensions (e.g. cost, performance, team familiarity). Columns = entities being compared.
- Every non-empty cell must carry a `[src:src_xxx]` tag. Use "—" for cells with no evidence.
- Supports 3+ entities by adding columns; keep ≤ 4 to stay readable.
- The **Summary** sentence below the table is required and must NOT repeat cell content verbatim — it synthesizes.
- Bold the entity names in the heading on first mention.

## Example

```
## Comparison: **Clerk** vs **Auth0**

| Dimension | Clerk | Auth0 |
|---|---|---|
| Pricing above 10k MAU | Flat tier [src:src_aaa1111111] | Scales per MAU [src:src_bbb2222222] |
| SAML support | Paid add-on [src:src_ccc3333333] | Included in Enterprise [src:src_ddd4444444] |
| Team familiarity | 2 engineers shipped prod | None |

**Summary:** Clerk wins on predictable pricing and existing team experience; Auth0 is stronger for enterprise SSO.
```
