#!/usr/bin/env bats
setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Set BUILD_CONFIG_FILE to avoid issues when sourcing
    export BUILD_CONFIG_FILE="/tmp/test_config.json"
    # Source the script to test its functions
    source scripts/deploy/prepare_config.sh 2>/dev/null
}

@test "get_config returns file content for valid file" {
    TEST_FILE=$(mktemp)
    echo 'key: value' > "$TEST_FILE"
    run get_config "$TEST_FILE"
    [ "$status" -eq 0 ]
    if [ "$output" != 'key: value' ]; then
        echo "get_config failed with status $status"
        echo "Output: >$output<"
    fi
    [ "$output" = 'key: value' ]

    rm "$TEST_FILE"
}

@test "get_config returns yaml string if valid yaml" {
    run get_config 'key: value'
    [ "$status" -eq 0 ]
    if [ "$output" != 'key: value' ]; then
        echo "get_config failed with status $status"
        echo "Output: >$output<"
    fi
    [ "$output" = 'key: value' ]
}

@test "get_config returns empty dict for invalid input" {
    run get_config "invalid"
    [ "$status" -eq 0 ]
    if [ "$output" != '{}' ]; then
        echo "get_config failed with status $status"
        echo "Output: >$output<"
    fi
    [ "$output" = "{}" ]
}

@test "prepare_config_for_ingest flattens simple json" {
    INPUT='{"core": {"key": "value"}}'
    run prepare_config_for_ingest "$INPUT"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.[] | select(.PATH == "core.key" and .VALUE == "value" and .TYPE == "string")' > /dev/null
}

@test "merge_yaml merges multiple configs" {
    CONFIG1='a: 1'
    CONFIG2='b: 2'
    run merge_yaml "$CONFIG1" "$CONFIG2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.[] | select(.PATH == "a" and .VALUE == 1)' > /dev/null
    echo "$output" | jq -e '.[] | select(.PATH == "b" and .VALUE == 2)' > /dev/null
}

@test "prepare_config.sh processes multiple config files end-to-end" {
    # Create temporary config files
    CONFIG_FILE1=$(mktemp)
    CONFIG_FILE2=$(mktemp)
    echo -e "core:\n  key1: value1" > "$CONFIG_FILE1"
    echo -e "core:\n  key2: value2" > "$CONFIG_FILE2"

    # Run the script with the config files
    run bash scripts/deploy/prepare_config.sh "$CONFIG_FILE1" "$CONFIG_FILE2"
    [ "$status" -eq 0 ]

    # Check the merged config output
    run cat "$BUILD_CONFIG_FILE"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.[] | select(.PATH == "core.key1" and .VALUE == "value1" and .TYPE == "str")' > /dev/null
    echo "$output" | jq -e '.[] | select(.PATH == "core.key2" and .VALUE == "value2" and .TYPE == "str")' > /dev/null

    # Cleanup
    rm "$CONFIG_FILE1" "$CONFIG_FILE2"
}