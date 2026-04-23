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
-- APP.V_TABLE_CLUSTERING reads from the staging table TABLE_CLUSTERING_RESULTS
-- and exposes clustering depth metrics in the standard DSOA view contract.
-- Only rows collected within the last 7 hours are returned (freshness gate).
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_TABLE_CLUSTERING
as
select
    extract(epoch_nanosecond from current_timestamp)                                                                    as START_TIME,

    concat('Table clustering metrics for ', coalesce(TABLE_FULL_NAME, ''))                                              as _MESSAGE,
    -- metric and span dimensions
    object_construct(
        'db.namespace',                                             TABLE_CATALOG,
        'snowflake.schema.name',                                    TABLE_SCHEMA,
        'db.collection.name',                                       TABLE_NAME,
        'snowflake.table.full_name',                                TABLE_FULL_NAME,
        'snowflake.table.clustering_key',                           CLUSTERING_KEY
    )                                                                                                                   as DIMENSIONS,
    object_construct(
    )                                                                                                                   as ATTRIBUTES,
    object_construct(
    )                                                                                                                   as EVENT_TIMESTAMPS,
    -- metrics
    object_construct(
        'snowflake.table.clustering.depth',                         AVERAGE_DEPTH,
        'snowflake.table.clustering.overlap',                       AVERAGE_OVERLAPS,
        'snowflake.table.clustering.total_partitions',              TOTAL_PARTITION_COUNT,
        'snowflake.table.clustering.constant_partition_ratio',
            TOTAL_CONSTANT_PARTITION_COUNT / nullif(TOTAL_PARTITION_COUNT, 0)
    )                                                                                                                   as METRICS
from DTAGENT_DB.APP.TABLE_CLUSTERING_RESULTS
where COLLECTED_AT >= dateadd(hour, -7, current_timestamp)
;

grant select on table DTAGENT_DB.APP.V_TABLE_CLUSTERING to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select *
from DTAGENT_DB.APP.V_TABLE_CLUSTERING
limit 10;
 */
