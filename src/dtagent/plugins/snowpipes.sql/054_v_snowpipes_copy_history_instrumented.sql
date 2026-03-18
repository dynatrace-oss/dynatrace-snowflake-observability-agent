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
-- APP.V_SNOWPIPES_COPY_HISTORY_INSTRUMENTED — Deep-mode view on ACCOUNT_USAGE.COPY_HISTORY.
-- Provides per-file ingestion details: rows, errors, latency, diagnostics.
-- Filtered to pipe-driven loads only (PIPE_NAME IS NOT NULL).
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view APP.V_SNOWPIPES_COPY_HISTORY_INSTRUMENTED
as
with cte_copy_history as (
    select *
    from SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
    where PIPE_NAME IS NOT NULL
    and LAST_LOAD_TIME >= GREATEST(
        DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('snowpipes_copy_history'),
        TIMEADD(
            HOUR,
            -1 * CONFIG.F_GET_CONFIG_VALUE('plugins.snowpipes.lookback_hours', 4)::INT,
            CURRENT_TIMESTAMP()
        )
    )
)
select
    EXTRACT(EPOCH_NANOSECOND FROM LAST_LOAD_TIME::TIMESTAMP_LTZ)                                    as TIMESTAMP,
    PIPE_NAME                                                                                        as NAME,
    CONCAT('Snowpipe load: ', FILE_NAME, ' -> ', TABLE_NAME, ' (', STATUS, ')')                     as _MESSAGE,
    OBJECT_CONSTRUCT(
        'snowflake.pipe.name',          PIPE_NAME,
        'snowflake.pipe.catalog_name',  PIPE_CATALOG_NAME,
        'snowflake.pipe.schema_name',   PIPE_SCHEMA_NAME,
        'db.namespace',                 TABLE_CATALOG_NAME,
        'snowflake.schema.name',        TABLE_SCHEMA_NAME,
        'db.collection.name',           TABLE_NAME
    )                                                                                                as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.copy.file_name',                     FILE_NAME,
        'snowflake.copy.stage_location',                STAGE_LOCATION,
        'snowflake.copy.status',                        STATUS,
        'snowflake.copy.first_error.message',           FIRST_ERROR_MESSAGE,
        'snowflake.copy.first_error.line_number',       FIRST_ERROR_LINE_NUMBER,
        'snowflake.copy.first_error.column_name',       FIRST_ERROR_COLUMN_NAME,
        'snowflake.copy.first_error.character_position', FIRST_ERROR_CHARACTER_POS,
        'snowflake.copy.errors.limit',                  ERROR_LIMIT,
        'snowflake.copy.pipe.received_time',            PIPE_RECEIVED_TIME,
        'snowflake.copy.first_commit_time',             FIRST_COMMIT_TIME
    )                                                                                                as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.pipe.files.ingested',    CASE WHEN UPPER(STATUS) = 'LOADED' THEN 1 ELSE 0 END,
        'snowflake.pipe.rows.loaded',       ROW_COUNT,
        'snowflake.pipe.rows.parsed',       ROW_PARSED,
        'snowflake.pipe.errors',            CASE WHEN UPPER(STATUS) IN ('LOAD_FAILED', 'PARTIALLY_LOADED') THEN 1 ELSE 0 END,
        'snowflake.pipe.ingest.latency',
            CASE WHEN PIPE_RECEIVED_TIME IS NOT NULL AND LAST_LOAD_TIME IS NOT NULL
                 THEN DATEDIFF('millisecond', PIPE_RECEIVED_TIME, LAST_LOAD_TIME) ELSE NULL END,
        'snowflake.copy.errors',            ERROR_COUNT,
        'snowflake.copy.file_size',         FILE_SIZE,
        'snowflake.copy.bytes_billed',      BYTES_BILLED
    )                                                                                                as METRICS
from cte_copy_history
order by TIMESTAMP asc
;

grant select on view APP.V_SNOWPIPES_COPY_HISTORY_INSTRUMENTED to role DTAGENT_VIEWER;

/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select *
from APP.V_SNOWPIPES_COPY_HISTORY_INSTRUMENTED
limit 10;
 */
