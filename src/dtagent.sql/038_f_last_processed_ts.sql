--
-- These materials contain confidential information and
-- trade secrets of Dynatrace LLC.  You shall
-- maintain the materials as confidential and shall not
-- disclose its contents to any third party except as may
-- be required by law or regulation.  Use, disclosure,
-- or reproduction is prohibited without the prior express
-- written permission of Dynatrace LLC.
-- 
-- All Compuware products listed within the materials are
-- trademarks of Dynatrace LLC.  All other company
-- or product names are trademarks of their respective owners.
-- 
-- Copyright (c) 2024 Dynatrace LLC.  All rights reserved.
--
--
--
use role DTAGENT_ADMIN; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH; 

create or replace function DTAGENT_DB.APP.F_LAST_PROCESSED_TS(t_measurement_source text) 
returns timestamp_ltz
AS
$$
  select NVL(max(LAST_TIMESTAMP), '1970-01-01'::timestamp_ltz)
  from DTAGENT_DB.STATUS.PROCESSED_MEASUREMENTS_LOG
  where MEASUREMENTS_SOURCE = t_measurement_source
$$
;

grant usage on function DTAGENT_DB.APP.F_LAST_PROCESSED_TS(text) to role DTAGENT_VIEWER;