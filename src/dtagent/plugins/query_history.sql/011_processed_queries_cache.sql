--
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
-- This table keeps a log of queries that were already processed within last 2 hours. 
-- When a query is processed it will have PROCESSED_TIME not NULL.
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace table DTAGENT_DB.STATUS.PROCESSED_QUERIES_CACHE (
    START_TIME     timestamp_ltz not null,
    QUERY_ID       text not null,
    SESSION_ID     text not null,
    PROCESSED_TIME timestamp_ltz
);

-- grants to the DTAGENT_VIEWER

grant select, insert, update, delete on table STATUS.PROCESSED_QUERIES_CACHE to role DTAGENT_VIEWER;

