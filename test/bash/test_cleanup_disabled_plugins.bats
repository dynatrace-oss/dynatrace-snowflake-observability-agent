#!/usr/bin/env bats
#
# Tests for inject_cleanup_for_excluded_plugins() in prepare_deploy_script.sh.
# Verifies that --options=cleanup_disabled drops views, procedures, and tasks for
# disabled plugins, handles removed_plugins.yml entries, and detects orphaned tasks
# via INFORMATION_SCHEMA.TASKS (injected as a Snowflake EXECUTE IMMEDIATE block).
#

setup() {
    # shellcheck disable=SC2154
    cd "$BATS_TEST_DIRNAME/../.." || exit

    TEST_CONFIG_FILE=$(mktemp)
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    TEST_SQL_FILE=$(mktemp)

    mkdir -p build/30_plugins build/09_upgrade

    # Minimal required build files
    cat > build/00_init.sql << 'EOSQL'
CREATE SCHEMA IF NOT EXISTS MAIN_SCHEMA;
--%PLUGIN:tasks:
CREATE TABLE tasks_table (id INT);
--%:PLUGIN:tasks
--%PLUGIN:snowpipes:
CREATE TABLE snowpipes_table (id INT);
--%:PLUGIN:snowpipes
--%PLUGIN:event_log:
CREATE TABLE event_log_table (id INT);
--%:PLUGIN:event_log
EOSQL

    cat > build/10_admin.sql << 'EOSQL'
CREATE ROLE IF NOT EXISTS DTAGENT_ADMIN;
EOSQL

    cat > build/20_setup.sql << 'EOSQL'
CREATE PROCEDURE main_proc() AS BEGIN SELECT 1; END;
EOSQL

    cat > build/40_config.sql << 'EOSQL'
SELECT 'config';
EOSQL

    cat > build/70_agents.sql << 'EOSQL'
CREATE PROCEDURE main_agent() RETURNS OBJECT LANGUAGE PYTHON RUNTIME_VERSION='3.13' PACKAGES=('requests') HANDLER='main' AS $$ def main(): pass $$;
EOSQL

    # tasks plugin: one task, one procedure, one view
    cat > build/30_plugins/tasks.sql << 'EOSQL'
--%PLUGIN:tasks:
CREATE OR REPLACE VIEW DTAGENT_DB.APP.V_TASKS AS SELECT * FROM INFORMATION_SCHEMA.TASKS;
CREATE OR REPLACE PROCEDURE DTAGENT_DB.APP.TASKS_HANDLER() RETURNS TABLE() LANGUAGE PYTHON AS $$ def h(): return [] $$;
CREATE OR REPLACE TASK DTAGENT_DB.APP.TASK_DTAGENT_TASKS WAREHOUSE = DTAGENT_WH SCHEDULE = '5 MINUTES' AS CALL tasks_handler();
--%:PLUGIN:tasks
EOSQL

    # snowpipes plugin: two tasks, one procedure, one view
    cat > build/30_plugins/snowpipes.sql << 'EOSQL'
--%PLUGIN:snowpipes:
CREATE OR REPLACE VIEW DTAGENT_DB.APP.V_SNOWPIPES AS SELECT * FROM INFORMATION_SCHEMA.PIPES;
CREATE OR REPLACE PROCEDURE DTAGENT_DB.APP.SNOWPIPES_HANDLER() RETURNS TABLE() LANGUAGE PYTHON AS $$ def h(): return [] $$;
CREATE OR REPLACE TASK DTAGENT_DB.APP.TASK_DTAGENT_SNOWPIPES WAREHOUSE = DTAGENT_WH SCHEDULE = '5 MINUTES' AS CALL snowpipes_handler();
CREATE OR REPLACE TASK DTAGENT_DB.APP.TASK_DTAGENT_SNOWPIPES_HISTORY WAREHOUSE = DTAGENT_WH SCHEDULE = '60 MINUTES' AS CALL snowpipes_history();
--%:PLUGIN:snowpipes
EOSQL

    # event_log plugin: enabled, should not appear in cleanup
    cat > build/30_plugins/event_log.sql << 'EOSQL'
--%PLUGIN:event_log:
CREATE OR REPLACE VIEW DTAGENT_DB.APP.V_EVENT_LOG AS SELECT * FROM INFORMATION_SCHEMA.QUERY_HISTORY;
CREATE OR REPLACE PROCEDURE DTAGENT_DB.APP.EVENT_LOG_HANDLER() RETURNS TABLE() LANGUAGE PYTHON AS $$ def h(): return [] $$;
CREATE OR REPLACE TASK DTAGENT_DB.APP.TASK_DTAGENT_EVENT_LOG WAREHOUSE = DTAGENT_WH SCHEDULE = '5 MINUTES' AS CALL event_log_handler();
--%:PLUGIN:event_log
EOSQL

    # Create a temporary removed_plugins.yml pointing to our test conf dir
    export REMOVED_PLUGINS_TEST_FILE=""
}

teardown() {
    rm -f "$TEST_CONFIG_FILE" "$TEST_SQL_FILE"
    rm -f build/00_init.sql build/10_admin.sql build/20_setup.sql build/40_config.sql build/70_agents.sql
    rm -rf build/09_upgrade build/30_plugins
    unset BUILD_CONFIG_FILE
    # Restore conf/removed_plugins.yml if we backed it up
    if [ -f conf/removed_plugins.yml.bats_backup ]; then
        mv conf/removed_plugins.yml.bats_backup conf/removed_plugins.yml
    fi
}

# Helper: config with one disabled plugin
_config_with_disabled() {
    local plugin="$1"
    cat > "$TEST_CONFIG_FILE" << EOF
[
  {"PATH": "plugins.deploy_disabled_plugins", "TYPE": "bool", "VALUE": false},
  {"PATH": "plugins.disabled_by_default",     "TYPE": "bool", "VALUE": false},
  {"PATH": "plugins.${plugin}.is_disabled",   "TYPE": "bool", "VALUE": true}
]
EOF
}

# Helper: config with all plugins enabled (nothing to clean up)
_config_all_enabled() {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {"PATH": "plugins.deploy_disabled_plugins", "TYPE": "bool", "VALUE": false},
  {"PATH": "plugins.disabled_by_default",     "TYPE": "bool", "VALUE": false}
]
EOF
}

# Helper: set up removed_plugins.yml with one removed plugin entry
_set_removed_plugins() {
    local plugin_name="$1"
    local task_name="$2"
    [ -f conf/removed_plugins.yml ] && cp conf/removed_plugins.yml conf/removed_plugins.yml.bats_backup
    cat > conf/removed_plugins.yml << EOF
removed_plugins:
  - name: ${plugin_name}
    removed_in_version: 0.9.0
    tasks:
      - ${task_name}
EOF
}

@test "no cleanup SQL when cleanup_disabled option not set" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" ""
    [ "$status" -eq 0 ]

    run grep -qi 'drop task if exists' "$TEST_SQL_FILE"
    [ "$status" -ne 0 ]
    run grep -qi 'drop procedure if exists' "$TEST_SQL_FILE"
    [ "$status" -ne 0 ]
    run grep -qi 'drop view if exists' "$TEST_SQL_FILE"
    [ "$status" -ne 0 ]
}

@test "no cleanup SQL when all plugins are enabled (even with cleanup_disabled)" {
    _config_all_enabled

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    run grep -qi 'drop task if exists.*TASK_DTAGENT' "$TEST_SQL_FILE"
    [ "$status" -ne 0 ]
}

@test "cleanup drops task for single-task disabled plugin (tasks)" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    grep -qi 'drop task if exists.*TASK_DTAGENT_TASKS' "$TEST_SQL_FILE"
}

@test "cleanup suspends task before dropping it" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    grep -qi 'alter task if exists.*TASK_DTAGENT_TASKS.*suspend' "$TEST_SQL_FILE"
    grep -qi 'drop task if exists.*TASK_DTAGENT_TASKS' "$TEST_SQL_FILE"
}

@test "cleanup drops both tasks for multi-task disabled plugin (snowpipes)" {
    _config_with_disabled "snowpipes"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    grep -qi 'drop task if exists.*TASK_DTAGENT_SNOWPIPES[^_]' "$TEST_SQL_FILE"
    grep -qi 'drop task if exists.*TASK_DTAGENT_SNOWPIPES_HISTORY' "$TEST_SQL_FILE"
}

@test "cleanup drops view for disabled plugin" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    grep -qi 'drop view if exists.*V_TASKS' "$TEST_SQL_FILE"
}

@test "cleanup drops procedure for disabled plugin" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    grep -qi 'drop procedure if exists.*TASKS_HANDLER' "$TEST_SQL_FILE"
}

@test "cleanup does not drop objects for enabled plugins" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    # event_log is enabled — must NOT appear in drop statements
    run grep -qi 'drop task if exists.*TASK_DTAGENT_EVENT_LOG' "$TEST_SQL_FILE"
    [ "$status" -ne 0 ]
    run grep -qi 'drop view if exists.*V_EVENT_LOG' "$TEST_SQL_FILE"
    [ "$status" -ne 0 ]
}

@test "cleanup uses correct role context (DTAGENT_OWNER)" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    grep -qi 'use role DTAGENT_OWNER' "$TEST_SQL_FILE"
}

@test "cleanup reads removed_plugins.yml and drops listed tasks" {
    _config_all_enabled
    _set_removed_plugins "legacy_metrics" "DTAGENT_DB.APP.TASK_DTAGENT_LEGACY_METRICS"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    grep -qi 'drop task if exists.*TASK_DTAGENT_LEGACY_METRICS' "$TEST_SQL_FILE"
}

@test "cleanup suspends removed plugin task before dropping" {
    _config_all_enabled
    _set_removed_plugins "legacy_metrics" "DTAGENT_DB.APP.TASK_DTAGENT_LEGACY_METRICS"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    grep -qi 'alter task if exists.*TASK_DTAGENT_LEGACY_METRICS.*suspend' "$TEST_SQL_FILE"
}

@test "cleanup injects orphan detection EXECUTE IMMEDIATE block for INFORMATION_SCHEMA.TASKS" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    grep -qi 'information_schema.tasks' "$TEST_SQL_FILE"
    grep -qi "task_name ilike 'TASK_DTAGENT_%'" "$TEST_SQL_FILE"
}

@test "orphan detection excludes known active plugin tasks" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    # Known active tasks (snowpipes, event_log) should appear in the exclusion list
    grep -qi 'TASK_DTAGENT_SNOWPIPES\|TASK_DTAGENT_EVENT_LOG' "$TEST_SQL_FILE"
}

@test "cleanup does not run for teardown scope" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "teardown" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    run grep -qi 'drop task if exists.*TASK_DTAGENT_TASKS' "$TEST_SQL_FILE"
    [ "$status" -ne 0 ]
}

@test "cleanup works with combined options (cleanup_disabled,skip_confirm)" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "skip_confirm,cleanup_disabled"
    [ "$status" -eq 0 ]

    grep -qi 'drop task if exists.*TASK_DTAGENT_TASKS' "$TEST_SQL_FILE"
}

@test "deploy log reports cleanup actions for disabled plugins" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual" "cleanup_disabled"
    [ "$status" -eq 0 ]

    [[ "$output" =~ \[deploy\]\ Cleaning\ up\ objects\ for\ disabled\ plugin:\ tasks ]]
}
