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

-- Grant ownership only if tables exist
DECLARE
    table_list ARRAY := [
        'TMP_USERS',
        'TMP_USERS_HELPER',
        'TMP_SHARES',
        'TMP_OUTBOUND_SHARES',
        'TMP_INBOUND_SHARES',
        'TMP_RESOURCE_MONITORS',
        'TMP_WAREHOUSES',
        'TMP_QUERY_ACCELERATION_ESTIMATES',
        'TMP_BUDGETS',
        'TMP_BUDGETS_RESOURCES',
        'TMP_BUDGETS_LIMITS',
        'TMP_BUDGET_SPENDING',
        'TMP_RECENT_QUERIES',
        'TMP_QUERY_OPERATOR_STATS'
    ];
    table_name VARCHAR;
    table_count INTEGER;
    grant_sql VARCHAR;
BEGIN
    FOR i IN 0 TO ARRAY_SIZE(:table_list) - 1 DO
        table_name := :table_list[i];

        -- Check if table exists
        SELECT COUNT(*)
        INTO :table_count
        FROM DTAGENT_DB.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = 'APP'
          AND TABLE_NAME = :table_name;

        -- Grant ownership if table exists
        IF (table_count > 0) THEN
            grant_sql := 'grant ownership on table DTAGENT_DB.APP.' || :table_name || ' to role DTAGENT_OWNER copy current grants';
            EXECUTE IMMEDIATE :grant_sql;
        END IF;
    END FOR;
END;