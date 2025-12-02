#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Create a temporary config file for testing
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "str",
    "VALUE": "test.dynatrace.com"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    TEST_SQL_FILE=$(mktemp)
}

teardown() {
    rm -f "$TEST_CONFIG_FILE" "$TEST_SQL_FILE"
    unset BUILD_CONFIG_FILE DTAGENT_TOKEN
}

@test "update_secret.sh succeeds with valid token" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"
    run ./scripts/deploy/update_secret.sh "$TEST_SQL_FILE"
    if [ "$status" -ne 0 ]; then
        echo "update_secret.sh failed with status $status"
        echo "Output: $output"
    fi
    [ "$status" -eq 0 ]

    # Check that SQL was appended
    run grep -q "create or replace secret DTAGENT_API_KEY" "$TEST_SQL_FILE"
    if [ "$status" -ne 0 ]; then
        echo "Content of $TEST_SQL_FILE:"
        cat "$TEST_SQL_FILE"
    fi
    [ "$status" -eq 0 ]

    run grep -q "test.dynatrace.com" "$TEST_SQL_FILE"
    if [ "$status" -ne 0 ]; then
        echo "Content of $TEST_SQL_FILE:"
        cat "$TEST_SQL_FILE"
        echo "Content of TEST_CONFIG_FILE:"
        cat "$TEST_CONFIG_FILE"
    fi
    [ "$status" -eq 0 ]
}

@test "update_secret.sh fails with invalid token" {
    export DTAGENT_TOKEN="invalid_token"
    run ./scripts/deploy/update_secret.sh "$TEST_SQL_FILE"
    [ "$status" -eq 1 ]
    # Check warning message
    [[ "$output" =~ "DTAGENT_API_KEY will NOT be updated" ]]
    # Check no SQL was written
    [ ! -s "$TEST_SQL_FILE" ]
}