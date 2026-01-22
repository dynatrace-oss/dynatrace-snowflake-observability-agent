#!/usr/bin/env bash
#
# Test script for list_options_to_exclude.sh functionality
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIST_OPTIONS_SCRIPT="$PROJECT_ROOT/scripts/deploy/list_options_to_exclude.sh"
GET_CONFIG_SCRIPT="$PROJECT_ROOT/scripts/deploy/get_config_key.sh"

# Create a temporary directory for test files
TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

echo "Testing list_options_to_exclude.sh..."

# Test 1: Both admin and resource_monitor disabled
echo "Test 1: Both admin and resource_monitor set to '-'"
cat > "$TEST_DIR/config-test1.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test.snowflake.com
    host_name: test.snowflake.com
    roles:
      admin: "-"
    resource_monitor:
      name: "-"
      credit_quota: 5
EOF

# Prepare config
cd "$TEST_DIR"
cat config-test1.yml | yq -o json '.' | jq -r '
    def flatten:
      . as $in
      | (paths(scalars|true) as $p
      | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
      | $out;
    [flatten]
  ' > config-test1.json

export BUILD_CONFIG_FILE="$TEST_DIR/config-test1.json"

RESULT=$(bash "$LIST_OPTIONS_SCRIPT")
if [[ "$RESULT" != *"dtagent_admin"* ]]; then
    echo "ERROR: Expected 'dtagent_admin' in excluded options, got: $RESULT"
    exit 1
fi
if [[ "$RESULT" != *"resource_monitor"* ]]; then
    echo "ERROR: Expected 'resource_monitor' in excluded options, got: $RESULT"
    exit 1
fi
echo "✓ Test 1 passed: $RESULT"

# Test 2: Only admin disabled
echo "Test 2: Only admin role set to '-'"
cat > "$TEST_DIR/config-test2.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test.snowflake.com
    host_name: test.snowflake.com
    roles:
      admin: "-"
    resource_monitor:
      name: "CUSTOM_RS"
      credit_quota: 5
EOF

cd "$TEST_DIR"
cat config-test2.yml | yq -o json '.' | jq -r '
    def flatten:
      . as $in
      | (paths(scalars|true) as $p
      | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
      | $out;
    [flatten]
  ' > config-test2.json

export BUILD_CONFIG_FILE="$TEST_DIR/config-test2.json"

RESULT=$(bash "$LIST_OPTIONS_SCRIPT")
if [[ "$RESULT" != *"dtagent_admin"* ]]; then
    echo "ERROR: Expected 'dtagent_admin' in excluded options, got: $RESULT"
    exit 1
fi
if [[ "$RESULT" == *"resource_monitor"* ]]; then
    echo "ERROR: Did not expect 'resource_monitor' in excluded options, got: $RESULT"
    exit 1
fi
echo "✓ Test 2 passed: $RESULT"

# Test 3: Only resource_monitor disabled
echo "Test 3: Only resource monitor set to '-'"
cat > "$TEST_DIR/config-test3.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test.snowflake.com
    host_name: test.snowflake.com
    roles:
      admin: "CUSTOM_ADMIN"
    resource_monitor:
      name: "-"
      credit_quota: 5
EOF

cd "$TEST_DIR"
cat config-test3.yml | yq -o json '.' | jq -r '
    def flatten:
      . as $in
      | (paths(scalars|true) as $p
      | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
      | $out;
    [flatten]
  ' > config-test3.json

export BUILD_CONFIG_FILE="$TEST_DIR/config-test3.json"

RESULT=$(bash "$LIST_OPTIONS_SCRIPT")
if [[ "$RESULT" == *"dtagent_admin"* ]]; then
    echo "ERROR: Did not expect 'dtagent_admin' in excluded options, got: $RESULT"
    exit 1
fi
if [[ "$RESULT" != *"resource_monitor"* ]]; then
    echo "ERROR: Expected 'resource_monitor' in excluded options, got: $RESULT"
    exit 1
fi
echo "✓ Test 3 passed: $RESULT"

# Test 4: Neither disabled (empty strings should use defaults)
echo "Test 4: Neither disabled (empty values use defaults)"
cat > "$TEST_DIR/config-test4.yml" <<'EOF'
core:
  dynatrace_tenant_address: test.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: test.snowflake.com
    host_name: test.snowflake.com
    roles:
      admin: ""
    resource_monitor:
      name: ""
      credit_quota: 5
EOF

cd "$TEST_DIR"
cat config-test4.yml | yq -o json '.' | jq -r '
    def flatten:
      . as $in
      | (paths(scalars|true) as $p
      | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
      | $out;
    [flatten]
  ' > config-test4.json

export BUILD_CONFIG_FILE="$TEST_DIR/config-test4.json"

RESULT=$(bash "$LIST_OPTIONS_SCRIPT")
if [[ -n "$RESULT" ]]; then
    echo "ERROR: Expected no excluded options, got: $RESULT"
    exit 1
fi
echo "✓ Test 4 passed: No options excluded (empty result)"

echo ""
echo "✓ All list_options_to_exclude.sh tests passed!"

exit 0
