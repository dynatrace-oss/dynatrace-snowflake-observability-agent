--
--
-- Copyright (c) 2026 Dynatrace Open Source
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
-- v0.9.5 Upgrade
-- Create STATUS.RESOURCE_MONITOR_THRESHOLD_STATE table if it does not yet exist.
-- This table persists the last-emitted threshold band per resource monitor and is
-- required by the credits quota threshold alerting feature introduced in 0.9.5.
-- Idempotent: safe to run against deployments that already have the table.
--
--%PLUGIN:resource_monitors:
use role DTAGENT_OWNER; use database DTAGENT_DB;

create table if not exists STATUS.RESOURCE_MONITOR_THRESHOLD_STATE (
    MONITOR_NAME    TEXT          NOT NULL,
    LAST_BAND       TEXT          NOT NULL,
    LAST_USED_PCT   NUMBER(6, 2)  NOT NULL,
    LAST_UPDATED    TIMESTAMP_LTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    constraint PK_RM_THRESHOLD_STATE primary key (MONITOR_NAME)
);

grant select, insert, update, delete on STATUS.RESOURCE_MONITOR_THRESHOLD_STATE to role DTAGENT_VIEWER;
--%:PLUGIN:resource_monitors
