#!/usr/bin/env bats

setup() {
    CWD="$(pwd)"
    TEST_DIR="$(mktemp -d)"
    cp test/bash/test_object.json "$TEST_DIR"
    cd "$TEST_DIR"
    git init
    git add test_object.json
    git commit -m "initial"
}

teardown() {
    cd /
    rm -rf "$TEST_DIR"
}

@test "convert and git mv object JSON" {
    cd "$TEST_DIR"
    run "$CWD/tools/config_to_yaml.sh" "$TEST_DIR/test_object.json"
    if [ "$status" -ne 0 ]; then
        echo "build.sh failed with status $status"
        echo "Output: $output"
    fi
    [ "$status" -eq 0 ]
    [ -f "$TEST_DIR/test_object.yaml" ]
    [ ! -f "$TEST_DIR/test_object.json" ]

    run git status --porcelain
    [[ "$output" == *"R"* ]]  # renamed
}