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
-- APP.V_TABLE_HEALTH_DERIVED computes period-over-period growth and clustering
-- degradation signals from the two most recent snapshots in TABLE_HEALTH_HISTORY.
-- Only tables with at least two snapshots are included.
-- CLUSTERING_DEGRADED is set when depth increased by more than
-- plugins.table_health.clustering_degradation_threshold (default 2).
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_TABLE_HEALTH_DERIVED as
with RANKED AS (
    select
        TABLE_FULL_NAME,
        TABLE_CATALOG,
        TABLE_SCHEMA,
        TABLE_NAME,
        ACTIVE_BYTES,
        AVERAGE_DEPTH,
        SNAPSHOTTED_AT,
        row_number() over (partition by TABLE_FULL_NAME order by SNAPSHOTTED_AT desc) AS RN
    from DTAGENT_DB.APP.TABLE_HEALTH_HISTORY
),
CURRENT_SNAP AS (
    select * from RANKED where RN = 1
),
PREV_SNAP AS (
    select * from RANKED where RN = 2
),
THRESHOLD AS (
    select coalesce(
        (
            select VALUE::float
            from DTAGENT_DB.CONFIG.CONFIGURATIONS
            where PATH = 'plugins.table_health.clustering_degradation_threshold'
        ),
        2.0
    ) AS DEGRADATION_THRESHOLD
),
DERIVED AS (
    select
        c.TABLE_FULL_NAME,
        c.TABLE_CATALOG,
        c.TABLE_SCHEMA,
        c.TABLE_NAME,
        c.SNAPSHOTTED_AT,
        -- byte growth since previous snapshot
        (c.ACTIVE_BYTES - p.ACTIVE_BYTES)                                                       AS GROWTH_BYTES,
        -- percentage growth (null-safe: avoid division by zero)
        iff(
            p.ACTIVE_BYTES > 0,
            round((c.ACTIVE_BYTES - p.ACTIVE_BYTES) / p.ACTIVE_BYTES * 100.0, 4),
            null
        )                                                                                       AS GROWTH_PCT,
        -- clustering depth change (positive = degraded, negative = improved)
        (c.AVERAGE_DEPTH - p.AVERAGE_DEPTH)                                                     AS DEPTH_CHANGE,
        -- degradation flag: 1 when depth increased beyond threshold, else 0
        iff(
            c.AVERAGE_DEPTH is not null
            and p.AVERAGE_DEPTH is not null
            and (c.AVERAGE_DEPTH - p.AVERAGE_DEPTH) > t.DEGRADATION_THRESHOLD,
            1,
            0
        )                                                                                       AS CLUSTERING_DEGRADED
    from CURRENT_SNAP AS c
    join PREV_SNAP AS p
        on p.TABLE_FULL_NAME = c.TABLE_FULL_NAME
    cross join THRESHOLD AS t
)
select
    extract(epoch_nanosecond from SNAPSHOTTED_AT)                                               as START_TIME,
    concat('Table health derived metrics for ', TABLE_FULL_NAME)                                as _MESSAGE,
    OBJECT_CONSTRUCT(
        'db.namespace',                     TABLE_CATALOG,
        'snowflake.schema.name',            TABLE_SCHEMA,
        'db.collection.name',               TABLE_NAME,
        'snowflake.table.full_name',        TABLE_FULL_NAME
    )                                                                                           as DIMENSIONS,
    OBJECT_CONSTRUCT()                                                                          as ATTRIBUTES,
    OBJECT_CONSTRUCT()                                                                          as EVENT_TIMESTAMPS,
    OBJECT_CONSTRUCT(
        'snowflake.table.growth_bytes',                 GROWTH_BYTES,
        'snowflake.table.growth_pct',                   GROWTH_PCT,
        'snowflake.table.clustering.depth_change',      DEPTH_CHANGE,
        'snowflake.table.clustering.degraded',          CLUSTERING_DEGRADED
    )                                                                                           as METRICS
from DERIVED
;

grant select on view DTAGENT_DB.APP.V_TABLE_HEALTH_DERIVED to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select *
from DTAGENT_DB.APP.V_TABLE_HEALTH_DERIVED
order by START_TIME desc
limit 20;
 */
