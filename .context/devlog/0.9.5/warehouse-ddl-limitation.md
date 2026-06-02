# Warehouse DDL Limitation — ACCESS_HISTORY.object_modified_by_ddl

## Finding (discovered 2026-05-25, QA ses_ant3b)

`ALTER WAREHOUSE` (and other warehouse-level DDL: `CREATE WAREHOUSE`, `DROP WAREHOUSE`,
`ALTER RESOURCE MONITOR`, etc.) is **NOT** captured by
`ACCESS_HISTORY.OBJECT_MODIFIED_BY_DDL`. That column only contains DDL for
**database objects**: tables, views, dynamic tables, streams, tasks, stages, schemas,
procedures, functions, and similar objects that live inside a database.

Confirmed during live QA (ses_ant3b, 2026-05-25): after executing
`ALTER WAREHOUSE DSOA_TEST_WH_DDL_SIM SET COMMENT = '...'` and waiting for the
ACCESS_HISTORY lag window, `V_QUERY_HISTORY.ddl_target_domain` returned only
`"Dynamic table"` entries — never `"Warehouse"`. The `OBJECT_MODIFIED_BY_DDL` field
was NULL for all warehouse DDL query IDs.

---

## Impact on DSOA

### Affected feature

`query_history` plugin — experimental `track_ddl_changes` feature (BDX-1998).

### What the feature does

When `plugins.query_history.track_ddl_changes=true`, the plugin joins
`ACCESS_HISTORY.OBJECT_MODIFIED_BY_DDL` to extract structured DDL attribution
(object domain, id, name, operation type, property delta) and emits it as five
span/log attributes:

- `snowflake.object.type`
- `snowflake.object.id`
- `snowflake.object.name`
- `snowflake.object.ddl.operation`
- `snowflake.object.ddl.properties`

### What it misses

**Warehouse and resource-monitor DDL will never populate these five attributes.**
The `OBJECT_MODIFIED_BY_DDL` field is NULL for all warehouse-level operations.
The hold-back logic in `V_QUERY_HISTORY` (lines 331–343 of `051_v_query_history.sql`)
correctly waits for `ah.ddl_operation IS NOT NULL` before emitting the row — but for
warehouse DDL this condition is **never satisfied**, so the row is held back
indefinitely and never emitted.

> **Critical:** This means `ALTER_WAREHOUSE`, `CREATE_WAREHOUSE`, `DROP_WAREHOUSE`,
> `ALTER_RESOURCE_MONITOR`, `CREATE_RESOURCE_MONITOR`, and `DROP_RESOURCE_MONITOR`
> rows are **silently dropped** when `track_ddl_changes=true`. They are not emitted
> without DDL attributes, and they are not emitted with DDL attributes either.

### Affected downstream artifact

The `warehouse-sensitive-change-alert` workflow queries for spans/logs with
`isNotNull(snowflake.object.ddl.operation)` filtered to
`snowflake.object.type in ("Warehouse", "Resource Monitor")`. Because warehouse DDL
never populates `OBJECT_MODIFIED_BY_DDL`, this filter will **never match** for real
warehouse changes. The workflow will never fire for its intended purpose.

---

## Alternatives

### Option A: QUERY_HISTORY query_type filtering (recommended)

`SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` records every executed statement including
warehouse DDL, with `query_type` values such as `ALTER_WAREHOUSE`,
`CREATE_WAREHOUSE`, `DROP_WAREHOUSE`, `ALTER_RESOURCE_MONITOR`, etc.

The `query_history` plugin **already emits these rows as spans** via the standard
pipeline — they appear with `db.operation.name = "ALTER_WAREHOUSE"` (mapped from
`query_type`). The raw SQL is available in `db.query.text`.

**What is missing:** structured property delta (`ddl_properties`). The raw SQL
contains the change (e.g. `SET WAREHOUSE_SIZE = 'LARGE'`) but it is not parsed.

**Workflow fix:** Change the `detect_sensitive_changes` DQL from filtering on
`snowflake.object.ddl.operation` to filtering on `db.operation.name` with warehouse
query types, and scan `db.query.text` for sensitive property keywords instead of
`snowflake.object.ddl.properties`.

### Option B: WAREHOUSE_EVENTS_HISTORY

`SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY` records operational warehouse
events (RESUME, SUSPEND, RESIZE, etc.) with structured fields. DSOA already queries
this view in the `warehouse_usage` plugin
(`src/dtagent/plugins/warehouse_usage.sql/070_v_warehouse_event_history.sql`).

However, this view captures **operational events** (auto-suspend, auto-resume, resize
triggered by load), not user-initiated DDL changes. It does not record who ran
`ALTER WAREHOUSE SET WAREHOUSE_SIZE = 'LARGE'`.

**Not suitable** as a replacement for DDL change attribution.

### Option C: Current behavior (query_history spans — no hold-back)

The `query_history` plugin already captures `ALTER_WAREHOUSE` etc. as spans when
`track_ddl_changes=false` (the default). These spans carry:

- `db.operation.name` = `"ALTER_WAREHOUSE"`
- `db.user`, `snowflake.role.name` (actor)
- `db.query.text` (raw SQL, possibly obfuscated)
- `snowflake.warehouse.name` (warehouse that ran the query, not the target)

They do **not** carry `snowflake.object.name` (the target warehouse name) or
`snowflake.object.ddl.properties` (structured property delta).

This is the **currently working signal** for warehouse change detection.

---

## Recommended Fix

### Immediate (this PR)

1. **Fix the hold-back logic** in `051_v_query_history.sql` to NOT hold back
   warehouse/resource-monitor DDL rows indefinitely. Two options:
   - **Option 1a (preferred):** Remove `ALTER_WAREHOUSE` etc. from the hold-back
     filter entirely. These rows will be emitted without DDL attributes (all five
     `snowflake.object.*` attributes will be NULL), which is correct and honest.
   - **Option 1b:** Keep the hold-back but add a timeout (e.g. if `end_time` is
     more than 4 hours ago, emit anyway). More complex, not recommended.

2. **Update the workflow** `warehouse-sensitive-change-alert.yml` to use
   `db.operation.name` filtering instead of `snowflake.object.ddl.operation`:

   ```dql
   fetch spans, from: now()-90m
   | filter db.system == "snowflake"
   | filter in(db.operation.name, array(
       "ALTER_WAREHOUSE", "CREATE_WAREHOUSE", "DROP_WAREHOUSE",
       "ALTER_RESOURCE_MONITOR", "CREATE_RESOURCE_MONITOR", "DROP_RESOURCE_MONITOR"
     ))
   | filter contains(toString(db.query.text), "WAREHOUSE_SIZE")
        or contains(toString(db.query.text), "SCALING_POLICY")
        or contains(toString(db.query.text), "RESOURCE_MONITOR")
        or contains(toString(db.query.text), "AUTO_SUSPEND")
        or contains(toString(db.query.text), "MIN_CLUSTER_COUNT")
        or contains(toString(db.query.text), "MAX_CLUSTER_COUNT")
   | fields timestamp, deployment.environment, db.user,
            snowflake.role.name, db.operation.name, db.query.text
   | sort timestamp desc
   | limit 100
   ```

   **Caveat:** `db.query.text` is subject to obfuscation if
   `plugins.query_history.obfuscation_mode` is not `off`. Document this.

3. **Update the readme** for the workflow to document the limitation and the
   corrected signal source.

4. **Update `setup_test_warehouse_ddl.sql`** to remove the incorrect claim that
   `ALTER WAREHOUSE` will populate `OBJECT_MODIFIED_BY_DDL`.

5. **Update the QA checklist** E3.2 entry to use the corrected DQL.

### Future work

If structured property delta for warehouse DDL is required, it must be extracted
by parsing `db.query.text` server-side (in the plugin SQL) or via a dedicated
Snowflake stored procedure that calls `SHOW WAREHOUSES` before and after the DDL.
This is out of scope for 0.9.5.

---

## Files Affected

| File | Change needed |
|------|---------------|
| `src/dtagent/plugins/query_history.sql/051_v_query_history.sql` | Remove warehouse/resource-monitor types from hold-back filter (lines 338–342) |
| `docs/workflows/warehouse-sensitive-change-alert/warehouse-sensitive-change-alert.yml` | Replace DDL-attribute DQL with `db.operation.name` + `db.query.text` approach |
| `docs/workflows/warehouse-sensitive-change-alert/readme.md` | Document limitation; update telemetry source table |
| `test/tools/setup_test_warehouse_ddl.sql` | Remove incorrect claim about warehouse DDL in `OBJECT_MODIFIED_BY_DDL` |
| `test/qa/RELEASE-CHECKLIST.template.md` | Update E3.2 entry with corrected DQL and limitation note |
| `test/qa/results/RELEASE-CHECKLIST.md` | Update E3.2 entry with audit finding |
| `test/qa/results/ai-memory/session-ses_ant3b_2026-05-25.md` | Add audit note |
| `.context/devlog/0.9.5/warehouse-change-attribution.md` | Add limitation note to open items |
| `.context/pm-notes/stories/BDX-1998-warehouse-change-detection.md` | Add Limitation section (if file exists) |
