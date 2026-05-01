# Wiki Maintainer auto-mode soak runbook

This runbook covers §22 of the `oss-redesign-production-wiring` change —
the staging soak that gates flipping `WIKI_MAINTENANCE_MODE=auto` to
default ON in production.

The unit + integration tests verify the structural correctness of
each layer in isolation. The soak verifies the integrated behaviour
in a live environment over a 2-week window, with real LLM cost.

## §22.1 E2E — full ingest → extraction → wiki refresh

Run in staging with a fresh test channel. Verifies the redesign's
"compounding LLM Wiki" promise end-to-end.

```bash
# 1. Create a test channel + register a push source for it.
curl -X POST https://atlas.staging/api/admin/sources \
  -H "X-Admin-Token: $BEEVER_ADMIN_TOKEN" \
  -d '{"source_id": "soak-test", "allowed_channels_pattern": "soak-*"}'

# 2. Push 100 synthetic messages signed with the returned secret.
# (See docs/integrations/push-sources.md for the signing recipe.)

# 3. Watch extraction drain.
watch -n 5 "curl -s https://atlas.staging/api/channels/soak-channel-1/extraction-status \
  -H 'Authorization: Bearer $BEARER' | jq"

# 4. After counts.pending=0, fetch one wiki page and assert content
#    is NOT the legacy placeholder.
PAGE=$(curl -s "https://atlas.staging/api/channels/soak-channel-1/wiki/page/topic:auth" \
  -H "Authorization: Bearer $BEARER")
echo "$PAGE" | jq -r '.sections[].content_md' | grep -q "New facts integrated:" \
  && echo "FAIL: placeholder still in content_md" \
  || echo "PASS: real LLM content"
```

Pass criteria:
- Within ~60s of the last push, all 100 messages reach `extraction_status="done"`.
- The maintainer fires (visible in logs as `wiki_maintainer.on_extraction_done`).
- Affected wiki pages contain natural-language content, NOT the literal
  string `"New facts integrated: <ids>"`.

## §22.2 E2E — admin UI → signed push round-trip

1. Navigate to `/admin/sources` in the staging dashboard.
2. Register a new source (`soak-source-2`).
3. Copy the secret from the modal.
4. Use it to sign + POST 50 events to the staging API (see
   `docs/integrations/push-sources.md`).
5. Open the wiki for the target channel; expect pages to refresh
   within seconds (with `wiki.maintenance_mode=auto`).

Pass criteria:
- Events appear in `channel_messages` with the new `source_id`.
- The maintainer rewrites affected pages (visible in
  `GET /api/admin/extraction-worker/metrics` `claim_rate` rising then
  falling).
- The wiki UI reflects new content.

## §22.3 E2E — lint with intentional orphans

1. Pick a channel with an existing wiki.
2. Manually delete a topic cluster from Weaviate (or seed a stale
   `wiki_pages` row whose `cluster_id` no longer exists). Document the
   exact one-shot SQL/CLI used.
3. POST `/api/channels/{id}/wiki/lint`.
4. Expect a finding with `category="orphan"` for the orphaned page.
5. Click the finding in the UI → navigates to the affected page.

## §22.4-§22.7 Drift A/B comparator soak (the actual gate)

This is the longest-running step. Run it on **at least 3 real channels**
for a continuous 2-week window. The comparator emits one
`wiki_drift_report` log line per `apply_update`; aggregate them through
your logging stack.

### Setup

1. Pick 3 channels with active conversation: ideally one short
   (low traffic), one medium, one busy.
2. Set `WIKI_DRIFT_AB=true` in their staging env.
3. Set `wiki.maintenance_mode=auto` per-channel (via the
   ChannelSettingsTab toggle).
4. Wire the comparator into `WikiMaintainer.apply_update`'s success
   path so each successful incremental update also runs the regenerate
   factory in parallel. (The comparator service is shipped; this
   wiring is the §19.4 "deferred" step.)

### Monitoring

Tail logs, filter to `event=wiki_drift_report`. Alternatively:

```bash
# Aggregate per-channel medians + p95 from the structured log lines.
# Adjust the log path to your environment.
grep -h "event=wiki_drift_report" /var/log/beever-atlas/*.log \
  | python -c "
import sys, statistics
from collections import defaultdict
sections = defaultdict(list)
for line in sys.stdin:
    parts = dict(p.split('=') for p in line.split() if '=' in p)
    if 'levenshtein_section_p50' in parts:
        sections[parts.get('channel_id', '?')].append(float(parts['levenshtein_section_p50']))
for ch, vals in sections.items():
    print(f'{ch}: median={statistics.median(vals):.3f} '
          f'p95={statistics.quantiles(vals, n=20)[-1]:.3f} samples={len(vals)}')
"
```

### Pass criterion

Median Levenshtein < 0.15 AND p95 < 0.30 across all sections, sustained
for 2 weeks across all 3 channels. Document the daily summary.

### If pass

- Open a PR flipping the env-default `WIKI_MAINTENANCE_MODE` from
  `"manual"` to `"auto"`.
- Tag the responsible operator + a code reviewer.
- Roll forward to production with the new default after staging burn-in
  passes.

### If fail (drift exceeds threshold on any channel)

- Do NOT flip the default.
- Capture sample drifts (the structured log line includes
  `sample_section_diffs` for the worst sections).
- Iterate on the `_render_apply_update_prompt` template OR the
  `plan_updates` routing (the most common cause of drift is
  the maintainer routing facts to the wrong page; second most common
  is prompt template not preserving voice).
- Re-run the soak on the iterated prompt for another 2 weeks.

## Scheduled re-runs

After the initial soak, schedule a re-run quarterly so prompt-shift
on the underlying LLM doesn't silently drift back over the threshold.
The drift comparator stays in the code; flip `WIKI_DRIFT_AB=true` for
the soak window each quarter.
