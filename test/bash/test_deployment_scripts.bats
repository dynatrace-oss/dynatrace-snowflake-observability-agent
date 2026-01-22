#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Create minimal test config and build artifacts
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  },
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"

    # Create necessary build artifacts for deployment tests
    mkdir -p build/09_upgrade build/30_plugins conf
    echo "SELECT 'init';" > build/00_init.sql
    echo "SELECT 'admin';" > build/10_admin.sql
    echo "SELECT 'setup';" > build/20_setup.sql
    echo "SELECT 'config';" > build/40_config.sql
    echo "SELECT 'agents';" > build/70_agents.sql
    echo "SELECT 'upgrade 1.0.0';" > build/09_upgrade/v1.0.0.sql
    echo "SELECT 'plugin';" > build/30_plugins/test_plugin.sql

    # Create minimal config file
    cp "$TEST_CONFIG_FILE" "conf/config-test.json"
    echo "core:" > "conf/config-test.yml"
    echo "  tag: TEST" >> "conf/config-test.yml"
}

teardown() {
    rm -f "$TEST_CONFIG_FILE"
    rm -f conf/config-test.json conf/config-test.yml
    rm -f build/00_init.sql build/10_admin.sql build/20_setup.sql build/40_config.sql build/70_agents.sql
    rm -rf build/09_upgrade build/30_plugins
    unset BUILD_CONFIG_FILE
}

@test "setup.sh checks for missing tools" {
    run ./scripts/deploy/setup.sh
    # It should check for jq, etc., and may install if missing
    # But in test, just check it runs
    [ "$status" -eq 0 ] || [ "$status" -eq 1 ]
}

@test "deploy.sh requires ENV parameter" {
    run ./scripts/deploy/deploy.sh
    [ "$status" -ne 0 ]  # Should fail without ENV
}

@test "deploy.sh manual mode produces deployment file" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    DEPLOY_SCRIPT="test-manual-mode.sql"
    # Run deploy in manual mode with init scope (simpler than all)
    run timeout 30 ./scripts/deploy/deploy.sh test --scope=init --output-file="$DEPLOY_SCRIPT" --options=manual,skip_confirm
    [ "$status" -eq 0 ]

    # Check that deployment script was created
    [ -f "$DEPLOY_SCRIPT" ]

    # Verify the file contains expected content
    grep -q "init" "$DEPLOY_SCRIPT"

    # Cleanup
    rm -f "$DEPLOY_SCRIPT"
}

@test "deploy.sh init scope generates correct deployment" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    DEPLOY_SCRIPT="test-init-scope.sql"
    run timeout 30 ./scripts/deploy/deploy.sh test --scope=init --output-file="$DEPLOY_SCRIPT" --options=manual,skip_confirm
    [ "$status" -eq 0 ]

    [ -f "$DEPLOY_SCRIPT" ]
    grep -q "init" "$DEPLOY_SCRIPT"
    ! grep -q "setup" "$DEPLOY_SCRIPT"
    ! grep -q "agents" "$DEPLOY_SCRIPT"

    rm -f "$DEPLOY_SCRIPT"
}

@test "deploy.sh setup scope generates correct deployment" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    DEPLOY_SCRIPT="test-setup-scope.sql"
    run timeout 30 ./scripts/deploy/deploy.sh test --scope=setup --output-file="$DEPLOY_SCRIPT" --options=manual,skip_confirm
    [ "$status" -eq 0 ]

    [ -f "$DEPLOY_SCRIPT" ]
    grep -q "setup" "$DEPLOY_SCRIPT"
    ! grep -q "init" "$DEPLOY_SCRIPT"
    ! grep -q "agents" "$DEPLOY_SCRIPT"

    rm -f "$DEPLOY_SCRIPT"
}

@test "deploy.sh plugins scope generates correct deployment" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    DEPLOY_SCRIPT="test-plugins-scope.sql"
    run timeout 30 ./scripts/deploy/deploy.sh test --scope=plugins --output-file="$DEPLOY_SCRIPT" --options=manual,skip_confirm
    [ "$status" -eq 0 ]

    [ -f "$DEPLOY_SCRIPT" ]
    grep -q "plugin" "$DEPLOY_SCRIPT"
    ! grep -q "init" "$DEPLOY_SCRIPT"
    ! grep -q "setup" "$DEPLOY_SCRIPT"

    rm -f "$DEPLOY_SCRIPT"
}

@test "deploy.sh config scope generates correct deployment" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    DEPLOY_SCRIPT="test-config-scope.sql"
    run timeout 30 ./scripts/deploy/deploy.sh test --scope=config --output-file="$DEPLOY_SCRIPT" --options=manual,skip_confirm
    [ "$status" -eq 0 ]

    [ -f "$DEPLOY_SCRIPT" ]
    grep -q "config" "$DEPLOY_SCRIPT"
    ! grep -q "init" "$DEPLOY_SCRIPT"
    ! grep -q "agents" "$DEPLOY_SCRIPT"

    rm -f "$DEPLOY_SCRIPT"
}

@test "deploy.sh agents scope generates correct deployment" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    DEPLOY_SCRIPT="test-agents-scope.sql"
    run timeout 30 ./scripts/deploy/deploy.sh test --scope=agents --output-file="$DEPLOY_SCRIPT" --options=manual,skip_confirm
    [ "$status" -eq 0 ]

    [ -f "$DEPLOY_SCRIPT" ]
    grep -q "agents" "$DEPLOY_SCRIPT"
    ! grep -q "init" "$DEPLOY_SCRIPT"
    ! grep -q "setup" "$DEPLOY_SCRIPT"

    rm -f "$DEPLOY_SCRIPT"
}

@test "deploy.sh all scope generates complete deployment" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    DEPLOY_SCRIPT="test-all-scope.sql"
    run timeout 30 ./scripts/deploy/deploy.sh test --scope=all --output-file="$DEPLOY_SCRIPT" --options=manual,skip_confirm
    [ "$status" -eq 0 ]

    cat "$DEPLOY_SCRIPT"

    [ -f "$DEPLOY_SCRIPT" ]
    # All scope should include all components
    grep -q "init" "$DEPLOY_SCRIPT"
    grep -q "setup" "$DEPLOY_SCRIPT"
    grep -q "plugin" "$DEPLOY_SCRIPT"
    grep -q "config" "$DEPLOY_SCRIPT"
    grep -q "agents" "$DEPLOY_SCRIPT"

    rm -f "$DEPLOY_SCRIPT"
}

@test "deploy.sh upgrade scope requires from-version parameter" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    run timeout 30 ./scripts/deploy/deploy.sh test --scope=upgrade --options=manual,skip_confirm
    [ "$status" -ne 0 ]
    [[ "$output" =~ "--from-version" ]]
}

@test "deploy.sh upgrade scope with from-version generates correct deployment" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    DEPLOY_SCRIPT="test-upgrade-scope.sql"
    run timeout 30 ./scripts/deploy/deploy.sh test --scope=upgrade --from-version=0.9.0 --output-file="$DEPLOY_SCRIPT" --options=manual,skip_confirm
    [ "$status" -eq 0 ]

    [ -f "$DEPLOY_SCRIPT" ]
    grep -q "upgrade" "$DEPLOY_SCRIPT"
    ! grep -q "init" "$DEPLOY_SCRIPT"

    rm -f "$DEPLOY_SCRIPT"
}
