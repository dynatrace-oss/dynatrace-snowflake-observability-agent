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
# This script analyses JSON configuration file (stored in BUILD_CONFIG_FILE=build/config.json)
# to list all plugins that either enabled or disabled, explicitly or implicitly, and should be excluded from deployment package.
# It uses jq to parse the JSON file and extract the value associated with the specified key.

list_plugins_by_status() {
  local STATUS_TYPE=$1
  local STATUS_VALUE=$2

  echo $(jq -r --argjson STATUS_VALUE "$STATUS_VALUE" --arg STATUS_TYPE "$STATUS_TYPE" '.[] | select(.PATH | startswith("plugins.") and endswith(".is_" + $STATUS_TYPE)) | select(.TYPE == "bool") | select(.VALUE == $STATUS_VALUE) | .PATH | sub("plugins\\."; "") | sub("\\.is_" + $STATUS_TYPE; "")' "$BUILD_CONFIG_FILE")
}

CWD=$(dirname "$0")

DEPLOY_DISABLED_PLUGINS="$($CWD/get_config_key.sh plugins.deploy_disabled_plugins)"
DISABLED_BY_DEFAULT="$($CWD/get_config_key.sh plugins.disabled_by_default)"
DISABLED_PLUGINS=$(list_plugins_by_status "disabled" "true")
NOT_DISABLED_PLUGINS=$(list_plugins_by_status "disabled" "false")
ENABLED_PLUGINS=$(list_plugins_by_status "enabled" "true")
NOT_ENABLED_PLUGINS=$(list_plugins_by_status "enabled" "false")

if [ "$DEPLOY_DISABLED_PLUGINS" == "false" ]; then
  # We will only list plugins not to deploy when we are not deploying disabled plugins
  # Otherwise, we assume all plugins are to be deployed

  # First, list all plugins that are explicitly disabled
  for PLUGIN in $DISABLED_PLUGINS; do
    echo "$PLUGIN"
  done

  # Then, if plugins are disabled by default, list all plugins that are NOT explicitly enabled
  if [ "$DISABLED_BY_DEFAULT" == "true" ]; then
    # We need to take the list of all plugins that are not explicitly disable (which is a default state) and exclude those that are explicitly enabled
    for PLUGIN in $NOT_DISABLED_PLUGINS; do
      if ! [[ " $ENABLED_PLUGINS " =~ " $PLUGIN " ]]; then
      echo "$PLUGIN"
      fi
    done
  fi
fi