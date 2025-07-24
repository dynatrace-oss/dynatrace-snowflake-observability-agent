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
# This is a script for prepares SQL code that will insert instrumetns definition into temporary table
INSTRUMENTS_FILE="build/instruments-def.json"

FILTERED_JSON=$(jq 'walk(if type == "object" then with_entries(select(.key | test("^__") | not)) else . end)' "$INSTRUMENTS_FILE")
COMPRESSED_JSON=$(echo "$FILTERED_JSON" | jq -c .)
ESCAPED_JSON=$(echo "$COMPRESSED_JSON" | sed "s/'/''/g")

# the final SQL code
SQL="INSERT INTO TEMP_INSTRUMENTS (DATA) SELECT (PARSE_JSON('"$ESCAPED_JSON"'));"

echo $SQL