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
-- Upgrade: drop objects replaced or renamed in 0.9.5 (BDX-1965 / BDX-674):
--   V_QUERY_HISTORY             -> replaced by F_GET_QUERY_HISTORY() procedure
--   V_QUERY_HISTORY_INSTRUMENTED (old instrumentation-layer view)
--                               -> replaced by F_GET_QUERY_HISTORY() procedure
--   V_RECENT_QUERIES            -> renamed to V_QUERY_HISTORY_INSTRUMENTED (BDX-674)
--   P_GET_RECENT_QUERIES        -> interim procedure, superseded by F_GET_QUERY_HISTORY()
--   TMP_QUERY_HISTORY_PARAMS    -> interim staging table, no longer needed
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

--%PLUGIN:query_history:
drop view if exists DTAGENT_DB.APP.V_QUERY_HISTORY;
drop view if exists DTAGENT_DB.APP.V_RECENT_QUERIES;
drop procedure if exists DTAGENT_DB.APP.P_GET_RECENT_QUERIES();
drop table if exists DTAGENT_DB.APP.TMP_QUERY_HISTORY_PARAMS;
--%:PLUGIN:query_history
