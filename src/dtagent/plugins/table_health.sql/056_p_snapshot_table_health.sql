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
-- APP.P_SNAPSHOT_TABLE_HEALTH() inserts one row per table into TABLE_HEALTH_HISTORY
-- by joining V_TABLE_STORAGE with TABLE_CLUSTERING_RESULTS, then prunes rows older
-- than plugins.table_health.history_retention_days.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.P_SNAPSHOT_TABLE_HEALTH()
    returns varchar
    language sql
    execute as caller
as
$$
declare
    v_retention_days    integer default 30;
    v_inserted          integer default 0;
    v_pruned            integer default 0;
begin
    -- read retention from config (default 30 days)
    let c_cfg cursor for
        select VALUE::integer
        from DTAGENT_DB.CONFIG.CONFIGURATIONS
        where PATH = 'plugins.table_health.history_retention_days';
    open c_cfg;
    fetch c_cfg into v_retention_days;
    close c_cfg;

    -- insert snapshot: join storage view with latest clustering results
    insert into DTAGENT_DB.APP.TABLE_HEALTH_HISTORY (
        TABLE_FULL_NAME,
        TABLE_CATALOG,
        TABLE_SCHEMA,
        TABLE_NAME,
        ACTIVE_BYTES,
        ROW_COUNT,
        TIME_TRAVEL_BYTES,
        FAILSAFE_BYTES,
        RETAINED_FOR_CLONE_BYTES,
        AVERAGE_DEPTH,
        AVERAGE_OVERLAPS,
        SNAPSHOTTED_AT
    )
    select
        s.TABLE_FULL_NAME,
        s.TABLE_CATALOG,
        s.TABLE_SCHEMA,
        s.TABLE_NAME,
        s.ACTIVE_BYTES,
        s.ROW_COUNT,
        s.TIME_TRAVEL_BYTES,
        s.FAILSAFE_BYTES,
        s.RETAINED_FOR_CLONE_BYTES,
        c.AVERAGE_DEPTH,
        c.AVERAGE_OVERLAPS,
        current_timestamp()
    from DTAGENT_DB.APP.V_TABLE_STORAGE AS s
    left join DTAGENT_DB.APP.TABLE_CLUSTERING_RESULTS AS c
        on c.TABLE_FULL_NAME = s.TABLE_FULL_NAME;

    v_inserted := sqlrowcount;

    -- prune old rows
    delete from DTAGENT_DB.APP.TABLE_HEALTH_HISTORY
    where SNAPSHOTTED_AT < dateadd('day', -v_retention_days, current_timestamp());

    v_pruned := sqlrowcount;

    return 'inserted=' || v_inserted::varchar || ' pruned=' || v_pruned::varchar;
end;
$$;

grant usage on procedure DTAGENT_DB.APP.P_SNAPSHOT_TABLE_HEALTH() to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_OWNER;
call DTAGENT_DB.APP.P_SNAPSHOT_TABLE_HEALTH();
 */
