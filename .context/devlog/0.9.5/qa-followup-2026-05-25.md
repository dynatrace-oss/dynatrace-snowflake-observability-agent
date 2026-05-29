# QA Follow-Up — 2026-05-25

## Overview

This file documents all 9 QA follow-up items investigated and resolved during the
2026-05-25 ANT-1 QA session for DSOA 0.9.5. Items 1–5 were addressed in earlier
sessions; items 6, 7, and 9 are covered here. Item 8 was a documentation-only fix.

---

## Item 1 — BUG-E2.5a: org-contract-balance-warning SDK import error

**Status:** FIXED (commit `bd39309`, branch `fix/0.9.5/org-contract-balance-warning-sdk`)

**Root cause:** The workflow's JavaScript action imported `@dynatrace-sdk/client-metrics`,
a module that does not exist on the Dynatrace automation runtime. All other DSOA workflows
use `@dynatrace-sdk/client-classic-environment-v2`.

**Fix:** Changed the import to `@dynatrace-sdk/client-classic-environment-v2` which
correctly exports `metricsClient` (Metrics v2 API client).

**File:** `docs/workflows/org-contract-balance-warning/org-contract-balance-warning.yml` line 41

---

## Item 2 — BUG-E2.5b: org-contract-balance-warning metrics query 406 error

**Status:** FIXED (commit `d02fb1e`, branch `fix/0.9.5/org-contract-balance-warning-406`)

**Root cause:** After fixing the SDK import, `metricsClient.query()` returned HTTP 406.
The Metrics v2 query API does not support the query format used in the workflow action.

**Fix:** Replaced the `metricsClient.query()` call with a DQL `execute-dql-query` action
that queries `timeseries avg(snowflake.org.billing.capacity_balance)` directly. This is
consistent with how other DSOA workflows query Snowflake telemetry.

**File:** `docs/workflows/org-contract-balance-warning/org-contract-balance-warning.yml`

---

## Item 3 — warehouse-sensitive-change-alert: ALTER WAREHOUSE not in ACCESS_HISTORY

**Status:** CLOSED — platform limitation documented; workflow and test tooling corrected

**Finding:** `ALTER WAREHOUSE` DDL statements do **not** populate
`ACCESS_HISTORY.OBJECT_MODIFIED_BY_DDL` in Snowflake. This is a Snowflake platform
behaviour, not a DSOA bug. The field captures DDL on database objects (tables, views,
schemas) but not warehouse-level administrative DDL.

**Impact:** The `warehouse-sensitive-change-alert` workflow was updated to detect
warehouse DDL via `db.operation.name` + `db.query.text` keyword matching (not
`snowflake.object.ddl.operation`). The workflow now scans for sensitive property keywords
(WAREHOUSE_SIZE, SCALING_POLICY, AUTO_SUSPEND, MIN_CLUSTER_COUNT, MAX_CLUSTER_COUNT,
GENERATION, ENABLE_QUERY_ACCELERATION, QUERY_ACCELERATION_MAX_SCALE_FACTOR,
MAX_CONCURRENCY_LEVEL) in the raw SQL text.

**Dashboard:** *Warehouse Change Detection* dashboard uses the same approach with
`parse upper(db.query.text)` to extract warehouse names and operations.

**E3.2 QA validation (2026-05-29):** Workflow triggered successfully, 6 events ingested
via `dsoa.warehouse_sensitive_change` ad.source. Exec ID: `dc665507-8b99-4e84-9d52-91b3c3802b2a`.

See also: `.context/devlog/0.9.5/warehouse-ddl-limitation.md` for full investigation.

---

## Item 4 — Configuration parameter documentation: uppercase keys

**Status:** FIXED (ANT-4 fix)

**Finding:** Four plugin `config.md` files referenced configuration keys in uppercase
(e.g. `PLUGINS.QUERY_HISTORY.SLOW_QUERIES_THRESHOLD`) instead of the lowercase format
required by the YAML config template and Snowflake configuration table.

**Affected files:**
- `src/dtagent/plugins/query_history.config/config.md`
- `src/dtagent/plugins/active_queries.config/config.md`
- `src/dtagent/plugins/dynamic_tables.config/config.md`
- `src/dtagent/plugins/snowpipes.config/config.md`

**Fix:** All config key references corrected to lowercase.

---

## Item 5 — include/exclude wildcard documentation: % not *

**Status:** FIXED (ANT-2 fix)

**Finding:** Plugin documentation for `query_history` include/exclude filters described
the wildcard character as `*` (glob-style), but the actual implementation uses SQL `LIKE`
wildcards: `%` for any sequence of characters and `_` for a single character.

**Fix:** Documentation updated to use `%` and `_` examples throughout. Users who had
configured `*` patterns would have seen no matches — this is a silent misconfiguration
risk.

---

## Item 6 — BDX-682 premium metering history status

**Status:** CLOSED — no gap in DSOA; org-level costs covered by `org_costs` plugin

**Investigation:**

The `metering` plugin sources from `SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY` and
excludes `WAREHOUSE_METERING` service type (handled by the `budgets` plugin via
`WAREHOUSE_METERING_HISTORY`). The SQL filter is:

```sql
where mh.SERVICE_TYPE != 'WAREHOUSE_METERING'
```

Live service types observed on the test-qa account:
`AUTO_CLUSTERING`, `COPY_FILES`, `PIPE`, `QUERY_ACCELERATION`, `SERVERLESS_TASK`,
`TELEMETRY_DATA_INGEST`, `TRUST_CENTER`, `WAREHOUSE_METERING`.

`PREMIUM_CREDIT_USAGE` is an account-tier feature not present on the test tenant.
It is not a gap in DSOA — the `metering` plugin will capture it automatically if
present on a customer account (no service type exclusion applies to it).

BDX-682 was about org-level costs. This is implemented via the `org_costs` plugin
(shipped in 0.9.5), which sources from `SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY`
and covers org-level credit consumption, storage, data transfer, billing amounts, and
remaining contract balances. The `org_costs` plugin is disabled by default and requires
ORGADMIN.

**Conclusion:** No code change needed. BDX-682 is addressed by the `org_costs` plugin.

---

## Item 7 — Review `plugins.*` fields added — sounds off

**Status:** CLOSED — no telemetry leak; config dict is internal only

**Investigation:**

`config.py` line 164 stores plugin config under `self._config["plugins"]`:

```python
"plugins": __unpack_prefixed_keys(config_dict, "plugins."),
```

This dict is accessed **only** via `Configuration.get(plugin_name=..., key=...)` inside
plugin Python code. The `get()` method returns individual scalar values to plugin logic
(e.g. `self._configuration.get("max_entries", plugin_name="query_history")`).

Verification:
- `grep -rn '"plugins\.' src/dtagent/otel/ src/dtagent/agent.py src/dtagent/connector.py`
  → **0 results** — no `plugins.*` string literals in telemetry emitters
- `grep -rn '_config\["plugins"\]' src/dtagent/` (excluding config.py)
  → **0 results** — raw config dict never accessed outside config.py
- `otel/logs.py` builds payloads from SQL row data, not from the config dict

**Conclusion:** `plugins.*` config values are internal configuration only. They are
never passed to any telemetry exporter as attributes. No code change needed.

---

## Item 8 — README.md check

**Status:** CLOSED — no changes needed

README.md does not reference the specific workflow or plugin behaviours that were fixed.
The workflow descriptions in `docs/workflows/*/readme.md` were updated as part of items
2 and 3 above.

---

## Item 9 — CHANGELOG + devlog + README updates

**Status:** DONE (this file + CHANGELOG.md updates)

Changes made:
- `docs/CHANGELOG.md`: added Fixed entries for BUG-E2.5a, BUG-E2.5b, warehouse-ddl
  finding, config docs casing; added Clarified section for include/exclude wildcards;
  verified `org_costs` plugin (BDX-682) already present under Added.
- `.context/devlog/0.9.5/qa-followup-2026-05-25.md`: this file.
- `test/qa/results/ai-memory/session-ses_1c0b.md`: appended item 6/7 verification results.
- `test/qa/results/ANT-1-2026-05-25-final-handoff.md`: created final handoff document.
