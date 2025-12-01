#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Source the script to test its functions
    source prepare_config.sh
}

@test "get_config returns file content for valid file" {
    TEST_FILE=$(mktemp)
    echo '{"key": "value"}' > "$TEST_FILE"
    run get_config "$TEST_FILE"
    [ "$status" -eq 0 ]
    [ "$output" = '{"key": "value"}' ]
    rm "$TEST_FILE"
}

@test "get_config returns json string if valid json" {
    run get_config '{"key": "value"}'
    [ "$status" -eq 0 ]
    [ "$output" = '{"key": "value"}' ]
}

@test "get_config returns empty dict for invalid input" {
    run get_config "invalid"
    [ "$status" -eq 0 ]
    [ "$output" = "{}" ]
}

@test "prepare_config_for_ingest flattens simple json" {
    INPUT='{"core": {"key": "value"}}'
    run prepare_config_for_ingest "$INPUT"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.[] | select(.PATH == "core.key" and .VALUE == "value" and .TYPE == "string")' > /dev/null
}

@test "merge_json merges multiple configs" {
    CONFIG1='{"a": 1}'
    CONFIG2='{"b": 2}'
    run merge_json "$CONFIG1" "$CONFIG2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.[] | select(.PATH == "a" and .VALUE == 1)' > /dev/null
    echo "$output" | jq -e '.[] | select(.PATH == "b" and .VALUE == 2)' > /dev/null
}