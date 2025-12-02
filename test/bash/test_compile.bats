#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Backup original files if exist
    [ -f build/_version.py ] && cp build/_version.py build/_version.py.bak
    [ -f build/_dtagent.py ] && cp build/_dtagent.py build/_dtagent.py.bak
    [ -f build/_send_telemetry.py ] && cp build/_send_telemetry.py build/_send_telemetry.py.bak
}

teardown() {
    # Restore or clean up
    [ -f build/_version.py.bak ] && mv build/_version.py.bak build/_version.py || rm -f build/_version.py
    [ -f build/_dtagent.py.bak ] && mv build/_dtagent.py.bak build/_dtagent.py || rm -f build/_dtagent.py
    [ -f build/_send_telemetry.py.bak ] && mv build/_send_telemetry.py.bak build/_send_telemetry.py || rm -f build/_send_telemetry.py
}

@test "compile.sh creates compiled files" {
    run ./scripts/dev/compile.sh
    [ "$status" -eq 0 ]
    [ -f build/_version.py ]
    [ -f build/_dtagent.py ]
    [ -f build/_send_telemetry.py ]
    grep -q "BUILD =" build/_version.py
}