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
-- Migrate configuration paths from flat structure to nested snowflake structure
-- This upgrade script refactors configuration keys to support the new hierarchical structure
--
use role DTAGENT_OWNER; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

-- Migrate core.snowflake_account_name to core.snowflake.account_name
update DTAGENT_DB.CONFIG.CONFIGURATIONS
set PATH = 'core.snowflake.account_name'
where PATH = 'core.snowflake_account_name';

-- Migrate core.snowflake_host_name to core.snowflake.host_name
update DTAGENT_DB.CONFIG.CONFIGURATIONS
set PATH = 'core.snowflake.host_name'
where PATH = 'core.snowflake_host_name';

-- Migrate core.snowflake_credit_quota to core.snowflake.resource_monitor.credit_quota
update DTAGENT_DB.CONFIG.CONFIGURATIONS
set PATH = 'core.snowflake.resource_monitor.credit_quota'
where PATH = 'core.snowflake_credit_quota';

-- Migrate core.snowflake_data_retention_time_in_days to core.snowflake.database.data_retention_time_in_days
update DTAGENT_DB.CONFIG.CONFIGURATIONS
set PATH = 'core.snowflake.database.data_retention_time_in_days'
where PATH = 'core.snowflake_data_retention_time_in_days';

-- Log the migration
insert into DTAGENT_DB.STATUS.PROCESSED_MEASUREMENTS_LOG (
    TIMESTAMP_UTC,
    PLUGIN,
    SCOPE,
    STATUS
) values (
    current_timestamp(),
    'upgrade',
    'config_migration_0.9.3',
    'Configuration paths migrated to nested snowflake structure'
);
