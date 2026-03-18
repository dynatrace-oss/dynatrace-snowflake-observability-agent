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
-- APP.P_GRANT_IMPORTED_PRIVILEGES(VARCHAR) grants imported privileges on a
-- shared database to DTAGENT_VIEWER role.
--
-- !! Requires DTAGENT_ADMIN role (admin deployment scope) because
-- !! GRANT IMPORTED PRIVILEGES needs MANAGE GRANTS on ACCOUNT.
--
--%OPTION:dtagent_admin:
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.P_GRANT_IMPORTED_PRIVILEGES(db_name VARCHAR)
returns text
language sql
execute as caller
as
$$
DECLARE
    safe_identifier_re  TEXT DEFAULT '^[A-Za-z_][A-Za-z0-9_$]*$';
    db_name_q           TEXT DEFAULT '';
BEGIN
    IF (NOT REGEXP_LIKE(UPPER(:db_name), :safe_identifier_re)) THEN
        SYSTEM$LOG_WARN('P_GRANT_IMPORTED_PRIVILEGES: skipping invalid database name (unsafe identifier): ' || :db_name);
        RETURN 'skipped: unsafe database name ' || :db_name;
    END IF;

    db_name_q := '"' || UPPER(:db_name) || '"';
    EXECUTE IMMEDIATE concat('GRANT IMPORTED PRIVILEGES on DATABASE ', :db_name_q, ' TO ROLE DTAGENT_VIEWER');

    RETURN 'imported privileges granted on ' || :db_name;
EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);

    return SQLERRM;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_GRANT_IMPORTED_PRIVILEGES(VARCHAR) to role DTAGENT_VIEWER;
--%:OPTION:dtagent_admin
