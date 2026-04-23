#!/usr/bin/env bats
#
# Tests for deploy.sh --defaults mode
#

setup() {
    # shellcheck disable=SC2154
    cd "$BATS_TEST_DIRNAME/../.." || exit 1

    # Create minimal build artifacts
    mkdir -p build/09_upgrade build/30_plugins conf
    echo "SELECT 'init';" > build/00_init.sql
    echo "SELECT 'admin'; CREATE ROLE IF NOT EXISTS DTAGENT_ADMIN;" > build/10_admin.sql
    echo "SELECT 'setup'; CREATE SCHEMA IF NOT EXISTS MAIN_SCHEMA;" > build/20_setup.sql
    echo "SELECT 'config';" > build/40_config.sql
    echo "SELECT 'agents';" > build/70_agents.sql
    echo "SELECT 'plugin';" > build/30_plugins/test_plugin.sql

    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    # Ensure no leftover config
    rm -f conf/config-defaults-test.yml
}

teardown() {
    rm -f conf/config-defaults-test.yml
    rm -f build/00_init.sql build/10_admin.sql build/20_setup.sql build/40_config.sql build/70_agents.sql
    rm -rf build/09_upgrade build/30_plugins
    unset DSOA_DT_TENANT DSOA_DEPLOYMENT_ENV DSOA_SF_ACCOUNT
}

@test "--defaults with all env vars generates config file" {
    export DSOA_DT_TENANT="abc12345.live.dynatrace.com"
    export DSOA_DEPLOYMENT_ENV="PRODUCTION"
    export DSOA_SF_ACCOUNT="myorg-myaccount"

    run ./scripts/deploy/deploy.sh --env=defaults-test --defaults --scope=init --options=manual,skip_confirm
    [ "$status" -eq 0 ]
    [ -f "conf/config-defaults-test.yml" ]
}

@test "--defaults sets dynatrace_tenant_address from DSOA_DT_TENANT" {
    export DSOA_DT_TENANT="abc12345.live.dynatrace.com"
    export DSOA_DEPLOYMENT_ENV="PRODUCTION"
    export DSOA_SF_ACCOUNT="myorg-myaccount"

    run ./scripts/deploy/deploy.sh --env=defaults-test --defaults --scope=init --options=manual,skip_confirm
    [ "$status" -eq 0 ]
    grep -q "abc12345.live.dynatrace.com" conf/config-defaults-test.yml
}

@test "--defaults sets snowflake account_name from DSOA_SF_ACCOUNT" {
    export DSOA_DT_TENANT="abc12345.live.dynatrace.com"
    export DSOA_DEPLOYMENT_ENV="PRODUCTION"
    export DSOA_SF_ACCOUNT="myorg-myaccount"

    run ./scripts/deploy/deploy.sh --env=defaults-test --defaults --scope=init --options=manual,skip_confirm
    [ "$status" -eq 0 ]
    grep -q "myorg-myaccount" conf/config-defaults-test.yml
}

@test "--defaults without DSOA_DT_TENANT fails with error" {
    unset DSOA_DT_TENANT
    export DSOA_DEPLOYMENT_ENV="PRODUCTION"
    export DSOA_SF_ACCOUNT="myorg-myaccount"

    run ./scripts/deploy/deploy.sh --env=defaults-test --defaults --scope=init --options=manual,skip_confirm
    [ "$status" -ne 0 ]
    echo "$output" | grep -qi "DSOA_DT_TENANT"
}

@test "--defaults with existing config uses it without regenerating" {
    # Pre-create config
    mkdir -p conf
    cat > conf/config-defaults-test.yml << 'EOF'
core:
  dynatrace_tenant_address: "existing.live.dynatrace.com"
  deployment_environment: "EXISTING"
  snowflake:
    account_name: "existing-account"
  log_level: "WARN"
  procedure_timeout: 3600
plugins:
  deploy_disabled_plugins: true
EOF

    export DSOA_DT_TENANT="new-tenant.live.dynatrace.com"

    run ./scripts/deploy/deploy.sh --env=defaults-test --defaults --scope=init --options=manual,skip_confirm
    [ "$status" -eq 0 ]
    # Should still have the original content, not the new tenant
    grep -q "existing.live.dynatrace.com" conf/config-defaults-test.yml
}

@test "--defaults implicitly sets skip_confirm" {
    export DSOA_DT_TENANT="abc12345.live.dynatrace.com"
    export DSOA_DEPLOYMENT_ENV="PRODUCTION"
    export DSOA_SF_ACCOUNT="myorg-myaccount"

    # Run with manual mode — if skip_confirm is set, it won't hang waiting for input
    DEPLOY_SCRIPT="test-defaults-skip.sql"
    run timeout 10 ./scripts/deploy/deploy.sh --env=defaults-test --defaults --scope=init --output-file="$DEPLOY_SCRIPT" --options=manual
    [ "$status" -eq 0 ]
    rm -f "$DEPLOY_SCRIPT"
}
