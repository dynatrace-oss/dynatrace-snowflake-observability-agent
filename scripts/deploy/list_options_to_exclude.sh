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
# This script checks configuration to list optional components that should be excluded
# from deployment when their corresponding configuration values are set to "-"
#
# Returns: Space-separated list of option names to exclude (e.g., "dtagent_admin resource_monitor")

CWD=$(dirname "$0")

EXCLUDED_OPTIONS=""

# Check if admin role is disabled (value is "-")
ADMIN_ROLE="$($CWD/get_config_key.sh core.snowflake.roles.admin)"
if [ "$ADMIN_ROLE" == "-" ]; then
  EXCLUDED_OPTIONS="$EXCLUDED_OPTIONS dtagent_admin"
fi

# Check if resource monitor is disabled (value is "-")
RESOURCE_MONITOR="$($CWD/get_config_key.sh core.snowflake.resource_monitor.name)"
if [ "$RESOURCE_MONITOR" == "-" ]; then
  EXCLUDED_OPTIONS="$EXCLUDED_OPTIONS resource_monitor"
fi

# Trim leading/trailing spaces and output
echo "$EXCLUDED_OPTIONS" | xargs
