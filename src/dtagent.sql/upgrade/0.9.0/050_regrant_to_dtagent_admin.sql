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
use role ACCOUNTADMIN;
grant ownership on table DTAGENT_DB.APP.TMP_USERS to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_USERS_HELPER to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_SHARES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_OUTBOUND_SHARES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_INBOUND_SHARES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_RESOURCE_MONITORS to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_WAREHOUSES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_QUERY_ACCELERATION_ESTIMATES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_BUDGETS to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_BUDGETS_RESOURCES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_BUDGETS_LIMITS to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_BUDGET_SPENDING to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_RECENT_QUERIES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_QUERY_OPERATOR_STATS to role DTAGENT_ADMIN copy current grants;
