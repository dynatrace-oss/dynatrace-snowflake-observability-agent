#!/usr/bin/env bash
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

##
# Shared bash library for interactive deployment wizard.
#
# Provides logging, prompting, validation, and configuration helpers.
##

##region Logging Functions

##
# Log an informational message.
#
# Args:
#   $1: Message text
#
# Returns:
#   0 always
##
log_info() {
    local msg="$1"
    echo "[INFO] $msg" >&2
}

##
# Log a success message.
#
# Args:
#   $1: Message text
#
# Returns:
#   0 always
##
log_ok() {
    local msg="$1"
    echo "✓ $msg" >&2
}

##
# Log a warning message.
#
# Args:
#   $1: Message text
#
# Returns:
#   0 always
##
log_warn() {
    local msg="$1"
    echo "⚠ WARNING: $msg" >&2
}

##
# Log an error message.
#
# Args:
#   $1: Message text
#
# Returns:
#   0 always
##
log_error() {
    local msg="$1"
    echo "✗ ERROR: $msg" >&2
}

##endregion

##region Prompt Functions

##
# Prompt user for text input with optional default value.
#
# Args:
#   $1: Prompt text
#   $2: Default value (optional)
#
# Returns:
#   0 on success, 1 on EOF
#
# Outputs:
#   User input or default value
##
prompt_input() {
    local prompt="$1"
    local default="$2"
    local input

    if [[ -n "$default" ]]; then
        echo -n "$prompt [$default]: " >&2
    else
        echo -n "$prompt: " >&2
    fi

    if ! read -r input; then
        return 1
    fi

    if [[ -z "$input" && -n "$default" ]]; then
        echo "$default"
    else
        echo "$input"
    fi
}

##
# Prompt user for yes/no confirmation.
#
# Args:
#   $1: Prompt text
#   $2: Default answer (y/n, optional, defaults to n)
#
# Returns:
#   0 if yes, 1 if no
##
prompt_yesno() {
    local prompt="$1"
    local default="${2:-n}"
    local input
    local default_display

    if [[ "$default" == "y" ]]; then
        default_display="Y/n"
    else
        default_display="y/N"
    fi

    echo -n "$prompt [$default_display]: " >&2

    if ! read -r input; then
        # EOF: use default
        [[ "$default" == "y" ]] && return 0 || return 1
    fi

    input="${input,,}"  # lowercase
    if [[ "$input" == "y" || "$input" == "yes" ]]; then
        return 0
    elif [[ "$input" == "n" || "$input" == "no" ]]; then
        return 1
    elif [[ -z "$input" ]]; then
        # Empty input: use default
        [[ "$default" == "y" ]] && return 0 || return 1
    else
        # Invalid input: ask again
        log_warn "Please enter 'y' or 'n'"
        prompt_yesno "$prompt" "$default"
    fi
}

##
# Prompt user to select one option from a list.
#
# Args:
#   $1: Prompt text
#   $2: Default option (optional)
#   $@: Options (remaining args)
#
# Returns:
#   0 on success, 1 on EOF
#
# Outputs:
#   Selected option
##
prompt_select_one() {
    local prompt="$1"
    shift
    local default="$1"
    shift
    local options=("$@")
    local input
    local i

    echo "$prompt" >&2
    for i in "${!options[@]}"; do
        if [[ "${options[$i]}" == "$default" ]]; then
            echo "  $((i + 1))) ${options[$i]} (default)" >&2
        else
            echo "  $((i + 1))) ${options[$i]}" >&2
        fi
    done

    echo -n "Select option [1-${#options[@]}]: " >&2

    if ! read -r input; then
        return 1
    fi

    # Empty input: select the default option
    if [[ -z "$input" ]]; then
        if [[ -n "$default" ]]; then
            echo "$default"
            return 0
        fi
        log_warn "No default available. Please enter a number between 1 and ${#options[@]}"
        prompt_select_one "$prompt" "$default" "${options[@]}"
        return
    fi

    # Validate input is a number in range
    if ! [[ "$input" =~ ^[0-9]+$ ]] || ((input < 1 || input > ${#options[@]})); then
        log_warn "Invalid selection. Please enter a number between 1 and ${#options[@]}"
        prompt_select_one "$prompt" "$default" "${options[@]}"
        return
    fi

    echo "${options[$((input - 1))]}"
}

##
# Prompt user to select multiple options from a list using bash select.
#
# Args:
#   $1: Prompt text
#   $@: Options (remaining args)
#
# Returns:
#   0 on success, 1 on EOF
#
# Outputs:
#   Selected options (one per line)
##
prompt_select_multi() {
    local prompt="$1"
    shift
    local options=("$@")
    local selected=()
    local i
    local input

    echo "$prompt" >&2
    echo "(Enter option numbers separated by spaces, or 'done' to finish)" >&2

    for i in "${!options[@]}"; do
        echo "  $((i + 1))) ${options[$i]}" >&2
    done

    while true; do
        echo -n "Select options [1-${#options[@]}] or 'done': " >&2

        if ! read -r input; then
            return 1
        fi

        if [[ "$input" == "done" ]]; then
            break
        fi

        # Parse space-separated numbers
        local valid=1
        for num in $input; do
            if ! [[ "$num" =~ ^[0-9]+$ ]] || ((num < 1 || num > ${#options[@]})); then
                log_warn "Invalid selection: $num. Please enter numbers between 1 and ${#options[@]}"
                valid=0
                break
            fi
        done

        if [[ $valid -eq 1 ]]; then
            for num in $input; do
                selected+=("${options[$((num - 1))]}")
            done
            break
        fi
    done

    # Output selected options
    for opt in "${selected[@]}"; do
        echo "$opt"
    done
}

##endregion

##region Validator Functions

##
# Validate Dynatrace tenant address format.
#
# Args:
#   $1: Tenant address
#
# Returns:
#   0 if valid, 1 if invalid
#
# Outputs:
#   Corrected address if auto-correction applied
##
validate_dt_tenant() {
    local tenant="$1"

    # Auto-correct .apps.dynatrace.com to .live.dynatrace.com
    if [[ "$tenant" == *".apps.dynatrace.com"* ]]; then
        tenant="${tenant//.apps.dynatrace.com/.live.dynatrace.com}"
        echo "$tenant"
        return 0
    fi

    # Accept *.live.dynatrace.com (production tenants)
    if [[ "$tenant" =~ ^[a-zA-Z0-9-]+\.live\.dynatrace\.com$ ]]; then
        echo "$tenant"
        return 0
    fi

    # Accept *.sprint.dynatracelabs.com and *.dev.dynatracelabs.com (internal tenants)
    if [[ "$tenant" =~ ^[a-zA-Z0-9-]+\.(sprint|dev)\.dynatracelabs\.com$ ]]; then
        echo "$tenant"
        return 0
    fi

    return 1
}

##
# Validate Snowflake account identifier format.
#
# Args:
#   $1: Account identifier
#
# Returns:
#   0 if valid, 1 if invalid
##
validate_sf_account() {
    local account="$1"

    # Accept org-account format (e.g., myorg-myaccount)
    if [[ "$account" =~ ^[a-zA-Z0-9_-]+\-[a-zA-Z0-9_-]+$ ]]; then
        return 0
    fi

    # Accept legacy locator.region format (e.g., abc12345.us-east-1)
    if [[ "$account" =~ ^[a-zA-Z0-9]+\.[a-zA-Z0-9_-]+$ ]]; then
        return 0
    fi

    return 1
}

##
# Validate non-empty string.
#
# Args:
#   $1: String to validate
#
# Returns:
#   0 if non-empty, 1 if empty
##
validate_nonempty() {
    local value="$1"
    [[ -n "$value" ]]
}

##
# Validate alphanumeric string (plus underscore).
#
# Args:
#   $1: String to validate
#
# Returns:
#   0 if valid, 1 if invalid
##
validate_alphanumeric() {
    local value="$1"
    [[ "$value" =~ ^[a-zA-Z0-9_]*$ ]]
}

##
# Probe Dynatrace tenant reachability via HTTPS.
#
# Args:
#   $1: Tenant address
#
# Returns:
#   0 if reachable, 1 if unreachable
##
probe_dt_tenant() {
    local tenant="$1"
    if curl -s -m 5 -o /dev/null -w "%{http_code}" "https://$tenant/api/v2/environments" 2>/dev/null | grep -q "^[23]"; then
        return 0
    fi
    return 1
}

##
# Probe Snowflake account reachability via HTTPS.
#
# Args:
#   $1: Account identifier
#
# Returns:
#   0 if reachable, 1 if unreachable
##
probe_sf_account() {
    local account="$1"
    # Extract account locator from org-account format
    local locator="${account%-*}"
    if [[ "$account" == *"."* ]]; then
        locator="${account%%.*}"
    fi

    if curl -s -m 5 -o /dev/null -w "%{http_code}" "https://$locator.snowflakecomputing.com/" 2>/dev/null | grep -q "^[23]"; then
        return 0
    fi
    return 1
}

##endregion

##region Config Helper Functions

##
# Read a configuration value from YAML file using yq.
#
# Args:
#   $1: Config file path
#   $2: Key path (dot-separated, e.g., "core.dynatrace_tenant_address")
#
# Returns:
#   0 on success, 1 if key not found
#
# Outputs:
#   Configuration value
##
read_config_key() {
    local config_file="$1"
    local key_path="$2"

    if [[ ! -f "$config_file" ]]; then
        return 1
    fi

    # Convert dot-separated path to yq path (e.g., "core.key" -> ".core.key")
    local yq_path=".${key_path//./.}"
    local value
    value=$(yq eval "$yq_path" "$config_file" 2>/dev/null)

    if [[ -z "$value" || "$value" == "null" ]]; then
        return 1
    fi

    echo "$value"
    return 0
}

##
# Write a configuration value to YAML file using yq.
#
# Args:
#   $1: Config file path
#   $2: Key path (dot-separated, e.g., "core.dynatrace_tenant_address")
#   $3: Value
#   $4: Type (optional: str, int, bool, default: str)
#
# Returns:
#   0 on success, 1 on failure
##
write_config_key() {
    local config_file="$1"
    local key_path="$2"
    local value="$3"
    local value_type="${4:-str}"

    # Create file if it doesn't exist
    if [[ ! -f "$config_file" ]]; then
        echo "{}" > "$config_file"
    fi

    # Convert dot-separated path to yq path (e.g., "core.key" -> ".core.key")
    local yq_path=".${key_path//./.}"

    # Format value based on type
    local formatted_value="$value"
    if [[ "$value_type" == "bool" ]]; then
        formatted_value="${value,,}"  # lowercase for boolean
    elif [[ "$value_type" == "int" ]]; then
        formatted_value="$value"
    fi

    # Use yq to write the value
    yq eval "$yq_path = \"$formatted_value\"" -i "$config_file" 2>/dev/null || return 1
    return 0
}

##endregion
