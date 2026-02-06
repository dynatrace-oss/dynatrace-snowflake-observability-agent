#!/usr/bin/env bats

# Test that query_history plugin works correctly with and without event_log plugin

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    TEST_DIR=$(mktemp -d)
    TEST_CONFIG_FILE="$TEST_DIR/config.json"
    TEST_SQL_FILE="$TEST_DIR/deploy.sql"
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"
}

teardown() {
    rm -rf "$TEST_DIR"
    unset BUILD_CONFIG_FILE
    unset DTAGENT_TOKEN
}

@test "query_history plugin: trace columns excluded when event_log disabled" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
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
    "PATH": "plugins.query_history.is_enabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.event_log.is_enabled",
    "TYPE": "bool",
    "VALUE": false
  }
]
EOF

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "agents" "" "manual"
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
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
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
    "PATH": "plugins.query_history.is_enabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.event_log.is_enabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "agents" "" "manual"
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
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
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
    "PATH": "plugins.query_history.is_enabled",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.event_log.is_enabled",
    "TYPE": "bool",
    "VALUE": false
  }
]
EOF

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "agents" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should NOT contain query_history views when plugin is disabled
    ! grep -iq "V_QUERY_HISTORY" "$TEST_SQL_FILE"

    # Should NOT contain event_log table
    ! grep -iq "EVENT_LOG" "$TEST_SQL_FILE"
}

@test "query_history plugin: only event_log enabled (query_history disabled)" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
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
    "PATH": "plugins.query_history.is_enabled",
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

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "agents" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should NOT contain query_history views
    ! grep -iq "V_QUERY_HISTORY" "$TEST_SQL_FILE"

    # Should contain EVENT_LOG table (from event_log plugin)
    grep -iq "event.*table.*EVENT_LOG" "$TEST_SQL_FILE"
}
