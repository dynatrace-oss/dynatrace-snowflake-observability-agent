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
-- APP.TABLE_HEALTH_HISTORY stores periodic snapshots of table storage and clustering
-- metrics.  P_SNAPSHOT_TABLE_HEALTH() writes one row per table per run.
-- Rows older than plugins.table_health.history_retention_days are pruned on each run.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create table if not exists DTAGENT_DB.APP.TABLE_HEALTH_HISTORY (
    TABLE_FULL_NAME                 varchar(1000)   not null,
    TABLE_CATALOG                   varchar(255)    not null,
    TABLE_SCHEMA                    varchar(255)    not null,
    TABLE_NAME                      varchar(255)    not null,
    ACTIVE_BYTES                    number,
    ROW_COUNT                       number,
    TIME_TRAVEL_BYTES               number,
    FAILSAFE_BYTES                  number,
    RETAINED_FOR_CLONE_BYTES        number,
    AVERAGE_DEPTH                   float,
    AVERAGE_OVERLAPS                float,
    SNAPSHOTTED_AT                  timestamp_ntz   not null default current_timestamp
)
cluster by (TABLE_FULL_NAME, SNAPSHOTTED_AT)
;

grant select on table DTAGENT_DB.APP.TABLE_HEALTH_HISTORY to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select *
from DTAGENT_DB.APP.TABLE_HEALTH_HISTORY
order by SNAPSHOTTED_AT desc
limit 20;
 */
