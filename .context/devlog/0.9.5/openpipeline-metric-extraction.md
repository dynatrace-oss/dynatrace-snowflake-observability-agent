# [0.9.5] — OpenPipeline Metric-Extraction Rules

## Motivation

DSOA reports Snowflake task run states and login failures as structured log attributes
(`snowflake.task.run.state`, `status.code`). To build time-series charts or Davis AI anomaly
detection on these signals, operators previously had to write DQL `makeTimeseries` queries in
every dashboard. OpenPipeline metric-extraction rules derive these counters once at ingest time,
making them available as first-class Dynatrace metrics without runtime query cost.

## Implementation

**New directory — `docs/openpipeline/`**

A single Settings 2.0 pipeline YAML (`docs/openpipeline/snowagent-logs-pipeline/snowagent-logs-pipeline.yml`)
ships three new metric-extraction processors alongside the existing pipeline configuration.
The file follows the standard `objectid/schemaid/schemaversion/value` envelope and is applied
natively by `dtctl apply` without any YAML-to-JSON conversion.

New processors in `value.metricExtraction.processors`:

- `processor_snowflake.task.run.failed_6971` — matches
  `dsoa.run.context == "task_history" and snowflake.task.run.state == "FAILED"`;
  dimensions: `db.namespace`, `snowflake.schema.name`, `snowflake.task.name`.
- `processor_snowflake.task.run.cancelled_3812` — same as above with `CANCELLED`.
- `processor_snowflake.task.run.successful_5104` — same as above with `SUCCEEDED`.

`snowflake.task.run.id` is intentionally excluded from all dimensions (high-cardinality guard).

**Deploy script updates — `scripts/deploy/deploy_dt_assets.sh`**

- Scope validation extended: `dashboards | workflows | openpipeline | all`.
- New `deploy_openpipeline_rules()` function applies YAML files directly via `dtctl apply -f <file>.yml`.
  No YAML-to-JSON conversion; no id write-back (Settings 2.0 objects use a stable `objectid`).
- `all` scope now also calls `deploy_openpipeline_rules`.

**Login attempt metric processors — `snowflake.login.attempts.*`**

Three additional processors were added for `login_history` counters. They were initially named
`log.snowflake.logins.{failed,successful,total}` (using the `log.*` prefix) because custom
`snowflake.*`-namespace metrics could not be created in OpenPipeline at the time. That constraint
has been lifted; the processors have been renamed to the canonical `snowflake.login.attempts.*`
scheme, consistent with the rest of the DSOA metric taxonomy:

- `processor_snowflake.login.attempts.failed_4856` — matches `event.name == "LOGIN" and
  dsoa.run.context == "login_history" and status.code == "ERROR"`; dimensions: `db.system`,
  `deployment.environment`, `db.user`, `host.name`, `client.type`.
- `processor_snowflake.login.attempts.successful_3900` — same matcher with `status.code == "OK"`;
  dimensions: `db.system`, `deployment.environment`, `db.user`, `client.type`, `host.name`.
- `processor_snowflake.login.attempts.total_6874` — matches all LOGIN events regardless of status;
  same dimension set as failed.

Numeric suffixes preserved for traceability. Re-applying the YAML drops the old `log.*` processors
and creates the renamed ones — no data migration required as they are counters starting from the
apply time.

`KNOWN_METRIC_KEYS` in `test/core/test_openpipeline_rules.py` extended to include all three login
keys; dimension-presence and enabled-state guards extended to cover `snowflake.login.attempts.*`
prefix alongside `snowflake.task.run.*`.

**New test file — `test/core/test_openpipeline_rules.py`**

12 pytest tests across three classes:

- `TestOpenpipelineRuleStructure` (8 tests): required top-level fields, non-empty processors list,
  required processor fields, `type == "metricExtraction"`, metric key allow-list, non-empty
  dimensions, high-cardinality dimension guard, matcher contains `dsoa.run.context`.
- `TestOpenpipelineRuleUniqueness` (2 tests): unique ids across files, unique metric keys per
  processor.
- `TestOpenpipelineRuleCount` (2 tests): exactly 4 rule files, all known metric keys covered.

**Bats test updates — `test/bash/test_deploy_dt_assets.bats`**

Added fixture for `docs/openpipeline/test-openpipeline-rule/` and 6 new tests covering:
valid scope acceptance, output mentions `openpipeline`, scope filtering (no dashboards/workflows
deployed), `all` deploys all three types, name extraction from `# OPENPIPELINE:` comment,
graceful handling of missing directory.
