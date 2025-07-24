--
--
-- These materials contain confidential information and
-- trade secrets of Dynatrace LLC.  You shall
-- maintain the materials as confidential and shall not
-- disclose its contents to any third party except as may
-- be required by law or regulation.  Use, disclosure,
-- or reproduction is prohibited without the prior express
-- written permission of Dynatrace LLC.
-- 
-- All Compuware products listed within the materials are
-- trademarks of Dynatrace LLC.  All other company
-- or product names are trademarks of their respective owners.
-- 
-- Copyright (c) 2024 Dynatrace LLC.  All rights reserved.
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