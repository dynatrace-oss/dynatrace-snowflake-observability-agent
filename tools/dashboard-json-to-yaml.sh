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
DASHBOARD_FILE=$1
YAML_FILE=$2

#DASHBOARD_NAME=`echo "${DASHBOARD_FILE_NAME%.*}" | tr '_-' '  ' | sed 's/\b\w/\U&/g'`
DASHBOARD_NAME=$(basename "${DASHBOARD_FILE%.*}" | tr '_-' '  ' | sed 's/\b\w/\U&/g')

HEADER="#
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
# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# DASHBOARD: $DASHBOARD_NAME
# DESCRIPTION: 
# OWNER: $(whoami)
# PLUGINS: 
# TAGS: 
#"

echo "$HEADER" > "$YAML_FILE"

jq '
  .tiles |= (to_entries | map(
    .value.davis.davisVisualization.selectedOutputs |= empty |
    .value.davis.componentState.inputData |= walk(if type == "object" and has("query") then del(.query) else . end)
  ) | from_entries) |
  walk(
    if type == "object" then
      (if has("input") then .input |= sub("\\s+\\n"; "\n"; "g") | .input |= sub("\\n\\s+$"; "\n"; "g") else . end) |
      (if has("query") then .query |= sub("\\s+\\n"; "\n"; "g") | .query |= sub("\\n\\s+$"; "\n"; "g") else . end)
    else . end
  )
' "$DASHBOARD_FILE" | \
yq -P  >> "$YAML_FILE"