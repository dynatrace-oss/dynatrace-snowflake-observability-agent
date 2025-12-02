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

# Updating build number

TS=$(date +%s%3)
sed -E 's/^BUILD[ ]*=[ ]*([0-9]+)/BUILD = '"$TS"'/g' src/dtagent/version.py >build/_version.py

check_missing_imports() {
  DTAGENT_CHECK=$(flake8 "$1" --select F821)
  if [ ! -z "$DTAGENT_CHECK" ]; then
    echo "$1 has potentially missing imports:"
    echo "$DTAGENT_CHECK"
    exit 1
  fi
}

#
# This script is used to preprocess single *.py src/file before it can be referenced in other files,
# which are source for those processed in process_files function
#
preprocess_files() {
  local src_file=$1
  local dest_file=$2

  gawk 'match($0, /[#]{2}INSERT (.+)/, a) {system("cat \""a[1]"\""); next } 1' "$src_file" > "$dest_file"

  black --line-length 140 "$dest_file"
}

#
# This script is used to create single 700_dtagent.py src/file from src/dtagent package
#
process_files() {
  local src_file=$1
  local dest_file=$2

  echo "# pylint: disable=W0404, W0105, C0302", C0412, C0413 > "$dest_file"

  gawk 'match($0, /[#]{2}INSERT (.+)/, a) {system("sed -e \"1,/##endregion COMPILE_REMOVE/d\" "a[1]); next } 1' "$src_file" |
    sed -e '/##region.* IMPORTS/,/##endregion COMPILE_REMOVE/d' |
    grep -v '# COMPILE_REMOVE' >> "$dest_file"

  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' -e '/dtagent/!b' -e '/import/d' "$dest_file"
  else
    sed -i -e '/dtagent/!b' -e '/import/d' "$dest_file"
  fi

  check_missing_imports "$dest_file"
}

PYTHONPATH=src python src/build/assemble_semantics.py

preprocess_files "src/dtagent/otel/semantics.py" "build/_semantics.py"

process_files "src/dtagent/agent.py" "build/_dtagent.py"
process_files "src/dtagent/connector.py" "build/_send_telemetry.py"

echo "Compiling Dynatrace Snowflake Observability Agent done"
