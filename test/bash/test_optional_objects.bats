#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    TEST_SQL_FILE=$(mktemp)

    # Create build directory structure
    mkdir -p build/30_plugins

    # Create test SQL files with OPTION blocks
    cat > build/10_admin.sql << 'EOSQL'
-- Admin setup
use role DTAGENT_OWNER;

--%OPTION:dtagent_admin:
-- Create admin role
create role if not exists DTAGENT_ADMIN;
grant role DTAGENT_ADMIN to role DTAGENT_OWNER;

-- Grant admin privileges
grant manage grants on account to role DTAGENT_ADMIN;
--%:OPTION:dtagent_admin

-- Continue with other setup
select 'admin setup complete';
EOSQL

    cat > build/20_setup.sql << 'EOSQL'
-- Setup
use role DTAGENT_OWNER;

--%OPTION:resource_monitor:
-- Create resource monitor
create or replace resource monitor DTAGENT_RS with
  credit_quota = 100;
alter warehouse DTAGENT_WH set resource_monitor = DTAGENT_RS;
--%:OPTION:resource_monitor

-- Create warehouse (always)
create warehouse if not exists DTAGENT_WH;

--%OPTION:dtagent_admin:
-- Admin-only grants
grant operate on warehouse DTAGENT_WH to role DTAGENT_ADMIN;
--%:OPTION:dtagent_admin
EOSQL

    cat > build/40_config.sql << 'EOSQL'
-- Config procedures
create or replace procedure CONFIG.UPDATE_CONFIG()
returns string
as
begin
  return 'config updated';
end;

--%OPTION:resource_monitor:
create or replace procedure CONFIG.P_UPDATE_RESOURCE_MONITOR(credit_quota int)
returns string
as
begin
  alter resource monitor DTAGENT_RS set credit_quota = :credit_quota;
  return 'resource monitor updated';
end;
--%:OPTION:resource_monitor
EOSQL
}

teardown() {
    rm -f "$TEST_SQL_FILE" "$TEST_CONFIG_FILE"
    rm -rf build/10_admin.sql build/20_setup.sql build/40_config.sql build/30_plugins
    unset BUILD_CONFIG_FILE
}

@test "optional objects: both admin and resource monitor disabled" {
    # Create config with both admin and resource monitor disabled
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.roles.admin",
    "TYPE": "string",
    "VALUE": "-"
  },
  {
    "PATH": "core.snowflake.resource_monitor.name",
    "TYPE": "string",
    "VALUE": "-"
  },
  {
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    # Use only setup,config scope (not admin) since admin role is disabled
    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup,config" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should NOT contain admin role references
    ! grep -q "create role if not exists DTAGENT_ADMIN" "$TEST_SQL_FILE"
    ! grep -q "grant manage grants on account to role DTAGENT_ADMIN" "$TEST_SQL_FILE"
    ! grep -q "grant operate on warehouse DTAGENT_WH to role DTAGENT_ADMIN" "$TEST_SQL_FILE"

    # Should NOT contain resource monitor references
    ! grep -q "create or replace resource monitor DTAGENT_RS" "$TEST_SQL_FILE"
    ! grep -q "alter warehouse DTAGENT_WH set resource_monitor" "$TEST_SQL_FILE"
    ! grep -q "P_UPDATE_RESOURCE_MONITOR" "$TEST_SQL_FILE"

    # Should still contain regular code (from setup and config scopes)
    grep -q "create warehouse if not exists DTAGENT_WH" "$TEST_SQL_FILE"
    grep -q "CONFIG.UPDATE_CONFIG()" "$TEST_SQL_FILE"
}

@test "optional objects: admin enabled, resource monitor disabled" {
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.roles.admin",
    "TYPE": "string",
    "VALUE": "CUSTOM_ADMIN_ROLE"
  },
  {
    "PATH": "core.snowflake.resource_monitor.name",
    "TYPE": "string",
    "VALUE": "-"
  },
  {
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "admin,setup,config" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should contain admin role references (with custom name)
    grep -q "create role if not exists CUSTOM_ADMIN_ROLE" "$TEST_SQL_FILE"
    grep -q "grant manage grants on account to role CUSTOM_ADMIN_ROLE" "$TEST_SQL_FILE"

    # Should NOT contain resource monitor references
    ! grep -q "create or replace resource monitor DTAGENT_RS" "$TEST_SQL_FILE"
    ! grep -q "P_UPDATE_RESOURCE_MONITOR" "$TEST_SQL_FILE"

    # Should contain regular code
    grep -q "create warehouse if not exists DTAGENT_WH" "$TEST_SQL_FILE"
}

@test "optional objects: admin disabled, resource monitor enabled" {
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.roles.admin",
    "TYPE": "string",
    "VALUE": "-"
  },
  {
    "PATH": "core.snowflake.resource_monitor.name",
    "TYPE": "string",
    "VALUE": "CUSTOM_RM"
  },
  {
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    # Use only setup,config scope (not admin) since admin role is disabled
    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup,config" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should NOT contain admin role references
    ! grep -q "grant manage grants on account to role DTAGENT_ADMIN" "$TEST_SQL_FILE"
    ! grep -q "grant operate on warehouse DTAGENT_WH to role DTAGENT_ADMIN" "$TEST_SQL_FILE"

    # Should contain resource monitor references (with custom name)
    grep -q "create or replace resource monitor CUSTOM_RM" "$TEST_SQL_FILE"
    grep -q "alter warehouse DTAGENT_WH set resource_monitor" "$TEST_SQL_FILE"
    grep -q "P_UPDATE_RESOURCE_MONITOR" "$TEST_SQL_FILE"
}

@test "optional objects: both admin and resource monitor enabled" {
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.roles.admin",
    "TYPE": "string",
    "VALUE": "DTAGENT_ADMIN"
  },
  {
    "PATH": "core.snowflake.resource_monitor.name",
    "TYPE": "string",
    "VALUE": "DTAGENT_RS"
  },
  {
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "admin,setup,config" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should contain admin role references
    grep -q "create role if not exists DTAGENT_ADMIN" "$TEST_SQL_FILE"
    grep -q "grant manage grants on account to role DTAGENT_ADMIN" "$TEST_SQL_FILE"

    # Should contain resource monitor references
    grep -q "create or replace resource monitor DTAGENT_RS" "$TEST_SQL_FILE"
    grep -q "P_UPDATE_RESOURCE_MONITOR" "$TEST_SQL_FILE"
}

@test "optional objects: admin scope rejected when admin role disabled" {
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.roles.admin",
    "TYPE": "string",
    "VALUE": "-"
  },
  {
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "admin" "" "manual"
    [ "$status" -ne 0 ]
    [[ "$output" =~ "ERROR: Deployment scope 'admin' was requested" ]]
    [[ "$output" =~ "core.snowflake.roles.admin is set to '-' (disabled)" ]]
}

@test "optional objects: non-admin scope works when admin disabled" {
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.roles.admin",
    "TYPE": "string",
    "VALUE": "-"
  },
  {
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup,config" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should contain setup code
    grep -q "create warehouse if not exists DTAGENT_WH" "$TEST_SQL_FILE"
}
