#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    TEST_SQL_FILE=$(mktemp)
    TEST_CONFIG_FILE=$(mktemp)

    # Ensure build directory has necessary files
    mkdir -p build/30_plugins build/09_upgrade

    # Copy files from package/build if they don't exist
    for file in 00_init.sql 10_admin.sql 20_setup.sql 40_config.sql 70_agents.sql; do
        if [ ! -f "build/$file" ] && [ -f "package/build/$file" ]; then
            cp "package/build/$file" "build/$file"
        fi
    done

    # Copy plugins if needed
    if [ -d "package/build/30_plugins" ]; then
        cp -r package/build/30_plugins/* build/30_plugins/ 2>/dev/null || true
    fi
}

teardown() {
    rm -f "$TEST_SQL_FILE" "$TEST_CONFIG_FILE"
    # Don't remove build files as they might be needed by other tests
    unset BUILD_CONFIG_FILE DTAGENT_TOKEN
}

@test "custom names: all objects with custom names" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.database.name",
    "TYPE": "string",
    "VALUE": "MY_CUSTOM_DB"
  },
  {
    "PATH": "core.snowflake.warehouse.name",
    "TYPE": "string",
    "VALUE": "MY_CUSTOM_WH"
  },
  {
    "PATH": "core.snowflake.resource_monitor.name",
    "TYPE": "string",
    "VALUE": "MY_CUSTOM_RS"
  },
  {
    "PATH": "core.snowflake.roles.owner",
    "TYPE": "string",
    "VALUE": "MY_CUSTOM_OWNER"
  },
  {
    "PATH": "core.snowflake.roles.admin",
    "TYPE": "string",
    "VALUE": "MY_CUSTOM_ADMIN"
  },
  {
    "PATH": "core.snowflake.roles.viewer",
    "TYPE": "string",
    "VALUE": "MY_CUSTOM_VIEWER"
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

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "admin,setup" "" "manual"
    if [ "$status" -ne 0 ]; then
        echo "Error output: $output"
    fi
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Verify custom names are used
    grep -q "MY_CUSTOM_OWNER" "$TEST_SQL_FILE"
    grep -q "MY_CUSTOM_DB" "$TEST_SQL_FILE"
    grep -q "MY_CUSTOM_WH" "$TEST_SQL_FILE"
    grep -q "MY_CUSTOM_ADMIN" "$TEST_SQL_FILE"
    grep -q "MY_CUSTOM_VIEWER" "$TEST_SQL_FILE"
    grep -q "MY_CUSTOM_RS" "$TEST_SQL_FILE"

    # Verify default names are NOT present (except in partial matches)
    ! grep -E "(^|[^A-Za-z0-9_$])DTAGENT_OWNER([^A-Za-z0-9_$]|$)" "$TEST_SQL_FILE"
    ! grep -E "use role DTAGENT_ADMIN" "$TEST_SQL_FILE"
    ! grep -E "create role if not exists DTAGENT_VIEWER" "$TEST_SQL_FILE"
    ! grep -E "create resource monitor if not exists DTAGENT_RS" "$TEST_SQL_FILE"
}

@test "custom names: partial replacement (only database and warehouse)" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.database.name",
    "TYPE": "string",
    "VALUE": "ANALYTICS_DB"
  },
  {
    "PATH": "core.snowflake.warehouse.name",
    "TYPE": "string",
    "VALUE": "ANALYTICS_WH"
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

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "admin,setup" "" "manual"
    [ "$status" -eq 0 ]

    # Verify custom names are used
    grep -q "ANALYTICS_DB" "$TEST_SQL_FILE"
    grep -q "ANALYTICS_WH" "$TEST_SQL_FILE"

    # Verify default names remain for non-customized objects
    grep -q "DTAGENT_OWNER" "$TEST_SQL_FILE"
    grep -q "DTAGENT_ADMIN" "$TEST_SQL_FILE"
    grep -q "DTAGENT_VIEWER" "$TEST_SQL_FILE"
    grep -q "DTAGENT_RS" "$TEST_SQL_FILE"
}

@test "custom names: no custom names (use defaults)" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.dynatrace_tenant_address",
    "TYPE": "string",
    "VALUE": "test.dynatrace.com"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "admin,setup" "" "manual"
    [ "$status" -eq 0 ]

    # Verify all default names are present
    grep -q "DTAGENT_DB" "$TEST_SQL_FILE"
    grep -q "DTAGENT_WH" "$TEST_SQL_FILE"
    grep -q "DTAGENT_OWNER" "$TEST_SQL_FILE"
    grep -q "DTAGENT_ADMIN" "$TEST_SQL_FILE"
    grep -q "DTAGENT_VIEWER" "$TEST_SQL_FILE"
    grep -q "DTAGENT_RS" "$TEST_SQL_FILE"
}

@test "custom names: reject invalid name with spaces" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.database.name",
    "TYPE": "string",
    "VALUE": "MY INVALID DB"
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

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup" "" "manual"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Invalid database name"* ]]
    [[ "$output" == *"contains spaces"* ]]
}

@test "custom names: reject invalid name with special characters" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.warehouse.name",
    "TYPE": "string",
    "VALUE": "MY-WAREHOUSE"
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

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup" "" "manual"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Invalid warehouse name"* ]]
}

@test "custom names: reject name starting with number" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.roles.owner",
    "TYPE": "string",
    "VALUE": "123_OWNER"
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

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup" "" "manual"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Invalid owner role name"* ]]
}

@test "custom names: accept valid names with underscores and numbers" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.snowflake.database.name",
    "TYPE": "string",
    "VALUE": "DB_ANALYTICS_2024"
  },
  {
    "PATH": "core.snowflake.warehouse.name",
    "TYPE": "string",
    "VALUE": "WH_COMPUTE_01"
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

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup" "" "manual"
    [ "$status" -eq 0 ]

    grep -q "DB_ANALYTICS_2024" "$TEST_SQL_FILE"
    grep -q "WH_COMPUTE_01" "$TEST_SQL_FILE"
}

@test "custom names: TAG and custom names work together (custom names used, TAG for telemetry)" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "string",
    "VALUE": "ENV01"
  },
  {
    "PATH": "core.snowflake.database.name",
    "TYPE": "string",
    "VALUE": "MY_CUSTOM_DB"
  },
  {
    "PATH": "core.snowflake.warehouse.name",
    "TYPE": "string",
    "VALUE": "MY_CUSTOM_WH"
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

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "admin,setup" "" "manual"
    [ "$status" -eq 0 ]

    # Verify custom names are used (not TAG-based names)
    grep -q "MY_CUSTOM_DB" "$TEST_SQL_FILE"
    grep -q "MY_CUSTOM_WH" "$TEST_SQL_FILE"

    # Verify TAG-based names are NOT used for these customized objects
    ! grep -E "(^|[^A-Za-z0-9_$])DTAGENT_ENV01_DB([^A-Za-z0-9_$]|$)" "$TEST_SQL_FILE"
    ! grep -E "(^|[^A-Za-z0-9_$])DTAGENT_ENV01_WH([^A-Za-z0-9_$]|$)" "$TEST_SQL_FILE"

    # When any custom name is used, TAG does NOT affect object naming at all
    # Objects without custom names use DEFAULT names (not TAG-based names)
    grep -q "DTAGENT_OWNER" "$TEST_SQL_FILE"
    grep -q "DTAGENT_ADMIN" "$TEST_SQL_FILE"
    grep -q "DTAGENT_VIEWER" "$TEST_SQL_FILE"

    # Verify TAG-based names are NOT used for any objects
    ! grep -E "(^|[^A-Za-z0-9_$])DTAGENT_ENV01_OWNER([^A-Za-z0-9_$]|$)" "$TEST_SQL_FILE"
    ! grep -E "(^|[^A-Za-z0-9_$])DTAGENT_ENV01_ADMIN([^A-Za-z0-9_$]|$)" "$TEST_SQL_FILE"
    ! grep -E "(^|[^A-Za-z0-9_$])DTAGENT_ENV01_VIEWER([^A-Za-z0-9_$]|$)" "$TEST_SQL_FILE"
}

@test "custom names: TAG works when no custom names set" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "string",
    "VALUE": "TEST"
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

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "setup" "" "manual"
    [ "$status" -eq 0 ]

    # Verify TAG-based names are used
    grep -q "DTAGENT_TEST_DB" "$TEST_SQL_FILE"
    grep -q "DTAGENT_TEST_WH" "$TEST_SQL_FILE"
    grep -q "DTAGENT_TEST_OWNER" "$TEST_SQL_FILE"
}

@test "OPTION filtering: resource_monitor disabled removes all references" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
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

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "init,setup" "" "manual"
    [ "$status" -eq 0 ]

    # Verify resource monitor creation is NOT present (init scope)
    ! grep -q "create resource monitor" "$TEST_SQL_FILE"

    # Verify P_UPDATE_RESOURCE_MONITOR procedure definition is NOT present (setup scope)
    ! grep -q "create or replace procedure.*P_UPDATE_RESOURCE_MONITOR" "$TEST_SQL_FILE"

    # Verify calls to P_UPDATE_RESOURCE_MONITOR are NOT present (setup scope - indented blocks)
    ! grep -q "call.*P_UPDATE_RESOURCE_MONITOR" "$TEST_SQL_FILE"
}

@test "OPTION filtering: indented markers work correctly" {
    # Create a test SQL file with indented OPTION markers
    TEST_INPUT_FILE=$(mktemp)
    cat > "$TEST_INPUT_FILE" << 'EOF'
-- Normal code
SELECT 1;

-- Indented block with OPTION markers (like in stored procedure)
CREATE PROCEDURE TEST_PROC()
AS
$$
BEGIN
    --%OPTION:resource_monitor:
    CALL P_UPDATE_RESOURCE_MONITOR();
    --%:OPTION:resource_monitor

    SELECT 'after block';
END;
$$;

-- More normal code
SELECT 2;
EOF

    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
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

    # Get excluded options and apply filter directly
    EXCLUDED_OPTIONS=$(./scripts/deploy/list_options_to_exclude.sh)

    # Apply the filter using the same logic as prepare_deploy_script.sh
    local temp_file=$(mktemp)
    cp "$TEST_INPUT_FILE" "$temp_file"

    for option_name in $EXCLUDED_OPTIONS; do
        awk -v option="$option_name" '
            BEGIN { active=1; }
            {
                # Check for start marker: --%OPTION:option_name: or #%OPTION:option_name: (with optional leading whitespace)
                if ($0 ~ /^[ \t]*(--|#)%OPTION:/) {
                    start_pattern = "%OPTION:" option ":"
                    if (index($0, start_pattern) > 0) {
                        active=0;
                    }
                }

                # Print line only if active
                if (active==1) print $0;

                # Check for end marker: --%:OPTION:option_name or #%:OPTION:option_name (with optional leading whitespace)
                if ($0 ~ /^[ \t]*(--|#)%:OPTION:/) {
                    end_pattern = "%:OPTION:" option
                    # Make sure we match the exact option name, not a prefix
                    if (index($0, end_pattern) > 0) {
                        # Check if followed by end of line or whitespace
                        idx = index($0, end_pattern)
                        len = length(end_pattern)
                        rest = substr($0, idx + len)
                        if (rest == "" || rest ~ /^[ \t]*$/) {
                            active=1;
                        }
                    }
                }
            }
        ' "$temp_file" > "$TEST_SQL_FILE"
        cp "$TEST_SQL_FILE" "$temp_file"
    done
    rm -f "$temp_file"

    # Verify the indented block was removed
    ! grep -q "P_UPDATE_RESOURCE_MONITOR" "$TEST_SQL_FILE"

    # Verify code before and after remains
    grep -q "SELECT 1" "$TEST_SQL_FILE"
    grep -q "SELECT 'after block'" "$TEST_SQL_FILE"
    grep -q "SELECT 2" "$TEST_SQL_FILE"

    rm -f "$TEST_INPUT_FILE"
}

@test "OPTION filtering: non-indented markers work correctly" {
    # Create a test SQL file with non-indented OPTION markers
    TEST_INPUT_FILE=$(mktemp)
    cat > "$TEST_INPUT_FILE" << 'EOF'
-- Normal code
SELECT 1;

--%OPTION:resource_monitor:
CREATE RESOURCE MONITOR TEST_RS;
--%:OPTION:resource_monitor

-- More normal code
SELECT 2;
EOF

    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
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

    # Get excluded options and apply filter directly
    EXCLUDED_OPTIONS=$(./scripts/deploy/list_options_to_exclude.sh)

    # Apply the filter using the same logic as prepare_deploy_script.sh
    local temp_file=$(mktemp)
    cp "$TEST_INPUT_FILE" "$temp_file"

    for option_name in $EXCLUDED_OPTIONS; do
        awk -v option="$option_name" '
            BEGIN { active=1; }
            {
                # Check for start marker: --%OPTION:option_name: or #%OPTION:option_name: (with optional leading whitespace)
                if ($0 ~ /^[ \t]*(--|#)%OPTION:/) {
                    start_pattern = "%OPTION:" option ":"
                    if (index($0, start_pattern) > 0) {
                        active=0;
                    }
                }

                # Print line only if active
                if (active==1) print $0;

                # Check for end marker: --%:OPTION:option_name or #%:OPTION:option_name (with optional leading whitespace)
                if ($0 ~ /^[ \t]*(--|#)%:OPTION:/) {
                    end_pattern = "%:OPTION:" option
                    # Make sure we match the exact option name, not a prefix
                    if (index($0, end_pattern) > 0) {
                        # Check if followed by end of line or whitespace
                        idx = index($0, end_pattern)
                        len = length(end_pattern)
                        rest = substr($0, idx + len)
                        if (rest == "" || rest ~ /^[ \t]*$/) {
                            active=1;
                        }
                    }
                }
            }
        ' "$temp_file" > "$TEST_SQL_FILE"
        cp "$TEST_SQL_FILE" "$temp_file"
    done
    rm -f "$temp_file"
    
    # Verify the block was removed
    ! grep -q "CREATE RESOURCE MONITOR" "$TEST_SQL_FILE"
    
    # Verify code before and after remains
    grep -q "SELECT 1" "$TEST_SQL_FILE"
    grep -q "SELECT 2" "$TEST_SQL_FILE"
    
    rm -f "$TEST_INPUT_FILE"
}
