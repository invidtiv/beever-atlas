# People Profile Card Template

Render a concise person profile from `find_experts` + `search_channel_facts` evidence.

## Format

```
## @<handle>

- **Inferred role:** <short role label, e.g. "backend lead", "design review owner">
- **Top topics:** <topic 1>, <topic 2>, <topic 3>
- **Recent activity:** <one-line summary of latest contributions>

**Evidence**
- <fact 1 in one sentence> [src:src_xxx]
- <fact 2 in one sentence> [src:src_xxx]
- <fact 3 in one sentence> [src:src_xxx]
```

## Rules

- Handle must be prefixed with `@` and copied verbatim from the tool result.
- Inferred role ≤ 40 characters. Do not over-claim; if unclear, say "contributor".
- Exactly 3 top topics; fewer only if the evidence supports fewer.
- Exactly 3 evidence bullets, each with a `[src:...]` tag.
- Do not guess email, timezone, or employer unless directly present in a cited fact.

## Example

```
## @jordan

- **Inferred role:** data-pipeline maintainer
- **Top topics:** Airflow, ingest reliability, on-call rotation
- **Recent activity:** Led the Airflow 2.9 upgrade and wrote the runbook.

**Evidence**
- Shipped the Airflow 2.9 upgrade PR in April. [src:src_aaa1111111]
- Wrote the weekend on-call runbook after the March outage. [src:src_bbb2222222]
- Mentors two junior engineers on DAG design patterns. [src:src_ccc3333333]
```
