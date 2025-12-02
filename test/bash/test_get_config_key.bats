#!/usr/bin/env bats

setup() {
    # Create a temporary config file for testing
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
    "VALUE": "value2"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
}

teardown() {
    rm -f "$TEST_CONFIG_FILE"
    unset BUILD_CONFIG_FILE
}

@test "get_config_key.sh returns correct value for existing key" {
    run ./get_config_key.sh test.key1
    [ "$status" -eq 0 ]
    [ "$output" = "value1" ]
}

@test "get_config_key.sh returns empty for non-existing key" {
    run ./get_config_key.sh test.nonexistent
    [ "$status" -eq 0 ]
    [ "$output" = "" ]
}

@test "get_config_key.sh handles multiple calls" {
    run ./get_config_key.sh test.key2
    [ "$status" -eq 0 ]
    [ "$output" = "value2" ]
}