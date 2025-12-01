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
    run ./update_secret.sh "$TEST_SQL_FILE"
    [ "$status" -eq 0 ]
    # Check that SQL was appended
    grep -q "create or replace secret DTAGENT_API_KEY" "$TEST_SQL_FILE"
    grep -q "test.dynatrace.com" "$TEST_SQL_FILE"
}

@test "update_secret.sh fails with invalid token" {
    export DTAGENT_TOKEN="invalid_token"
    run ./update_secret.sh "$TEST_SQL_FILE"
    [ "$status" -eq 1 ]
    # Check warning message
    [[ "$output" =~ "DTAGENT_API_KEY will NOT be updated" ]]
    # Check no SQL was written
    [ ! -s "$TEST_SQL_FILE" ]
}