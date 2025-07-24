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
use role DTAGENT_ADMIN; use schema DTAGENT_DB.APP; use warehouse DTAGENT_WH; 

create or replace function DTAGENT_DB.APP.F_GET_CONFIG_VALUE(s_path text, default_value variant)
returns variant
language sql
AS 
$$
  select coalesce(
    (select value::variant
     from CONFIG.CONFIGURATIONS
     where PATH = s_path
     limit 1),
    default_value
  )
$$;

grant usage on function DTAGENT_DB.APP.F_GET_CONFIG_VALUE(text, variant) to role DTAGENT_VIEWER;
