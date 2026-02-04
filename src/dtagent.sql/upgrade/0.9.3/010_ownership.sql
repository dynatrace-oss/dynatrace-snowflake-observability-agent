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
-- This will ensure ownership on all objects is properly transferred to DTAGENT_OWNER
-- according to what a clean install would create in version 0.9.3+
--
use role ACCOUNTADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

-- ============================================================================
-- CORE INFRASTRUCTURE OWNERSHIP
-- ============================================================================

create role if not exists DTAGENT_OWNER;
grant role DTAGENT_OWNER to role ACCOUNTADMIN;

-- Database and schemas
grant ownership on database DTAGENT_DB to role DTAGENT_OWNER copy current grants;
grant ownership on schema DTAGENT_DB.PUBLIC to role DTAGENT_OWNER copy current grants;
grant ownership on schema DTAGENT_DB.APP to role DTAGENT_OWNER copy current grants;
grant ownership on schema DTAGENT_DB.CONFIG to role DTAGENT_OWNER copy current grants;
grant ownership on schema DTAGENT_DB.STATUS to role DTAGENT_OWNER copy current grants;

-- Warehouse
grant ownership on warehouse DTAGENT_WH to role DTAGENT_OWNER copy current grants;

-- Resource monitor
--%OPTION:resource_monitor:
grant ownership on resource monitor DTAGENT_RS to role DTAGENT_OWNER copy current grants;
--%:OPTION:resource_monitor

-- Roles
grant ownership on role DTAGENT_VIEWER to role DTAGENT_OWNER copy current grants;
--%OPTION:dtagent_admin:
grant ownership on role DTAGENT_ADMIN to role DTAGENT_OWNER copy current grants;
--%:OPTION:dtagent_admin

-- Secrets, network rules, and integrations
grant ownership on secret DTAGENT_DB.CONFIG.DTAGENT_API_KEY to role DTAGENT_OWNER copy current grants;
grant ownership on network rule DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE to role DTAGENT_OWNER copy current grants;
grant ownership on integration DTAGENT_API_INTEGRATION to role DTAGENT_OWNER copy current grants;

-- ============================================================================
-- CONFIG SCHEMA OBJECTS - owned by DTAGENT_OWNER
-- ============================================================================

grant ownership on all tables in schema DTAGENT_DB.CONFIG to role DTAGENT_OWNER copy current grants;
grant ownership on all functions in schema DTAGENT_DB.CONFIG to role DTAGENT_OWNER copy current grants;
grant ownership on all procedures in schema DTAGENT_DB.CONFIG to role DTAGENT_OWNER copy current grants;

-- ============================================================================
-- STATUS SCHEMA OBJECTS - owned by DTAGENT_OWNER
-- ============================================================================

grant ownership on all tables in schema DTAGENT_DB.STATUS to role DTAGENT_OWNER copy current grants;
grant ownership on all views in schema DTAGENT_DB.STATUS to role DTAGENT_OWNER copy current grants;
grant ownership on all functions in schema DTAGENT_DB.STATUS to role DTAGENT_OWNER copy current grants;
grant ownership on all procedures in schema DTAGENT_DB.STATUS to role DTAGENT_OWNER copy current grants;

-- ============================================================================
-- APP SCHEMA OBJECTS - owned by DTAGENT_OWNER (except TASKS)
-- ============================================================================

grant ownership on all views in schema DTAGENT_DB.APP to role DTAGENT_OWNER copy current grants;
grant ownership on all tables in schema DTAGENT_DB.APP to role DTAGENT_OWNER copy current grants;
grant ownership on all procedures in schema DTAGENT_DB.APP to role DTAGENT_OWNER copy current grants;
grant ownership on all functions in schema DTAGENT_DB.APP to role DTAGENT_OWNER copy current grants;


