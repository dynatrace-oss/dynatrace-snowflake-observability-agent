#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Create minimal test config
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    TEST_SQL_FILE=$(mktemp)
    mkdir -p build
    echo "SELECT 1;" > build/001_test.sql
}

teardown() {
    rm -f "$TEST_CONFIG_FILE" "$TEST_SQL_FILE"
    rm -f build/001_test.sql
    unset BUILD_CONFIG_FILE
}

@test "prepare_deploy_script.sh runs with manual param" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"
    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "001_test" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]  # file should not be empty
    grep -q "SELECT 1" "$TEST_SQL_FILE"
}