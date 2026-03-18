#!/usr/bin/env bats

#
# Regression test: no stored procedures should use "execute as owner"
# (explicitly or implicitly) unless they are in the exclusion list.
#
# Scans source .sql files under src/ for:
#  1. Explicit "execute as owner" declarations
#  2. Procedures missing an "execute as" clause entirely (implicit owner)
#
# Exclusion list: add fully-qualified procedure names here if they
# genuinely require "execute as owner" with a justifying comment.
#

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    SRC_DIR="src"

    # -------------------------------------------------------------------
    # EXCLUSION LIST — procedures that are allowed to use execute as owner
    # Add entries as "|"-separated patterns (grep -E), e.g.:
    #   "P_SOME_SPECIAL_PROC|P_ANOTHER_ONE"
    # Currently empty: no procedures should use execute as owner.
    # -------------------------------------------------------------------
    EXCLUSION_PATTERN=""
}

# -----------------------------------------------------------------------
# Test 1: No source SQL files contain "execute as owner"
# -----------------------------------------------------------------------
@test "no procedures use explicit 'execute as owner'" {
    # Find all .sql source files (exclude .off.sql disabled files)
    matches=$(grep -r -i -l "execute as owner" "$SRC_DIR" --include="*.sql" || true)

    if [ -n "$EXCLUSION_PATTERN" ]; then
        matches=$(echo "$matches" | grep -v -E "$EXCLUSION_PATTERN" || true)
    fi

    if [ -n "$matches" ]; then
        echo "ERROR: The following source files still use 'execute as owner':"
        echo "$matches"
        # Show the offending lines for debugging
        for f in $matches; do
            echo "--- $f ---"
            grep -n -i "execute as owner" "$f"
        done
        return 1
    fi
}

# -----------------------------------------------------------------------
# Test 2: All procedures have an explicit "execute as" clause
#         (procedures without it default to "execute as owner")
# -----------------------------------------------------------------------
@test "all procedures have explicit 'execute as' clause" {
    missing_files=""

    # Find all .sql source files that define a procedure (exclude .off.sql)
    while IFS= read -r file; do
        # For each CREATE PROCEDURE block, check if "execute as" appears
        # between "create ... procedure" and the "as" delimiter before $$
        #
        # Strategy: extract the header (lines between "create.*procedure" and
        # the line containing only "as" or "as\n$$") and check for "execute as"
        #
        # We use awk to find procedure headers without "execute as"
        result=$(awk '
            BEGIN { IGNORECASE=1; in_header=0; header=""; proc_name="" }
            /create[[:space:]]+(or[[:space:]]+replace[[:space:]]+)?procedure/ {
                in_header=1
                header=$0
                proc_name=$0
                next
            }
            in_header {
                header = header "\n" $0
                if ($0 ~ /^\$\$/ || $0 ~ /^as[[:space:]]*$/) {
                    if (header !~ /execute[[:space:]]+as/) {
                        print FILENAME ": " proc_name
                    }
                    in_header=0
                    header=""
                }
            }
        ' "$file")

        if [ -n "$result" ]; then
            missing_files="$missing_files\n$result"
        fi
    done < <(find "$SRC_DIR" -name "*.sql" ! -name "*.off.sql" -type f)

    if [ -n "$missing_files" ]; then
        echo "ERROR: The following procedures are missing an explicit 'execute as' clause"
        echo "       (Snowflake defaults to 'execute as owner' when omitted):"
        echo -e "$missing_files"
        return 1
    fi
}
