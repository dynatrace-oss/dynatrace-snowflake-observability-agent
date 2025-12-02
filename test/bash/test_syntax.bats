#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
}

@test "build.sh has valid bash syntax" {
    run bash -n build.sh
    [ "$status" -eq 0 ]
}

@test "compile.sh has valid bash syntax" {
    run bash -n compile.sh
    [ "$status" -eq 0 ]
}

@test "build_docs.sh has valid bash syntax" {
    run bash -n build_docs.sh
    [ "$status" -eq 0 ]
}

@test "deploy.sh has valid bash syntax" {
    run bash -n deploy.sh
    [ "$status" -eq 0 ]
}

@test "install_snow_cli.sh has valid bash syntax" {
    run bash -n install_snow_cli.sh
    [ "$status" -eq 0 ]
}

@test "package.sh has valid bash syntax" {
    run bash -n package.sh
    [ "$status" -eq 0 ]
}

@test "setup.sh has valid bash syntax" {
    run bash -n setup.sh
    [ "$status" -eq 0 ]
}