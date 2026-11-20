# `heartbeat` plugin

Proposal: `.context/proposals/heartbeat-plugin.md`.

## Scope

- New plugin `heartbeat` (context `heartbeat`), task `TASK_DTAGENT_HEARTBEAT`, default `USING CRON 0 6 * * * UTC`, `window_hours: 24`.
- `APP.F_HEARTBEAT_INSTRUMENTED()` joins three sources, one row per task:
  - configuration: `CONFIG.CONFIGURATIONS` (`plugins.<p>.schedule[_<aux>]`, enabled rule copied from `UPDATE_PLUGIN_SCHEDULE`),
  - deployed: `SHOW TASKS IN SCHEMA DTAGENT_DB.APP` read through `RESULT_SCAN`,
  - runs: `DTAGENT_DB.INFORMATION_SCHEMA.TASK_HISTORY()` with `RESULT_LIMIT => 10000`.
- `expected_runs` is computed in Python (`_expected_runs` in `heartbeat.py`) with `croniter`; the `USING CRON` prefix and the time zone are stripped and the time zone is applied to the window instead. Interval schedules (`<n> MINUTE[S]`, also second/hour/day) use plain arithmetic; `AFTER ...` and unparsable schedules give `schedule_supported = false` and no `expected_runs`.
- Window arithmetic is done in UTC (real elapsed time) so that hourly schedules yield 24 on DST days.

## Decisions

- **Multitenancy**: task names have no TAG, and `TASK_HISTORY()` spans databases, so history is filtered on `DATABASE_NAME`/`SCHEMA_NAME` in addition to the task name. `DTAGENT_DB` is written literally so that the deploy script rewrites it for tagged/custom database names. `db.namespace` is a row dimension; `deployment.environment(.name|.tag)` come from the agent's resource attributes.
- `deployment.environment` is not emitted from the SQL: the agent attaches it (and `.name`, `.tag`) to every log and metric, and no other plugin repeats it. An SQL dimension was added first and removed because it broke core ownership of that dimension in `test_matching_documentation`.
- Mid-window suspend/resume is flagged, not corrected for (`expected_runs` always spans the whole window).
- Coverage ratio is not stored; DQL derives it from `runs.succeeded` and `expected_runs`.

## Related change

`_report_execution` (self-monitoring log) now emits `dsoa.run.first_timestamp` (`Plugin.processed_min_timestamp`, tracked per `_process_and_report` execution) and `dsoa.run.last_timestamp` (skipped for snowpark `Column` values such as `current_timestamp()`). Both are in the ignored dynamic fields of `test/_mocks/telemetry.py`.

## Dependencies

`croniter` added to `requirements.txt`, the `DTAGENT` procedure packages (`700_dtagent.sql`) and the compiled import list in `src/dtagent/__init__.py`.

## Open / not done

- The fixture-based plugin test needs fixtures captured from live Snowflake (`-p`); until then `test_documentation` reports the `dsoa.heartbeat.*` fields as not seen in telemetry.
- To verify on `test-qa`: `result_scan(:QID)` with a bind variable, `DTAGENT_VIEWER` access to `SHOW TASKS`/`TASK_HISTORY()`.
- `tasks` plugin `V_TASK_HISTORY` has the same cross-database exposure and is not filtered; separate fix.
- Follow-ups: dashboard tile and an absence alert workflow for the heartbeat.
