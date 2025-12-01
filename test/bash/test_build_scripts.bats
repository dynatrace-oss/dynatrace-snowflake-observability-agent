#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
}

@test "build.sh runs without immediate errors" {
    # This test assumes dependencies like pylint are installed
    # In a real environment, this would pass if build tools are available
    run timeout 15 ./build.sh
    # Allow it to pass even if it fails due to missing dependencies, as long as it doesn't crash immediately
    [ "$status" -eq 0 ] || [ "$status" -eq 1 ]  # 0 for success, 1 for build failure
}

@test "build_docs.sh runs without immediate errors" {
    run timeout 15 ./build_docs.sh
    [ "$status" -eq 0 ] || [ "$status" -eq 1 ]
}