--
--
-- Copyright (c) 2025 Dynatrace Open Source
--
-- Permission is hereby granted, free of charge, to any person obtaining a copy
-- of this software and associated documentation files (the "Software"), to deal
-- in the Software without restriction, including without limitation the rights
-- to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
-- copies of the Software, and to permit persons to whom the Software is
-- furnished to do so, subject to the following conditions:
--
-- The above copyright notice and this permission notice shall be included in all
-- copies or substantial portions of the Software.
--
-- THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
-- IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
-- FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
-- AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
-- LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
-- OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
-- SOFTWARE.
--
--
--
--  APP.F_HEARTBEAT_INSTRUMENTED() returns one row per Dynatrace Snowflake Observability Agent task, comparing
--  - what is configured (CONFIG.CONFIGURATIONS: plugin enabled flags and schedules),
--  - what is deployed (SHOW TASKS in the agent's own schema), and
--  - what actually ran in the configured window (INFORMATION_SCHEMA.TASK_HISTORY()).
--
--  Multitenancy: task names carry no TAG, so everything is scoped to this instance's database and APP schema,
--  and the database name (db.namespace) is reported as a dimension; deployment.environment(.name|.tag) are attached by the
--  agent as resource attributes to every log and metric line.
--  expected_runs (cron / interval arithmetic) is NOT computed here - it is added by HeartbeatPlugin in Python.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.F_HEARTBEAT_INSTRUMENTED()
returns table (
    TIMESTAMP   timestamp_ltz,
    _MESSAGE    varchar,
    DIMENSIONS  object,
    ATTRIBUTES  object,
    METRICS     object
)
language sql
execute as caller
as
$$
declare
    WINDOW_HOURS    int;
    WINDOW_END      timestamp_ltz;
    QID             varchar;
    RUNS            array default array_construct();
    res_tasks       resultset;
    res             resultset;
    V_SUCCEEDED     int;
    V_FAILED        int;
    V_SKIPPED       int;
    V_CANCELLED     int;
begin
    WINDOW_HOURS := (select DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.heartbeat.window_hours', 24)::int);

    -- SHOW TASKS must be the last statement before the query reading its result; scoped to this instance's schema only
    show tasks in schema DTAGENT_DB.APP;
    QID := last_query_id();
    WINDOW_END := current_timestamp();

    -- TASK_HISTORY applies RESULT_LIMIT before any other filter, so a single account-wide query could be truncated by unrelated
    -- activity; instead the history is read per deployed task (RESULT_LIMIT is then per task) with an explicit window end
    res_tasks := (
        select "name" as TASK_NAME
        from table(result_scan(:QID))
        where "database_name" = upper('DTAGENT_DB') and "schema_name" = 'APP' and "name" like 'TASK_DTAGENT_%'
    );
    for rec in res_tasks do
        select
            -- the heartbeat's own run is still EXECUTING while it measures itself; count it so its coverage is not always one short
            count_if(th.STATE = 'SUCCEEDED' or (th.STATE = 'EXECUTING' and th.NAME = 'TASK_DTAGENT_HEARTBEAT')),
            count_if(th.STATE = 'FAILED'),
            count_if(th.STATE = 'SKIPPED'),
            count_if(th.STATE = 'CANCELLED')
        into :V_SUCCEEDED, :V_FAILED, :V_SKIPPED, :V_CANCELLED
        from table(DTAGENT_DB.INFORMATION_SCHEMA.TASK_HISTORY(
                TASK_NAME => rec.TASK_NAME,
                SCHEDULED_TIME_RANGE_START => dateadd(hour, -1 * :WINDOW_HOURS, :WINDOW_END),
                SCHEDULED_TIME_RANGE_END => :WINDOW_END,
                RESULT_LIMIT => 10000)) th
        where th.DATABASE_NAME = upper('DTAGENT_DB') and th.SCHEMA_NAME = 'APP';

        RUNS := (select array_append(:RUNS, object_construct(
                    'TASK_NAME', rec.TASK_NAME, 'SUCCEEDED', :V_SUCCEEDED, 'FAILED', :V_FAILED,
                    'SKIPPED', :V_SKIPPED, 'CANCELLED', :V_CANCELLED)));
    end for;

    res := (
        with
        cte_global as (
            select NVL((select VALUE::boolean from DTAGENT_DB.CONFIG.CONFIGURATIONS where PATH = 'plugins.disabled_by_default'), false) as DISABLED_BY_DEFAULT
        ),
        -- per-plugin enabled/disabled overrides (same inputs as UPDATE_PLUGIN_SCHEDULE)
        cte_plugin_flags as (
            select
                split_part(PATH, '.', 2)                                                        as PLUGIN,
                boolor_agg(iff(split_part(PATH, '.', 3) = 'is_disabled', VALUE::boolean, null)) as IS_DISABLED,
                boolor_agg(iff(split_part(PATH, '.', 3) = 'is_enabled', VALUE::boolean, null))  as IS_ENABLED
            from DTAGENT_DB.CONFIG.CONFIGURATIONS
            where regexp_like(PATH, '^plugins[.][^.]+[.](is_disabled|is_enabled)$')
            group by split_part(PATH, '.', 2)
        ),
        -- one row per configured task: plugins.<p>.schedule -> TASK_DTAGENT_<P>, plugins.<p>.schedule_<aux> -> TASK_DTAGENT_<P>_<AUX>
        cte_configured as (
            select
                split_part(c.PATH, '.', 2)                                                      as PLUGIN,
                concat('TASK_DTAGENT_', upper(split_part(c.PATH, '.', 2)),
                       upper(substr(split_part(c.PATH, '.', 3), 9)))                            as TASK_NAME,
                c.VALUE::varchar                                                                as SCHEDULE,
                not (
                    (NVL(pf.IS_DISABLED, false) or g.DISABLED_BY_DEFAULT)
                    and not NVL(pf.IS_ENABLED, false)
                )                                                                               as IS_ENABLED
            from DTAGENT_DB.CONFIG.CONFIGURATIONS c
            cross join cte_global g
            left join cte_plugin_flags pf on pf.PLUGIN = split_part(c.PATH, '.', 2)
            where regexp_like(c.PATH, '^plugins[.][^.]+[.]schedule(_[^.]+)?$')
        ),
        -- tasks actually deployed in Snowflake
        cte_deployed as (
            select
                "name"          as TASK_NAME,
                lower("state")  as STATE,
                "schedule"      as SCHEDULE
            from table(result_scan(:QID))
            where "database_name" = upper('DTAGENT_DB') and "schema_name" = 'APP' and "name" like 'TASK_DTAGENT_%'
        ),
        -- runs in the window, collected per task above
        cte_runs as (
            select
                f.VALUE:TASK_NAME::varchar  as TASK_NAME,
                f.VALUE:SUCCEEDED::int      as SUCCEEDED,
                f.VALUE:FAILED::int         as FAILED,
                f.VALUE:SKIPPED::int        as SKIPPED,
                f.VALUE:CANCELLED::int      as CANCELLED
            from table(flatten(input => :RUNS)) f
        ),
        cte_joined as (
            select
                NVL(cfg.TASK_NAME, dep.TASK_NAME)                                               as TASK_NAME,
                NVL(cfg.PLUGIN, lower(regexp_replace(dep.TASK_NAME, '^TASK_DTAGENT_', '')))     as PLUGIN,
                cfg.IS_ENABLED                                                                  as IS_ENABLED,
                cfg.SCHEDULE                                                                    as CONFIGURED_SCHEDULE,
                NVL(dep.STATE, 'missing')                                                       as ACTUAL_STATE,
                dep.SCHEDULE                                                                    as ACTUAL_SCHEDULE,
                -- schedules are compared case/whitespace-insensitively; "30 MINUTES" and "30 MINUTE" are the same
                regexp_replace(regexp_replace(upper(trim(cfg.SCHEDULE)), ' +', ' '), '^([0-9]+) (SECOND|MINUTE|HOUR|DAY)S$', '\\1 \\2') as CFG_NORM,
                regexp_replace(regexp_replace(upper(trim(dep.SCHEDULE)), ' +', ' '), '^([0-9]+) (SECOND|MINUTE|HOUR|DAY)S$', '\\1 \\2') as DEP_NORM,
                NVL(r.SUCCEEDED, 0) as SUCCEEDED,
                NVL(r.FAILED, 0)    as FAILED,
                NVL(r.SKIPPED, 0)   as SKIPPED,
                NVL(r.CANCELLED, 0) as CANCELLED
            from cte_configured cfg
            full outer join cte_deployed dep on dep.TASK_NAME = cfg.TASK_NAME
            left join cte_runs r on r.TASK_NAME = NVL(cfg.TASK_NAME, dep.TASK_NAME)
        ),
        -- grants / cleanup tasks belong to the optional admin scope; when none of them is deployed the scope is not installed
        cte_admin_scope as (
            select count_if(regexp_like(TASK_NAME, '.*_(GRANTS|CLEANUP)$')) > 0 as IS_INSTALLED from cte_deployed
        ),
        cte_flags as (
            select
                j.*,
                NVL(j.IS_ENABLED, false) and j.ACTUAL_STATE = 'missing'
                    and (not regexp_like(j.TASK_NAME, '.*_(GRANTS|CLEANUP)$') or a.IS_INSTALLED)    as IS_MISSING,
                not NVL(j.IS_ENABLED, false) and j.ACTUAL_STATE = 'started'                     as IS_UNEXPECTED,
                NVL(j.IS_ENABLED, false) and j.ACTUAL_STATE = 'suspended'                       as IS_SUSPENDED,
                NVL(j.IS_ENABLED, false) and j.ACTUAL_STATE != 'missing' and NVL(j.CFG_NORM, '') != NVL(j.DEP_NORM, '') as HAS_SCHEDULE_DRIFT
            from cte_joined j
            cross join cte_admin_scope a
        )
        select
            current_timestamp()                                                                 as TIMESTAMP,
            concat('Heartbeat for ', f.TASK_NAME, ': configured_enabled=', NVL(f.IS_ENABLED::varchar, 'unknown'),
                   ', state=', f.ACTUAL_STATE, ', runs succeeded=', f.SUCCEEDED, ' failed=', f.FAILED,
                   ' skipped=', f.SKIPPED, ' cancelled=', f.CANCELLED, ' in last ', :WINDOW_HOURS, 'h')  as _MESSAGE,
            OBJECT_CONSTRUCT(
                'db.namespace',                         upper('DTAGENT_DB'),
                'dsoa.heartbeat.plugin',                f.PLUGIN,
                'dsoa.heartbeat.task',                  f.TASK_NAME
            )                                                                                   as DIMENSIONS,
            OBJECT_CONSTRUCT(
                'dsoa.heartbeat.configured_enabled',    f.IS_ENABLED,
                'dsoa.heartbeat.configured_schedule',   f.CONFIGURED_SCHEDULE,
                'dsoa.heartbeat.actual_state',          f.ACTUAL_STATE,
                'dsoa.heartbeat.actual_schedule',       f.ACTUAL_SCHEDULE,
                'dsoa.heartbeat.is_missing',            f.IS_MISSING,
                'dsoa.heartbeat.is_unexpected',         f.IS_UNEXPECTED,
                'dsoa.heartbeat.is_suspended',          f.IS_SUSPENDED,
                'dsoa.heartbeat.has_schedule_drift',    f.HAS_SCHEDULE_DRIFT,
                'dsoa.heartbeat.window_hours',          :WINDOW_HOURS
            )                                                                                   as ATTRIBUTES,
            OBJECT_CONSTRUCT(
                'dsoa.heartbeat.runs.succeeded',        f.SUCCEEDED,
                'dsoa.heartbeat.runs.failed',           f.FAILED,
                'dsoa.heartbeat.runs.skipped',          f.SKIPPED,
                'dsoa.heartbeat.runs.cancelled',        f.CANCELLED
            )                                                                                   as METRICS
        from cte_flags f
        order by f.TASK_NAME
    );

    return table(res);
exception
    when statement_error then
        -- do not return an empty table: that would look like a successful heartbeat with nothing to report
        SYSTEM$LOG_ERROR(SQLERRM);
        raise;
end;
$$
;

grant usage on procedure DTAGENT_DB.APP.F_HEARTBEAT_INSTRUMENTED() to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
call DTAGENT_DB.APP.F_HEARTBEAT_INSTRUMENTED();
*/
