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
-- This is a no-op stub for P_GRANT_IMPORTED_PRIVILEGES.
-- The real implementation lives in shares.sql/admin/051_p_grant_imported_privileges.sql
-- and requires the DTAGENT_ADMIN deployment scope (MANAGE GRANTS on ACCOUNT).
-- When the admin scope is deployed, it overwrites this stub with the working procedure.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace procedure DTAGENT_DB.APP.P_GRANT_IMPORTED_PRIVILEGES(db_name VARCHAR)
returns text
language sql
execute as caller
as
$$
BEGIN
    SYSTEM$LOG_WARN('P_GRANT_IMPORTED_PRIVILEGES: requires DTAGENT_ADMIN deployment scope; skipping grant for ' || :db_name);
    RETURN 'skipped: DTAGENT_ADMIN scope not deployed; cannot grant imported privileges on ' || :db_name;
END;
$$
;
grant usage on procedure DTAGENT_DB.APP.P_GRANT_IMPORTED_PRIVILEGES(VARCHAR) to role DTAGENT_VIEWER;

-- use role DTAGENT_OWNER;
-- call DTAGENT_DB.APP.P_GET_SHARES();
