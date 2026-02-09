#!/usr/bin/env bats

# Test that query_history plugin works correctly with and without event_log plugin

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    TEST_CONFIG_FILE=$(mktemp)
    TEST_SQL_FILE=$(mktemp)
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    # Ensure build directory exists with minimal structure
    mkdir -p build/09_upgrade build/30_plugins

    # Create minimal required SQL files for deployment script
    echo "-- Init code" > build/00_init.sql
    echo "SELECT 'init';" >> build/00_init.sql

    echo "-- Admin code" > build/10_admin.sql
    echo "SELECT 'admin';" >> build/10_admin.sql

    echo "-- Setup code" > build/20_setup.sql
    echo "SELECT 'setup';" >> build/20_setup.sql

    echo "-- Config code" > build/40_config.sql
    echo "SELECT 'config';" >> build/40_config.sql

    echo "-- Agent code" > build/70_agents.sql
    echo "SELECT 'agents';" >> build/70_agents.sql

    # Create query_history plugin SQL with conditional event_log integration
    cat > build/30_plugins/query_history.sql << 'EOSQL'
--%PLUGIN:query_history:
-- Query History Plugin
create or replace view APP.V_QUERY_HISTORY as
select
    qh.query_id,
    qh.query_text,
    qh.user_name,
    qh.start_time,
    qh.end_time
--%PLUGIN:event_log:
    , l.trace:span_id::varchar as _SPAN_ID
    , l.trace:trace_id::varchar as _TRACE_ID
    , l.trace
--%:PLUGIN:event_log
from SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh
--%PLUGIN:event_log:
left join STATUS.EVENT_LOG l
    on l.RECORD_TYPE = 'SPAN'
    and l.RESOURCE_ATTRIBUTES:"snow.query.id"::varchar = qh.query_id
--%:PLUGIN:event_log
where qh.end_time >= timeadd(minute, -120, current_timestamp);
--%:PLUGIN:query_history
EOSQL

    # Create event_log plugin SQL
    cat > build/30_plugins/event_log.sql << 'EOSQL'
--%PLUGIN:event_log:
-- Event Log Plugin
create event table if not exists STATUS.EVENT_LOG;
--%:PLUGIN:event_log
EOSQL
}

teardown() {
    rm -f "$TEST_CONFIG_FILE" "$TEST_SQL_FILE"
    rm -f build/00_init.sql build/10_admin.sql build/20_setup.sql build/40_config.sql build/70_agents.sql
    rm -f build/30_plugins/query_history.sql build/30_plugins/event_log.sql
    unset BUILD_CONFIG_FILE
    unset DTAGENT_TOKEN
}

@test "query_history plugin: trace columns excluded when event_log disabled" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  },
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.disabled_by_default",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.query_history.is_disabled",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.query_history.is_enabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.event_log.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should NOT contain EVENT_LOG join when event_log is disabled
    ! grep -iq "STATUS\.EVENT_LOG" "$TEST_SQL_FILE"

    # Should NOT contain trace column references in select
    ! grep -q "l\.trace" "$TEST_SQL_FILE"

    # Should NOT contain _SPAN_ID and _TRACE_ID extractions from trace
    ! grep -q "trace:span_id" "$TEST_SQL_FILE"
    ! grep -q "trace:trace_id" "$TEST_SQL_FILE"

    # Should still contain query_history views
    grep -iq "V_QUERY_HISTORY" "$TEST_SQL_FILE"
}

@test "query_history plugin: trace columns included when event_log enabled" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  },
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.disabled_by_default",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.query_history.is_disabled",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.query_history.is_enabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.event_log.is_disabled",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.event_log.is_enabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should contain EVENT_LOG join when event_log is enabled
    grep -iq "STATUS\.EVENT_LOG" "$TEST_SQL_FILE"

    # Should contain trace column references
    grep -q "l\.trace" "$TEST_SQL_FILE"

    # Should contain _SPAN_ID and _TRACE_ID extractions from trace
    grep -q "trace:span_id" "$TEST_SQL_FILE"
    grep -q "trace:trace_id" "$TEST_SQL_FILE"

    # Should contain query_history views
    grep -iq "V_QUERY_HISTORY" "$TEST_SQL_FILE"
}

@test "query_history plugin: both plugins disabled" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  },
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.disabled_by_default",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.query_history.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.event_log.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should NOT contain query_history views when plugin is disabled
    ! grep -i "create.*view.*V_QUERY_HISTORY" "$TEST_SQL_FILE"

    # Should NOT contain event_log table creation
    ! grep -i "create.*event.*table.*EVENT_LOG" "$TEST_SQL_FILE"
}

@test "query_history plugin: only event_log enabled (query_history disabled)" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  },
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.disabled_by_default",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.query_history.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.event_log.is_disabled",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.event_log.is_enabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should NOT contain query_history views
    ! grep -iq "V_QUERY_HISTORY" "$TEST_SQL_FILE"

    # Should contain EVENT_LOG table (from event_log plugin)
    grep -iq "event.*table.*EVENT_LOG" "$TEST_SQL_FILE"
}
