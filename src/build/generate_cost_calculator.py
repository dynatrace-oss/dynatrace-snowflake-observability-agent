"""Generates build/dsoa-cost-estimate.sql - the read-only, pre-install DSOA cost estimate script (BIZOBS-3285).

Inputs: plugin *-config.yml, instruments-def.yml, test fixtures (bytes per record), cost_model.yml
(rate card, run durations, per-plugin model). Fails when the model no longer matches the plugin definitions.
"""

#
#
# Copyright (c) 2025 Dynatrace Open Source
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#

import json
import os
import sys
from typing import Any, Dict, List, Optional, Set

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLUGINS_DIR = os.path.join(ROOT, "src", "dtagent", "plugins")
FIXTURES_DIR = os.path.join(ROOT, "test", "test_results")
MODEL_FILE = os.path.join(os.path.dirname(__file__), "cost_model.yml")
OUTPUT_FILE = os.path.join(ROOT, "build", "dsoa-cost-estimate.sql")
# Committed copy, so the script can be downloaded from the repository without building. Not a build input: build.sh only
# reads the named src/dtagent.sql sub-directories (init, setup, ...), never this one.
REPO_COPY = os.path.join(ROOT, "src", "dtagent.sql", "estimate-cost", "dsoa-cost-estimate.sql")

SIGNALS = ("logs", "metrics", "events", "spans", "bizevents")
LOOKBACK_DAYS = 7
GIB = 1073741824
SECONDS_PER_DAY = 86400
MONTH_DAYS = 30

# signal -> fixture file
FIXTURE_FILES = {"logs": "logs.json", "events": "events.json", "spans": "spans.json", "bizevents": "biz_events.json"}

# Rate card variables: SQL variable name -> (model key, description)
RATE_VARS = {
    "p_logs_gib": ("logs_ingest_per_gib", "Logs: ingest & process, per GiB"),
    "p_spans_gib": ("spans_ingest_per_gib", "Traces/spans: ingest & process, per GiB"),
    "p_events_gib": ("events_ingest_per_gib", "Events: ingest & process, per GiB"),
    "p_bizevents_gib": ("bizevents_ingest_per_gib", "Business events: ingest & process, per GiB"),
    "p_metrics_100k": ("metrics_ingest_per_100k_datapoints", "Metrics: ingest & process, per 100k data points"),
    "p_retain_gib_day": ("retain_per_gib_day", "Retain, per GiB per day (all signals)"),
}

# Measurements of the account (7-day lookback). Each entry measures one or more drivers in a single query.
# All sources are read-only views of the SNOWFLAKE database.
_AU = "SNOWFLAKE.ACCOUNT_USAGE"
_TBL_SCOPE = "TABLE_SCHEMA <> 'INFORMATION_SCHEMA' AND TABLE_NAME NOT LIKE 'TMP!_%' ESCAPE '!'"
# Sources the script cannot work without: checked first, the script stops with a short message when any is unreadable.
REQUIRED_SOURCES = [
    f"{_AU}.{view}"
    for view in (
        "TABLES", "PIPES", "WAREHOUSE_METERING_HISTORY", "USERS", "GRANTS_TO_SHARES", "DATABASES",
        "QUERY_HISTORY", "LOGIN_HISTORY", "SESSIONS", "TASK_HISTORY", "COPY_HISTORY",
    )
]
# Sources that improve the estimate; when unreadable the script shows "n/a" with the reason and uses a default.
OPTIONAL_SOURCES = [
    f"{_AU}.RESOURCE_MONITORS",
    f"{_AU}.DYNAMIC_TABLE_REFRESH_HISTORY",
    "SNOWFLAKE.TRUST_CENTER.FINDINGS",
    "SNOWFLAKE.TELEMETRY.EVENTS",
    "SNOWFLAKE.ORGANIZATION_USAGE.USAGE_IN_CURRENCY_DAILY",
    "DTAGENT_DB.STATUS.PROCESSED_MEASUREMENTS_LOG",
]
MEASUREMENTS: List[Dict[str, Any]] = [
    {
        "drivers": ["tables_in_scope"],
        "sql": f"SELECT COUNT(*) FROM {_AU}.TABLES WHERE DELETED IS NULL AND {_TBL_SCOPE} "
        "AND (TABLE_CATALOG = 'DTAGENT_DB' OR TABLE_SCHEMA = 'PUBLIC')",
    },
    {
        "drivers": ["dynamic_tables"],
        "sql": f"SELECT COUNT(*) FROM {_AU}.TABLES WHERE DELETED IS NULL AND IS_DYNAMIC = 'YES' AND TABLE_CATALOG <> 'DTAGENT_DB'",
    },
    {"drivers": ["pipes"], "sql": f"SELECT COUNT(*) FROM {_AU}.PIPES WHERE DELETED IS NULL AND PIPE_CATALOG <> 'DTAGENT_DB'"},
    {
        "drivers": ["warehouses"],
        "sql": f"SELECT COUNT(DISTINCT WAREHOUSE_NAME) FROM {_AU}.WAREHOUSE_METERING_HISTORY "
        f"WHERE START_TIME >= DATEADD(day, -{LOOKBACK_DAYS}, CURRENT_TIMESTAMP()) AND WAREHOUSE_NAME <> 'DTAGENT_WH'",
    },
    {"drivers": ["resource_monitors"], "sql": f"SELECT COUNT(*) FROM {_AU}.RESOURCE_MONITORS"},
    {"drivers": ["users"], "sql": f"SELECT COUNT(*) FROM {_AU}.USERS WHERE DELETED_ON IS NULL"},
    {"drivers": ["share_grants_out"], "sql": f"SELECT COUNT(*) FROM {_AU}.GRANTS_TO_SHARES WHERE DELETED_ON IS NULL"},
    {
        "drivers": ["tables_in_shares"],
        "sql": f"SELECT COUNT(*) FROM {_AU}.TABLES WHERE DELETED IS NULL AND TABLE_CATALOG IN "
        f"(SELECT DATABASE_NAME FROM {_AU}.DATABASES WHERE TYPE = 'IMPORTED DATABASE' AND DELETED IS NULL)",
    },
    {"drivers": ["trust_center_findings"], "sql": "SELECT COUNT(*) FROM SNOWFLAKE.TRUST_CENTER.FINDINGS"},
    {
        "drivers": ["queries_day", "slow_queries_day", "ddl_day"],
        "sql": "SELECT COUNT(*) / {lb}, COUNT_IF(TOTAL_ELAPSED_TIME > 10000) / {lb}, "
        "COUNT_IF(REGEXP_LIKE(QUERY_TYPE, '^(CREATE|ALTER|DROP).*')) / {lb} "
        f"FROM {_AU}.QUERY_HISTORY WHERE START_TIME >= DATEADD(day, -{LOOKBACK_DAYS}, CURRENT_TIMESTAMP()) "
        "AND WAREHOUSE_NAME IS DISTINCT FROM 'DTAGENT_WH'",
    },
    {
        "drivers": ["log_rows_day", "span_rows_day", "metric_rows_day"],
        "sql": "SELECT COUNT_IF(RECORD_TYPE = 'LOG') / {lb}, COUNT_IF(RECORD_TYPE IN ('SPAN', 'SPAN_EVENT')) / {lb}, "
        "COUNT_IF(RECORD_TYPE = 'METRIC') / {lb} FROM SNOWFLAKE.TELEMETRY.EVENTS "
        f"WHERE TIMESTAMP >= DATEADD(day, -{LOOKBACK_DAYS}, CURRENT_TIMESTAMP())",
    },
    {
        "drivers": ["logins_day"],
        "sql": f"SELECT COUNT(*) / {{lb}} FROM {_AU}.LOGIN_HISTORY WHERE EVENT_TIMESTAMP >= DATEADD(day, -{LOOKBACK_DAYS}, CURRENT_TIMESTAMP())",
    },
    {
        "drivers": ["sessions_day"],
        "sql": f"SELECT COUNT(*) / {{lb}} FROM {_AU}.SESSIONS WHERE CREATED_ON >= DATEADD(day, -{LOOKBACK_DAYS}, CURRENT_TIMESTAMP())",
    },
    {
        "drivers": ["task_runs_day"],
        "sql": f"SELECT COUNT(*) / {{lb}} FROM {_AU}.TASK_HISTORY WHERE SCHEDULED_TIME >= DATEADD(day, -{LOOKBACK_DAYS}, CURRENT_TIMESTAMP())",
    },
    {
        "drivers": ["files_loaded_day"],
        "sql": f"SELECT COUNT(*) / {{lb}} FROM {_AU}.COPY_HISTORY WHERE LAST_LOAD_TIME >= DATEADD(day, -{LOOKBACK_DAYS}, CURRENT_TIMESTAMP())",
    },
    {
        "drivers": ["dt_refreshes_day"],
        "sql": f"SELECT COUNT(*) / {{lb}} FROM {_AU}.DYNAMIC_TABLE_REFRESH_HISTORY "
        f"WHERE REFRESH_START_TIME >= DATEADD(day, -{LOOKBACK_DAYS}, CURRENT_TIMESTAMP())",
    },
]


def _read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_model() -> Dict[str, Any]:
    """Loads the cost model (rate card, durations, per-plugin model)."""
    return _read_yaml(MODEL_FILE)


def load_plugin_config(plugin: str) -> Dict[str, Any]:
    """Returns the shipped default configuration of the given plugin."""
    path = os.path.join(PLUGINS_DIR, f"{plugin}.config", f"{plugin}-config.yml")
    return _read_yaml(path)["plugins"][plugin]


def count_metric_defs(plugin: str) -> int:
    """Returns the number of metrics defined in the plugin's instruments-def.yml."""
    path = os.path.join(PLUGINS_DIR, f"{plugin}.config", "instruments-def.yml")
    return len(_read_yaml(path).get("metrics") or {})


def discover_plugins() -> Set[str]:
    """Returns the names of all plugins shipped in src/dtagent/plugins."""
    return {name[: -len(".config")] for name in os.listdir(PLUGINS_DIR) if name.endswith(".config")}


def validate_model(model: Dict[str, Any]) -> List[str]:
    """Compares the model with the shipped plugin definitions.

    Returns:
        List[str]: human readable drift messages; empty when the model is up to date
    """
    problems: List[str] = []
    model_plugins = model["plugins"]
    for plugin in sorted(discover_plugins() - set(model_plugins)):
        problems.append(f"{plugin}: plugin has no entry in cost_model.yml")
    for plugin in sorted(set(model_plugins) - discover_plugins()):
        problems.append(f"{plugin}: cost_model.yml entry has no plugin")
    for plugin in sorted(discover_plugins() & set(model_plugins)):
        entry = model_plugins[plugin]
        config = load_plugin_config(plugin)
        if config.get("schedule") != entry["expected_schedule"]:
            problems.append(f"{plugin}: schedule is '{config.get('schedule')}', model expects '{entry['expected_schedule']}'")
        if (not config.get("is_disabled", False)) != entry["default_on"]:
            problems.append(f"{plugin}: default_on in the model does not match is_disabled in the plugin config")
        awake_key = entry.get("awake_schedule_key")
        if awake_key and config.get(awake_key) != entry["expected_awake_schedule"]:
            problems.append(
                f"{plugin}: '{awake_key}' is '{config.get(awake_key)}', model expects '{entry['expected_awake_schedule']}'"
            )
        metric_defs = count_metric_defs(plugin)
        if metric_defs != entry["expected_metric_defs"]:
            problems.append(f"{plugin}: instruments-def has {metric_defs} metrics, model expects {entry['expected_metric_defs']}")
        for key, expected in entry["expected_scope"].items():
            if config.get(key) != expected:
                problems.append(f"{plugin}: default '{key}' is {config.get(key)!r}, model expects {expected!r}")
        for context in entry["contexts"]:
            if context["driver"] not in model["drivers"]:
                problems.append(f"{plugin}/{context['name']}: unknown driver '{context['driver']}'")
        for fixture in entry["fixtures"]:
            if not os.path.isdir(os.path.join(FIXTURES_DIR, fixture)):
                problems.append(f"{plugin}: fixture '{fixture}' does not exist")
    return problems


def cron_run_minutes(schedule: str) -> List[int]:
    """Expands 'USING CRON m h * * * TZ' into the sorted minutes of the day (0-1439) at which the task runs."""
    fields = schedule.replace("USING CRON", "").split()
    minute, hour = fields[0], fields[1]
    if fields[2:5] != ["*", "*", "*"]:
        raise ValueError(f"Unsupported schedule (day/month/weekday must be '*'): {schedule}")

    def expand(field: str, upper: int) -> List[int]:
        if field == "*":
            return list(range(upper))
        if field.startswith("*/"):
            return list(range(0, upper, int(field[2:])))
        return [int(part) for part in field.split(",")]

    return sorted(h * 60 + m for h in expand(hour, 24) for m in expand(minute, 60))


def _fixture_stats(fixtures: List[str]) -> Dict[str, Optional[float]]:
    """Average bytes per record for each signal over the given fixtures; None when no fixture has the signal."""
    totals = {signal: [0, 0] for signal in SIGNALS}  # [bytes, records]
    for fixture in fixtures:
        base = os.path.join(FIXTURES_DIR, fixture)
        for signal, file_name in FIXTURE_FILES.items():
            path = os.path.join(base, file_name)
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as file:
                    for record in json.load(file):
                        totals[signal][0] += len(json.dumps(record, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
                        totals[signal][1] += 1
        path = os.path.join(base, "metrics.txt")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as file:
                for line in file:
                    if line.strip() and not line.startswith("#"):
                        totals["metrics"][0] += len(line.encode("utf-8"))
                        totals["metrics"][1] += 1
    return {signal: (b / n if n else None) for signal, (b, n) in totals.items()}


def bytes_per_record(model: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Bytes per record per plugin and signal; signals missing in a plugin's fixtures use the average over all fixtures."""
    all_fixtures = sorted(d for d in os.listdir(FIXTURES_DIR) if os.path.isdir(os.path.join(FIXTURES_DIR, d)))
    global_stats = _fixture_stats(all_fixtures)
    result: Dict[str, Dict[str, float]] = {}
    for plugin, entry in model["plugins"].items():
        stats = _fixture_stats(entry["fixtures"])
        result[plugin] = {signal: round(stats[signal] or global_stats[signal] or 0, 1) for signal in SIGNALS}
    return result


def awake_seconds(plugins: List[str], model: Dict[str, Any]) -> float:
    """Seconds per day DTAGENT_WH is awake when the given plugins run on their default schedules.

    A run keeps the warehouse busy for its duration plus a fixed overhead and the auto-suspend tail; overlapping intervals are merged.
    """
    durations = model["run_duration_seconds"]
    tail = model["snowflake"]["auto_suspend_seconds"] + model["snowflake"].get("run_overhead_seconds", 0)
    intervals = []
    for plugin in plugins:
        duration = durations.get(plugin, durations["default"])
        entry = model["plugins"][plugin]
        for minute in cron_run_minutes(entry.get("expected_awake_schedule", entry["expected_schedule"])):
            intervals.append((minute * 60, minute * 60 + duration + tail))
    awake = 0
    current_end = -1
    for start, end in sorted(intervals):
        start = max(start, current_end)
        if end > start:
            awake += end - start
            current_end = end
    return float(awake)


def snowflake_credits(model: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Credits/day per plugin (standalone and allocated) and totals, with and without org_costs, and for a default install."""
    per_hour = model["snowflake"]["credits_per_hour"]
    plugins = [p for p, e in model["plugins"].items() if not e.get("deprecated")]

    def scenario(selected: List[str]) -> Dict[str, Any]:
        standalone = {p: awake_seconds([p], model) / 3600 * per_hour for p in selected}
        total = awake_seconds(selected, model) / 3600 * per_hour
        weight = sum(standalone.values()) or 1.0
        return {"total": total, "standalone": standalone, "allocated": {p: total * s / weight for p, s in standalone.items()}}

    with_org = scenario(plugins)
    without_org = scenario([p for p in plugins if not model["plugins"][p].get("requires_org_account")])
    default_on = scenario([p for p in plugins if model["plugins"][p]["default_on"]])
    return {"with_org": with_org, "without_org": without_org, "default": default_on}


def _num(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def _rows_per_run(context: Dict[str, Any], runs: int) -> str:
    """SQL expression for the number of rows a context handles per run."""
    base = f":v_{context['driver']} * {_num(context['coefficient'])}"
    if context["mode"] == "snapshot":
        cap = context.get("max_rows")
        return f"LEAST({base}, {cap})" if cap else f"({base})"
    cap = context.get("max_per_run")
    per_run = f"({base} / {runs})"
    return f"LEAST({per_run}, {cap})" if cap else per_run


def records_expression(plugin: str, signal: str, model: Dict[str, Any]) -> Optional[str]:
    """SQL expression (records per day) for a plugin and signal, or None when the plugin emits none."""
    entry = model["plugins"][plugin]
    runs = len(cron_run_minutes(entry["expected_schedule"]))
    terms = []
    for context in entry["contexts"]:
        per_row = context["per_row"].get(signal, 0)
        if per_row:
            terms.append(f"{runs} * {_rows_per_run(context, runs)} * {_num(per_row)}")
        if signal in ("logs", "metrics"):
            terms.append(f"{runs}")  # per-run overhead: 1 log and 1 metric per context
    if signal == "bizevents" and entry["contexts"]:
        terms.append(f"{2 * runs}")  # dsoa.task STARTED/FINISHED
    if not terms:
        return None
    expression = " + ".join(terms)
    return f"({expression}) * :v_org" if entry.get("requires_org_account") else f"({expression})"


def _sql_str(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _declare_block(model: Dict[str, Any]) -> List[str]:
    lines = ["-- ===== RATE CARD (edit prices here, nothing else needs to change) ====="]
    card = model["rate_card"]
    lines.append(f"-- As of {card['as_of']}, {card['currency']}. Source: {card['source']}")
    lines.append("-- Contract prices: replace the values below. Retention is the number of days kept in Grail.")
    for var, (key, description) in RATE_VARS.items():
        lines.append(f"  {var} FLOAT DEFAULT {_num(card[key])}; -- {description}")
    lines.append(f"  p_retention_days FLOAT DEFAULT {card['retention_days']}; -- retention in days")
    lines.append("-- ===== MEASURED INPUTS (filled by the script, 7-day lookback scaled to per day) =====")
    for name, driver in model["drivers"].items():
        if name != "const":
            lines.append(f"  v_{name} FLOAT DEFAULT {driver['fallback']}; n_{name} VARCHAR DEFAULT 'measured'; -- {driver['description']}")
    lines.append("  v_const FLOAT DEFAULT 1;")
    lines.append("  v_org FLOAT DEFAULT 0; n_org VARCHAR DEFAULT 'measured'; -- 1 when this is an organization account")
    lines.append("  v_actual_credits FLOAT; v_actual_days FLOAT; n_actual_credits VARCHAR DEFAULT 'not installed';")
    lines.append("  v_actual_records FLOAT; v_actual_rec_days FLOAT; n_actual_records VARCHAR DEFAULT 'not installed';")
    lines.append("  v_probe FLOAT; v_role VARCHAR; v_failed FLOAT DEFAULT 0; v_missing VARCHAR DEFAULT ''; v_message VARCHAR;")
    lines.append("  res_denied RESULTSET;")
    lines.append("  res RESULTSET;")
    return lines


def _permission_check_blocks() -> List[str]:
    """Probes every required source first and returns a short message instead of the report when any is unreadable."""
    lines = ["  SELECT CURRENT_ROLE() INTO :v_role;"]
    for source in REQUIRED_SOURCES:
        lines += [
            "  BEGIN",
            f"    SELECT COUNT(*) INTO :v_probe FROM (SELECT 1 FROM {source} LIMIT 1);",
            "  EXCEPTION WHEN OTHER THEN",
            f"    v_failed := v_failed + 1; v_missing := v_missing || '{source}; ';",
            "  END;",
        ]
    lines += [
        "  IF (v_failed > 0) THEN",
        "    v_message := 'Cannot run the DSOA cost estimate: the current role ' || v_role || ' cannot read ' || v_failed || ' of "
        f"{len(REQUIRED_SOURCES)} required sources: ' || v_missing",
        "      || 'Run the script with a role that can read the SNOWFLAKE database (for example ACCOUNTADMIN), or ask an account admin to run: '",
        "      || 'GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE ' || v_role || ';';",
        "    res_denied := (SELECT 'MISSING PERMISSIONS' AS STATUS, :v_message AS MESSAGE);",
        "    RETURN TABLE(res_denied);",
        "  END IF;",
    ]
    return lines


def _measure_blocks(model: Dict[str, Any]) -> List[str]:
    lines = _permission_check_blocks()
    for item in MEASUREMENTS:
        names = item["drivers"]
        into = ", ".join(f":v_{n}" for n in names)
        sql = item["sql"].replace("{lb}", str(LOOKBACK_DAYS))
        lines += ["  BEGIN", f"    {sql.replace(' FROM', ' INTO ' + into + ' FROM', 1)};"]
        lines.append("  EXCEPTION WHEN OTHER THEN")
        for name in names:
            lines.append(f"    v_{name} := {model['drivers'][name]['fallback']}; n_{name} := 'n/a, using default: ' || SQLERRM;")
        lines.append("  END;")
        for name in names:
            lines.append(
                f"  IF (v_{name} IS NULL) THEN v_{name} := {model['drivers'][name]['fallback']}; "
                f"n_{name} := 'n/a, no data returned, using default'; END IF;"
            )
    lines += [
        "  BEGIN",
        "    SELECT COUNT(*) INTO :v_org FROM (SELECT 1 FROM SNOWFLAKE.ORGANIZATION_USAGE.USAGE_IN_CURRENCY_DAILY LIMIT 1);",
        "    v_org := 1;",
        "  EXCEPTION WHEN OTHER THEN",
        "    v_org := 0; n_org := 'n/a, requires an organization account: ' || SQLERRM;",
        "  END;",
        "  BEGIN -- actual vs estimate, only when DSOA is already installed; averaged over the days that have data",
        "    SELECT SUM(CREDITS_USED), COUNT(DISTINCT TO_DATE(START_TIME)) INTO :v_actual_credits, :v_actual_days",
        "      FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY",
        f"      WHERE WAREHOUSE_NAME = 'DTAGENT_WH' AND START_TIME >= DATEADD(day, -{LOOKBACK_DAYS}, CURRENT_TIMESTAMP());",
        "    IF (v_actual_days > 0) THEN",
        "      v_actual_credits := v_actual_credits / v_actual_days;",
        "      n_actual_credits := 'measured, average over ' || v_actual_days || ' day(s) with data';",
        "    ELSE",
        "      v_actual_credits := NULL; n_actual_credits := 'not installed';",
        "    END IF;",
        "  EXCEPTION WHEN OTHER THEN",
        "    n_actual_credits := 'n/a: ' || SQLERRM;",
        "  END;",
        "  BEGIN",
        "    SELECT SUM(f.value::NUMBER), COUNT(DISTINCT TO_DATE(l.PROCESS_TIME)) INTO :v_actual_records, :v_actual_rec_days",
        "      FROM DTAGENT_DB.STATUS.PROCESSED_MEASUREMENTS_LOG l, LATERAL FLATTEN(l.ENTRIES_COUNT, RECURSIVE => TRUE) f",
        f"      WHERE l.PROCESS_TIME >= DATEADD(day, -{LOOKBACK_DAYS}, CURRENT_TIMESTAMP())",
        "        AND f.key IN ('log_lines', 'metrics', 'events', 'spans') AND IS_INTEGER(f.value);",
        "    IF (v_actual_rec_days > 0) THEN",
        "      v_actual_records := v_actual_records / v_actual_rec_days;",
        "      n_actual_records := 'measured, average over ' || v_actual_rec_days || ' day(s) with data';",
        "    ELSE",
        "      v_actual_records := NULL; n_actual_records := 'not installed';",
        "    END IF;",
        "  EXCEPTION WHEN OTHER THEN",
        "    n_actual_records := 'n/a: ' || SQLERRM;",
        "  END;",
    ]
    return lines


def _signal_union(model: Dict[str, Any], sizes: Dict[str, Dict[str, float]]) -> str:
    parts = []
    for plugin, entry in model["plugins"].items():
        if entry.get("deprecated"):
            continue
        for signal in SIGNALS:
            expression = records_expression(plugin, signal, model)
            if expression:
                parts.append(f"      SELECT {_sql_str(plugin)}, {_sql_str(signal)}, ({expression})::FLOAT, {sizes[plugin][signal]}")
    return "\n      UNION ALL\n".join(parts)


def _credit_values(model: Dict[str, Any]) -> str:
    credit_model = snowflake_credits(model)
    rows = []
    for plugin, entry in model["plugins"].items():
        deprecated = bool(entry.get("deprecated"))
        status = "deprecated" if deprecated else ("on by default" if entry["default_on"] else "off by default")
        if deprecated:
            alloc_org = alloc_no_org = stand = "NULL"
        else:
            stand = _num(credit_model["with_org"]["standalone"][plugin])
            alloc_org = _num(credit_model["with_org"]["allocated"][plugin])
            alloc_no_org = _num(credit_model["without_org"]["allocated"].get(plugin, 0)) if plugin in credit_model["without_org"]["allocated"] else "0"
        note = entry.get("deprecated") or ("n/a, requires org account" if entry.get("requires_org_account") else "")
        rows.append(
            f"      ({_sql_str(plugin)}, {_sql_str(status)}, {int(entry['default_on'])}, {int(deprecated)}, "
            f"{int(bool(entry.get('requires_org_account')))}, {stand}, {alloc_org}, {alloc_no_org}, {_sql_str(note)})"
        )
    return ",\n".join(rows)


def _gaps_values(model: Dict[str, Any]) -> str:
    """SQL rows (plugin, names of its inputs that could not be measured) so unreadable inputs are visible on the plugin row."""
    rows = []
    for plugin, entry in model["plugins"].items():
        drivers = sorted({c["driver"] for c in entry["contexts"] if c["driver"] != "const"})
        if drivers and not entry.get("deprecated"):
            expression = " || ".join(f"IFF(:n_{d} <> 'measured', '{d} ', '')" for d in drivers)
            rows.append(f"      SELECT {_sql_str(plugin)} AS plugin, {expression} AS gap")
    return "\n      UNION ALL\n".join(rows)


def _output_query(model: Dict[str, Any], sizes: Dict[str, Dict[str, float]]) -> str:
    card = model["rate_card"]
    credit_model = snowflake_credits(model)
    headroom = model["snowflake"]["resource_monitor_headroom"]
    header = [
        "DSOA cost estimate - DSOA defaults, all plugins enabled, no config",
        f"Rate card as of {card['as_of']} ({card['currency']}), retention {card['retention_days']} days - edit the rate-card block at the top to re-price",
        "Dynatrace query cost (dashboards, notebooks, workflows, ad-hoc DQL) is NOT included: it depends on how the data is used",
        "Snowflake cost covers DTAGENT_WH only (credits); Snowflake event table ingest and cloud services above the 10% adjustment are reported separately",
        "Run durations per plugin are model constants, volumes are modelled from measured object counts and workload - see docs/INSTALL.md",
    ]
    header_rows = "\n".join(
        f"      UNION ALL SELECT '1 HEADER', {_sql_str(line)}, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, {i}"
        for i, line in enumerate(header)
    )
    input_rows = "\n".join(
        f"      UNION ALL SELECT '2 INPUT', {_sql_str(name)}, NULL, :n_{name}, :v_{name}, NULL, NULL, NULL, NULL, NULL, NULL, NULL, {i}"
        for i, name in enumerate(n for n in model["drivers"] if n != "const")
    )
    return f"""
    WITH
    sig(plugin, signal, records_day, bytes_per_record) AS (
{_signal_union(model, sizes)}
    ),
    gaps AS (
{_gaps_values(model)}
    ),
    sf(plugin, status, default_on, deprecated, needs_org, standalone, alloc_org, alloc_no_org, note) AS (
      SELECT * FROM VALUES
{_credit_values(model)}
    ),
    priced AS (
      SELECT plugin, signal, records_day,
        records_day * bytes_per_record / {GIB} AS gib_day,
        IFF(signal = 'metrics', records_day * {MONTH_DAYS} / 100000 * :p_metrics_100k,
            records_day * bytes_per_record / {GIB} * {MONTH_DAYS} * CASE signal
              WHEN 'logs' THEN :p_logs_gib WHEN 'spans' THEN :p_spans_gib
              WHEN 'events' THEN :p_events_gib ELSE :p_bizevents_gib END) AS usd_ingest_month
      FROM sig
    ),
    costed AS (
      SELECT plugin, signal, records_day, gib_day, gib_day * :p_retention_days AS gib_retained,
        usd_ingest_month + gib_day * 15 * :p_retain_gib_day * {MONTH_DAYS} AS usd_month_1,
        usd_ingest_month + gib_day * :p_retention_days * :p_retain_gib_day * {MONTH_DAYS} AS usd_month_steady
      FROM priced
    ),
    by_plugin AS (
      SELECT s.plugin,
        s.status || IFF(s.note <> '' AND s.deprecated = 0, ', ' || s.note, IFF(s.deprecated = 1, ', ' || s.note, ''))
          || IFF(COALESCE(g.gap, '') <> '', ' - ESTIMATE INCOMPLETE, input n/a: ' || RTRIM(g.gap), '') AS status_note,
        s.default_on, s.deprecated, s.needs_org,
        SUM(c.records_day) AS records_day, SUM(c.gib_day) AS gib_day, SUM(c.gib_retained) AS gib_retained,
        SUM(c.usd_month_1) AS usd_month_1, SUM(c.usd_month_steady) AS usd_month_steady,
        IFF(s.deprecated = 1, NULL, IFF(:v_org = 1, s.alloc_org, s.alloc_no_org)) AS sf_alloc,
        IFF(s.deprecated = 1 OR (s.needs_org = 1 AND :v_org = 0), NULL, s.standalone) AS sf_standalone
      FROM sf s LEFT JOIN costed c ON c.plugin = s.plugin LEFT JOIN gaps g ON g.plugin = s.plugin
      GROUP BY s.plugin, g.gap, s.status, s.note, s.default_on, s.deprecated, s.needs_org, s.alloc_org, s.alloc_no_org, s.standalone
    ),
    top_signal AS (
      SELECT plugin, signal, usd_month_steady / NULLIFZERO(SUM(usd_month_steady) OVER (PARTITION BY plugin)) AS share
      FROM costed QUALIFY ROW_NUMBER() OVER (PARTITION BY plugin ORDER BY usd_month_steady DESC) = 1
    ),
    totals AS (
      SELECT SUM(records_day) AS records_day, SUM(gib_day) AS gib_day, SUM(gib_retained) AS gib_retained,
        SUM(usd_month_1) AS usd_month_1, SUM(usd_month_steady) AS usd_month_steady, SUM(sf_alloc) AS sf_alloc, SUM(sf_standalone) AS sf_standalone,
        SUM(IFF(default_on = 1, records_day, 0)) AS d_records, SUM(IFF(default_on = 1, gib_day, 0)) AS d_gib,
        SUM(IFF(default_on = 1, gib_retained, 0)) AS d_retained, SUM(IFF(default_on = 1, usd_month_1, 0)) AS d_m1,
        SUM(IFF(default_on = 1, usd_month_steady, 0)) AS d_steady
      FROM by_plugin
    ),
    out(section, item, signal, note, value, records_day, gib_day, gib_retained, usd_month_1, usd_month_steady, sf_alloc, sf_standalone, sort_key) AS (
      SELECT '1 HEADER', 'Rate card (editable)', NULL, 'logs ' || :p_logs_gib || ', spans ' || :p_spans_gib || ', events ' || :p_events_gib
        || ', bizevents ' || :p_bizevents_gib || ' per GiB; metrics ' || :p_metrics_100k || ' per 100k data points; retain ' || :p_retain_gib_day
        || ' per GiB-day', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, -1
{header_rows}
{input_rows}
      UNION ALL SELECT '3 PLUGIN', plugin, NULL, status_note, NULL, records_day, gib_day, gib_retained, usd_month_1, usd_month_steady,
        sf_alloc, sf_standalone, ROW_NUMBER() OVER (ORDER BY plugin) FROM by_plugin
      UNION ALL SELECT '4 PLUGIN SIGNAL', plugin, signal, NULL, NULL, records_day, gib_day, gib_retained, usd_month_1, usd_month_steady,
        NULL, NULL, ROW_NUMBER() OVER (ORDER BY plugin, signal) FROM costed
      UNION ALL SELECT '0 TOTAL', 'all plugins (incl. off by default)', NULL, 'every plugin that is not deprecated, including off-by-default ones; org_costs only on an organization account', NULL, records_day, gib_day, gib_retained,
        usd_month_1, usd_month_steady, sf_alloc, sf_standalone, 0 FROM totals
      UNION ALL SELECT '0 TOTAL', 'default install', NULL, 'only plugins enabled in the shipped config; excludes budgets, table_health, org_costs, event_usage', NULL, d_records, d_gib, d_retained, d_m1, d_steady,
        {_num(credit_model['default']['total'])}, NULL, 1 FROM totals
      UNION ALL SELECT '5 RESOURCE MONITOR', 'core.snowflake.resource_monitor.credit_quota (all plugins)', NULL,
        'estimated credits/day x {headroom}, rounded up', CEIL(sf_alloc * {headroom}), NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0 FROM totals
      UNION ALL SELECT '5 RESOURCE MONITOR', 'core.snowflake.resource_monitor.credit_quota (default install)', NULL,
        'estimated credits/day x {headroom}, rounded up', CEIL({_num(credit_model['default']['total'])} * {headroom}), NULL, NULL, NULL, NULL, NULL, NULL, NULL, 1 FROM totals
      UNION ALL SELECT '6 TOP COST DRIVER', p.plugin, t.signal, 'Dynatrace $/month at steady state, ' || ROUND(t.share * 100) || '% from ' || t.signal,
        NULL, p.records_day, p.gib_day, p.gib_retained, p.usd_month_1, p.usd_month_steady, p.sf_alloc, p.sf_standalone,
        ROW_NUMBER() OVER (ORDER BY p.usd_month_steady DESC NULLS LAST)
        FROM by_plugin p JOIN top_signal t ON t.plugin = p.plugin
        QUALIFY ROW_NUMBER() OVER (ORDER BY p.usd_month_steady DESC NULLS LAST) <= 3
      UNION ALL SELECT '7 ACTUAL VS ESTIMATE', 'DTAGENT_WH credits/day', NULL, 'actual: ' || :n_actual_credits, :v_actual_credits, NULL, NULL, NULL, NULL, NULL,
        sf_alloc, NULL, 0 FROM totals
      UNION ALL SELECT '7 ACTUAL VS ESTIMATE', 'records/day logged in PROCESSED_MEASUREMENTS_LOG (logs, metrics, events, spans; no bizevents)', NULL,
        'actual: ' || :n_actual_records, :v_actual_records,
        (SELECT SUM(records_day) FROM costed WHERE signal <> 'bizevents'), NULL, NULL, NULL, NULL, NULL, NULL, 1 FROM totals
    )
    SELECT section AS SECTION, item AS ITEM, signal AS SIGNAL, note AS NOTE, value AS VALUE,
      ROUND(records_day) AS RECORDS_DAY, ROUND(gib_day, 4) AS DT_GIB_INGESTED_DAY, ROUND(gib_retained, 3) AS DT_GIB_RETAINED_STEADY,
      ROUND(usd_month_1, 2) AS DT_USD_MONTH_1, ROUND(usd_month_steady, 2) AS DT_USD_MONTH_STEADY,
      ROUND(sf_alloc, 3) AS SF_CREDITS_DAY_ALLOCATED, ROUND(sf_standalone, 3) AS SF_CREDITS_DAY_STANDALONE,
      ROUND(sf_alloc * {MONTH_DAYS}, 1) AS SF_CREDITS_MONTH_ALLOCATED
    FROM out ORDER BY section, sort_key"""


def render_sql(model: Dict[str, Any]) -> str:
    """Renders the full Snowsight worksheet script."""
    sizes = bytes_per_record(model)
    declare = "\n".join(_declare_block(model))
    measure = "\n".join(_measure_blocks(model))
    output = _output_query(model, sizes)
    return f"""-- DSOA cost estimate (generated by src/build/generate_cost_calculator.py - do not edit, change cost_model.yml and rebuild)
-- READ-ONLY: creates nothing. Run in a Snowsight worksheet with a role that can read the SNOWFLAKE database
-- (for example ACCOUNTADMIN, or a role granted IMPORTED PRIVILEGES on SNOWFLAKE). The script first checks that it can read the
-- required ACCOUNT_USAGE views and, if not, returns one MISSING PERMISSIONS row instead of the report. See docs/COST_ESTIMATE.md.
-- Assumes all plugins enabled with shipped defaults. Sources that cannot be read are shown as "n/a" with the reason.
-- The scan covers the last {LOOKBACK_DAYS} days of ACCOUNT_USAGE, QUERY_HISTORY and the account event table.
EXECUTE IMMEDIATE $$
DECLARE
{declare}
BEGIN
{measure}
  res := ({output}
  );
  RETURN TABLE(res);
END;
$$;
"""


def main() -> int:
    """Validates the model against the plugins and writes build/dsoa-cost-estimate.sql and its committed copy."""
    model = load_model()
    problems = validate_model(model)
    if problems:
        print("cost_model.yml is out of date:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    script = render_sql(model)
    for target in (OUTPUT_FILE, REPO_COPY):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as file:
            file.write(script)
        print(f"Generated {os.path.relpath(target, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
