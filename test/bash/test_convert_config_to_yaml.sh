#!/usr/bin/env bash
#
# Test script for convert_config_to_yaml.sh migration functionality
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONVERT_SCRIPT="$PROJECT_ROOT/scripts/deploy/convert_config_to_yaml.sh"

# Create a temporary directory for test files
TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

echo "Testing config path migration in convert_config_to_yaml.sh..."

# Test 1: Old format JSON with SNOWFLAKE_* keys
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

# Run the conversion
bash "$CONVERT_SCRIPT" "$TEST_DIR/test-old-format.json"

# Verify the output file exists
if [ ! -f "$TEST_DIR/test-old-format.yml" ]; then
    echo "ERROR: Output YAML file was not created"
    exit 1
fi

# Verify new structure exists
if ! grep -q "snowflake:" "$TEST_DIR/test-old-format.yml"; then
    echo "ERROR: New 'snowflake:' section not found"
    exit 1
fi

if ! grep -q "account_name: myaccount.us-east-1" "$TEST_DIR/test-old-format.yml"; then
    echo "ERROR: account_name not migrated correctly"
    exit 1
fi

if ! grep -q "host_name: myaccount.us-east-1.snowflakecomputing.com" "$TEST_DIR/test-old-format.yml"; then
    echo "ERROR: host_name not migrated correctly"
    exit 1
fi

if ! grep -q "credit_quota: 10" "$TEST_DIR/test-old-format.yml"; then
    echo "ERROR: credit_quota not migrated correctly"
    exit 1
fi

if ! grep -q "data_retention_time_in_days: 7" "$TEST_DIR/test-old-format.yml"; then
    echo "ERROR: data_retention_time_in_days not migrated correctly"
    exit 1
fi

# Verify old keys are removed
if grep -q "snowflake_account_name:" "$TEST_DIR/test-old-format.yml"; then
    echo "ERROR: Old key 'snowflake_account_name' still present"
    exit 1
fi

if grep -q "snowflake_host_name:" "$TEST_DIR/test-old-format.yml"; then
    echo "ERROR: Old key 'snowflake_host_name' still present"
    exit 1
fi

if grep -q "snowflake_credit_quota:" "$TEST_DIR/test-old-format.yml"; then
    echo "ERROR: Old key 'snowflake_credit_quota' still present"
    exit 1
fi

echo "✓ All migration tests passed!"

# Display the converted file for manual inspection
echo ""
echo "Converted YAML output:"
cat "$TEST_DIR/test-old-format.yml"

exit 0
