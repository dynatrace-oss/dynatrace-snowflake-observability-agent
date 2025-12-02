#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Create a temporary instruments file
    TEST_INSTRUMENTS_FILE=$(mktemp)
    cat > "$TEST_INSTRUMENTS_FILE" << 'EOF'
{
  "test": "value",
  "__skip": "this"
}
EOF
    mkdir -p build
    cp "$TEST_INSTRUMENTS_FILE" build/instruments-def.json
}

teardown() {
    rm -f "$TEST_INSTRUMENTS_FILE"
    rm -f build/instruments-def.json
}

@test "prepare_instruments_ingest.sh generates correct SQL" {
    run ./scripts/deploy/prepare_instruments_ingest.sh
    [ "$status" -eq 0 ]
    [[ "$output" =~ "INSERT INTO TEMP_INSTRUMENTS" ]]
    [[ "$output" =~ "PARSE_JSON" ]]
    [[ "$output" =~ '"test":"value"' ]]
    [[ ! "$output" =~ "__skip" ]]  # should filter out __ keys
}