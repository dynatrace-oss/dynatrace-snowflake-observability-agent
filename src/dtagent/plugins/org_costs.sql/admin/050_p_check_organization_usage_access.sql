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
-- APP.P_CHECK_ORGANIZATION_USAGE_ACCESS() is a diagnostic helper for the org_costs plugin.
-- It verifies that the current account can read from SNOWFLAKE.ORGANIZATION_USAGE and returns
-- a status message.  Call this procedure manually after deployment to confirm the plugin has
-- the access it needs.
--
-- Requires the DTAGENT_VIEWER role to have IMPORTED PRIVILEGES on SNOWFLAKE (granted during init).
--
--%PLUGIN:org_costs:
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.P_CHECK_ORGANIZATION_USAGE_ACCESS()
returns text
language sql
execute as caller
as
$$
DECLARE
    probe_value INT DEFAULT 0;
BEGIN
    SELECT 1
    INTO   :probe_value
    FROM   SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY
    LIMIT  1;

    RETURN 'OK: SNOWFLAKE.ORGANIZATION_USAGE is accessible — org_costs plugin is ready.';

EXCEPTION
    WHEN STATEMENT_ERROR THEN
        RETURN 'WARNING: ' || SQLERRM ||
               ' — SNOWFLAKE.ORGANIZATION_USAGE is not accessible. ' ||
               'Ensure this account belongs to a Snowflake organization and that ' ||
               'DTAGENT_VIEWER has IMPORTED PRIVILEGES on the SNOWFLAKE database.';
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_CHECK_ORGANIZATION_USAGE_ACCESS() to role DTAGENT_VIEWER;
--%:PLUGIN:org_costs
