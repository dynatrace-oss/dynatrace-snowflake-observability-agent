#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."

    # Set test DTAGENT_TOKEN for tests that need it
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    # Create minimal test config
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": ""
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"

    TEST_SQL_FILE=$(mktemp)

    # Create build directory structure with test files
    mkdir -p build/30_plugins build/09_upgrade

    echo "-- Test init" > build/00_init.sql
    echo "SELECT 'init';" >> build/00_init.sql

    echo "-- Test admin" > build/10_admin.sql
    echo "SELECT 'admin';" >> build/10_admin.sql

    echo "-- Test setup" > build/20_setup.sql
    echo "SELECT 'setup';" >> build/20_setup.sql

    echo "-- Test plugin 1" > build/30_plugins/query_history.sql
    echo "SELECT 'plugin1';" >> build/30_plugins/query_history.sql

    echo "-- Test plugin 2" > build/30_plugins/warehouse_usage.sql
    echo "SELECT 'plugin2';" >> build/30_plugins/warehouse_usage.sql

    echo "-- Test config" > build/40_config.sql
    echo "SELECT 'config';" >> build/40_config.sql

    echo "-- Test agents" > build/70_agents.sql
    echo "SELECT 'agents';" >> build/70_agents.sql
}

teardown() {
    rm -f "$TEST_CONFIG_FILE" "$TEST_SQL_FILE"
    rm -f build/00_init.sql build/10_admin.sql build/20_setup.sql build/40_config.sql build/70_agents.sql
    rm -rf build/30_plugins build/09_upgrade
    unset BUILD_CONFIG_FILE DTAGENT_TOKEN
}

# Test: Single scope (baseline functionality)
@test "prepare_deploy_script.sh: single scope 'setup' works" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup" "" "true"
    [ "$status" -eq 0 ]
    [ -f "$TEST_SQL_FILE" ]
    grep -q "setup" "$TEST_SQL_FILE"
    ! grep -q "admin" "$TEST_SQL_FILE"
}

# Test: Multi-scope with two scopes
@test "prepare_deploy_script.sh: multi-scope 'setup,config' includes both" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup,config" "" "true"
    [ "$status" -eq 0 ]
    [ -f "$TEST_SQL_FILE" ]
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    ! grep -q "admin" "$TEST_SQL_FILE"
}

# Test: Multi-scope with three scopes
@test "prepare_deploy_script.sh: multi-scope 'setup,plugins,config' includes all three" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup,plugins,config" "" "true"
    [ "$status" -eq 0 ]
    [ -f "$TEST_SQL_FILE" ]
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "plugin" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
}

# Test: Multi-scope with four scopes (common use case)
@test "prepare_deploy_script.sh: multi-scope 'setup,plugins,config,agents' includes all four" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup,plugins,config,agents" "" "true"
    [ "$status" -eq 0 ]
    [ -f "$TEST_SQL_FILE" ]
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "plugin" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    grep -q "agents" "$TEST_SQL_FILE"
    ! grep -q "admin" "$TEST_SQL_FILE"
}

# Test: Multi-scope with spaces around commas
@test "prepare_deploy_script.sh: multi-scope handles spaces 'setup, config, agents'" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup, config, agents" "" "true"
    [ "$status" -eq 0 ]
    [ -f "$TEST_SQL_FILE" ]
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    grep -q "agents" "$TEST_SQL_FILE"
}

# Test: Error - combining 'all' with other scopes
@test "prepare_deploy_script.sh: error when 'all' combined with other scopes" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all,setup" "" "true"
    [ "$status" -ne 0 ]
    [[ "$output" == *"ERROR"* ]]
    [[ "$output" == *"cannot be combined"* ]]
}

# Test: Success - combining 'apikey' with other scopes (now allowed)
@test "prepare_deploy_script.sh: success when 'apikey' combined with other scopes" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup,plugins,config,agents,apikey" "" "true"
    [ "$status" -eq 0 ]
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "plugin" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    grep -q "agents" "$TEST_SQL_FILE"
    # Verify apikey content is included
    grep -q "Updating API Key" "$TEST_SQL_FILE" || grep -q "UPDATE_FROM_CONFIGURATIONS" "$TEST_SQL_FILE"
}

# Test: Error - combining 'teardown' with other scopes
@test "prepare_deploy_script.sh: error when 'teardown' combined with other scopes" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "teardown,config" "" "true"
    [ "$status" -ne 0 ]
    [[ "$output" == *"ERROR"* ]]
    [[ "$output" == *"cannot be combined"* ]]
}

# Test: Scope ordering doesn't affect output (files are sorted)
@test "prepare_deploy_script.sh: scope ordering independence 'config,setup' vs 'setup,config'" {
    TEST_SQL_FILE1=$(mktemp)
    TEST_SQL_FILE2=$(mktemp)

    bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE1" "test" "config,setup" "" "true"
    bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE2" "test" "setup,config" "" "true"

    run diff "$TEST_SQL_FILE1" "$TEST_SQL_FILE2"
    [ "$status" -eq 0 ]

    rm -f "$TEST_SQL_FILE1" "$TEST_SQL_FILE2"
}

# Test: All standard scopes without 'all' keyword
@test "prepare_deploy_script.sh: all standard scopes listed individually" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "init,admin,setup,plugins,config,agents" "" "true"
    [ "$status" -eq 0 ]
    [ -f "$TEST_SQL_FILE" ]
    grep -q "init" "$TEST_SQL_FILE"
    grep -q "admin" "$TEST_SQL_FILE"
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "plugin" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    grep -q "agents" "$TEST_SQL_FILE"
}

# Test: Single 'all' scope still works
@test "prepare_deploy_script.sh: single 'all' scope includes everything" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "true"
    [ "$status" -eq 0 ]
    [ -f "$TEST_SQL_FILE" ]
    grep -q "init" "$TEST_SQL_FILE"
    grep -q "admin" "$TEST_SQL_FILE"
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "plugin" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    grep -q "agents" "$TEST_SQL_FILE"
}

# Test: Multi-scope with init and admin
@test "prepare_deploy_script.sh: multi-scope 'init,admin,setup' includes privileged scopes" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "init,admin,setup" "" "true"
    [ "$status" -eq 0 ]
    [ -f "$TEST_SQL_FILE" ]
    grep -q "init" "$TEST_SQL_FILE"
    grep -q "admin" "$TEST_SQL_FILE"
    grep -q "setup" "$TEST_SQL_FILE"
}

# Test: Multi-scope excludes non-specified scopes
@test "prepare_deploy_script.sh: multi-scope 'setup,config' excludes other scopes" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup,config" "" "true"
    [ "$status" -eq 0 ]
    [ -f "$TEST_SQL_FILE" ]
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    ! grep -q "init" "$TEST_SQL_FILE"
    ! grep -q "admin" "$TEST_SQL_FILE"
    ! grep -q "agents" "$TEST_SQL_FILE"
}

# Test: Multi-scope 'agents,config' - regression test for file expansion issue
@test "prepare_deploy_script.sh: multi-scope 'agents,config' includes both files" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "agents,config" "" "true"
    [ "$status" -eq 0 ]
    [ -f "$TEST_SQL_FILE" ]
    # Verify both agents and config content are present
    grep -q "agents" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    # Verify excluded scopes are not present
    ! grep -q "init" "$TEST_SQL_FILE"
    ! grep -q "admin" "$TEST_SQL_FILE"
    ! grep -q "setup" "$TEST_SQL_FILE"
    ! grep -q "plugin" "$TEST_SQL_FILE"
    # Verify both SQL files were processed (check for script markers or content)
    # The script should include content from both 70_agents.sql and 40_config.sql
    line_count=$(wc -l < "$TEST_SQL_FILE")
    [ "$line_count" -ge 2 ]
}

# Test: apikey can be combined at the beginning
@test "prepare_deploy_script.sh: multi-scope 'apikey,setup,config' works with apikey first" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "apikey,setup,config" "" "true"
    [ "$status" -eq 0 ]
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    grep -q "UPDATE_FROM_CONFIGURATIONS" "$TEST_SQL_FILE"
}

# Test: apikey can be combined in the middle
@test "prepare_deploy_script.sh: multi-scope 'setup,apikey,config' works with apikey in middle" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup,apikey,config" "" "true"
    [ "$status" -eq 0 ]
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    grep -q "UPDATE_FROM_CONFIGURATIONS" "$TEST_SQL_FILE"
}

# Test: Full deployment flow without admin using apikey
@test "prepare_deploy_script.sh: multi-scope 'init,setup,plugins,config,agents,apikey' complete flow" {
    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "init,setup,plugins,config,agents,apikey" "" "true"
    [ "$status" -eq 0 ]
    grep -q "init" "$TEST_SQL_FILE"
    grep -q "setup" "$TEST_SQL_FILE"
    grep -q "plugin" "$TEST_SQL_FILE"
    grep -q "config" "$TEST_SQL_FILE"
    grep -q "agents" "$TEST_SQL_FILE"
    grep -q "UPDATE_FROM_CONFIGURATIONS" "$TEST_SQL_FILE"
    ! grep -q "admin" "$TEST_SQL_FILE"
}

# Test: File validation works correctly with multiple scopes
@test "prepare_deploy_script.sh: file validation handles multiple patterns correctly" {
    # Remove one of the required files to trigger validation error
    rm -f build/40_config.sql

    run bash scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "agents,config" "" "true"
    [ "$status" -ne 0 ]
    [[ "$output" == *"ERROR: Build file missing"* ]]
    [[ "$output" == *"40_config.sql"* ]]

    # Restore the file for other tests
    echo "-- Test config" > build/40_config.sql
    echo "SELECT 'config';" >> build/40_config.sql
}
