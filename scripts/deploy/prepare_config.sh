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
# Refactors config files to 3 levels of nesting (path, value, type) and redirects it to build/.
# Excludes keys starting with _ prefix.
# Args: path(s) to config files, specified when running `deploy.sh`
#FIXME review for YAML parsing

# Returns dictionary based on the YAML content of given file - or an empty dictionary
# Args:
#     yaml_var (str): path to the file to load YAML into dict/yaml string
# Returns:
#     Optional[dict]: dictionary based on the YAML content of the given file. if yaml_var is not a path, but a valid yaml, yaml_var is returned
get_config() {
  local yaml_var="$1"
  if [[ -f "$yaml_var" ]]; then
    cat "$yaml_var"
  elif [[ -n "$yaml_var" ]] && echo "$yaml_var" | yq -e 'tag == "!!map"' >/dev/null 2>/dev/null; then
    echo "$yaml_var"
  else
    echo "{}"
  fi
}

# Converts configuration in a form of a dictionary, just like in config/config-template.yml
#     In order to properly load the data into table with 3 columns (path, value, type) we need to flatten the yaml to one level of nesting.
#     This will allow for inputting yaml key as context, nested yaml key as key and nested yaml value as value into CONFIG.CONFIGURATIONS.
#     To get the desired values of keys from the structure of the config yaml, we need to combine some of the keys into one.
#     So we use stack to iterate over each key and prepare the combined key.
# Args:
#     config_data (YAML Object): Configuration dictionary
# Returns:
#     JSON Array: configuration flattened into a list of three-column objects to make it easier to load into Snowflake
prepare_config_for_ingest() {
  local config_data="$1"
  echo "$config_data" | yq -o json '.' | jq -r '
    def flatten:
      . as $in
      | (paths(scalars|true) as $p
      | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": (getpath($p) | type), "VALUE": getpath($p)}) as $out
      | $out;
    def flatten_arrays:
      . as $in
      | (paths(arrays) as $p
      | {"PATH": ($p | map(tostring | ascii_downcase) | join(".")), "TYPE": "list", "VALUE": getpath($p)}) as $out
      | $out;
    [flatten, flatten_arrays]
  '
}

# Enables to load given files with configuration YAMLs one by one, and keep overriding existing keys (path)
# Returns:
#     list: the result is a merge of multiple configurations with values from last files in the list overriding those in previous positions
merge_yaml() {
  local merged="[]"
  for yaml in "$@"; do
    local config
    config=$(get_config "$yaml")
    local flattened
    flattened=$(prepare_config_for_ingest "$config")
    merged=$(jq -s '.[0] + .[1]' <(echo "$merged") <(echo "$flattened"))
  done
  echo "$merged" |\
   jq -r 'group_by(.PATH)
        | map(last)
        | map(select(.PATH | test("\\.[0-9]+$") | not))
        | map(select(.PATH | test("^_") | not))
        | sort_by(.PATH)' | jq '
  def update_type:
    if .TYPE == "number" then .TYPE = "int"
    elif .TYPE == "boolean" then .TYPE = "bool"
    elif .TYPE == "string" then .TYPE = "str"
    elif .TYPE == "array" then .TYPE = "list"
    else . end;
  map(update_type)
'
}

# Main function
merged_config=$(merge_yaml "$@")
echo "$merged_config" | jq '.' > "$BUILD_CONFIG_FILE"