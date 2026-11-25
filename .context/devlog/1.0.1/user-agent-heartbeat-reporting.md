# Heartbeat summary reported through the User-Agent

## Why

Dynatrace routes the `User-Agent` of ingest requests to the DSOA self-monitoring tenant, regardless of the customer tenant the data goes to.
The tenant needs, per instance and signal, expected vs delivered records, and expected vs successful task runs. Port of the dynamic User-Agent
from the `snowagent-sk` fork plus heartbeat integration. Proposal: `.context/proposals/user-agent-heartbeat-reporting.md`.

## First attempt and why it was replaced

The first version put the whole summary (up to 512 characters, a guess) in a class-level User-Agent state while a log line was flushed. The real
limit turned out to be much lower (see below): the requests carrying the long header were rejected, and because the state was shared with the
asynchronous log exporter, the heartbeat's own log batches were rejected with them - no heartbeat entry reached the tenant.

## Second correction: the limit is 64

With a 128 cap the first reports arrived on the self-monitoring tenant cut at exactly 64 characters (`...;ok=613;f`, `...;dlv=818`). The limit
cannot be raised, so: `MAX_USER_AGENT_LENGTH` = 64; a report (`build_user_agent(..., report=True)`) has no `plugin` segment (`hb` says what it
is) and the environment is cut to `MAX_REPORT_ENVIRONMENT_LENGTH` = 16; `win`, `to` and `for` were dropped - the report's arrival time is its
period end, and deltas sum correctly even when a heartbeat is missed. Worst case that fits: five-digit task counts, eight-digit signal counts;
a longer segment is dropped whole.

## Per-task completion

`hb=t` only gave totals over all tasks. `tk=<task>;exp=<n>;ok=<n>` is reported per task (name without `TASK_DTAGENT_`, lower case), so the
tenant can tell which task missed its runs. Names reach 23 characters (`table_health_clustering`), which together with a 16 character
environment does not fit next to the counts, so `build_user_agent(..., shrink_key="tk")` shortens that one value to what is left after the other
segments (and drops it if nothing is left); the counts are never dropped for a name. Tasks with no expected and no actual runs are skipped;
`exp` is omitted when the schedule is not supported (an unknown number must not look like 0). Costs one request per task (about 25): sending
stops at the first report that cannot be sent (connection error / timeout), so a dead endpoint does not hold the heartbeat for 25 timeouts.
A response with any status counts as sent: the empty body is answered with 400, yet the User-Agent is routed. (Earlier the loop stopped at the
first non-202, so with the empty body only `hb=t`, the first report, ever arrived.) `hb=t` stays (it also has `fail`).

## What

- `otel/otel_manager.py`: `_sanitize_ua_segment` (also strips `;`), class state `_run_environment` / `_current_plugin` only,
  `build_user_agent(segments)` (hard `MAX_USER_AGENT_LENGTH` = 64; priority: version, plugin, env (truncated), segments in order, a segment that
  does not fit is dropped), `get_dsoa_headers(segments)` (never raises), `send_user_agent_report()` (dedicated `requests.post` of the
  payload `USER_AGENT_REPORT_PAYLOAD` (empty on purpose); not counted in export stats or the failure counter; never raises), `SessionUserAgentMixin`.
- logs / spans exporters call `refresh_user_agent()` at the start of `export()` (headers were set once in `__init__`).
- `agent.py` / `connector.py` set the current plugin next to `ExportStatsCollector.set_plugin`; `DynatraceSnowAgent._set_max_consecutive_fails`
  also sets the environment.
- `plugins/heartbeat.py`: rows are aggregated while streamed; `_build_user_agent_reports` makes self-contained reports (`hb=t` for tasks, one
  per signal for exports; only `exp` / `ok` / `fail` / `dlv`) and `_report_via_user_agent` sends one request per report, after reading both contexts and before marking the export
  statistics as reported. Opt-out: `plugins.heartbeat.report_via_user_agent` (default true). Needs no logs.
- Hybrid semantics: export counts = unreported delta (`to`, `for`); task counts = window totals (`win`).

## Known issues / open points

- The carrier is an empty POST to the metrics endpoint: it answers 400 and leaves no data on the customer tenant, while the User-Agent of the
  rejected request is still routed (seen on the self-monitoring side). Switching means changing `USER_AGENT_REPORT_PAYLOAD` and the URL.
- Whether the self-monitoring tenant stores one record per request, and whether `env` alone identifies an instance, is unverified.
- `test_instruments_def_schema[_core]` fails on this branch independently of this change (`attributes.anomaly.subject.__type`).
