# Remove `query_metric_metadata.js` — replace with `dtctl query --metadata=metrics`

**Date:** 2026-07-06
**Branch:** `feat/1.0.0/bizobs-151-semantic-export`
**Ticket:** BIZOBS-151

---

## Why the workaround existed

`scripts/test/verify_metric_units.sh` (Phase 3.7 of the QA runner) needed to
verify that every `dt.meta.unit` value DSOA sends is actually *recognized* by
Dynatrace — not just accepted as free text. The Grail Query API supports an
`?enrich=metric-metadata` parameter that populates `metadata.metrics[].unit`
with the canonical display name Dynatrace resolved (e.g. `MiBy` → `MebiByte`,
`%` → `Percent`).

The problem: `dtctl query` did not expose that parameter as a CLI flag. Neither
`dtctl query`'s plain DQL JSON (which only has `records[].interval/timeframe`)
nor the classic Metrics API v2 descriptor (which echoes back the raw symbol we
sent) returned the *resolved* unit — only `?enrich=metric-metadata` did.

The workaround was `scripts/test/query_metric_metadata.js`, a JavaScript
function executed via `dtctl exec function -f <file> --payload '{"metricKey":"..."}'`
inside the App Engine sandbox. The sandbox provided automatic platform OAuth
auth, calling `@dynatrace-sdk/client-query`'s `queryExecutionClient` directly
with the `enrich: "metric-metadata"` option. The result was parsed as
`.result.unit`.

---

## The replacement: `dtctl query --metadata=metrics`

`dtctl` has been extended: running

```bash
dtctl query "timeseries sum(<key>), from: -90m" -o json --metadata=metrics
```

now returns the full metric-metadata enrichment natively. The response shape is:

```json
{
  "metadata": {
    "metrics": [
      {
        "metric.key": "dt.host.cpu.user",
        "fieldName": "sum(dt.host.cpu.user)",
        "aggregation": "sum",
        "unit": "Percent",
        "displayName": "CPU user activity"
      }
    ]
  },
  "records": [...]
}
```

Both `unit` and `displayName` are populated for metrics that have them registered.
The `jq` extraction path is:

```bash
jq -r --arg k "$metric_name" \
  '.metadata.metrics[] | select(.["metric.key"] == $k) | .unit // "NOT_FOUND"'
```

No App Engine sandbox, no JS file, no `app-engine:functions:run` OAuth scope
required.

---

## Files changed

| File | Change |
|---|---|
| `scripts/test/query_metric_metadata.js` | **Deleted.** The entire JS workaround is obsolete. |
| `scripts/test/verify_metric_units.sh` | Updated header comment (removed NOTE block explaining the limitation), prerequisites block (dropped `app-engine:functions:run` scope mention), `usage()` text, Step 3 echo, and Step 3 loop body — replaced `dtctl exec function` + `.result.unit` with `dtctl query --metadata=metrics` + `.metadata.metrics[].unit`. |
| `.opencode/skills/qa-runner/SKILL.md` | Updated Phase 3.7 step 3 description to reflect the native `--metadata=metrics` flag. |
