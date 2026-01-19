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
-- Initializing Dynatrace Snowflake Observability Agent by creating: view role
--
use role ACCOUNTADMIN;
create role if not exists DTAGENT_VIEWER;

-- viewer permissions are a subset of those for the admin
grant role DTAGENT_VIEWER to role DTAGENT_ADMIN;

grant MONITOR on ACCOUNT to role DTAGENT_VIEWER;
grant MONITOR USAGE on ACCOUNT to role DTAGENT_VIEWER;
grant MONITOR EXECUTION on ACCOUNT to role DTAGENT_VIEWER;

grant MODIFY SESSION LOG LEVEL on account to role DTAGENT_VIEWER;
grant IMPORTED PRIVILEGES on database SNOWFLAKE to role DTAGENT_VIEWER;

grant EXECUTE TASK on account to role DTAGENT_VIEWER;

grant ownership on role DTAGENT_VIEWER to role DTAGENT_OWNER;