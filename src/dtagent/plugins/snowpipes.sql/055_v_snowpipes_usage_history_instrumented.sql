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
-- APP.V_SNOWPIPES_USAGE_HISTORY_INSTRUMENTED — Deep-mode view on ACCOUNT_USAGE.PIPE_USAGE_HISTORY.
-- Provides cost (credits), volume (bytes), and file count per pipe.
-- Joins with ACCOUNT_USAGE.PIPES to resolve the UUID PIPE_NAME to a human-readable FQN.
-- Pipes that have been deleted will have a NULL join; UUID is preserved as snowflake.pipe.id.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view APP.V_SNOWPIPES_USAGE_HISTORY_INSTRUMENTED
as
with cte_usage_history as (
    select h.*,
        -- Join with PIPES to resolve UUID -> human-readable FQN
        p.PIPE_NAME                                                     as RESOLVED_PIPE_FQN,
        SPLIT_PART(COALESCE(p.PIPE_NAME, ''), '.', 1)                  as RESOLVED_DB_NAME,
        SPLIT_PART(COALESCE(p.PIPE_NAME, ''), '.', 2)                  as RESOLVED_SCHEMA_NAME,
        -- Short name: last dot-separated part of FQN; fallback to UUID if deleted pipe
        COALESCE(
            NULLIF(SPLIT_PART(p.PIPE_NAME, '.', -1), ''),
            h.PIPE_NAME
        )                                                               as RESOLVED_PIPE_NAME
    from SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY h
    left join SNOWFLAKE.ACCOUNT_USAGE.PIPES p
        on h.PIPE_ID = p.PIPE_ID
    where h.END_TIME >= GREATEST(
        DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('snowpipes_usage_history'),
        TIMEADD(
            HOUR,
            -1 * CONFIG.F_GET_CONFIG_VALUE('plugins.snowpipes.lookback_hours_usage', 6)::INT,
            CURRENT_TIMESTAMP()
        )
    )
)
select
    EXTRACT(EPOCH_NANOSECOND FROM END_TIME::TIMESTAMP_LTZ)                                           as TIMESTAMP,
    RESOLVED_PIPE_NAME                                                                               as NAME,
    CONCAT('Snowpipe usage: ', RESOLVED_PIPE_NAME, ' (', CREDITS_USED, ' credits)')                 as _MESSAGE,
    OBJECT_CONSTRUCT(
        'snowflake.pipe.name',          RESOLVED_PIPE_NAME,
        'snowflake.pipe.full_name',     RESOLVED_PIPE_FQN,
        'snowflake.pipe.id',            PIPE_NAME,
        'snowflake.pipe.catalog',       RESOLVED_DB_NAME,
        'snowflake.pipe.schema',        RESOLVED_SCHEMA_NAME
    )                                                                                                as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.pipe.usage.start_time',      START_TIME
    )                                                                                                as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.pipe.data.ingested',         BYTES_BILLED,
        'snowflake.pipe.cost.credits_used',     CREDITS_USED,
        'snowflake.pipe.files.inserted',        TO_NUMBER(FILES_INSERTED),
        'snowflake.pipe.cost.bytes_billed',     BYTES_BILLED
    )                                                                                                as METRICS
from cte_usage_history
order by TIMESTAMP asc
;

grant select on view APP.V_SNOWPIPES_USAGE_HISTORY_INSTRUMENTED to role DTAGENT_VIEWER;

/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select *
from APP.V_SNOWPIPES_USAGE_HISTORY_INSTRUMENTED
limit 10;
 */
