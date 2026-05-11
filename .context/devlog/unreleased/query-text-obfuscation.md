# [Unreleased] — Query Text Obfuscation

## Problem

Raw query text from `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` flowed through DSOA unchanged into Dynatrace spans/logs. Query text can contain hardcoded credentials (`COPY INTO ... CREDENTIALS=(...)`), API tokens in UDF bodies, or PII in `WHERE` clauses. Syntax error messages (when `ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR=TRUE`) compound this — the offending query text is embedded in `snowflake.error.message`.

## Design

Three-mode obfuscation applied at two layers:

1. **SQL layer (primary)** — `APP.F_OBFUSCATE_QUERY_TEXT(TEXT, MODE)` UDF in `052_f_obfuscate_query_text.sql`. Called from `053_v_query_history_instrumented.sql` for both `db.query.text` (line 77) and `snowflake.error.message` (line 97). Config value read inline via `CONFIG.F_GET_CONFIG_VALUE('plugins.query_history.obfuscation_mode', 'off')`. Obfuscation is applied before data is materialised into `TMP_RECENT_QUERIES`, so no unobfuscated text enters the processing pipeline.
2. **Python layer (fallback)** — `QueryHistoryPlugin._obfuscate_query_text()` in `query_history.py`. Applied to the log message body (`db.query.text` value passed to `send_log`). Guards against any future path where query text is read from Python before the SQL layer can act on it.

## Modes

- `off` (default): no transformation — backward compatible.
- `literals`: `REGEXP_REPLACE` replaces `'[^']*'` (string literals) and `\b[0-9]+\.?[0-9]*\b` (numeric literals) with `?`. SQL keywords, identifiers, and structure are preserved. Best-effort — does not handle dollar-quoted strings or escaped quotes; documented as intentional.
- `full`: replaces entire text with `[OBFUSCATED]`. Covers both `db.query.text` and `snowflake.error.message` for maximum privacy. Error diagnostics (line/position info) are lost; trade-off is explicit in documentation.

## `ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR` interaction

This Snowflake account parameter is set to `TRUE` by `009_query_history_init.sql` (init scope only). It causes syntax-error query text to appear in `snowflake.error.message`. Because `obfuscation_mode` is also applied to `snowflake.error.message`, customers who set `obfuscation_mode: literals` or `obfuscation_mode: full` are protected against leaking query text via this path too. Customers who want to disable the parameter itself are documented in `readme.md` — DSOA does not reset it on non-init deploys.

## Files changed

| File | Change |
|------|--------|
| `query_history.sql/052_f_obfuscate_query_text.sql` | New SQL UDF with CASE/REGEXP_REPLACE logic |
| `query_history.sql/053_v_query_history_instrumented.sql` | Wrap `db.query.text` and `snowflake.error.message` with UDF |
| `query_history.py` | Add `_obfuscate_query_text()`, apply to log body; import `re` |
| `query_history-config.yml` | Add `obfuscation_mode: "off"` |
| `conf/config-template.yml` | Add `obfuscation_mode: "off"` |
| `bom.yml` | Add `F_OBFUSCATE_QUERY_TEXT(VARCHAR, VARCHAR)` |
| `readme.md` | Document obfuscation modes and `ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR` |
| `config.md` | Document `PLUGINS.QUERY_HISTORY.OBFUSCATION_MODE` config key |
| `test/plugins/test_query_history_obfuscation.py` | 19 unit tests across all modes and edge cases |
