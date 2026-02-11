#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Create test CSV
    TEST_CSV=$(mktemp)
    echo "old_field;new_field" > "$TEST_CSV"
    # Create test directory with files
    TEST_DIR=$(mktemp -d)
    echo "some old_field here" > "$TEST_DIR/test.txt"
    echo "old_field and more" > "$TEST_DIR/test.py"
}

teardown() {
    rm -f "$TEST_CSV"
    rm -rf "$TEST_DIR"
}

@test "refactor_field_names.sh replaces identifiers in files" {
    run ./scripts/deploy/refactor_field_names.sh "$TEST_CSV" "$TEST_DIR"
    [ "$status" -eq 0 ]
    grep -q "new_field" "$TEST_DIR/test.txt"
    grep -q "new_field" "$TEST_DIR/test.py"
    [[ "$output" =~ "Identifiers updated successfully!" ]]
}