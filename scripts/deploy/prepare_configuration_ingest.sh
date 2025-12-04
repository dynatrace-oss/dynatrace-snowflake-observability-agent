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
# This is a script for prepares SQL code that will insert configuration into temporary table
SELECT_STATEMENTS=""

while IFS= read -r config; do
  ESCAPED_CONFIG=$(echo "$config" | sed "s/'/''/g")
  SELECT_STATEMENTS+="SELECT PARSE_JSON('$ESCAPED_CONFIG') as data UNION ALL "
done < <(jq -c 'map(if .VALUE | type == "string" then .VALUE |= gsub("\\*"; "\\\\*") else . end) | .[]' "${BUILD_CONFIG_FILE}")

# this ensures we only have comma separated entries in case of > 1
SELECT_STATEMENTS=${SELECT_STATEMENTS%UNION ALL }

# final SQL code
SQL="INSERT INTO TEMP_CONFIG (DATA) $SELECT_STATEMENTS;"

echo $SQL