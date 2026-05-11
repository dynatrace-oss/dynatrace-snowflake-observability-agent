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
-- APP.V_QUERY_COST_ATTRIBUTION_SUMMARY provides aggregated compute cost totals from
-- SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY, grouped by warehouse, user, and query tag.
-- Used by the query_cost_attribution context of the query_history plugin.
-- Requires USAGE_VIEWER or GOVERNANCE_VIEWER database role on the SNOWFLAKE database.
-- Note: QAH has an ~8h latency; data for recent queries will not yet appear here.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view APP.V_QUERY_COST_ATTRIBUTION_SUMMARY
as
select
    extract(epoch_nanosecond from max(qah.end_time))                                    as TIMESTAMP,
    concat('Query cost attribution summary for ', coalesce(qah.warehouse_name, ''))     as _MESSAGE,
    OBJECT_CONSTRUCT(
        'snowflake.warehouse.name',          qah.warehouse_name,
        'db.user',                           qah.user_name,
        'snowflake.query.tag',               qah.query_tag,
        'snowflake.query.hash',              qah.query_hash,
        'snowflake.query.parametrized_hash', qah.query_parameterized_hash
    )                                                                                   as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.cost_attribution.period_start',          min(qah.start_time),
        'snowflake.cost_attribution.period_end',            max(qah.end_time)
    )                                                                                   as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.credits.attributed_compute',             sum(qah.credits_attributed_compute),
        'snowflake.credits.query_acceleration',             sum(qah.credits_used_query_acceleration),
        'snowflake.cost_attribution.query_count',           count(*)
    )                                                                                   as METRICS
from
    SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY qah
where
    qah.start_time >= timeadd(
        hour,
        -CONFIG.F_GET_CONFIG_VALUE('plugins.query_history.query_cost_attribution.summary_window_hours', 24)::int,
        current_timestamp
    )
group by
    qah.warehouse_name,
    qah.user_name,
    qah.query_tag,
    qah.query_hash,
    qah.query_parameterized_hash
;
grant select on view APP.V_QUERY_COST_ATTRIBUTION_SUMMARY to role DTAGENT_VIEWER;

-- example call
/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select *
from APP.V_QUERY_COST_ATTRIBUTION_SUMMARY
limit 10;
 */
