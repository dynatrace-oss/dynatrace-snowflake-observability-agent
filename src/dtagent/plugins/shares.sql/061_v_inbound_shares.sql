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
create or replace view DTAGENT_DB.APP.V_INBOUND_SHARE_TABLES
as
select
    case
        when LEN(NVL(s.comment, '')) > 0 then s.comment
        else concat('Inbound share details for ', s.name)
    end                                                         as _MESSAGE,

    current_timestamp                                   as TIMESTAMP,

    OBJECT_CONSTRUCT(
        'snowflake.share.name',                         s.name,
        'db.namespace',                                 s.database_name,
        'snowflake.schema.name',                        ins.DETAILS:"TABLE_SCHEMA",
        'db.collection.name',                           ins.DETAILS:"TABLE_NAME"
    )                                                           as DIMENSIONS,

    OBJECT_CONSTRUCT(
        'snowflake.table.owner',                        ins.DETAILS:"TABLE_OWNER",
        'snowflake.table.type',                         ins.DETAILS:"TABLE_TYPE",
        'snowflake.table.clustering_key',               ins.DETAILS:"CLUSTERING_KEY",
        'snowflake.data.rows',                          ins.DETAILS:"ROW_COUNT",
        'snowflake.data.size',                          ins.DETAILS:"BYTES",
        'snowflake.table.retention_time',               ins.DETAILS:"RETENTION_TIME",
        'snowflake.table.last_ddl_by',                  ins.DETAILS:"LAST_DDL_BY",
        'snowflake.table.is_auto_clustering_on',        ins.DETAILS:"AUTO_CLUSTERING_ON",
        'snowflake.table.comment',                      ins.DETAILS:"COMMENT",
        'snowflake.table.is_transient',                 ins.DETAILS:"IS_TRANSIENT",
        'snowflake.table.is_temporary',                 ins.DETAILS:"IS_TEMPORARY",
        'snowflake.table.is_iceberg',                   ins.DETAILS:"IS_ICEBERG",
        'snowflake.table.is_dynamic',                   ins.DETAILS:"IS_DYNAMIC",
        'snowflake.table.is_hybrid',                    ins.DETAILS:"IS_HYBRID",
        'snowflake.share.has_db_deleted',               ins.DETAILS:"HAS_DB_DELETED",
        'snowflake.share.has_details_reported',         ins.IS_REPORTED,
        'snowflake.share.kind',                         s.kind,
        'snowflake.share.shared_from',                  s.owner_account,
        'snowflake.share.shared_to',                    s.given_to,
        'snowflake.share.owner',                        s.owner,
        'snowflake.share.is_secure_objects_only',       s.secure_objects_only,
        'snowflake.share.listing_global_name',          s.listing_global_name
    )                                                       as ATTRIBUTES,
    
    OBJECT_CONSTRUCT(
        'snowflake.table.created_on',                   extract(epoch_nanosecond from ins.DETAILS:"CREATED"::timestamp_ltz),
        'snowflake.table.update',                       extract(epoch_nanosecond from ins.DETAILS:"LAST_ALTERED"::timestamp_ltz),
        'snowflake.table.ddl',                          extract(epoch_nanosecond from ins.DETAILS:"LAST_DDL"::timestamp_ltz)
    )                                                       as EVENT_TIMESTAMPS

from DTAGENT_DB.APP.TMP_SHARES s
left join DTAGENT_DB.APP.TMP_INBOUND_SHARES ins
on s.name = ins.SHARE_NAME
where s.kind = 'INBOUND';

grant select on view DTAGENT_DB.APP.V_INBOUND_SHARE_TABLES to role DTAGENT_VIEWER;

-- select * from DTAGENT_DB.APP.V_INBOUND_SHARE_TABLES;