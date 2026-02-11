#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    TEST_DIR=$(mktemp -d)
}

teardown() {
    rm -rf "$TEST_DIR"
    unset BUILD_CONFIG_FILE
}

@test "list_options_to_exclude: both admin and resource_monitor disabled" {
    cat > "$TEST_DIR/config.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test.snowflake.com
    host_name: test.snowflake.com
    roles:
      admin: "-"
    resource_monitor:
      name: "-"
      credit_quota: 5
EOF

    # Prepare config JSON
    cat "$TEST_DIR/config.yml" | yq -o json '.' | jq -r '
        def flatten:
          . as $in
          | (paths(scalars|true) as $p
          | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
          | $out;
        [flatten]
      ' > "$TEST_DIR/config.json"

    export BUILD_CONFIG_FILE="$TEST_DIR/config.json"

    run ./scripts/deploy/list_options_to_exclude.sh
    [ "$status" -eq 0 ]
    [[ "$output" == *"dtagent_admin"* ]]
    [[ "$output" == *"resource_monitor"* ]]
}

@test "list_options_to_exclude: only admin disabled" {
    cat > "$TEST_DIR/config.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test.snowflake.com
    host_name: test.snowflake.com
    roles:
      admin: "-"
    resource_monitor:
      name: "CUSTOM_RS"
      credit_quota: 5
EOF

    cat "$TEST_DIR/config.yml" | yq -o json '.' | jq -r '
        def flatten:
          . as $in
          | (paths(scalars|true) as $p
          | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
          | $out;
        [flatten]
      ' > "$TEST_DIR/config.json"

    export BUILD_CONFIG_FILE="$TEST_DIR/config.json"

    run ./scripts/deploy/list_options_to_exclude.sh
    [ "$status" -eq 0 ]
    [[ "$output" == *"dtagent_admin"* ]]
    [[ "$output" != *"resource_monitor"* ]]
}

@test "list_options_to_exclude: only resource_monitor disabled" {
    cat > "$TEST_DIR/config.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test.snowflake.com
    host_name: test.snowflake.com
    roles:
      admin: "CUSTOM_ADMIN"
    resource_monitor:
      name: "-"
      credit_quota: 5
EOF

    cat "$TEST_DIR/config.yml" | yq -o json '.' | jq -r '
        def flatten:
          . as $in
          | (paths(scalars|true) as $p
          | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
          | $out;
        [flatten]
      ' > "$TEST_DIR/config.json"

    export BUILD_CONFIG_FILE="$TEST_DIR/config.json"

    run ./scripts/deploy/list_options_to_exclude.sh
    [ "$status" -eq 0 ]
    [[ "$output" != *"dtagent_admin"* ]]
    [[ "$output" == *"resource_monitor"* ]]
}

@test "list_options_to_exclude: both enabled (empty output)" {
    cat > "$TEST_DIR/config.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test.snowflake.com
    host_name: test.snowflake.com
    roles:
      admin: "DTAGENT_ADMIN"
    resource_monitor:
      name: "DTAGENT_RS"
      credit_quota: 5
EOF

    cat "$TEST_DIR/config.yml" | yq -o json '.' | jq -r '
        def flatten:
          . as $in
          | (paths(scalars|true) as $p
          | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
          | $out;
        [flatten]
      ' > "$TEST_DIR/config.json"

    export BUILD_CONFIG_FILE="$TEST_DIR/config.json"

    run ./scripts/deploy/list_options_to_exclude.sh
    [ "$status" -eq 0 ]
    [[ "$output" != *"dtagent_admin"* ]]
    [[ "$output" != *"resource_monitor"* ]]
}

@test "list_options_to_exclude: admin empty (default) - enabled" {
    cat > "$TEST_DIR/config.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test.snowflake.com
    host_name: test.snowflake.com
    roles:
      admin: ""
    resource_monitor:
      name: "-"
      credit_quota: 5
EOF

    cat "$TEST_DIR/config.yml" | yq -o json '.' | jq -r '
        def flatten:
          . as $in
          | (paths(scalars|true) as $p
          | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
          | $out;
        [flatten]
      ' > "$TEST_DIR/config.json"

    export BUILD_CONFIG_FILE="$TEST_DIR/config.json"

    run ./scripts/deploy/list_options_to_exclude.sh
    [ "$status" -eq 0 ]
    # Empty admin means use default, so it should be enabled
    [[ "$output" != *"dtagent_admin"* ]]
    [[ "$output" == *"resource_monitor"* ]]
}
