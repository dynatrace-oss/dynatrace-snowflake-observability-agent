#!/usr/bin/env bats
#
# Tests that 040_update_config.sql uses DELETE + INSERT (full-replace) semantics
# instead of the old additive MERGE pattern.
#

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
}

@test "040_update_config.sql uses DELETE FROM instead of MERGE INTO" {
    run grep -i 'delete from.*CONFIGURATIONS' src/dtagent.sql/config/040_update_config.sql
    [ "$status" -eq 0 ]
    [[ "$output" =~ "CONFIGURATIONS" ]]
}

@test "040_update_config.sql uses INSERT INTO instead of MERGE INTO" {
    run grep -i 'insert into.*CONFIGURATIONS' src/dtagent.sql/config/040_update_config.sql
    [ "$status" -eq 0 ]
    [[ "$output" =~ "CONFIGURATIONS" ]]
}

@test "040_update_config.sql does NOT contain MERGE INTO CONFIGURATIONS" {
    run grep -i 'merge into.*CONFIGURATIONS' src/dtagent.sql/config/040_update_config.sql
    [ "$status" -ne 0 ]
}

@test "040_update_config.sql wraps DELETE+INSERT in a BEGIN...END block" {
    run grep -i '^begin' src/dtagent.sql/config/040_update_config.sql
    [ "$status" -eq 0 ]
    run grep -i '^end;' src/dtagent.sql/config/040_update_config.sql
    [ "$status" -eq 0 ]
}

@test "040_update_config.sql still calls UPDATE_FROM_CONFIGURATIONS after upload" {
    run grep 'UPDATE_FROM_CONFIGURATIONS' src/dtagent.sql/config/040_update_config.sql
    [ "$status" -eq 0 ]
}
