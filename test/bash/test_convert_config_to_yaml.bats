#!/usr/bin/env bats

setup() {
    TEST_DIR="$(mktemp -d)"
    cp test/bash/test_object.json "$TEST_DIR/"
    cp test/bash/test_array.json "$TEST_DIR/"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "convert object JSON to YAML" {
    run scripts/deploy/convert_config_to_yaml.sh "$TEST_DIR/test_object.json"
    [ "$status" -eq 0 ]
    [ -f "$TEST_DIR/test_object.yaml" ]
    run cat "$TEST_DIR/test_object.yaml"
    [[ "$output" == *"core:"* ]]
    [[ "$output" == *"dynatrace_tenant_address: test.com"* ]]
}

@test "convert array JSON to multiple YAMLs" {
    run scripts/deploy/convert_config_to_yaml.sh "$TEST_DIR/test_array.json"
    [ "$status" -eq 0 ]
    [ -f "$TEST_DIR/test_array.yaml" ]
    [ -f "$TEST_DIR/test_array_1.yaml" ]
    run cat "$TEST_DIR/test_array.yaml"
    [[ "$output" == *"core:"* ]]
    [[ "$output" == *"dynatrace_tenant_address: test1.com"* ]]
    run cat "$TEST_DIR/test_array_1.yaml"
    [[ "$output" == *"dynatrace_tenant_address: test2.com"* ]]
}

@test "fail without argument" {
    run scripts/deploy/convert_config_to_yaml.sh
    [ "$status" -eq 1 ]
    [[ "$output" == *"Usage"* ]]
}