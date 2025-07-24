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

