#!/usr/bin/env bats

setup() {
    TEST_DIR="$(mktemp -d)"
    cp test/bash/test_object.json "$TEST_DIR/"
    cp test/bash/test_array.json "$TEST_DIR/"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "convert object JSON to YAML" {
    run scripts/deploy/convert_config_to_yaml.sh "$TEST_DIR/test_object.json"
    [ "$status" -eq 0 ]
    [ -f "$TEST_DIR/test_object.yml" ]
    run cat "$TEST_DIR/test_object.yml"
    [[ "$output" == *"core:"* ]]
    [[ "$output" == *"dynatrace_tenant_address: test.com"* ]]
}

@test "convert array JSON to multiple YAMLs" {
    run scripts/deploy/convert_config_to_yaml.sh "$TEST_DIR/test_array.json"
    [ "$status" -eq 0 ]
    [ -f "$TEST_DIR/test_array.yml" ]
    [ -f "$TEST_DIR/test_array_1.yml" ]
    run cat "$TEST_DIR/test_array.yml"
    [[ "$output" == *"core:"* ]]
    [[ "$output" == *"dynatrace_tenant_address: test1.com"* ]]
    run cat "$TEST_DIR/test_array_1.yml"
    [[ "$output" == *"dynatrace_tenant_address: test2.com"* ]]
}

@test "fail without argument" {
    run scripts/deploy/convert_config_to_yaml.sh
    [ "$status" -eq 1 ]
    [[ "$output" == *"Usage"* ]]
}

@test "migrate old SNOWFLAKE_* keys to nested structure" {
    # Create old format JSON with SNOWFLAKE_* keys
    cat > "$TEST_DIR/test-old-format.json" <<'EOF'
[
    {
        "CORE": {
            "DYNATRACE_TENANT_ADDRESS": "test.dynatrace.com",
            "DEPLOYMENT_ENVIRONMENT": "TEST",
            "SNOWFLAKE_ACCOUNT_NAME": "myaccount.us-east-1",
            "SNOWFLAKE_HOST_NAME": "myaccount.us-east-1.snowflakecomputing.com",
            "SNOWFLAKE_CREDIT_QUOTA": 10,
            "SNOWFLAKE_DATA_RETENTION_TIME_IN_DAYS": 7,
            "LOG_LEVEL": "DEBUG"
        },
        "PLUGINS": {
            "DISABLED_BY_DEFAULT": true
        }
    }
]
EOF

    run scripts/deploy/convert_config_to_yaml.sh "$TEST_DIR/test-old-format.json"
    [ "$status" -eq 0 ]
    [ -f "$TEST_DIR/test-old-format.yml" ]

    # Read the output for verification
    output=$(cat "$TEST_DIR/test-old-format.yml")

    # Verify new structure exists
    [[ "$output" == *"snowflake:"* ]]
    [[ "$output" == *"account_name: myaccount.us-east-1"* ]]
    [[ "$output" == *"host_name: myaccount.us-east-1.snowflakecomputing.com"* ]]

    # Verify resource_monitor nested structure
    [[ "$output" == *"resource_monitor:"* ]]
    [[ "$output" == *"credit_quota: 10"* ]]

    # Verify database nested structure
    [[ "$output" == *"database:"* ]]
    [[ "$output" == *"data_retention_time_in_days: 7"* ]]

    # Verify old keys are removed
    [[ "$output" != *"snowflake_account_name:"* ]]
    [[ "$output" != *"snowflake_host_name:"* ]]
    [[ "$output" != *"snowflake_credit_quota:"* ]]
    [[ "$output" != *"snowflake_data_retention_time_in_days:"* ]]
}
