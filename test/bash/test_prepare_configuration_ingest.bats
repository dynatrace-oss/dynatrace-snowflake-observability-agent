#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Create a temporary config file
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "test.key1",
    "TYPE": "str",
    "VALUE": "value1"
  },
  {
    "PATH": "test.key2",
    "TYPE": "str",
    "VALUE": "value*with*stars"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
}

teardown() {
    rm -f "$TEST_CONFIG_FILE"
    unset BUILD_CONFIG_FILE
}

@test "prepare_configuration_ingest.sh generates correct SQL" {
    run ./prepare_configuration_ingest.sh
    [ "$status" -eq 0 ]
    [[ "$output" =~ "INSERT INTO TEMP_CONFIG" ]]
    [[ "$output" =~ "PARSE_JSON" ]]
    [[ "$output" =~ "value1" ]]
    [[ "$output" =~ "value\\\\\\\\*with\\\\\\\\*stars" ]]  # escaped stars
}