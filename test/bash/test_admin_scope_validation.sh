#!/usr/bin/env bash
#
# Integration test for admin scope with disabled admin role
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Create a temporary directory for test files
TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

echo "Testing admin scope deployment with disabled admin role..."

# Test: Deploy with admin scope when admin role is disabled
echo "Test: Attempting admin scope deployment with admin role disabled (should fail)"

# Create config with admin disabled
cat > "$TEST_DIR/config-no-admin.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test-account
    host_name: test-account.snowflakecomputing.com
    roles:
      admin: "-"
    resource_monitor:
      credit_quota: 5
EOF

# Mock the deployment environment
export ENV="test-no-admin"
export BUILD_DIR="$TEST_DIR/build"
mkdir -p "$BUILD_DIR"

# Copy the config to test location
cp "$TEST_DIR/config-no-admin.yml" "$TEST_DIR/config-$ENV.yml"

# Prepare the config in JSON format (simulate prepare_config.sh)
cd "$TEST_DIR"
cat "config-$ENV.yml" | yq -o json '.' | jq -r '
    def flatten:
      . as $in
      | (paths(scalars|true) as $p
      | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
      | $out;
    [flatten]
  ' > "$BUILD_DIR/config.json"

export BUILD_CONFIG_FILE="$BUILD_DIR/config.json"

# Create a mock prepare_deploy_script.sh that only checks the admin scope validation
cat > "$TEST_DIR/mock_prepare_deploy.sh" <<MOCK_SCRIPT
#!/usr/bin/env bash
SCOPE="\$1"

# Source the list_options_to_exclude script
EXCLUDED_OPTIONS=\$("$PROJECT_ROOT/scripts/deploy/list_options_to_exclude.sh")

# Check if admin scope is requested but dtagent_admin is disabled
if [[ "\$SCOPE" == *"admin"* ]] && [[ "\$EXCLUDED_OPTIONS" == *"dtagent_admin"* ]]; then
    echo "ERROR: Deployment scope 'admin' was requested, but core.snowflake.roles.admin is set to '-' (disabled)."
    echo "       The admin role will not be created and no admin-related operations can be performed."
    echo ""
    echo "To fix this:"
    echo "  1. Remove 'admin' from the deployment scope, OR"
    echo "  2. Set core.snowflake.roles.admin to a valid role name (or leave empty for default 'DTAGENT_ADMIN')"
    exit 1
fi

echo "Validation passed: SCOPE=\$SCOPE, EXCLUDED_OPTIONS=\$EXCLUDED_OPTIONS"
exit 0
MOCK_SCRIPT

chmod +x "$TEST_DIR/mock_prepare_deploy.sh"

# Test the validation - should fail
if "$TEST_DIR/mock_prepare_deploy.sh" "admin" 2>&1 | grep -q "ERROR.*admin.*disabled"; then
    echo "✓ Test passed: Admin scope correctly rejected when admin role is disabled"
else
    echo "ERROR: Expected failure when deploying admin scope with disabled admin role"
    exit 1
fi

# Test 2: Non-admin scope should work
echo "Test: Non-admin scope deployment with admin role disabled (should succeed)"
if "$TEST_DIR/mock_prepare_deploy.sh" "setup,plugins" > /dev/null 2>&1; then
    echo "✓ Test passed: Non-admin scope works when admin role is disabled"
else
    echo "ERROR: Non-admin scope should work even when admin is disabled"
    exit 1
fi

# Test 3: Admin scope with admin enabled should work
echo "Test: Admin scope deployment with admin role enabled (should succeed)"
cat > "$TEST_DIR/config-with-admin.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test-account
    host_name: test-account.snowflakecomputing.com
    roles:
      admin: "CUSTOM_ADMIN"
    resource_monitor:
      credit_quota: 5
EOF

cd "$TEST_DIR"
cat "config-with-admin.yml" | yq -o json '.' | jq -r '
    def flatten:
      . as $in
      | (paths(scalars|true) as $p
      | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
      | $out;
    [flatten]
  ' > "$BUILD_DIR/config-with-admin.json"

export BUILD_CONFIG_FILE="$BUILD_DIR/config-with-admin.json"

if "$TEST_DIR/mock_prepare_deploy.sh" "admin" > /dev/null 2>&1; then
    echo "✓ Test passed: Admin scope works when admin role is enabled"
else
    echo "ERROR: Admin scope should work when admin is enabled"
    exit 1
fi

echo ""
echo "✓ All admin scope validation tests passed!"

exit 0
