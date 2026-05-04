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
-- APP.TABLE_CLUSTERING_RESULTS is a staging table that holds the latest clustering
-- information collected by P_COLLECT_CLUSTERING_INFO() for each clustered table.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create table if not exists DTAGENT_DB.APP.TABLE_CLUSTERING_RESULTS (
    TABLE_FULL_NAME                 varchar(1000)   not null,
    TABLE_CATALOG                   varchar(255)    not null,
    TABLE_SCHEMA                    varchar(255)    not null,
    TABLE_NAME                      varchar(255)    not null,
    CLUSTERING_KEY                  varchar(1000)   not null,
    AVERAGE_DEPTH                   float,
    AVERAGE_OVERLAPS                float,
    TOTAL_PARTITION_COUNT           number,
    TOTAL_CONSTANT_PARTITION_COUNT  number,
    COLLECTED_AT                    timestamp_ntz   not null default current_timestamp,
    constraint PK_TABLE_CLUSTERING_RESULTS primary key (TABLE_FULL_NAME)
);

grant select on table DTAGENT_DB.APP.TABLE_CLUSTERING_RESULTS to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select *
from DTAGENT_DB.APP.TABLE_CLUSTERING_RESULTS
order by COLLECTED_AT desc
limit 10;
 */
