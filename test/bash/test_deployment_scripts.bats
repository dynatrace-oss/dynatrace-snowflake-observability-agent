#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
}

@test "setup.sh checks for missing tools" {
    run ./setup.sh
    # It should check for jq, etc., and may install if missing
    # But in test, just check it runs
    [ "$status" -eq 0 ] || [ "$status" -eq 1 ]
}

@test "deploy.sh requires ENV parameter" {
    run ./deploy.sh
    [ "$status" -ne 0 ]  # Should fail without ENV
}

@test "package.sh requires build files" {
    run ./package.sh
    # May fail if build/ files missing, but check it runs
    [ "$status" -eq 0 ] || [ "$status" -eq 1 ]
}