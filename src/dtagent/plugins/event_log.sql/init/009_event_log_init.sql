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
-- Configuring event logs table
-- and enable logs collection on the account level
--
use role ACCOUNTADMIN; use database DTAGENT_DB; use schema STATUS; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.SETUP_EVENT_TABLE()
returns TEXT
language SQL
execute as CALLER
as
$$
DECLARE
    -- account-level EVENT_TABLE parameter value ('' = none set)
    s_account_et           TEXT    DEFAULT '';
    -- STATUS.EVENT_LOG object type detection
    is_status_et_a_table   BOOLEAN DEFAULT FALSE;   -- any TABLE (BASE TABLE or EVENT TABLE)
    is_status_event_table  BOOLEAN DEFAULT FALSE;   -- specifically an EVENT TABLE
    -- ownership and capability flags
    b_we_own_account_et    BOOLEAN DEFAULT FALSE;   -- DSOA owns/set the account-level event table
    b_has_log_event_level  BOOLEAN DEFAULT FALSE;
    n_param_rows           INTEGER DEFAULT 0;
    b_discover_db_tables   BOOLEAN DEFAULT FALSE;
    b_any_db_et_at_init    BOOLEAN DEFAULT FALSE;   -- preliminary scan: any DB-level override found?

    -- per-database event table discovery (Steps 1 and 4a)
    n_override_count      INTEGER DEFAULT 0;
    s_override_dbs_csv    TEXT    DEFAULT '';
    s_union_parts         TEXT    DEFAULT '';
    s_db_name             TEXT    DEFAULT '';
    s_db_et               TEXT    DEFAULT '';
    s_view_sql            TEXT    DEFAULT '';
    a_db_patterns         ARRAY   DEFAULT ARRAY_CONSTRUCT();
    a_filtered_dbs        ARRAY   DEFAULT ARRAY_CONSTRUCT();
    a_all_dbs             ARRAY   DEFAULT ARRAY_CONSTRUCT();
BEGIN
  -- Step 0: Read current account and schema state
  show PARAMETERS like 'EVENT_TABLE' in ACCOUNT;
  select "value" into s_account_et from TABLE(result_scan(last_query_id()));

  -- Detect whether LOG_EVENT_LEVEL parameter is supported (Snowflake BCR Bundle 2026_02+).
  BEGIN
    show PARAMETERS like 'LOG_EVENT_LEVEL' in ACCOUNT;
    select count(*) into n_param_rows from TABLE(result_scan(last_query_id()));
    b_has_log_event_level := (n_param_rows > 0);
  EXCEPTION
    WHEN OTHER THEN
      b_has_log_event_level := FALSE;
  END;

  select TABLE_TYPE like '%TABLE' into is_status_et_a_table
    from DTAGENT_DB.INFORMATION_SCHEMA.TABLES
    where TABLE_SCHEMA = 'STATUS' and TABLE_NAME = 'EVENT_LOG';

  select TABLE_TYPE = 'EVENT TABLE' into is_status_event_table
    from DTAGENT_DB.INFORMATION_SCHEMA.TABLES
    where TABLE_SCHEMA = 'STATUS' and TABLE_NAME = 'EVENT_LOG';

  b_we_own_account_et := (s_account_et = '' OR s_account_et = 'DTAGENT_DB.STATUS.EVENT_LOG');

  -- F_GET_CONFIG_VALUE may not exist at init time; fall back to false on any error.
  BEGIN
    b_discover_db_tables := coalesce(
        DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.event_log.discover_db_event_tables', false::variant)::boolean,
        false
    );
  EXCEPTION
    WHEN OTHER THEN
      b_discover_db_tables := false;
  END;

  -- Step 1: DB-level discovery (only when discover_db_tables=true via config)
  IF (:b_discover_db_tables) THEN
    -- Read allow-list once; avoids repeated F_GET_CONFIG_VALUE calls inside the loop.
    a_db_patterns := DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.event_log.databases', [])::ARRAY;
    SHOW DATABASES;
    -- Materialize before looping: RESULT_SCAN cursor field access (row.col) is unreliable in FOR loops.
    a_filtered_dbs := COALESCE(
        (
            SELECT ARRAY_AGG("name"::TEXT)
            FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
            WHERE (
                array_size(:a_db_patterns) = 0
                OR EXISTS (
                    SELECT 1
                    FROM TABLE(FLATTEN(:a_db_patterns)) f
                    WHERE "name" LIKE f.VALUE::varchar
                )
            )
        ),
        ARRAY_CONSTRUCT()
    );
    FOR i_db IN 0 TO array_size(:a_filtered_dbs) - 1 DO
        s_db_name := :a_filtered_dbs[i_db]::TEXT;
        s_db_et   := '';

        BEGIN
            EXECUTE IMMEDIATE 'show parameters like ''EVENT_TABLE'' in database "' || :s_db_name || '"';
            -- COALESCE avoids NO_DATA_FOUND when no DATABASE-level override exists
            SELECT COALESCE(MAX("value"), '')
              INTO s_db_et
              FROM TABLE(result_scan(last_query_id()))
             WHERE "level" = 'DATABASE';
        EXCEPTION
            WHEN OTHER THEN
                SYSTEM$LOG_WARN('Could not check event table override for DB ' || :s_db_name || ': ' || SQLERRM);
        END;

        IF (:s_db_et != '') THEN
            n_override_count := n_override_count + 1;

            BEGIN
                EXECUTE IMMEDIATE 'grant select on table ' || :s_db_et || ' to role DTAGENT_VIEWER';
            EXCEPTION
                WHEN OTHER THEN
                    SYSTEM$LOG_WARN('Could not grant select on override event table ' || :s_db_et || ': ' || SQLERRM);
            END;

            IF (:s_override_dbs_csv != '') THEN
                s_override_dbs_csv := :s_override_dbs_csv || ', ';
            END IF;
            s_override_dbs_csv := :s_override_dbs_csv || '''' || :s_db_name || '''';

            s_union_parts := :s_union_parts ||
                ' UNION ALL SELECT TIMESTAMP, START_TIMESTAMP, OBSERVED_TIMESTAMP, TRACE, RESOURCE,' ||
                ' OBJECT_INSERT(RESOURCE_ATTRIBUTES, ''_dsoa_source_table'', ''' || :s_db_et || '''::VARIANT) AS RESOURCE_ATTRIBUTES,' ||
                ' SCOPE, SCOPE_ATTRIBUTES, RECORD_TYPE, RECORD, RECORD_ATTRIBUTES, VALUE' ||
                ' FROM ' || :s_db_et;
        END IF;
    END FOR;

    IF (:n_override_count > 0) THEN
        -- Replace any existing STATUS.EVENT_LOG with the UNION ALL view
        IF (:b_we_own_account_et AND :is_status_et_a_table) THEN
            IF (:is_status_event_table) THEN
                -- Real event table: attempt to unset account parameter (requires ACCOUNTADMIN)
                BEGIN
                    ALTER ACCOUNT UNSET EVENT_TABLE;
                EXCEPTION WHEN OTHER THEN
                    SYSTEM$LOG_WARN('Could not unset account EVENT_TABLE: ' || SQLERRM);
                END;
            END IF;
            -- DTAGENT_OWNER owns the table (event or regular placeholder after ownership grant); drop it
            DROP TABLE IF EXISTS DTAGENT_DB.STATUS.EVENT_LOG;
            is_status_et_a_table := FALSE;
            is_status_event_table := FALSE;
        ELSE
            drop view if exists DTAGENT_DB.STATUS.EVENT_LOG;
        END IF;

        -- Build UNION ALL view SQL
        IF (NOT :b_we_own_account_et) THEN
            -- External account-level table: account branch excludes override DBs to avoid duplication
            s_view_sql :=
                'SELECT TIMESTAMP, START_TIMESTAMP, OBSERVED_TIMESTAMP, TRACE, RESOURCE,' ||
                ' OBJECT_INSERT(RESOURCE_ATTRIBUTES, ''_dsoa_source_table'', ''' || :s_account_et || '''::VARIANT) AS RESOURCE_ATTRIBUTES,' ||
                ' SCOPE, SCOPE_ATTRIBUTES, RECORD_TYPE, RECORD, RECORD_ATTRIBUTES, VALUE' ||
                ' FROM ' || :s_account_et ||
                ' WHERE COALESCE(RESOURCE_ATTRIBUTES[''snow.database.name'']::VARCHAR, '''') NOT IN (' || :s_override_dbs_csv || ')' ||
                :s_union_parts;
        ELSE
            -- No external account table (ours was dropped or never existed); view is DB-level overrides only.
            -- s_union_parts starts with ' UNION ALL '; strip the leading 11 chars to get a valid SELECT.
            s_view_sql := SUBSTR(:s_union_parts, 12);
        END IF;

        EXECUTE IMMEDIATE 'create or replace view DTAGENT_DB.STATUS.EVENT_LOG as ' || :s_view_sql;
        grant ownership on view DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_OWNER revoke current grants;
        grant select on view DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_VIEWER;

        RETURN 'Dynatrace Snowflake Observability Agent uses ' || :n_override_count::TEXT || ' DB-level event table override(s)';
    END IF;
    -- n_override_count == 0: no DB-level overrides found in filtered set; fall through to Steps 2/3/4
  END IF;

  -- Step 2: External account-level event table (not owned by DSOA)
  IF (NOT :b_we_own_account_et) THEN
    -- attempt to grant select on the account event table; ignore failures for read-only or Snowflake-managed tables
    BEGIN
      EXECUTE IMMEDIATE concat('grant select on table ', :s_account_et, ' to role DTAGENT_VIEWER');
    EXCEPTION
      WHEN OTHER THEN
        SYSTEM$LOG_WARN(concat('Could not grant select on table ', :s_account_et, ' to role DTAGENT_VIEWER: ', SQLERRM));
    END;

    IF (:is_status_et_a_table) THEN
      DROP TABLE IF EXISTS DTAGENT_DB.STATUS.EVENT_LOG;
    END IF;
    EXECUTE IMMEDIATE concat('create or replace view DTAGENT_DB.STATUS.EVENT_LOG as select * from ', :s_account_et);
    grant ownership on view DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_OWNER revoke current grants;
    grant select on view DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_VIEWER;

    RETURN 'Dynatrace Snowflake Observability Agent will use predefined Event table';
  END IF;

  -- Step 3: Existing DSOA-owned event table — keep it, just ensure grants are current
  IF (:is_status_event_table) THEN
    grant select, delete on table DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_VIEWER;
    RETURN 'Dynatrace Snowflake Observability Agent keeping existing Event table';
  END IF;

  -- Step 4: No suitable STATUS.EVENT_LOG exists; need to create one.
  -- Drop any stale view or regular placeholder table from a prior failed attempt.
  drop view if exists DTAGENT_DB.STATUS.EVENT_LOG;
  IF (:is_status_et_a_table AND NOT :is_status_event_table) THEN
    DROP TABLE IF EXISTS DTAGENT_DB.STATUS.EVENT_LOG;
  END IF;

  -- Step 4a: Preliminary unconstrained DB scan.
  -- Scan ALL visible databases for DB-level EVENT_TABLE overrides (no allow-list, no config needed).
  -- If any exist, create a placeholder regular table instead of a real event table — regular tables
  -- are safely droppable by DTAGENT_OWNER when the config phase later builds a UNION ALL view,
  -- avoiding the need for ACCOUNTADMIN to unset the account-level event table pointer.
  SHOW DATABASES;
  a_all_dbs := COALESCE(
      (SELECT ARRAY_AGG("name"::TEXT) FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))),
      ARRAY_CONSTRUCT()
  );
  FOR i_scan IN 0 TO array_size(:a_all_dbs) - 1 DO
      IF (NOT :b_any_db_et_at_init) THEN
          s_db_name := :a_all_dbs[i_scan]::TEXT;
          s_db_et   := '';
          BEGIN
              EXECUTE IMMEDIATE 'SHOW PARAMETERS LIKE ''EVENT_TABLE'' IN DATABASE "' || :s_db_name || '"';
              SELECT COALESCE(MAX("value"), '')
                INTO s_db_et
                FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
               WHERE "level" = 'DATABASE';
              IF (:s_db_et != '') THEN
                  b_any_db_et_at_init := TRUE;
              END IF;
          EXCEPTION
              WHEN OTHER THEN NULL;
          END;
      END IF;
  END FOR;

  -- Step 4b: Create event table or placeholder based on preliminary scan result
  IF (:b_any_db_et_at_init) THEN
    -- DB-level event tables detected at init. Create a placeholder regular table so plugin
    -- views compile and queries work. Enable discover_db_tables=true in config to activate
    -- the UNION ALL view that merges all DB-level event tables.
    SYSTEM$LOG_INFO('DB-level event table override(s) found. Creating placeholder regular table; enable discover_db_tables=true to activate UNION ALL view.');
    create table if not exists DTAGENT_DB.STATUS.EVENT_LOG (
      TIMESTAMP           TIMESTAMP_LTZ,
      START_TIMESTAMP     TIMESTAMP_LTZ,
      OBSERVED_TIMESTAMP  TIMESTAMP_LTZ,
      TRACE               VARIANT,
      RESOURCE            VARIANT,
      RESOURCE_ATTRIBUTES VARIANT,
      SCOPE               VARIANT,
      SCOPE_ATTRIBUTES    VARIANT,
      RECORD_TYPE         VARCHAR,
      RECORD              VARIANT,
      RECORD_ATTRIBUTES   VARIANT,
      VALUE               VARIANT
    );
    grant ownership on table DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_OWNER revoke current grants;
    grant select, delete on table DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_VIEWER;
    RETURN 'Dynatrace Snowflake Observability Agent created placeholder regular table (DB-level event tables found; set discover_db_tables=true to enable UNION ALL view)';
  ELSE
    BEGIN
      -- Standard path: create a proper event table and register it at the account level.
      create event table DTAGENT_DB.STATUS.EVENT_LOG;
      alter account set event_table = DTAGENT_DB.STATUS.EVENT_LOG;
      grant ownership on table DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_OWNER revoke current grants;
      grant select, delete on table DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_VIEWER;
      grant modify session LOG LEVEL on account to role DTAGENT_VIEWER;
      alter account set log_level = WARN;
      IF (:b_has_log_event_level) THEN
        alter account set LOG_EVENT_LEVEL = INFO;
        grant modify LOG EVENT LEVEL on account to role DTAGENT_VIEWER;
      END IF;
      RETURN 'Dynatrace Snowflake Observability Agent has setup own Event table';
    EXCEPTION WHEN OTHER THEN
      -- ACCOUNTADMIN not available (e.g. called from config context as DTAGENT_OWNER).
      -- Create a same-schema regular table so plugin views compile and queries work.
      -- No events will be auto-captured; redeploy with ACCOUNTADMIN to complete setup.
      SYSTEM$LOG_WARN('Could not create event table (' || SQLERRM || '). Creating placeholder regular table.');
      create table if not exists DTAGENT_DB.STATUS.EVENT_LOG (
        TIMESTAMP           TIMESTAMP_LTZ,
        START_TIMESTAMP     TIMESTAMP_LTZ,
        OBSERVED_TIMESTAMP  TIMESTAMP_LTZ,
        TRACE               VARIANT,
        RESOURCE            VARIANT,
        RESOURCE_ATTRIBUTES VARIANT,
        SCOPE               VARIANT,
        SCOPE_ATTRIBUTES    VARIANT,
        RECORD_TYPE         VARCHAR,
        RECORD              VARIANT,
        RECORD_ATTRIBUTES   VARIANT,
        VALUE               VARIANT
      );
      grant select, delete on table DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_VIEWER;
      RETURN 'Dynatrace Snowflake Observability Agent created placeholder regular table (ACCOUNTADMIN required for event capture)';
    END;
  END IF;
exception
    when statement_error then
        return SQLERRM;
end
$$
;

-- Call SETUP_EVENT_TABLE() immediately so STATUS.EVENT_LOG exists before plugin views are compiled
-- in 30_plugins/event_log.sql.  When F_GET_CONFIG_VALUE is not yet available (init phase) the
-- procedure falls back to the simple-view/event-table path (discover_db_tables = false).
-- UPDATE_FROM_CONFIGURATIONS() will call SETUP_EVENT_TABLE() again once real config values are
-- loaded, picking up discover_db_tables = true if configured.
call DTAGENT_DB.APP.SETUP_EVENT_TABLE();


--
-- EXAMPLE CALL:
/*
select *
from DTAGENT_DB.STATUS.EVENT_LOG
-- where
--   SCOPE['name'] = 'DTAGENT'
--   and RECORD['severity_text'] = 'DEBUG'
--   and RECORD_TYPE = 'LOG'
order by timestamp desc
limit 10;
 */
