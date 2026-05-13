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
-- STATUS.RESOURCE_MONITOR_THRESHOLD_STATE tracks the last-emitted threshold band per resource monitor.
-- Used by the threshold alerting logic to implement ACTIVE/CLOSED Davis event lifecycle.
--
--%PLUGIN:resource_monitors:
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create table if not exists STATUS.RESOURCE_MONITOR_THRESHOLD_STATE (
    MONITOR_NAME    TEXT        NOT NULL,
    LAST_BAND       TEXT        NOT NULL,
    LAST_USED_PCT   NUMBER(6,2) NOT NULL,
    LAST_UPDATED    TIMESTAMP_LTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    constraint PK_RM_THRESHOLD_STATE primary key (MONITOR_NAME)
);

grant select, insert, update, delete on STATUS.RESOURCE_MONITOR_THRESHOLD_STATE to role DTAGENT_VIEWER;
--%:PLUGIN:resource_monitors
