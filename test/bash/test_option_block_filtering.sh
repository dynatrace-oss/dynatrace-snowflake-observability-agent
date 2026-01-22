#!/usr/bin/env bash
#
# Test script for OPTION block filtering functionality
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Create a temporary directory for test files
TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

echo "Testing OPTION block filtering..."

# Test 1: Filter dtagent_admin blocks
echo "Test 1: Filter dtagent_admin OPTION blocks"
cat > "$TEST_DIR/test-admin.sql" <<'EOF'
-- Some initial code
use role DTAGENT_OWNER;

--%OPTION:dtagent_admin:
-- Admin-specific code
create role if not exists DTAGENT_ADMIN;
grant role DTAGENT_ADMIN to role DTAGENT_OWNER;
--%:OPTION:dtagent_admin

-- Code after admin block
select 'continue';
EOF

# Create a simple filter script that mimics prepare_deploy_script.sh logic
cat > "$TEST_DIR/filter_test.awk" <<'AWK_SCRIPT'
BEGIN { active=1; option="dtagent_admin"; }
{
    # Check for start marker
    if ($0 ~ /^(--|#)%OPTION:/) {
        start_pattern = "%OPTION:" option ":"
        if (index($0, start_pattern) > 0) {
            active=0;
        }
    }

    # Print line only if active
    if (active==1) print $0;

    # Check for end marker
    if ($0 ~ /^(--|#)%:OPTION:/) {
        end_pattern = "%:OPTION:" option
        if (index($0, end_pattern) > 0) {
            idx = index($0, end_pattern)
            len = length(end_pattern)
            rest = substr($0, idx + len)
            if (rest == "" || rest ~ /^[ \t]*$/) {
                active=1;
            }
        }
    }
}
AWK_SCRIPT

awk -f "$TEST_DIR/filter_test.awk" "$TEST_DIR/test-admin.sql" > "$TEST_DIR/filtered-admin.sql"

# Verify admin block was removed
if grep -q "DTAGENT_ADMIN" "$TEST_DIR/filtered-admin.sql"; then
    echo "ERROR: Admin code should have been filtered out"
    cat "$TEST_DIR/filtered-admin.sql"
    exit 1
fi

# Verify other code remains
if ! grep -q "use role DTAGENT_OWNER" "$TEST_DIR/filtered-admin.sql"; then
    echo "ERROR: Initial code should remain"
    exit 1
fi

if ! grep -q "continue" "$TEST_DIR/filtered-admin.sql"; then
    echo "ERROR: Code after block should remain"
    exit 1
fi

echo "✓ Test 1 passed: dtagent_admin blocks filtered correctly"

# Test 2: Filter resource_monitor blocks
echo "Test 2: Filter resource_monitor OPTION blocks"
cat > "$TEST_DIR/test-rm.sql" <<'EOF'
-- Initial setup
use role ACCOUNTADMIN;

--%OPTION:resource_monitor:
create or replace resource monitor DTAGENT_RS with
  credit_quota = 5;
alter warehouse DTAGENT_WH set resource_monitor = DTAGENT_RS;
--%:OPTION:resource_monitor

-- Continue with other setup
create warehouse if not exists DTAGENT_WH;
EOF

cat > "$TEST_DIR/filter_rm.awk" <<'AWK_SCRIPT'
BEGIN { active=1; option="resource_monitor"; }
{
    if ($0 ~ /^(--|#)%OPTION:/) {
        start_pattern = "%OPTION:" option ":"
        if (index($0, start_pattern) > 0) {
            active=0;
        }
    }

    if (active==1) print $0;

    if ($0 ~ /^(--|#)%:OPTION:/) {
        end_pattern = "%:OPTION:" option
        if (index($0, end_pattern) > 0) {
            idx = index($0, end_pattern)
            len = length(end_pattern)
            rest = substr($0, idx + len)
            if (rest == "" || rest ~ /^[ \t]*$/) {
                active=1;
            }
        }
    }
}
AWK_SCRIPT

awk -f "$TEST_DIR/filter_rm.awk" "$TEST_DIR/test-rm.sql" > "$TEST_DIR/filtered-rm.sql"

# Verify resource monitor block was removed
if grep -q "DTAGENT_RS" "$TEST_DIR/filtered-rm.sql"; then
    echo "ERROR: Resource monitor code should have been filtered out"
    cat "$TEST_DIR/filtered-rm.sql"
    exit 1
fi

# Verify other code remains
if ! grep -q "use role ACCOUNTADMIN" "$TEST_DIR/filtered-rm.sql"; then
    echo "ERROR: Initial code should remain"
    exit 1
fi

if ! grep -q "create warehouse" "$TEST_DIR/filtered-rm.sql"; then
    echo "ERROR: Code after block should remain"
    exit 1
fi

echo "✓ Test 2 passed: resource_monitor blocks filtered correctly"

# Test 3: Multiple blocks in same file
echo "Test 3: Multiple OPTION blocks in same file"
cat > "$TEST_DIR/test-multi.sql" <<'EOF'
-- Setup
use role DTAGENT_OWNER;

--%OPTION:dtagent_admin:
-- First admin block
grant something to DTAGENT_ADMIN;
--%:OPTION:dtagent_admin

-- Middle code
select 'middle';

--%OPTION:resource_monitor:
-- Resource monitor block
create resource monitor DTAGENT_RS;
--%:OPTION:resource_monitor

-- End code
select 'end';
EOF

# Filter both
awk -v option="dtagent_admin" 'BEGIN { active=1; }
{
    if ($0 ~ /^(--|#)%OPTION:/) {
        start_pattern = "%OPTION:" option ":"
        if (index($0, start_pattern) > 0) { active=0; }
    }
    if (active==1) print $0;
    if ($0 ~ /^(--|#)%:OPTION:/) {
        end_pattern = "%:OPTION:" option
        if (index($0, end_pattern) > 0) {
            idx = index($0, end_pattern); len = length(end_pattern); rest = substr($0, idx + len)
            if (rest == "" || rest ~ /^[ \t]*$/) { active=1; }
        }
    }
}' "$TEST_DIR/test-multi.sql" > "$TEST_DIR/temp-multi.sql"

awk -v option="resource_monitor" 'BEGIN { active=1; }
{
    if ($0 ~ /^(--|#)%OPTION:/) {
        start_pattern = "%OPTION:" option ":"
        if (index($0, start_pattern) > 0) { active=0; }
    }
    if (active==1) print $0;
    if ($0 ~ /^(--|#)%:OPTION:/) {
        end_pattern = "%:OPTION:" option
        if (index($0, end_pattern) > 0) {
            idx = index($0, end_pattern); len = length(end_pattern); rest = substr($0, idx + len)
            if (rest == "" || rest ~ /^[ \t]*$/) { active=1; }
        }
    }
}' "$TEST_DIR/temp-multi.sql" > "$TEST_DIR/filtered-multi.sql"

# Verify both blocks removed
if grep -q "DTAGENT_ADMIN\|DTAGENT_RS" "$TEST_DIR/filtered-multi.sql"; then
    echo "ERROR: Both blocks should have been filtered out"
    cat "$TEST_DIR/filtered-multi.sql"
    exit 1
fi

# Verify other code remains
if ! grep -q "middle" "$TEST_DIR/filtered-multi.sql"; then
    echo "ERROR: Middle code should remain"
    exit 1
fi

if ! grep -q "end" "$TEST_DIR/filtered-multi.sql"; then
    echo "ERROR: End code should remain"
    exit 1
fi

echo "✓ Test 3 passed: Multiple blocks filtered correctly"

echo ""
echo "✓ All OPTION block filtering tests passed!"

exit 0
