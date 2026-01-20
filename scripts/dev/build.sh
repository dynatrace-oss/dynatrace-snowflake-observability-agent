#!/usr/bin/env bash
#
#
# Copyright (c) 2025 Dynatrace Open Source
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#
#
# This script is used to build target SQLs that will be put into ../agent/sql/setup
# It processes the scripts in src/sql and looks for ##INSERT $fileName hints
#

set -euo pipefail

# Check for required commands
if ! command -v gawk &> /dev/null; then
    echo "Error: Required command 'gawk' is not installed."
    exit 1
fi

if ! command -v yq &> /dev/null; then
    echo "Error: Required command 'yq' is not installed."
    exit 1
fi

# Cleaning up build directory
rm -rf build
mkdir -p build/09_upgrade build/20_plugins

SOURCE_CODE_QUALITY_CHECK_FILE=.logs/source-code-quality-$(date '+%Y%m%d-%H%M%S').log
TEST_CODE_QUALITY_CHECK_FILE=.logs/test-code-quality-$(date '+%Y%m%d-%H%M%S').log

# The ignored cases are:
# C0301 - line-too-long - mostly caught in docstrings
# W0511 - TODO labels should be ignored, as we have them in the code to track what needs to be done
# W0611 - unused-import - we need general imports in src/dtagent/__init__.py, src/dtagent/agent.py, src/dtagent/connector.py
# E0401 - import-error - with all files being parsed to one this shows plenty false negatives
# C0415 - import-outside-top-level - these are necessary to avoid circular imports in some cases
# C0411 - wrong-import-order - impossible to avoid with imports in functions
# R0914 - too-many-locals - in the update_docs file, can't see how to avoid it
# R0902 - too-many-instance-attributes
# R0903 - too-few-public-methods
# R0913 - too-many-arguments - for generic methods like _log_entries - impossible to avoid without heavily refactoring
# R1737 - use-yield-from - yield from reparse objects it iterates on to strings, so it doesn't fit our use case
# R0915 - too-many-statements in a function

SRC_IGNORED_CASES=$(grep '^disable=' .pylintrc | sed 's/disable=//')
TEST_IGNORED_CASES=$(grep '^disable=' test/.pylintrc | sed 's/disable=//')

pylint src/ --recursive=y --disable=$SRC_IGNORED_CASES --output-format=parseable >$SOURCE_CODE_QUALITY_CHECK_FILE
pylint test/ --recursive=y --disable=$TEST_IGNORED_CASES --output-format=parseable >$TEST_CODE_QUALITY_CHECK_FILE

if (
    [ -s "$SOURCE_CODE_QUALITY_CHECK_FILE" ] && ! grep -q "at 10.00/10" "$SOURCE_CODE_QUALITY_CHECK_FILE" \
) || (
    [ -s "$TEST_CODE_QUALITY_CHECK_FILE" ] && ! grep -q "at 10.00/10" "$TEST_CODE_QUALITY_CHECK_FILE" \
); then
    echo "Found code quality issues."

    ! grep -q "at 10.00/10" "$SOURCE_CODE_QUALITY_CHECK_FILE" && echo "Result file $SOURCE_CODE_QUALITY_CHECK_FILE is not empty."
    ! grep -q "at 10.00/10" "$TEST_CODE_QUALITY_CHECK_FILE" && echo "Result file $TEST_CODE_QUALITY_CHECK_FILE is not empty."
    echo "Check the content and sort out code quality issues before proceeding."

    exit 1
else
    rm $SOURCE_CODE_QUALITY_CHECK_FILE
    rm $TEST_CODE_QUALITY_CHECK_FILE
    echo "Code quality checks passed for test/ and src/."
fi

# Compiling to build/_dtagent.py
./scripts/dev/compile.sh

if [ $? -eq 1 ]; then
    echo "Code compilation failed."
    exit 1
fi

# Assembling per-plugin configuration into one file
PLUGINS_CONFIG_FILES=()
while IFS= read -r -d '' file; do
    PLUGINS_CONFIG_FILES+=("$file")
done < <(find ./src -type f -name "*-config.yml" -print0)

CONFIG_TEMPLATE_FILE="conf/config-template.yml"
CONFIG_TEMPLATE="$(yq '.' $CONFIG_TEMPLATE_FILE)"

merged_sections="{}"
for file in "${PLUGINS_CONFIG_FILES[@]}"; do
    merged_sections=$(yq '
        . as $base
        | load("'"$file"'") as $f
        | .plugins = ($base.plugins // {}) + ($f.plugins // {})
        | .otel = ($base.otel // {}) + ($f.otel // {})
    ' <<<"$merged_sections")
done

# Combine the merged sections with the rest of the template
tmp_merged="$(mktemp -t merged.XXXXXX.yml)"
echo "$merged_sections" > "$tmp_merged"
yq '.plugins = (.plugins // {}) + load("'"$tmp_merged"'").plugins | .otel = (.otel // {}) + load("'"$tmp_merged"'").otel' "$CONFIG_TEMPLATE_FILE" > ./build/config-default.yml
rm -f "$tmp_merged"

# -----------------------------
# Build staged SQL scripts
# -----------------------------


process_sql_with_inserts() {
    local in_file="$1"
    local keep_copyright="${2:-0}"

    # Strip copyright headers (lines between two -- lines before and two -- lines after)
    gawk -v DEBUG=0 -v keep_copyright="$keep_copyright" '
        match($0, /[#]{2}INSERT (.+)/, a) {
            system("cat src/"a[1]);
            next
        }
        BEGIN{
            preamb1=0
            preamb2=0
            printout=keep_copyright
        }
        printout { print $0; next }
        !/^--\s*$/ { preamb2=0 }
        /^--\s*$/  {
            ++preamb1;
            if (preamb1 > 2) {++preamb2}
            if (preamb1 >= 2 && preamb2 >= 2) {printout=1}
             }
        #DEBUG { print preamb1,preamb2,printout,$0 }
    ' "$in_file"
}

append_sql_dir() {
    local src_dir="$1"
    local dest_file="$2"
    local first_file="${3:-1}"


    if [ ! -d "$src_dir" ]; then
        return 0
    fi

    # Append files in a stable order
    while IFS= read -r f; do
        [ -f "$f" ] || continue

        process_sql_with_inserts "$f" "$first_file" >> "$dest_file"
        first_file=0

        printf "\n" >> "$dest_file"
    done < <(find "$src_dir" -maxdepth 1 -type f -name "*.sql" ! -name "*.off.sql" | sort)
}

plugin_dirs() {
    if [ ! -d "src/dtagent/plugins" ]; then
        return 0
    fi
    # Plugins are stored under directories matching: src/dtagent/plugins/<plugin_name>.sql/
    find "src/dtagent/plugins" -maxdepth 1 -type d -name "*.sql" | sort
}

# build/00_init.sql <- combine(src/dtagent.sql/init/*.sql, plugin init/*.sql wrapped in plugin blocks)
: > build/00_init.sql
append_sql_dir "src/dtagent.sql/init" "build/00_init.sql"

while IFS= read -r pdir; do
    pbase="$(basename "$pdir")"
    pname="${pbase%.sql}"
    init_dir="$pdir/init"
    if compgen -G "$init_dir/*.sql" > /dev/null; then
        echo "--%PLUGIN:${pname}:" >> build/00_init.sql
        append_sql_dir "$init_dir" "build/00_init.sql" 0
        echo "--%:PLUGIN:${pname}" >> build/00_init.sql
        printf "\n" >> build/00_init.sql
    fi
done < <(plugin_dirs)

# build/09_upgrade/v$version.sql <- combine(src/dtagent.sql/upgrade/$version/*.sql)
if [ -d "src/dtagent.sql/upgrade" ]; then
    while IFS= read -r vdir; do
        vname="$(basename "$vdir")"
        : > "build/09_upgrade/v${vname}.sql"
        append_sql_dir "$vdir" "build/09_upgrade/v${vname}.sql"
    done < <(find "src/dtagent.sql/upgrade" -mindepth 1 -maxdepth 1 -type d | sort)
fi

# build/10_setup.sql <- combine(src/dtagent.sql/setup/*.sql)
: > build/10_setup.sql
append_sql_dir "src/dtagent.sql/setup" "build/10_setup.sql"

# build/20_plugins/$plugin_name.sql <- combine(src/dtagent/plugins/$plugin_name.sql/*.sql) (excluding init/) wrapped in plugin blocks
while IFS= read -r pdir; do
    pbase="$(basename "$pdir")"
    pname="${pbase%.sql}"
    dest="build/20_plugins/${pname}.sql"
    : > "$dest"

    echo "--%PLUGIN:${pname}:" >> "$dest"
    append_sql_dir "$pdir" "$dest"   # maxdepth=1, so it won't include init/*.sql
    echo "--%:PLUGIN:${pname}" >> "$dest"
    printf "\n" >> "$dest"
done < <(plugin_dirs)

# build/30_config.sql <- combine(src/dtagent.sql/config/*.sql)
: > build/30_config.sql
append_sql_dir "src/dtagent.sql/config" "build/30_config.sql"

# build/70_agents.sql <- combine(src/dtagent.sql/agents/*.sql)
: > build/70_agents.sql
append_sql_dir "src/dtagent.sql/agents" "build/70_agents.sql"

# Lint staged SQL (best-effort like before)
sqlfluff lint build/*.sql build/09_upgrade/*.sql build/20_plugins/*.sql --ignore parsing --disable-progress-bar

echo "Building Dynatrace Snowflake Observability Agent done"
