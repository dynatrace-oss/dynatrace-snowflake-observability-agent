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
-- APP.F_EVENT_LOG_INCLUDE(db_name) decides whether a given event log entry should be included
-- in reporting, based on two config options:
--
--   plugins.event_log.databases           (array, default empty = all DBs included)
--     Optional allow-list of database name patterns (SQL LIKE syntax, e.g. 'MYAPP_%').
--     When absent or empty every database passes; when non-empty only matching databases pass.
--
--   plugins.event_log.cross_tenant_monitoring  (boolean, default true)
--     Controls whether WARN/ERROR entries from other DTAGENT_*_DB instances are reported.
--     When false, only the local instance (DTAGENT_DB) is reported for DTAGENT-family DBs.
--     DTAGENT_DB is replaced with DTAGENT_$TAG_DB during deployment.
--
-- Severity filtering (DEBUG/INFO exclusion) for DTAGENT-family entries is handled inside
-- the calling views because it only applies to LOG record types, not to METRICs or SPANs.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace function DTAGENT_DB.APP.F_EVENT_LOG_INCLUDE(db_name VARCHAR)
returns BOOLEAN
language sql
as
$$
    -- Step 1: apply optional database allow-list (empty / absent = all databases pass)
    iff(
        array_size(DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.event_log.databases', [])::array) > 0
        and not exists (
            select 1
            from table(flatten(DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.event_log.databases', [])::array)) f
            where db_name like f.VALUE::varchar
        ),
        false,
        -- Step 2: for non-DTAGENT DBs always include
        iff(
            db_name not like 'DTAGENT%_DB',
            true,
            -- Step 3: for DTAGENT-family DBs include self always (severity handled in view);
            --         include other tenants only when cross_tenant_monitoring is true (default)
            iff(
                db_name = 'DTAGENT_DB'  -- DTAGENT_DB will be replaced with DTAGENT_$TAG_DB during deploy
                or coalesce(
                    DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.event_log.cross_tenant_monitoring', true::variant)::boolean,
                    true
                ),
                true,
                false
            )
        )
    )
$$;

grant usage on function DTAGENT_DB.APP.F_EVENT_LOG_INCLUDE(VARCHAR) to role DTAGENT_VIEWER;


-- example calls
/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select DTAGENT_DB.APP.F_EVENT_LOG_INCLUDE('MYAPP_DB');          -- true  (non-DTAGENT)
select DTAGENT_DB.APP.F_EVENT_LOG_INCLUDE('DTAGENT_DB');        -- true  (self)
select DTAGENT_DB.APP.F_EVENT_LOG_INCLUDE('DTAGENT_TNB_DB');    -- true  (cross_tenant_monitoring=true by default)
 */
