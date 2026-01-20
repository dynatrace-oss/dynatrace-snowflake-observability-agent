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
-- Initializing Dynatrace Snowflake Observability Agent by creating: warehouse
--
use role ACCOUNTADMIN;

-- ensure a warehouse is usable by provider
create warehouse if not exists DTAGENT_WH with
    warehouse_type=STANDARD
    warehouse_size=XSMALL
    scaling_policy=ECONOMY
    initially_suspended=TRUE
    auto_resume=TRUE
    auto_suspend=60;
grant ownership on warehouse DTAGENT_WH to role DTAGENT_OWNER revoke current grants;
-- FIXME: check config updates to makes sure they are run as owner
grant modify on warehouse DTAGENT_WH to role DTAGENT_OWNER;
grant usage, operate on warehouse DTAGENT_WH to role DTAGENT_VIEWER;

