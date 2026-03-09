#!/usr/bin/env bats

setup_file() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Ensure build directory exists (not present in a fresh CI checkout)
    mkdir -p build/30_plugins build/09_upgrade
    # Backup original files if exist
    [ -f build/_version.py ] && cp build/_version.py build/_version.py.bak
    [ -f build/_dtagent.py ] && cp build/_dtagent.py build/_dtagent.py.bak
    [ -f build/_send_telemetry.py ] && cp build/_send_telemetry.py build/_send_telemetry.py.bak
    # Run compile.sh once for all tests; communicate result via BATS_FILE_TMPDIR
    # (export from setup_file does not propagate into individual test subshells)
    ./scripts/dev/compile.sh
    echo $? > "${BATS_FILE_TMPDIR}/compile_status"
}

teardown_file() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Restore or clean up
    [ -f build/_version.py.bak ] && mv build/_version.py.bak build/_version.py || rm -f build/_version.py
    [ -f build/_dtagent.py.bak ] && mv build/_dtagent.py.bak build/_dtagent.py || rm -f build/_dtagent.py
    [ -f build/_send_telemetry.py.bak ] && mv build/_send_telemetry.py.bak build/_send_telemetry.py || rm -f build/_send_telemetry.py
}

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    COMPILE_STATUS=$(cat "${BATS_FILE_TMPDIR}/compile_status" 2>/dev/null || echo 1)
}

@test "compile.sh creates compiled files" {
    [ "$COMPILE_STATUS" -eq 0 ]
    [ -f build/_version.py ]
    [ -f build/_semantics.py ]
    [ -f build/_metric_semantics.txt ]
    [ -f build/_dtagent.py ]
    [ -f build/_send_telemetry.py ]

    grep -q "BUILD =" build/_version.py
}

@test "compile.sh removes docstrings from compiled files" {
    [ "$COMPILE_STATUS" -eq 0 ]

    # Check that compiled files exist
    [ -f build/_dtagent.py ]
    [ -f build/_send_telemetry.py ]

    # Check that docstrings are removed (no triple quotes followed by text)
    # We're checking that there are no typical docstring patterns
    ! grep -E '^\s*"""[^"]*"""' build/_dtagent.py
    ! grep -E "^\s*'''[^']*'''" build/_dtagent.py
    ! grep -E '^\s*"""[^"]*"""' build/_send_telemetry.py
    ! grep -E "^\s*'''[^']*'''" build/_send_telemetry.py
}