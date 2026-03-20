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
-- APP.F_SNOWPIPES_INSTRUMENTED() returns real-time status and backlog for all monitored Snowpipes.
-- Uses SHOW PIPES + SYSTEM$PIPE_STATUS() (cloud-services only, no warehouse required).
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace transient table DTAGENT_DB.APP.TMP_SNOWPIPES_RESULT (
    TIMESTAMP       number,
    NAME            text,
    _MESSAGE        text,
    DIMENSIONS      variant,
    ATTRIBUTES      variant,
    METRICS         variant,
    EVENT_TIMESTAMPS variant
) DATA_RETENTION_TIME_IN_DAYS = 0;

grant select, insert, truncate on table DTAGENT_DB.APP.TMP_SNOWPIPES_RESULT to role DTAGENT_VIEWER;

create or replace procedure DTAGENT_DB.APP.F_SNOWPIPES_INSTRUMENTED()
returns table (
    TIMESTAMP       number,
    NAME            text,
    _MESSAGE        text,
    DIMENSIONS      variant,
    ATTRIBUTES      variant,
    METRICS         variant,
    EVENT_TIMESTAMPS variant
)
language sql
execute as caller
as
$$
DECLARE
     tr_tmp_snowpipes_table     TEXT DEFAULT 'truncate table if exists DTAGENT_DB.APP.TMP_SNOWPIPES_RESULT;';

    rs_pipes RESULTSET;
    rs_result RESULTSET;
BEGIN
    EXECUTE IMMEDIATE :tr_tmp_snowpipes_table;

    rs_pipes := (SHOW PIPES IN ACCOUNT ->>
        with cte_includes as (
            select distinct ci.VALUE as db_pattern
            from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ci
            where c.PATH = 'plugins.snowpipes.include'
        )
        , cte_excludes as (
            select distinct ce.VALUE as db_pattern
            from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ce
            where c.PATH = 'plugins.snowpipes.exclude'
        )
        select
            "database_name"                                             as DATABASE_NAME,
            "schema_name"                                               as SCHEMA_NAME,
            "name"                                                      as PIPE_NAME,
            "database_name" || '.' || "schema_name" || '.' || "name"    as QUALIFIED_NAME,
            "definition"                                                as DEFINITION,
            "owner"                                                     as OWNER,
            "notification_channel"                                      as NOTIFICATION_CHANNEL,
            "invalid_reason"                                            as INVALID_REASON,
            "created_on"                                                as CREATED_ON
        from $1
        where QUALIFIED_NAME LIKE ANY (select db_pattern from cte_includes)
        and not QUALIFIED_NAME LIKE ANY (select db_pattern from cte_excludes)
    );

    LET c_pipes CURSOR FOR rs_pipes;

    FOR r_pipe IN c_pipes DO
        LET pipe_fqn            TEXT    := r_pipe.QUALIFIED_NAME;
        LET pipe_db_name        TEXT    := r_pipe.DATABASE_NAME;
        LET pipe_schema_name    TEXT    := r_pipe.SCHEMA_NAME;
        LET pipe_owner          TEXT    := r_pipe.OWNER;
        LET pipe_definition     TEXT    := r_pipe.DEFINITION;
        LET pipe_notif_channel  TEXT    := r_pipe.NOTIFICATION_CHANNEL;
        LET pipe_invalid_reason TEXT    := r_pipe.INVALID_REASON;
        LET pipe_created_on     TEXT    := r_pipe.CREATED_ON;
        LET pipe_status         TEXT    := '';
        LET execution_state     TEXT    := NULL;
        LET pending_file_count  NUMBER  := 0;
        LET oldest_file_timestamp TEXT  := NULL;
        LET oldest_file_latency_ms NUMBER := NULL;
        LET last_ingested_ts    TEXT    := NULL;
        LET last_received_msg_ts TEXT   := NULL;

        BEGIN
            pipe_status := SYSTEM$PIPE_STATUS(:pipe_fqn);

            execution_state := PARSE_JSON(:pipe_status):executionState::STRING;
            pending_file_count := COALESCE(PARSE_JSON(:pipe_status):pendingFileCount::NUMBER, 0);
            oldest_file_timestamp := PARSE_JSON(:pipe_status):oldestFileTimestamp::STRING;
            last_ingested_ts := PARSE_JSON(:pipe_status):lastIngestedTimestamp::STRING;
            last_received_msg_ts := PARSE_JSON(:pipe_status):lastReceivedMessageTimestamp::STRING;

            IF (oldest_file_timestamp IS NOT NULL) THEN
                oldest_file_latency_ms := DATEDIFF(
                    'millisecond',
                    TRY_TO_TIMESTAMP_LTZ(:oldest_file_timestamp),
                    CURRENT_TIMESTAMP()
                );
            END IF;
        EXCEPTION
            WHEN statement_error THEN
                SYSTEM$LOG_WARN('SYSTEM$PIPE_STATUS failed for ' || :pipe_fqn || ': ' || SQLERRM);
                execution_state := 'UNKNOWN';
        END;

        LET target_table TEXT := NULL;
        BEGIN
            target_table := REGEXP_SUBSTR(:pipe_definition, 'INTO\\s+(\\S+)', 1, 1, 'ie', 1);
        EXCEPTION
            WHEN statement_error THEN
                target_table := NULL;
        END;

        insert into DTAGENT_DB.APP.TMP_SNOWPIPES_RESULT
        select
            extract(epoch_nanosecond from current_timestamp())                                          as TIMESTAMP,
            :pipe_fqn                                                                                   as NAME,
            concat('Snowpipe (', :pipe_fqn, ') status: ', COALESCE(:execution_state, 'N/A'))           as _MESSAGE,
            OBJECT_CONSTRUCT(
                'snowflake.pipe.name',          r_pipe.PIPE_NAME,
                'snowflake.pipe.full_name',     :pipe_fqn,
                'db.namespace',                 :pipe_db_name,
                'snowflake.schema.name',        :pipe_schema_name,
                'db.collection.name',           :target_table,
                'snowflake.pipe.owner',         :pipe_owner,
                'snowflake.pipe.status',        :execution_state
            )                                                                                           as DIMENSIONS,
            OBJECT_CONSTRUCT(
                'snowflake.pipe.definition',                    :pipe_definition,
                'snowflake.pipe.invalid_reason',                :pipe_invalid_reason,
                'snowflake.pipe.notification_channel',          :pipe_notif_channel,
                'snowflake.pipe.created_on',                    :pipe_created_on,
                'snowflake.pipe.execution_state',               :execution_state,
                'snowflake.pipe.last_ingested_timestamp',       :last_ingested_ts,
                'snowflake.pipe.last_received_message_timestamp', :last_received_msg_ts,
                'snowflake.pipe.oldest_file_timestamp',         :oldest_file_timestamp
            )                                                                                           as ATTRIBUTES,
            OBJECT_CONSTRUCT(
                'snowflake.pipe.files.pending',                 :pending_file_count,
                'snowflake.pipe.latency.oldest_file',           :oldest_file_latency_ms
            )                                                                                           as METRICS,
            OBJECT_CONSTRUCT(
                'snowflake.pipe.created_on',                    extract(epoch_nanosecond from TRY_TO_TIMESTAMP_LTZ(:pipe_created_on))
            )                                                                                           as EVENT_TIMESTAMPS
        ;
    END FOR;

    rs_result := (select * from DTAGENT_DB.APP.TMP_SNOWPIPES_RESULT order by TIMESTAMP asc);
    RETURN TABLE(rs_result);
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.F_SNOWPIPES_INSTRUMENTED() to role DTAGENT_VIEWER;

/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select *
from table(DTAGENT_DB.APP.F_SNOWPIPES_INSTRUMENTED())
limit 10;
 */
