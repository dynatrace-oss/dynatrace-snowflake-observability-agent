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
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace view DTAGENT_DB.APP.V_OUTBOUND_SHARE_TABLES
as
select
    case
        when LEN(NVL(s.comment, '')) > 0 then s.comment
        else concat('Outbound share details for ', s.name)  
    end                                                 as _MESSAGE,

    current_timestamp                                   as TIMESTAMP,

    OBJECT_CONSTRUCT(
        'snowflake.grant.name',                     os.name,
        'snowflake.share.name',                     s.name,
        'db.namespace',                             s.database_name
    )                                                   as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.grant.privilege',                os.privilege,
        'snowflake.grant.on',                       os.granted_on,
        'snowflake.grant.to',                       os.granted_to,
        'snowflake.grant.grantee',                  os.grantee_name,
        'snowflake.grant.option',                   os.grant_option,
        'snowflake.grant.by',                       os.granted_by,
        'snowflake.share.kind',                     s.kind,
        'snowflake.share.shared_from',              s.owner_account,
        'snowflake.share.shared_to',                s.given_to,
        'snowflake.share.owner',                    s.owner,
        'snowflake.share.is_secure_objects_only',   s.secure_objects_only,
        'snowflake.share.listing_global_name',      s.listing_global_name
    )                                                   as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.grant.created_on',               extract(epoch_nanosecond from os.CREATED_ON)
    )                                                   as EVENT_TIMESTAMPS
from DTAGENT_DB.APP.TMP_SHARES s
left join DTAGENT_DB.APP.TMP_OUTBOUND_SHARES os
on s.name = os.share_name
where s.kind = 'OUTBOUND';


grant select on view DTAGENT_DB.APP.V_OUTBOUND_SHARE_TABLES to role DTAGENT_VIEWER;

-- select * from DTAGENT_DB.APP.V_OUTBOUND_SHARE_TABLES;