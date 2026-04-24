#!/usr/bin/env bats

setup() {
    # shellcheck disable=SC2154
    cd "$BATS_TEST_DIRNAME/../.." || exit 1

    # Create a temp working tree for fixtures
    TEST_TEMP_DIR=$(mktemp -d)

    # Dashboard fixtures
    mkdir -p "$TEST_TEMP_DIR/docs/dashboards/test-dashboard"
    cat > "$TEST_TEMP_DIR/docs/dashboards/test-dashboard/test-dashboard.yml" << 'EOF'
# DASHBOARD: Test Dashboard
version: 19
tiles: {}
EOF

    mkdir -p "$TEST_TEMP_DIR/docs/dashboards/another-dashboard"
    cat > "$TEST_TEMP_DIR/docs/dashboards/another-dashboard/another-dashboard.yml" << 'EOF'
# DASHBOARD: Another Dashboard
version: 19
tiles: {}
EOF

    # Workflow fixture
    mkdir -p "$TEST_TEMP_DIR/docs/workflows/test-workflow"
    cat > "$TEST_TEMP_DIR/docs/workflows/test-workflow/test-workflow.yml" << 'EOF'
# WORKFLOW: Test Workflow
title: Test Workflow
tasks: {}
EOF

    # Mock dtctl binary — records calls, simulates success
    MOCK_BIN_DIR="$TEST_TEMP_DIR/bin"
    mkdir -p "$MOCK_BIN_DIR"

    MOCK_DTCTL_LOG="$TEST_TEMP_DIR/dtctl-calls.log"
    export DTCTL_CALL_LOG="$MOCK_DTCTL_LOG"

    cat > "$MOCK_BIN_DIR/dtctl" << 'MOCK'
#!/usr/bin/env bash
echo "$@" >> "${DTCTL_CALL_LOG:-/dev/null}"
case "$1" in
    doctor) exit 0 ;;
    apply)
        # Return the same JSON structure as real dtctl apply
        echo '{"ok":true,"result":{"action":"created","resourceType":"dashboard","id":"aaaabbbb-0000-0000-0000-111122223333","name":"Test Dashboard","url":"https://example.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/aaaabbbb-0000-0000-0000-111122223333"}}'
        exit 0
        ;;
    *)      exit 0 ;;
esac
MOCK
    chmod +x "$MOCK_BIN_DIR/dtctl"

    # Mock yaml-to-json.sh under the fixture's scripts/tools directory
    MOCK_TOOLS_DIR="$TEST_TEMP_DIR/scripts/tools"
    mkdir -p "$MOCK_TOOLS_DIR"
    cat > "$MOCK_TOOLS_DIR/yaml-to-json.sh" << 'YQ_MOCK'
#!/usr/bin/env bash
echo '{"version":19,"tiles":{}}'
YQ_MOCK
    chmod +x "$MOCK_TOOLS_DIR/yaml-to-json.sh"

    # Copy deploy_dt_assets.sh into the fixture tree so REPO_ROOT resolves correctly
    FIXTURE_DEPLOY_DIR="$TEST_TEMP_DIR/scripts/deploy"
    mkdir -p "$FIXTURE_DEPLOY_DIR"
    cp scripts/deploy/deploy_dt_assets.sh "$FIXTURE_DEPLOY_DIR/deploy_dt_assets.sh"
    chmod +x "$FIXTURE_DEPLOY_DIR/deploy_dt_assets.sh"

    export TEST_TEMP_DIR MOCK_BIN_DIR MOCK_DTCTL_LOG MOCK_TOOLS_DIR FIXTURE_DEPLOY_DIR
}

teardown() {
    rm -rf "$TEST_TEMP_DIR"
    unset TEST_TEMP_DIR MOCK_BIN_DIR MOCK_DTCTL_LOG MOCK_TOOLS_DIR FIXTURE_DEPLOY_DIR DTCTL_CALL_LOG
}

# Helper: run the fixture copy of deploy_dt_assets.sh with the mock dtctl on PATH.
run_script() {
    PATH="$MOCK_BIN_DIR:$PATH" \
    DTCTL_CALL_LOG="$MOCK_DTCTL_LOG" \
    run "$FIXTURE_DEPLOY_DIR/deploy_dt_assets.sh" "$@"
}

# ── Test: missing dtctl ──────────────────────────────────────────────────────

@test "exits 0 with informative message when dtctl is not installed" {
    # Build a PATH that excludes any real dtctl by filtering out directories
    # that contain dtctl.  This ensures command -v dtctl fails.
    local dtctl_path
    dtctl_path=$(command -v dtctl 2>/dev/null || true)
    local dtctl_dir=""
    if [[ -n "$dtctl_path" ]]; then
        dtctl_dir=$(dirname "$dtctl_path")
    fi

    local safe_path
    if [[ -n "$dtctl_dir" ]]; then
        # Remove the dtctl directory from PATH
        safe_path=$(echo "$PATH" | tr ':' '\n' | grep -v "^${dtctl_dir}$" | tr '\n' ':' | sed 's/:$//')
    else
        safe_path="$PATH"
    fi

    PATH="$safe_path" \
    DTCTL_CALL_LOG="$MOCK_DTCTL_LOG" \
    run "$FIXTURE_DEPLOY_DIR/deploy_dt_assets.sh" --scope=all

    [ "$status" -eq 0 ]
    [[ "$output" =~ "dtctl is not installed" ]]
}

# ── Test: invalid scope ──────────────────────────────────────────────────────

@test "exits 1 with error for invalid scope" {
    run_script --scope=invalid
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Invalid scope" ]]
}

# ── Test: unknown parameter ──────────────────────────────────────────────────

@test "exits 1 with error for unknown parameter" {
    run_script --unknown-flag
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Unknown parameter" ]]
}

# ── Test: dry-run flag ───────────────────────────────────────────────────────

@test "dry-run mode logs dry-run enabled message" {
    run_script --scope=dashboards --dry-run
    [[ "$output" =~ "Dry-run" ]] || [[ "$output" =~ "dry-run" ]]
}

@test "dry-run mode passes --dry-run to dtctl apply" {
    run_script --scope=dashboards --dry-run
    # Check the dtctl call log contains --dry-run
    grep -q "\-\-dry-run" "$MOCK_DTCTL_LOG"
}

# ── Test: scope filtering ─────────────────────────────────────────────────────

@test "scope=dashboards output mentions dashboard but not workflow" {
    run_script --scope=dashboards
    [[ "$output" =~ "dashboard" ]]
    # workflow processing should not appear in output
    # shellcheck disable=SC2076
    [[ ! "$output" =~ "Deploying.*workflow" ]]
}

@test "scope=workflows output mentions workflow but not dashboard processing" {
    run_script --scope=workflows
    [[ "$output" =~ "workflow" ]]
    # shellcheck disable=SC2076
    [[ ! "$output" =~ "Deploying.*dashboard" ]]
}

@test "scope=all deploys both dashboards and workflows" {
    run_script --scope=all
    [[ "$output" =~ "dashboard" ]]
    [[ "$output" =~ "workflow" ]]
}

# ── Test: YAML→JSON conversion is called ─────────────────────────────────────

@test "deployment succeeds when yaml-to-json produces valid JSON" {
    run_script --scope=dashboards
    [ "$status" -eq 0 ]
    # The script should report success (URL printed and/or succeeded count)
    [[ "$output" =~ "succeeded" ]]
}

@test "deployment prints clickable Dynatrace URL on success" {
    run_script --scope=dashboards
    [ "$status" -eq 0 ]
    local url_marker='\[URL\]'
    [[ "$output" =~ $url_marker ]]
    [[ "$output" =~ "https://" ]]
}

@test "newly assigned ID is written back to YAML file" {
    # Confirm fixture YAML has no id before deploy
    [[ ! -f "$TEST_TEMP_DIR/docs/dashboards/test-dashboard/test-dashboard.yml" ]] && skip "fixture missing"
    run ! grep -q "^id:" "$TEST_TEMP_DIR/docs/dashboards/test-dashboard/test-dashboard.yml"

    run_script --scope=dashboards
    [ "$status" -eq 0 ]
    # The ID returned by mock dtctl should now be in the YAML
    grep -q "id: aaaabbbb" "$TEST_TEMP_DIR/docs/dashboards/test-dashboard/test-dashboard.yml"
}

# ── Test: missing docs/workflows is handled gracefully ───────────────────────

@test "missing workflows directory produces warning not error" {
    rm -rf "$TEST_TEMP_DIR/docs/workflows"
    run_script --scope=workflows
    [ "$status" -eq 0 ]
    [[ "$output" =~ "not found" ]] || [[ "$output" =~ "skipping" ]] || [[ "$output" =~ "Skipping" ]]
}

# ── Test: empty dashboards directory handled gracefully ──────────────────────

@test "missing dashboards directory produces warning not error" {
    rm -rf "$TEST_TEMP_DIR/docs/dashboards"
    run_script --scope=dashboards
    [ "$status" -eq 0 ]
}

# ── Test: summary output ─────────────────────────────────────────────────────

@test "summary output includes succeeded count" {
    run_script --scope=dashboards
    [[ "$output" =~ "succeeded" ]]
}

# ── Test: dashboard name extracted from DASHBOARD comment ────────────────────

@test "extracts human-readable dashboard name from DASHBOARD comment" {
    run_script --scope=dashboards
    [[ "$output" =~ "Test Dashboard" ]]
}

# ── Test: env label is included in output ────────────────────────────────────

@test "--env label appears in info output" {
    run_script --scope=dashboards --env=staging
    [[ "$output" =~ "staging" ]]
}
