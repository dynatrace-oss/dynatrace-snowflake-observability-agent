# deployment.environment.name — OTel canonical field co-emission

## Summary

Added `deployment.environment.name` as a new co-emitted resource attribute alongside the existing `deployment.environment`, aligning DSOA telemetry with OpenTelemetry Semantic Conventions. Both keys are emitted with the same value derived from `core.deployment_environment` for a 3-release deprecation window ending in 1.3.0.

## Root cause / motivation

`deployment.environment` is not an OTel semconv key — the canonical name is `deployment.environment.name`. Customers correlating DSOA telemetry with other OTel-native sources (APM, infra, k8s) need the canonical name to join on the same field. The alias is kept for backward compatibility with existing dashboards and DQL queries.

## Implementation details

### config.py

Added `"deployment.environment.name": ""` to `RESOURCE_ATTRIBUTES` (position after `deployment.environment`). In the runtime merge dict (lines 157–163), added `"deployment.environment.name": config_dict["core.deployment_environment"]` alongside the existing `deployment.environment` line. Both receive the same value at runtime.

### Why co-emission (not query-time coalesce) for metrics

`Metrics.report_via_metrics_api` builds dimensions from `_resattr_dims` (all resource attrs excluding `telemetry.exporter.*`). Each unique dimension set = one timeseries. Co-emitting `deployment.environment.name` with the same value as `deployment.environment` means:
- Distinct series count unchanged — both keys have identical values, so no fan-out
- Each metric point gains exactly +1 dimension key
- No query-time coalesce needed for metrics: dashboards can hard-switch to `deployment.environment.name`

For records (logs/spans/events), OTel resource attributes carry both keys, so `coalesce(deployment.environment.name, deployment.environment)` in DQL handles the migration window for older data.

### instruments-def.yml (global)

Registered `deployment.environment.name` as a new dimension with OTel-aligned description. Marked `deployment.environment` as deprecated with explicit removal version (1.3.0). The `__deprecated` field is custom metadata (not consumed by `update_docs.py`) but the description field contains the deprecation note for generated docs.

### Test fixtures

All `test/test_results/**/*.json` (logs, spans, events, bizevents, davis_events) and `**/metrics.txt` fixtures updated to include `deployment.environment.name` alongside `deployment.environment`. Fixture update was done programmatically via Python script to ensure consistency across ~120 files.

### Dashboards and workflows

Metric queries (`timeseries ...`): hard-switched `deployment.environment` → `deployment.environment.name` (write-time co-emission means both dimensions are available; new canonical key is preferred).

Record queries (`fetch logs/spans/events`): replaced with `coalesce(deployment.environment.name, deployment.environment)` to maintain continuity across the migration window.

Variable/dropdown queries: switched to `coalesce()` pattern for record-sourced variables; direct `deployment.environment.name` for metric-sourced variables.

### appx-a-fields-refactoring.csv

Added migration row `deployment.environment;deployment.environment.name` to Appendix A so the migration helper script can auto-update customer DQL queries.

## Deployment notes

- No Snowflake SQL changes required — this is purely an agent-side resource attribute emission change
- Existing dashboards continue to work via `deployment.environment` until upgraded to use `.name`
- The agent upgrade is a drop-in: `core.deployment_environment` config key unchanged, same value emitted under both keys
- Sunset: `deployment.environment` removed in release 1.3.0

## Files changed

- `src/dtagent/config.py` — RESOURCE_ATTRIBUTES + merge dict
- `src/dtagent.conf/instruments-def.yml` — dimension registration + deprecation
- `src/assets/appx-a-fields-refactoring.csv` — migration row
- `test/_utils.py` — test config includes new key
- `test/core/test_agent_source_parsing.py` — test resource attributes includes new key
- `test/test_results/**/*.json` — ~50 log/span/event/bizevent fixture files
- `test/test_results/**/metrics.txt` — ~31 metric fixture files
- `docs/CHANGELOG.md` — user-facing deprecation notice
- `docs/SEMANTICS.md` — regenerated (new dimension entry)
- `docs/APPENDIX.md` — regenerated (migration row added)
- `docs/dashboards/**/*.yml` — metric tiles hard-switched; record tiles use coalesce
- `docs/workflows/**/*.yml` — same metric/record split applied
