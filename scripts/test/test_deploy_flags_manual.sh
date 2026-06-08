#!/usr/bin/env bash
#
# Manual test walkthrough for scripts/deploy/deploy.sh flag parsing and config generation.
# Covers the scenarios in test/bash/test_deploy_new_flags.bats but runs interactively
# so a human can inspect output at each step.
#
# Usage:
#   bash scripts/test/test_deploy_flags_manual.sh
#
# Each test prints PASS or FAIL. A summary is printed at the end.
# No actual Snowflake connection is made — all tests stop before SQL execution.

set -euo pipefail

SCRIPT="scripts/deploy/deploy.sh"
PASS=0
FAIL=0
FAILURES=()

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 — $2"; FAIL=$(( FAIL + 1 )); FAILURES+=("$1"); }

run_test() {
    local name="$1"
    local cmd="$2"
    local expect_exit="${3:-any}"      # "0", "nonzero", or "any"
    local expect_output="${4:-}"       # substring to match (empty = skip check)
    local expect_absent="${5:-}"       # substring that must NOT appear

    echo ""
    echo "--- TEST: $name"
    local output exit_code
    set +e
    output=$(eval "$cmd" 2>&1)
    exit_code=$?
    set -e
    echo "  exit=$exit_code"
    echo "  output: $(echo "$output" | head -3)"

    local ok=1
    if [[ "$expect_exit" == "0" && $exit_code -ne 0 ]]; then
        fail "$name" "expected exit 0, got $exit_code"; ok=0
    elif [[ "$expect_exit" == "nonzero" && $exit_code -eq 0 ]]; then
        fail "$name" "expected non-zero exit, got 0"; ok=0
    fi
    if [[ -n "$expect_output" && "$output" != *"$expect_output"* ]]; then
        fail "$name" "expected output to contain: '$expect_output'"; ok=0
    fi
    if [[ -n "$expect_absent" && "$output" == *"$expect_absent"* ]]; then
        fail "$name" "expected output to NOT contain: '$expect_absent'"; ok=0
    fi
    if [[ $ok -eq 1 ]]; then pass "$name"; fi
}

##region ── Help / Usage ────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════"
echo " SECTION 1 — Help and usage output"
echo "════════════════════════════════════════"

run_test "help flag --help" \
    "bash $SCRIPT --help" \
    "0" \
    "--env=<ENV>" \
    "Unknown parameter"

run_test "help flag -h" \
    "bash $SCRIPT -h" \
    "0" \
    "Examples:" \
    "Unknown parameter"

run_test "no-args shows error not help" \
    "bash $SCRIPT" \
    "nonzero" \
    "required" \
    "Unknown parameter"

run_test "no-args error references --help" \
    "bash $SCRIPT" \
    "nonzero" \
    "--help"

##endregion

##region ── --env flag ──────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════"
echo " SECTION 2 — --env= flag parsing"
echo "════════════════════════════════════════"

# Create a temp env so deploy.sh finds a config file and proceeds past the early check
TMPDIR=$(mktemp -d)
mkdir -p "$TMPDIR/conf" "$TMPDIR/build/09_upgrade" "$TMPDIR/build/30_plugins"
cat > "$TMPDIR/conf/config-mytest.yml" <<'EOF'
core:
  dynatrace_tenant_address: "test.live.dynatrace.com"
  deployment_environment: "MYTEST"
  snowflake:
    account_name: "test-account"
plugins:
  deploy_disabled_plugins: false
EOF

# These tests check flag parsing only — they will fail during setup.sh / snow execution
# but must NOT produce "Unknown parameter" or "required" errors before that point

run_test "--env= is accepted (no unknown-param error)" \
    "bash $SCRIPT --env=mytest --scope=init 2>&1 | head -5" \
    "any" \
    "" \
    "Unknown parameter"

run_test "positional ENV shows deprecation warning" \
    "bash $SCRIPT mytest --scope=init 2>&1 | head -5" \
    "any" \
    "deprecated" \
    "Unknown parameter"

run_test "--env= alone (missing scope uses default) is accepted" \
    "bash $SCRIPT --env=mytest 2>&1 | head -5" \
    "any" \
    "" \
    "Unknown parameter"

run_test "unknown flag is rejected" \
    "bash $SCRIPT --env=mytest --not-a-flag 2>&1" \
    "nonzero" \
    "Unknown parameter"

##endregion

##region ── --defaults flag ─────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════"
echo " SECTION 3 — --defaults flag"
echo "════════════════════════════════════════"

DEFAULTS_DIR=$(mktemp -d)
mkdir -p "$DEFAULTS_DIR/conf"

run_test "--defaults creates config file" \
    "(cd \"$DEFAULTS_DIR\" && bash \"$(pwd)/$SCRIPT\" --env=newenv --defaults 2>&1 && [ -f conf/config-newenv.yml ] && echo 'FILE_CREATED')" \
    "0" \
    "FILE_CREATED"

run_test "--defaults file contains required keys" \
    "(cd \"$DEFAULTS_DIR\" && bash \"$(pwd)/$SCRIPT\" --env=newenv2 --defaults >/dev/null 2>&1; grep -q 'dynatrace_tenant_address' conf/config-newenv2.yml && grep -q 'deployment_environment' conf/config-newenv2.yml && echo 'KEYS_PRESENT')" \
    "0" \
    "KEYS_PRESENT"

# Config already exists — should fail
run_test "--defaults fails if config already exists" \
    "(cd \"$DEFAULTS_DIR\" && bash \"$(pwd)/$SCRIPT\" --env=newenv --defaults 2>&1)" \
    "nonzero" \
    "already exists"

run_test "--defaults + --interactive are mutually exclusive" \
    "bash $SCRIPT --env=anything --defaults --interactive 2>&1" \
    "nonzero" \
    "mutually exclusive"

rm -rf "$DEFAULTS_DIR"

##endregion

##region ── --options flag ──────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════"
echo " SECTION 4 — --options= flag parsing"
echo "════════════════════════════════════════"

run_test "--options=skip_confirm is accepted" \
    "bash $SCRIPT --env=anything --options=skip_confirm 2>&1 | head -5" \
    "any" \
    "" \
    "Unknown parameter"

run_test "--options=manual,no_dep is accepted" \
    "bash $SCRIPT --env=anything --options=manual,no_dep 2>&1 | head -5" \
    "any" \
    "" \
    "Unknown parameter"

##endregion

##region ── --scope flag ────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════"
echo " SECTION 5 — --scope= flag parsing"
echo "════════════════════════════════════════"

run_test "--scope=config is accepted" \
    "bash $SCRIPT --env=anything --scope=config 2>&1 | head -5" \
    "any" \
    "" \
    "Unknown parameter"

run_test "--scope=plugins,config,agents is accepted" \
    "bash $SCRIPT --env=anything --scope=plugins,config,agents 2>&1 | head -5" \
    "any" \
    "" \
    "Unknown parameter"

UPGRADE_DIR=$(mktemp -d)
mkdir -p "$UPGRADE_DIR/conf" "$UPGRADE_DIR/build"
# Minimal build artifact so the early build-check passes
touch "$UPGRADE_DIR/build/config-default.yml"
cat > "$UPGRADE_DIR/conf/config-anything.yml" <<'EOF'
core:
  dynatrace_tenant_address: "test.live.dynatrace.com"
  deployment_environment: "ANYTHING"
  snowflake:
    account_name: "test-account"
plugins:
  deploy_disabled_plugins: false
EOF

run_test "--scope=upgrade without --from-version fails" \
    "(cd \"$UPGRADE_DIR\" && bash \"$(pwd)/$SCRIPT\" --env=anything --scope=upgrade 2>&1)" \
    "nonzero" \
    "from-version"

run_test "--scope=upgrade with --from-version is accepted" \
    "(cd \"$UPGRADE_DIR\" && bash \"$(pwd)/$SCRIPT\" --env=anything --scope=upgrade --from-version=0.9.2 2>&1 | head -5)" \
    "any" \
    "" \
    "Unknown parameter"

rm -rf "$UPGRADE_DIR"

##endregion

##region ── Syntax check ────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════"
echo " SECTION 6 — Script syntax"
echo "════════════════════════════════════════"

run_test "deploy.sh has valid bash syntax" \
    "bash -n $SCRIPT" \
    "0"

for script in scripts/deploy/interactive_wizard.sh scripts/deploy/setup.sh scripts/deploy/lib.sh; do
    if [[ -f "$script" ]]; then
        run_test "$script has valid bash syntax" \
            "bash -n $script" \
            "0"
    fi
done

##endregion

##region ── ShellCheck (if available) ───────────────────────────────────────

echo ""
echo "════════════════════════════════════════"
echo " SECTION 7 — ShellCheck (optional)"
echo "════════════════════════════════════════"

if command -v shellcheck >/dev/null 2>&1; then
    run_test "shellcheck passes on deploy.sh" \
        "shellcheck --severity=warning $SCRIPT" \
        "0"
else
    echo "  SKIP: shellcheck not installed"
fi

##endregion

##region ── Summary ─────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════"
echo " SUMMARY"
echo "════════════════════════════════════════"
echo " PASS: $PASS"
echo " FAIL: $FAIL"
if [[ ${#FAILURES[@]} -gt 0 ]]; then
    echo ""
    echo " Failed tests:"
    for f in "${FAILURES[@]}"; do
        echo "   - $f"
    done
    echo ""
    exit 1
else
    echo ""
    echo " All tests passed."
    echo ""
fi

##endregion
