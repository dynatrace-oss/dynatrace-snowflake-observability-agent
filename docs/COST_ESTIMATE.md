# How to read the DSOA cost estimate

`dsoa-cost-estimate.sql` (see [INSTALL.md](INSTALL.md#estimate-dsoa-cost-before-you-install)) returns one result table.
Rows are grouped by the `SECTION` column and listed in section order. This page explains each section and column.

> **It is an estimate.** Volumes are modelled from the object counts and workload measured on your account,
> using the shipped plugin defaults. Use it to find the order of magnitude and the main cost drivers, not as an invoice.

## Required permissions

The script is read-only and needs no privileges other than reading views. Run it in a Snowsight worksheet with
`ACCOUNTADMIN`, or with any role that can read the `SNOWFLAKE` database. The simplest grant, run by an account admin, is:

```sql
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <role>;
```

**Required.** Before measuring anything, the script checks that it can read each of these views:

- `SNOWFLAKE.ACCOUNT_USAGE.TABLES`
- `SNOWFLAKE.ACCOUNT_USAGE.PIPES`
- `SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY`
- `SNOWFLAKE.ACCOUNT_USAGE.USERS`
- `SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_SHARES`
- `SNOWFLAKE.ACCOUNT_USAGE.DATABASES`
- `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY`
- `SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY`
- `SNOWFLAKE.ACCOUNT_USAGE.SESSIONS`
- `SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY`
- `SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY`

If any of them is unreadable, the script stops and returns a single row instead of the report:

| STATUS | MESSAGE |
|---|---|
| `MISSING PERMISSIONS` | Names the current role, the views it cannot read, and the `GRANT` above. Fix the grant (or switch role) and re-run |

A role such as `PUBLIC` typically fails on every view, with the error `Schema 'SNOWFLAKE.ACCOUNT_USAGE' does not exist or not authorized`.

**Optional.** These improve the estimate. When one cannot be read the script still runs: the input is shown as
`n/a, using default: <reason>` in section `2 INPUT` and the default below is used.

| Source | Used for |
|---|---|
| `SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS` | resource monitor count (default: 1) |
| `SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY` | dynamic table refreshes per day (default: 0) |
| `SNOWFLAKE.TRUST_CENTER.FINDINGS` | Trust Center findings (default: 0) |
| `SNOWFLAKE.TELEMETRY.EVENTS` | event table log, span and metric rows per day (default: 0). **Without it the `event_log` estimate is understated** (see below) |
| `SNOWFLAKE.ORGANIZATION_USAGE.USAGE_IN_CURRENCY_DAILY` | whether this is an organization account (default: no, `org_costs` shows n/a) |
| `DTAGENT_DB.STATUS.PROCESSED_MEASUREMENTS_LOG` | actual vs estimate, only when DSOA is installed |

**When an optional source is unreadable, the estimate for the plugins that depend on it is too low**, because its input
falls back to a default (mostly 0). Those plugins are marked in section `3 PLUGIN`, for example
`on by default - ESTIMATE INCOMPLETE, input n/a: log_rows_day metric_rows_day span_rows_day`. In particular the `event_log`
plugin is driven by the event table rows, which is usually one of the largest sources of DSOA volume, so fix that
grant before relying on the total.

`SNOWFLAKE.TELEMETRY.EVENTS` is the default account event table. It is not readable through `IMPORTED PRIVILEGES`; it
needs the `EVENTS_VIEWER` (or `EVENTS_ADMIN`) application role, for example
`GRANT APPLICATION ROLE SNOWFLAKE.EVENTS_VIEWER TO ROLE <role>;`. If your account uses a custom event table
(`ALTER ACCOUNT SET EVENT_TABLE`), the script does not read it and the input stays `n/a`.

Access to `SNOWFLAKE.TRUST_CENTER.FINDINGS` and `SNOWFLAKE.ORGANIZATION_USAGE` can need extra grants beyond
`IMPORTED PRIVILEGES` (for example the `TRUST_CENTER_VIEWER` application role, or the organization account).

## Columns

| Column | Meaning |
|---|---|
| `SECTION` | Which part of the report the row belongs to (see below) |
| `ITEM` | Plugin name, measured input, or total label |
| `SIGNAL` | `logs`, `metrics`, `events`, `spans` or `bizevents` (only on per-signal rows) |
| `NOTE` | Status or explanation: plugin on/off by default, `n/a` reasons, how a value was derived |
| `VALUE` | A single number for rows that have no other column fitting (measured inputs, resource monitor quota, actual values) |
| `RECORDS_DAY` | Records sent to Dynatrace per day. For `metrics` this is **data points** |
| `DT_GIB_INGESTED_DAY` | GiB ingested into Dynatrace per day |
| `DT_GIB_RETAINED_STEADY` | GiB kept in Grail once retention is full (ingest per day × retention days, 365 by default) |
| `DT_USD_MONTH_1` | Dynatrace $ per month in the **first month**: ingest plus retention of the data collected so far (on average about 15 days) |
| `DT_USD_MONTH_STEADY` | Dynatrace $ per month at **steady state** (month 12 and later): ingest plus a full year of retention |
| `SF_CREDITS_DAY_ALLOCATED` | Snowflake credits per day for the plugin's share of the `DTAGENT_WH` awake time. Over all plugins it adds up to the total |
| `SF_CREDITS_DAY_STANDALONE` | Snowflake credits per day if **only this plugin** were enabled |
| `SF_CREDITS_MONTH_ALLOCATED` | `SF_CREDITS_DAY_ALLOCATED` × 30 |

Empty (`NULL`) means "not applicable for this row", not zero.

## Sections

### `0 TOTAL`
The first two rows are the answer most people need. They differ in **which plugins are counted**:

| Row | Plugins counted | Use it when |
|---|---|---|
| `all plugins (incl. off by default)` | every plugin that is not deprecated, **including** the ones that are off in the shipped config: `budgets`, `table_health` and, on an organization account, `org_costs`. `event_usage` is excluded as deprecated | you plan to switch on everything |
| `default install` | only the plugins that are enabled in the shipped config, i.e. what you get without changing any `is_disabled` setting | you install DSOA with the defaults |

`all plugins` is always greater than or equal to `default install`, for Dynatrace $ and for Snowflake credits. The Snowflake
credits of `default install` are calculated for that smaller set of schedules on its own (the warehouse is awake for
less time), so they are not simply the sum of the per-plugin rows. Its credits are in `SF_CREDITS_DAY_ALLOCATED`.

Per-plugin Dynatrace $ and allocated credits add up to the `all plugins` row.

### `1 HEADER`
The assumptions behind every number: the rate card with its "as of" date, retention (365 days), "DSOA defaults, all plugins
enabled, no config", and the disclaimers. The first row lists the prices in use. If they are not your contract prices,
change the `p_*` values at the top of the script and re-run (see [INSTALL.md](INSTALL.md#estimate-dsoa-cost-before-you-install)).

### `2 INPUT`
What the script measured on your account (7-day lookback, scaled to per day for workload).

- Object counts (tables, dynamic tables, pipes, warehouses, users, ...) are plain counts.
- Workload rows (`queries_day`, `logins_day`, `task_runs_day`, ...) are per day.
- `NOTE = measured` means the source was readable.
- `NOTE = n/a, using default: <reason>` means the source could not be read (usually a missing privilege or an unavailable
  view). A documented default was used instead, so **every number that depends on that input is less reliable**.
  Grant access and re-run to improve it.

### `3 PLUGIN`
One row per plugin, summed over its signals. `NOTE` shows the status:

- `on by default` - counted in both totals
- `off by default` - counted in "all plugins" only (`budgets`, `table_health`, `org_costs`)
- `deprecated, not counted` - `event_usage` (replaced by `metering`), shown so it does not double-count
- `n/a, requires org account` - `org_costs`: shows zero cost unless this is an organization account

Use `DT_USD_MONTH_STEADY` and `SF_CREDITS_DAY_ALLOCATED` to compare plugins.

### `4 PLUGIN SIGNAL`
The same Dynatrace numbers split by signal. Use it to see **what** drives a plugin's cost (for example metrics vs logs).
There are no Snowflake columns here: Snowflake cost is per plugin, not per signal.

Every run also adds a small fixed overhead per plugin: 2 `dsoa.task` bizevents, plus 1 log and 1 metric per context.

### `5 RESOURCE MONITOR`
A suggested daily `core.snowflake.resource_monitor.credit_quota` in `VALUE`: estimated credits per day × 1.4, rounded up.
One row for all plugins, one for a default install. Pick the row that matches what you will enable.

### `6 TOP COST DRIVER`
The three plugins with the highest `DT_USD_MONTH_STEADY`, most expensive first. `NOTE` says which signal
accounts for what share of that plugin's cost, which is the first thing to look at when you want to reduce cost.

### `7 ACTUAL VS ESTIMATE`
Only filled when DSOA is already installed; otherwise `NOTE` says `not installed`. Actuals are averaged over the days
that have data (the `NOTE` says how many), so a recent installation is not diluted by empty days.

| Row | `VALUE` (actual) | Estimate is in |
|---|---|---|
| `DTAGENT_WH credits/day` | average from `WAREHOUSE_METERING_HISTORY` | `SF_CREDITS_DAY_ALLOCATED` |
| `records/day logged in PROCESSED_MEASUREMENTS_LOG (logs, metrics, events, spans; no bizevents)` | average records DSOA reports sending | `RECORDS_DAY` (the estimate without bizevents) |

Compare the two to judge how well the model fits your account. The installed DSOA may be configured differently from the
defaults the estimate assumes, so a gap is a reason to look, not a proof that the model is wrong (see
[How accurate is the estimate](#how-accurate-is-the-estimate)).

## Worked example

The example below is the output of a real run on a busy Snowflake account (about 627,000 queries per day). Figures are
rounded. Follow it from the top: each block says what the rows mean and how the number was calculated, so you can repeat
the arithmetic on your own output.

> The Snowflake credit figures in this example come from the first version of the model, which estimated 12.0 credits per
> day. The current script estimates about 9.8 for the same schedules (see [How accurate is the estimate](#how-accurate-is-the-estimate)).
> The Dynatrace figures are unchanged.

### 0 TOTAL - the answer

| ITEM | RECORDS_DAY | DT_GIB_INGESTED_DAY | DT_GIB_RETAINED_STEADY | DT_USD_MONTH_1 | DT_USD_MONTH_STEADY | SF_CREDITS_DAY_ALLOCATED | SF_CREDITS_MONTH_ALLOCATED |
|---|---|---|---|---|---|---|---|
| all plugins (incl. off by default) | 25,616,084 | 23.44 | 8,556 | 1,138 | 1,311 | 12.0 | 361 |
| default install | 25,615,285 | 23.44 | 8,556 | 1,138 | 1,311 | 12.0 | 360 |

How to read it:

- **25.6 million records per day** go to Dynatrace. Metrics count data points, the other signals count log lines,
  spans, events and bizevents.
- **23.4 GiB per day** is the payload size of those records. Data stays for 365 days, so the amount kept at steady state is
  23.44 x 365 = **8,556 GiB** (`DT_GIB_RETAINED_STEADY`).
- **$1,138 in the first month, $1,311 per month from month 12.** Ingest costs the same every month. Retention grows
  until a year of data is stored, so the first month is cheaper.
- **12.0 credits per day, 361 per month** is the Snowflake cost of `DTAGENT_WH`. Credits are not converted to money,
  because the price per credit depends on your contract.
- The two rows are almost equal here because the extra plugins of "all plugins" (`budgets`, `table_health`) are tiny on
  this account. See [section `0 TOTAL`](#0-total) for the difference.

### 2 INPUT - what was measured

| ITEM | VALUE | NOTE |
|---|---|---|
| queries_day | 627,110 | measured |
| logins_day | 213,567 | measured |
| ddl_day | 101,888 | measured |
| tables_in_scope | 69 | measured |
| warehouses | 47 | measured |
| trust_center_findings | 3,242 | measured |
| log_rows_day, span_rows_day, metric_rows_day | empty | `n/a, no data returned, using default` |

How to read it: these are the inputs of the model. Objects (tables, warehouses, ...) are counts, workload (queries,
logins, ...) is per day, averaged over the last 7 days. Every `n/a` row means the matching plugin is underestimated,
here `event_log` (see "3 PLUGIN"). Fix the access or accept the gap.

### 3 PLUGIN - one row per plugin (top rows)

| ITEM | NOTE | RECORDS_DAY | DT_GIB_INGESTED_DAY | DT_USD_MONTH_STEADY | SF_CREDITS_DAY_ALLOCATED | SF_CREDITS_DAY_STANDALONE |
|---|---|---|---|---|---|---|
| query_history | on by default | 24,457,465 | 22.45 | 1,278.90 | 0.98 | 2.00 |
| active_queries | on by default | 439,937 | 0.44 | 19.38 | 2.95 | 6.00 |
| login_history | on by default | 429,739 | 0.31 | 4.27 | 0.59 | 1.20 |
| snowpipes | on by default | 67,226 | 0.04 | 2.88 | 3.54 | 7.20 |
| event_log | on by default | 96 | 0.0001 | 0 | 0.98 | 2.00 |
| budgets | off by default | 8 | 0 | 0 | 0.01 | 0.03 |
| org_costs | off by default, n/a, requires org account | 416 | 0.0002 | 0.01 | 0.05 | 0.10 |

How to read it:

- **`query_history` is 98% of the Dynatrace cost** ($1,279 of $1,311). Its volume follows the number of queries:
  627,110 queries x (1 log + 1 span + 37 metric data points) = 24.46 million records, plus a small fixed amount per run.
  If you need to cut cost on a busy account, this is the plugin to look at first (include/exclude lists, `max_entries`).
- **Allocated vs standalone credits.** `SF_CREDITS_DAY_STANDALONE` is what the plugin would cost if it were the only one
  enabled. All plugins share one warehouse that is awake for the union of their schedules, so the standalone values add up to
  more than the real total (24.5 vs 12.0 here). `SF_CREDITS_DAY_ALLOCATED` splits the real total in proportion to each
  plugin's standalone cost, so the allocated values add up to the total.
- **Snowflake credits do not depend on how big the plugin's data is.** They come from the schedule and a typical run
  duration, not from your workload (see "How accurate is the estimate").
- **`event_log` shows 96 records**, which is only the fixed per-run overhead (2 bizevents for each of the 48 daily runs). Its real volume comes from the
  event table rows, which could not be read, so this row is **too low**.
- **`org_costs`** is `n/a, requires org account`: shown for completeness, with negligible values. It is only counted on
  an organization account.

### 4 PLUGIN SIGNAL - what a plugin's cost is made of (`query_history`)

| SIGNAL | RECORDS_DAY | DT_GIB_INGESTED_DAY | DT_GIB_RETAINED_STEADY | DT_USD_MONTH_1 | DT_USD_MONTH_STEADY |
|---|---|---|---|---|---|
| logs | 627,158 | 6.35 | 2,316 | 40.07 | 86.71 |
| spans | 627,110 | 4.10 | 1,497 | 25.90 | 56.04 |
| metrics | 23,203,102 | 12.00 | 4,382 | 1,047.92 | 1,136.15 |
| bizevents | 96 | 0.0001 | 0.02 | 0 | 0 |

How the dollars are calculated (the rate card is in the header, section `1 HEADER`):

- **logs**: ingest 6.35 GiB x 30 days x $0.20 = $38.1, retention 2,316 GiB x $0.0007 x 30 = $48.6, together **$86.7**.
- **metrics**: ingest is billed per data point, 23,203,102 x 30 / 100,000 x $0.15 = $1,044.1. Retention is
  4,382 GiB x $0.0007 x 30 = $92.0. Together **$1,136.2**. The GiB columns for metrics are only used for retention.
- **month 1** uses the same ingest cost but an average of 15 days of retained data instead of 365.
- Metrics are 89% of this plugin's cost: many data points per query, even though each is small. Section `6 TOP COST DRIVER` points
  to this.

### 5 RESOURCE MONITOR

`core.snowflake.resource_monitor.credit_quota` = **17**. This is 12.033 estimated credits per day x 1.4, rounded up. Set it
as the daily quota of the DSOA resource monitor so the monitor does not stop DSOA in normal operation.

### 6 TOP COST DRIVER

The three most expensive plugins at steady state, each with the signal that causes most of the cost (for example
`query_history` - "89% from metrics"). This tells you where to start when you want to reduce cost.

### 7 ACTUAL VS ESTIMATE

| ITEM | NOTE | VALUE (actual) | estimate |
|---|---|---|---|
| DTAGENT_WH credits/day | actual: measured, average over N day(s) with data | 4.35 | 12.03 (`SF_CREDITS_DAY_ALLOCATED`) |
| records/day logged in PROCESSED_MEASUREMENTS_LOG | actual: measured, average over N day(s) with data | 108,819 | 25,616,084 (`RECORDS_DAY`) |

How to read it: the first column is what DSOA really did on this account, the last one what the model expected. A big gap
does not necessarily mean the model is wrong: the installed DSOA may use other plugins, schedules or filters than the
defaults, or may have been running for only part of the period. See the next section.

## How accurate is the estimate

The estimate is a model with fixed assumptions, not a measurement of your future bill. This section records what
we learned when the script was first compared with two real accounts on 2026-11-02 (one with about 68,000 queries per day
and one with about 627,000).

| | Account 1 (68k queries/day) | Account 2 (627k queries/day) |
|---|---|---|
| Estimated records/day, all signals | 8.0 million | 25.6 million |
| Estimated Dynatrace $/month, steady state | 362 | 1,311 |
| Estimated Snowflake credits/day (first version) | 12.0 | 12.0 |
| **Actual** DTAGENT_WH credits/day | **2.4** | **4.4** |
| **Actual** records/day in PROCESSED_MEASUREMENTS_LOG | not readable | **109 thousand** |

What this shows:

1. **Dynatrace volume follows the workload, as intended.** The busy account is estimated at 3.2x the records of the small
   one, and `query_history` and the metrics it produces explain almost all of it.
2. **The records gap is explained by the installed plugins.** The self-monitoring data of both accounts shows that neither
   runs `query_history`, `active_queries`, `login_history` or `event_log`. The estimate counted all of them, and
   `query_history` alone is 24.5 of the 25.6 million records. Restricted to the plugins that really run (`data_schemas`,
   `data_volume`, `metering`, `snowpipes`, `tasks`, `trust_center`, `users`, `warehouse_usage`), the busy account is
   estimated at about 202 thousand records/day against 109 thousand logged, so the model is about 1.9x too high there.
   The record check says nothing about the 37 metric data points per query, because no account in the sample runs
   `query_history`.
3. **Snowflake credits: calibrated on measured run times.** The first version used placeholder run times and gave
   12.0 credits/day for every account. Three things changed:
   - The 5-minute Snowpipes task runs on cloud services only and does not keep the warehouse awake, so it is no
     longer counted.
   - The run times are the median of measured runs from 7 deployments (`run_duration_seconds` in `cost_model.yml`).
   - A fixed 50 seconds of warehouse time per run (`run_overhead_seconds`) is added on top. The measured run time is the
     time between the first and last self-monitoring event of a run, so it leaves out task start, warehouse resume
     and final bookkeeping. The value was fitted on the four observations below; it is a fit, not a measured quantity.

   | Observation | Plugins | Estimated credits/day | Actual credits/day |
   |---|---|---|---|
   | Account 1 | 9 | 2.0 | 2.4 |
   | Account 2 (627k queries/day) | 8 | 4.5 | 4.4 |
   | DEV, before the extra plugins were on | 9 | 2.3 | 2.2 to 2.5 |
   | DEV, 2 days with 16 plugins (353k queries/day) | 16 | 11.1 | 10.0 and 12.1 |

   Each estimate uses that account's own measured run times and the plugins it really runs, with the 50 s overhead.
   Without the overhead the estimates were 1.3, 3.8, 1.6 and 7.8, that is 20 to 45% below the actuals. DEV's two
   high days (28 and 29 October) include the first runs of the new plugins, which may be larger than later ones, and the
   daily credits fell back to about 2.3 afterwards, which suggests the extra plugins were switched off again
   (not confirmed), so the actual is not a steady-state value. A default installation
   with all plugins on, using the median run times, is estimated at 9.8 credits/day, mostly `query_history`
   (145 s per run), `active_queries` (every 6 minutes) and `snowpipes`.
4. **Run times depend on account size.** Between the 7 deployments the average run time of the same plugin differs by up
   to 20x (for example `data_schemas` 13 to 420 s, `snowpipes` 29 to 400 s, `data_volume` 12 to 147 s). The busy account is
   at the top of that range, so the median used as the default underestimates credits for accounts with many
   objects, and overestimates them for small ones. The model has no per-object run time yet.
5. **Inputs that could not be read bias the result.** In Account 1 the event table could not be read, so `event_log` was
   estimated near zero, and the plugin row said `ESTIMATE INCOMPLETE`. In Account 2 the same inputs came back empty but
   were reported as measured, which hid the gap. The script now shows `n/a, no data returned, using default` in this case.

How to use the estimate today:

- Use the **Dynatrace $ and the ranking of plugins** to understand where the cost comes from. The metrics-per-query factor
  is the main uncertainty for the total, and it has not been checked against a real `query_history` deployment.
- Treat **Snowflake credits** as a typical value for a default installation, not as a bound. Expect more on accounts
  with thousands of tables, warehouses or pipes, and less on small ones.
- Compare **actual vs estimate** (section 7) on your own account after installing, once every plugin has run for at least a few days (the actual is an average over all days with data, so a recent install understates it), and tune the plugins that drive
  the cost, or tell us the deviation so the model can be calibrated.

## What is not included

- **Dynatrace query cost** (dashboards, notebooks, workflows, ad-hoc DQL). It depends on how the data is used.
- Snowflake **event table ingest** and **cloud services** above the 10% adjustment. Only `DTAGENT_WH` credits are shown.
- Non-default configuration: other schedules, scopes, `max_entries`, include/exclude lists, multiple tenants.
- Snowflake $: costs are in **credits**, because the price per credit depends on your edition, region and contract.

## Common questions

- **Why is `DT_USD_MONTH_1` lower than `DT_USD_MONTH_STEADY`?** Retention cost grows until a full year of data is stored.
- **Why do allocated credits differ from standalone?** Plugins share one warehouse that is awake for the union of their
  schedules. Standalone shows each plugin alone, so the standalone values add up to more than the real total.
- **Why does a plugin show 0?** Its driver is 0 on your account (for example no pipes for `snowpipes`) or its input was
  `n/a`. Check section `2 INPUT`.
- **Metrics look small in GiB but cost a lot.** Metrics are priced per 100k data points, not per GiB.
