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
use role DTAGENT_OWNER; use database DTAGENT_DB; use schema APP; use warehouse DTAGENT_WH; -- fixed DP-11334

create or replace procedure DTAGENT_DB.APP.P_EXPLAIN_PLAN()
returns table (
  query_id            VARCHAR,
  partitions_total    INT,
  partitions_assigned INT,
  bytes_assigned      INT,
  operation_id        STRING,
  operation_type      STRING,
  expressions         ARRAY,
  objects             ARRAY,
  parent_operator     ARRAY
)
language sql
execute as owner
as
DECLARE
  query     TEXT;
  rs        RESULTSET;
  rs_empty  RESULTSET DEFAULT (SELECT NULL::VARCHAR AS query_id, NULL::INT AS partitions_total, NULL::INT AS partitions_assigned, NULL::INT AS bytes_assigned, NULL::STRING AS operation_id, NULL::STRING AS operation_type, NULL::ARRAY AS expressions, NULL::ARRAY AS objects, NULL::ARRAY AS parent_operators WHERE 1=0);
  c_query   CURSOR FOR SELECT
    'WITH cte_explain_queries AS (' ||
        LISTAGG(REPLACE($$SELECT '<query_id>' as query_id, PARSE_JSON(SYSTEM$EXPLAIN_PLAN_JSON(query_id)) AS plan_json$$,
                        '<query_id>', t.query_id), ' UNION ALL ') ||
    ')
     select
        query_id                                    AS query_id,
        plan_json:"GlobalStats":"partitionsTotal"   AS partitions_total,
        plan_json:GlobalStats:partitionsAssigned    AS partitions_assigned,
        plan_json:GlobalStats:bytesAssigned         AS bytes_assigned,
        operation.value:id::STRING                  AS operation_id,
        operation.value:operation::STRING           AS operation_type,
        operation.value:expressions::ARRAY          AS expressions,
        operation.value:objects::ARRAY              AS objects,
        operation.value:parentOperators::ARRAY      AS parent_operators
     from cte_explain_queries,
        LATERAL FLATTEN(input => plan_json:Operations)  as operations,
        LATERAL FLATTEN(input => operations.value)      as operation
     '
    AS query
  FROM DTAGENT_DB.APP.V_QUERY_HISTORY t
  WHERE
    query_type in (
        'SELECT',
        'INSERT',
        'UPDATE'
    )
    and user_name not in ('SYSTEM')
    and (
        t.bytes_spilled_to_local_storage > 0 or
        t.bytes_spilled_to_remote_storage > 0 or
        t.queued_overload_time > 0 or
        t.queued_provisioning_time > 0 or
        t.partitions_scanned > 0.9*t.partitions_total or
        t.transaction_blocked_time > 0 or
        t.queued_repair_time > 0
    )
  HAVING count(t.query_id) > 0;
BEGIN
  OPEN c_query;
  FETCH c_query INTO query;
  CLOSE c_query;

  IF (:query IS NOT NULL)
  THEN
    rs := (EXECUTE IMMEDIATE :query);
    RETURN TABLE(rs);
  ELSE
    SYSTEM$LOG_WARN('P_EXPLAIN_PLAN returned no results: ' || :query);
    RETURN TABLE(rs_empty);
  END IF;

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM || :query);

    return TABLE(rs_empty);
END;
;

grant usage on procedure DTAGENT_DB.APP.P_EXPLAIN_PLAN() to role DTAGENT_VIEWER;

-- use role DTAGENT_VIEWER;
-- call DTAGENT_DB.APP.P_EXPLAIN_PLAN();
