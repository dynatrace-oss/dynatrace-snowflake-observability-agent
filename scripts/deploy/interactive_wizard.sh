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
# Interactive deployment wizard for DSOA.
#
# Guides users through 5 phases of configuration:
# 1. Core configuration (DT tenant, token, SF account, env name, tag)
# 2. Deployment scope selection
# 3. Plugin selection and customization
# 4. Advanced settings (optional)
# 5. OpenTelemetry settings (optional)
#
# Usage:
#   ./interactive_wizard.sh --env=<ENV> [--existing-config=<FILE>] [--dry-run] [--output=<FILE>]
##

set -euo pipefail

# Source the shared library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

##region Global Variables

WIZARD_ENV=""
EXISTING_CONFIG=""
DRY_RUN=0
OUTPUT_FILE=""

# Path to default config — used to seed defaults dynamically
DEFAULT_CONFIG="${SCRIPT_DIR}/../../build/config-default.yml"

# Configuration values collected by wizard
DT_TENANT=""
DT_TOKEN=""
SF_ACCOUNT=""
DEPLOYMENT_ENV=""
TAG=""

# Phase 2 values
DEPLOYMENT_SCOPE="all"
FROM_VERSION=""
MANUAL_MODE=0
SKIP_CONFIRM=0
NO_DEP=0

# Phase 3 values
PLUGINS_MODE="all"  # all, none, selected
SELECTED_PLUGINS=()
DEPLOY_DISABLED_PLUGINS=1
CUSTOMIZE_PLUGINS=0
# Associative array: plugin_name -> "key=value key=value ..." overrides (space-separated)
declare -A PLUGIN_OVERRIDES

# Phase 4 values — seeded from default config, overridden by user
LOG_LEVEL="WARN"
PROCEDURE_TIMEOUT="3600"
RESOURCE_MONITOR_QUOTA=""

# Phase 5 OTel values — empty means "use default" (not written to config)
OTEL_LOGS_DISABLED=""
OTEL_SPANS_DISABLED=""
OTEL_METRICS_DISABLED=""
OTEL_EVENTS_DISABLED=""
OTEL_BIZ_EVENTS_DISABLED=""
OTEL_MAX_CONSECUTIVE_API_FAILS=""

##endregion

##region Helper Functions

##
# Read a default value from build/config-default.yml.
#
# Args:
#   $1: yq key path (e.g. "core.log_level")
#   $2: Fallback value if file absent or key missing
#
# Returns:
#   0 always
#
# Outputs:
#   Value from default config, or fallback
##
read_default() {
    local key_path="$1"
    local fallback="$2"

    if [[ ! -f "$DEFAULT_CONFIG" ]] || ! command -v yq >/dev/null 2>&1; then
        echo "$fallback"
        return 0
    fi

    local val
    val=$(yq eval ".${key_path}" "$DEFAULT_CONFIG" 2>/dev/null || true)
    if [[ -z "$val" || "$val" == "null" ]]; then
        echo "$fallback"
    else
        echo "$val"
    fi
}

##
# Parse command-line arguments.
#
# Args:
#   $@: Command-line arguments
#
# Returns:
#   0 on success, 1 on error
##
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --env=*)
                WIZARD_ENV="${1#*=}"
                shift
                ;;
            --existing-config=*)
                EXISTING_CONFIG="${1#*=}"
                shift
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --output=*)
                OUTPUT_FILE="${1#*=}"
                shift
                ;;
            *)
                log_error "Unknown argument: $1"
                return 1
                ;;
        esac
    done

    if [[ -z "$WIZARD_ENV" ]]; then
        log_error "--env is required"
        return 1
    fi

    return 0
}

##
# Derive default DEPLOYMENT_ENV and TAG from the --env value.
#
# Rules:
#   DEPLOYMENT_ENV = uppercase of WIZARD_ENV (e.g. test-qa2 → TEST-QA2)
#   TAG            = uppercase of last dash-segment when WIZARD_ENV contains a dash
#                    (e.g. test-qa2 → QA2, prod-tenant-a → A, production → "")
#
# Only sets the variables when they are currently empty (existing-config values
# loaded later will override these defaults).
#
# Returns:
#   0 always
##
derive_env_defaults() {
    if [[ -z "$DEPLOYMENT_ENV" ]]; then
        DEPLOYMENT_ENV="${WIZARD_ENV^^}"
    fi

    if [[ -z "$TAG" && "$WIZARD_ENV" == *-* ]]; then
        TAG="${WIZARD_ENV##*-}"
        TAG="${TAG^^}"
    fi

    return 0
}

##
# Seed phase defaults from build/config-default.yml (if present).
#
# Populates LOG_LEVEL and PROCEDURE_TIMEOUT from the default config so the
# wizard shows accurate defaults rather than hardcoded values.
#
# Returns:
#   0 always
##
seed_defaults_from_config() {
    LOG_LEVEL=$(read_default "core.log_level" "WARN")
    PROCEDURE_TIMEOUT=$(read_default "core.procedure_timeout" "3600")
    return 0
}

##
# Load existing configuration file if provided.
#
# Returns:
#   0 on success, 1 if file not found
##
load_existing_config() {
    if [[ -z "$EXISTING_CONFIG" ]]; then
        return 0
    fi

    if [[ ! -f "$EXISTING_CONFIG" ]]; then
        log_warn "Existing config file not found: $EXISTING_CONFIG"
        return 1
    fi

    log_info "Loading existing configuration from $EXISTING_CONFIG"

    # Load values from YAML
    DT_TENANT=$(read_config_key "$EXISTING_CONFIG" "core.dynatrace_tenant_address" 2>/dev/null || echo "")
    SF_ACCOUNT=$(read_config_key "$EXISTING_CONFIG" "core.snowflake.account_name" 2>/dev/null || echo "")
    DEPLOYMENT_ENV=$(read_config_key "$EXISTING_CONFIG" "core.deployment_environment" 2>/dev/null || echo "")
    TAG=$(read_config_key "$EXISTING_CONFIG" "core.tag" 2>/dev/null || echo "")

    return 0
}

##
# Run Phase 1: Core Configuration.
#
# Prompts for DT tenant, token, SF account, environment name, and tag.
#
# Returns:
#   0 on success, 1 on EOF
##
phase1_core_config() {
    log_info "=== Phase 1: Core Configuration ==="
    echo "" >&2

    # Dynatrace tenant address
    while true; do
        DT_TENANT=$(prompt_input "Dynatrace tenant address" "$DT_TENANT") || return 1
        DT_TENANT=$(validate_dt_tenant "$DT_TENANT") || {
            log_error "Invalid tenant address. Must match *.live.dynatrace.com, *.sprint.dynatracelabs.com, or *.dev.dynatracelabs.com"
            continue
        }
        log_ok "Tenant: $DT_TENANT"
        break
    done

    # Dynatrace API token
    while true; do
        DT_TOKEN=$(prompt_input "Dynatrace API token" "") || return 1
        if ! validate_nonempty "$DT_TOKEN"; then
            log_error "API token cannot be empty"
            continue
        fi
        log_ok "Token: (hidden)"
        break
    done

    # Snowflake account
    while true; do
        SF_ACCOUNT=$(prompt_input "Snowflake account identifier" "$SF_ACCOUNT") || return 1
        if ! validate_sf_account "$SF_ACCOUNT"; then
            log_error "Invalid account format. Use org-account or locator.region"
            continue
        fi
        log_ok "Account: $SF_ACCOUNT"
        break
    done

    # Deployment environment
    while true; do
        DEPLOYMENT_ENV=$(prompt_input "Deployment environment name" "$DEPLOYMENT_ENV") || return 1
        if ! validate_nonempty "$DEPLOYMENT_ENV"; then
            log_error "Environment name cannot be empty"
            continue
        fi
        log_ok "Environment: $DEPLOYMENT_ENV"
        break
    done

    # Multitenancy tag (optional)
    TAG=$(prompt_input "Multitenancy tag (optional)" "$TAG") || return 1
    if [[ -n "$TAG" ]]; then
        if ! validate_alphanumeric "$TAG"; then
            log_warn "Tag contains non-alphanumeric characters. Proceeding anyway."
        fi
    fi
    log_ok "Tag: ${TAG:-(none)}"

    echo "" >&2
    return 0
}

##
# Run Phase 2: Deployment Scope Selection.
#
# Prompts for deployment scope and options.
#
# Returns:
#   0 on success, 1 on EOF
##
phase2_deployment_scope() {
    log_info "=== Phase 2: Deployment Scope ==="
    echo "" >&2

    local scopes=(
        "Full install (all)"
        "Init + Admin"
        "Init only"
        "Post-init setup (setup,plugins,config,agents,apikey)"
        "Config update only"
        "API key update"
        "Upgrade"
        "Teardown"
        "DT Assets (dashboards/workflows)"
    )

    DEPLOYMENT_SCOPE=$(prompt_select_one "Select deployment scope:" "Full install (all)" "${scopes[@]}") || return 1

    case "$DEPLOYMENT_SCOPE" in
        "Full install (all)")
            DEPLOYMENT_SCOPE="all"
            ;;
        "Init + Admin")
            DEPLOYMENT_SCOPE="init,admin"
            ;;
        "Init only")
            DEPLOYMENT_SCOPE="init"
            ;;
        "Post-init setup (setup,plugins,config,agents,apikey)")
            DEPLOYMENT_SCOPE="setup,plugins,config,agents,apikey"
            ;;
        "Config update only")
            DEPLOYMENT_SCOPE="config"
            ;;
        "API key update")
            DEPLOYMENT_SCOPE="apikey"
            ;;
        "Upgrade")
            DEPLOYMENT_SCOPE="upgrade"
            FROM_VERSION=$(prompt_input "From version (e.g., 0.9.4)" "") || return 1
            ;;
        "Teardown")
            DEPLOYMENT_SCOPE="teardown"
            ;;
        "DT Assets (dashboards/workflows)")
            DEPLOYMENT_SCOPE="dt_assets"
            ;;
    esac

    log_ok "Scope: $DEPLOYMENT_SCOPE"

    # Options
    echo "" >&2
    if prompt_yesno "Generate SQL only (manual mode)?" "n"; then
        MANUAL_MODE=1
        SKIP_CONFIRM=1
        NO_DEP=1
        log_info "Manual mode enabled — skipping confirmation and bizevents prompts (not applicable)"
    else
        if prompt_yesno "Skip deployment confirmation?" "n"; then
            SKIP_CONFIRM=1
        fi

        if prompt_yesno "Skip deployment bizevents?" "n"; then
            NO_DEP=1
        fi
    fi

    echo "" >&2
    return 0
}

##
# Interactively customise per-plugin settings.
#
# For each enabled plugin, prompts for schedule, lookback_hours (if applicable),
# and is_disabled. Defaults are read from build/config-default.yml. Only
# non-default values are stored in PLUGIN_OVERRIDES.
#
# Returns:
#   0 on success, 1 on EOF
##
customize_plugins_interactive() {
    # Ordered list of plugins that have meaningful per-plugin settings.
    # Matches keys under plugins: in config-default.yml (excludes self_monitoring).
    local plugins=(
        event_log
        data_schemas
        budgets
        users
        login_history
        trust_center
        warehouse_usage
        resource_monitors
        dynamic_tables
        tasks
        event_usage
        snowpipes
        shares
        active_queries
        query_history
        data_volume
    )

    if [[ ${#plugins[@]} -eq 0 ]]; then
        log_info "No customizable plugins found."
        return 0
    fi

    log_info "--- Plugin Customization ---"
    log_info "Press Enter to accept the default value shown in [brackets]."
    echo "" >&2

    local plugin
    for plugin in "${plugins[@]}"; do
        local def_disabled def_schedule def_lookback
        def_disabled=$(read_default "plugins.${plugin}.is_disabled" "false")
        def_schedule=$(read_default "plugins.${plugin}.schedule" "")
        def_lookback=$(read_default "plugins.${plugin}.lookback_hours" "")

        echo "  Plugin: $plugin" >&2

        # is_disabled
        local cur_disabled="$def_disabled"
        local disabled_input
        disabled_input=$(prompt_input "    is_disabled (true/false)" "$cur_disabled") || return 1
        if [[ -z "$disabled_input" ]]; then
            disabled_input="$cur_disabled"
        fi

        # schedule (only if the plugin has one)
        local cur_schedule=""
        if [[ -n "$def_schedule" ]]; then
            local schedule_input
            schedule_input=$(prompt_input "    schedule" "$def_schedule") || return 1
            if [[ -z "$schedule_input" ]]; then
                schedule_input="$def_schedule"
            fi
            cur_schedule="$schedule_input"
        fi

        # lookback_hours (only if the plugin has one)
        local cur_lookback=""
        if [[ -n "$def_lookback" ]]; then
            local lookback_input
            lookback_input=$(prompt_input "    lookback_hours" "$def_lookback") || return 1
            if [[ -z "$lookback_input" ]]; then
                lookback_input="$def_lookback"
            fi
            cur_lookback="$lookback_input"
        fi

        # Collect non-default overrides
        local overrides=""
        if [[ "$disabled_input" != "$def_disabled" ]]; then
            overrides+="is_disabled=${disabled_input} "
        fi
        if [[ -n "$cur_schedule" && "$cur_schedule" != "$def_schedule" ]]; then
            overrides+="schedule=${cur_schedule} "
        fi
        if [[ -n "$cur_lookback" && "$cur_lookback" != "$def_lookback" ]]; then
            overrides+="lookback_hours=${cur_lookback} "
        fi

        if [[ -n "$overrides" ]]; then
            PLUGIN_OVERRIDES["$plugin"]="${overrides% }"
            log_ok "  $plugin: overrides saved"
        else
            log_info "  $plugin: using defaults"
        fi

        echo "" >&2
    done

    return 0
}

##
# Run Phase 3: Plugin Selection and Configuration.
#
# Triggered for scopes that involve plugin deployment or configuration:
# all, setup, plugins, agents, config. Manual mode does not skip this phase.
#
# Returns:
#   0 on success, 1 on EOF
##
phase3_plugin_selection() {
    # Run Phase 3 only for scopes that involve plugin deployment or configuration.
    # Manual mode does NOT skip this phase — SQL generation still needs plugin selection.
    if ! [[ "$DEPLOYMENT_SCOPE" =~ (all|setup|plugins|agents|config) ]]; then
        log_info "Skipping Phase 3 (plugin selection not applicable for this scope)"
        return 0
    fi

    log_info "=== Phase 3: Plugin Selection ==="
    echo "" >&2

    # Q1: Which plugins to enable?
    local q1_options=("All (default)" "None" "Selected")
    PLUGINS_MODE=$(prompt_select_one "Which plugins to enable?" "All (default)" "${q1_options[@]}") || return 1

    case "$PLUGINS_MODE" in
        "All (default)")
            PLUGINS_MODE="all"
            log_ok "All plugins enabled"
            ;;
        "None")
            PLUGINS_MODE="none"
            log_ok "No plugins enabled"
            ;;
        "Selected")
            PLUGINS_MODE="selected"
            log_ok "Selected plugins mode"
            ;;
    esac

    echo "" >&2

    # Q2: Deploy plugin code for disabled plugins?
    # Only meaningful when not all plugins are enabled — if all are enabled there
    # are no disabled plugins to deploy.
    if [[ "$PLUGINS_MODE" == "all" ]]; then
        DEPLOY_DISABLED_PLUGINS=1
    else
        if prompt_yesno "Deploy all plugin code (including disabled)?" "y"; then
            DEPLOY_DISABLED_PLUGINS=1
            log_ok "Will deploy all plugin code"
        else
            DEPLOY_DISABLED_PLUGINS=0
            log_ok "Will deploy only enabled plugin code"
        fi
        echo "" >&2
    fi

    # Q3: Customize plugin settings? (if not none)
    if [[ "$PLUGINS_MODE" != "none" ]]; then
        if prompt_yesno "Customize enabled plugin settings?" "n"; then
            CUSTOMIZE_PLUGINS=1
            customize_plugins_interactive || return 1
        fi
        echo "" >&2
    fi

    return 0
}

##
# Run Phase 4: Advanced Configuration.
#
# Optional phase, only if user opts in.
# Defaults are read from build/config-default.yml where available.
#
# Returns:
#   0 on success, 1 on EOF
##
phase4_advanced_config() {
    echo "" >&2
    if ! prompt_yesno "Configure advanced settings?" "n"; then
        log_info "Skipping advanced configuration"
        return 0
    fi

    log_info "=== Phase 4: Advanced Configuration ==="
    echo "" >&2

    # Log level — default from config-default.yml
    local log_levels=("DEBUG" "INFO" "WARN" "ERROR")
    LOG_LEVEL=$(prompt_select_one "Log level:" "$LOG_LEVEL" "${log_levels[@]}") || return 1
    log_ok "Log level: $LOG_LEVEL"

    # Procedure timeout — default from config-default.yml
    PROCEDURE_TIMEOUT=$(prompt_input "Procedure timeout (seconds)" "$PROCEDURE_TIMEOUT") || return 1
    log_ok "Procedure timeout: $PROCEDURE_TIMEOUT"

    echo "" >&2
    return 0
}

##
# Run Phase 5: OpenTelemetry Configuration.
#
# Optional phase, only if user opts in. Defaults are read from
# build/config-default.yml. Only non-default values are written to config.
#
# Returns:
#   0 on success, 1 on EOF
##
phase5_otel_config() {
    echo "" >&2
    if ! prompt_yesno "Configure OpenTelemetry settings?" "n"; then
        log_info "Skipping OpenTelemetry configuration"
        return 0
    fi

    log_info "=== Phase 5: OpenTelemetry Configuration ==="
    echo "" >&2
    log_info "Tip: Disable events and biz_events if your tenant does not have a DPS subscription."
    echo "" >&2

    local def_logs_dis def_spans_dis def_metrics_dis def_events_dis def_biz_dis def_max_fails
    def_logs_dis=$(read_default "otel.logs.is_disabled" "false")
    def_spans_dis=$(read_default "otel.spans.is_disabled" "false")
    def_metrics_dis=$(read_default "otel.metrics.is_disabled" "false")
    def_events_dis=$(read_default "otel.events.is_disabled" "false")
    def_biz_dis=$(read_default "otel.biz_events.is_disabled" "false")
    def_max_fails=$(read_default "otel.max_consecutive_api_fails" "10")

    local val

    val=$(prompt_input "otel.logs.is_disabled (true/false)" "$def_logs_dis") || return 1
    [[ -z "$val" ]] && val="$def_logs_dis"
    [[ "$val" != "$def_logs_dis" ]] && OTEL_LOGS_DISABLED="$val"

    val=$(prompt_input "otel.spans.is_disabled (true/false)" "$def_spans_dis") || return 1
    [[ -z "$val" ]] && val="$def_spans_dis"
    [[ "$val" != "$def_spans_dis" ]] && OTEL_SPANS_DISABLED="$val"

    val=$(prompt_input "otel.metrics.is_disabled (true/false)" "$def_metrics_dis") || return 1
    [[ -z "$val" ]] && val="$def_metrics_dis"
    [[ "$val" != "$def_metrics_dis" ]] && OTEL_METRICS_DISABLED="$val"

    val=$(prompt_input "otel.events.is_disabled (true/false)" "$def_events_dis") || return 1
    [[ -z "$val" ]] && val="$def_events_dis"
    [[ "$val" != "$def_events_dis" ]] && OTEL_EVENTS_DISABLED="$val"

    val=$(prompt_input "otel.biz_events.is_disabled (true/false)" "$def_biz_dis") || return 1
    [[ -z "$val" ]] && val="$def_biz_dis"
    [[ "$val" != "$def_biz_dis" ]] && OTEL_BIZ_EVENTS_DISABLED="$val"

    val=$(prompt_input "otel.max_consecutive_api_fails" "$def_max_fails") || return 1
    [[ -z "$val" ]] && val="$def_max_fails"
    [[ "$val" != "$def_max_fails" ]] && OTEL_MAX_CONSECUTIVE_API_FAILS="$val"

    echo "" >&2
    log_ok "OTel configuration collected"
    return 0
}

##
# Generate YAML configuration from collected values.
#
# Writes core, plugins, otel (non-default overrides only), and plugin
# customization overrides to the output file.
#
# Args:
#   $1: Output file path
#
# Returns:
#   0 on success, 1 on failure
##
generate_config_yaml() {
    local output_file="$1"

    # Create YAML structure
    cat > "$output_file" << EOF
# DSOA Configuration - Generated by interactive wizard
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

core:
  dynatrace_tenant_address: "$DT_TENANT"
  snowflake:
    account_name: "$SF_ACCOUNT"
  deployment_environment: "$DEPLOYMENT_ENV"
  log_level: "$LOG_LEVEL"
  procedure_timeout: $PROCEDURE_TIMEOUT
EOF

    if [[ -n "$TAG" ]]; then
        echo "  tag: \"$TAG\"" >> "$output_file"
    fi

    if [[ -n "$RESOURCE_MONITOR_QUOTA" ]]; then
        echo "  snowflake:" >> "$output_file"
        echo "    resource_monitor:" >> "$output_file"
        echo "      credit_quota: $RESOURCE_MONITOR_QUOTA" >> "$output_file"
    fi

    # OTel section — only write keys that differ from defaults
    local otel_written=0
    _otel_line() {
        local section="$1" key="$2" val="$3"
        if [[ $otel_written -eq 0 ]]; then
            echo "" >> "$output_file"
            echo "otel:" >> "$output_file"
            otel_written=1
        fi
        # Ensure sub-section header exists (idempotent for repeated calls to same section)
        if ! grep -q "^  ${section}:" "$output_file" 2>/dev/null; then
            echo "  ${section}:" >> "$output_file"
        fi
        echo "    ${key}: ${val}" >> "$output_file"
    }

    if [[ -n "$OTEL_MAX_CONSECUTIVE_API_FAILS" ]]; then
        echo "" >> "$output_file"
        echo "otel:" >> "$output_file"
        echo "  max_consecutive_api_fails: $OTEL_MAX_CONSECUTIVE_API_FAILS" >> "$output_file"
        otel_written=1
    fi
    [[ -n "$OTEL_LOGS_DISABLED" ]]    && _otel_line "logs"       "is_disabled" "$OTEL_LOGS_DISABLED"
    [[ -n "$OTEL_SPANS_DISABLED" ]]   && _otel_line "spans"      "is_disabled" "$OTEL_SPANS_DISABLED"
    [[ -n "$OTEL_METRICS_DISABLED" ]] && _otel_line "metrics"    "is_disabled" "$OTEL_METRICS_DISABLED"
    [[ -n "$OTEL_EVENTS_DISABLED" ]]  && _otel_line "events"     "is_disabled" "$OTEL_EVENTS_DISABLED"
    [[ -n "$OTEL_BIZ_EVENTS_DISABLED" ]] && _otel_line "biz_events" "is_disabled" "$OTEL_BIZ_EVENTS_DISABLED"

    # Plugins section
    cat >> "$output_file" << EOF

plugins:
  deploy_disabled_plugins: $DEPLOY_DISABLED_PLUGINS
EOF

    # Per-plugin overrides
    local plugin
    for plugin in "${!PLUGIN_OVERRIDES[@]}"; do
        local overrides="${PLUGIN_OVERRIDES[$plugin]}"
        echo "  ${plugin}:" >> "$output_file"
        local pair
        for pair in $overrides; do
            local k="${pair%%=*}"
            local v="${pair#*=}"
            echo "    ${k}: ${v}" >> "$output_file"
        done
    done

    # Add environment variable for token
    cat >> "$output_file" << EOF

# Set DTAGENT_TOKEN environment variable before deployment:
# export DTAGENT_TOKEN="$DT_TOKEN"
EOF

    return 0
}

##
# Display configuration summary and ask for persistence action.
#
# Returns:
#   0 if config should be saved/used, 1 if discarded
##
config_persistence() {
    echo "" >&2
    log_info "=== Configuration Summary ==="
    echo "" >&2

    cat << EOF >&2
Dynatrace Tenant:     $DT_TENANT
Snowflake Account:    $SF_ACCOUNT
Deployment Env:       $DEPLOYMENT_ENV
Multitenancy Tag:     ${TAG:-(none)}
Deployment Scope:     $DEPLOYMENT_SCOPE
Log Level:            $LOG_LEVEL
Procedure Timeout:    $PROCEDURE_TIMEOUT
Deploy Disabled Code: $( [[ "$DEPLOY_DISABLED_PLUGINS" -eq 1 ]] && echo "YES" || echo "NO" )
EOF

    echo "" >&2

    local action
    if [[ -n "$EXISTING_CONFIG" ]]; then
        # Editing an existing config — offer update-in-place as an option
        local persistence_options=(
            "Save as new config"
            "Update existing config"
            "Print to stdout only"
            "Discard"
        )
        action=$(prompt_select_one "What would you like to do?" "Save as new config" "${persistence_options[@]}") || return 1
    else
        # New config — no existing file to update
        local persistence_options=(
            "Save config"
            "Print to stdout only"
            "Discard"
        )
        action=$(prompt_select_one "What would you like to do?" "Save config" "${persistence_options[@]}") || return 1
    fi

    case "$action" in
        "Save as new config"|"Save config")
            local config_file="conf/config-${WIZARD_ENV}.yml"
            generate_config_yaml "$config_file"
            log_ok "Configuration saved to $config_file"
            return 0
            ;;
        "Update existing config")
            generate_config_yaml "$EXISTING_CONFIG"
            log_ok "Configuration updated in $EXISTING_CONFIG"
            return 0
            ;;
        "Print to stdout only")
            local temp_file
            temp_file=$(mktemp)
            generate_config_yaml "$temp_file"
            cat "$temp_file"
            rm -f "$temp_file"
            echo "" >&2
            if prompt_yesno "Continue to deployment?" "n"; then
                return 0
            else
                return 1
            fi
            ;;
        "Discard")
            log_info "Configuration discarded. Exiting."
            return 1
            ;;
    esac

    return 0
}

##endregion

##region Main Execution

##
# Main wizard execution.
#
# Returns:
#   0 on success, 1 on error or user cancellation
##
main() {
    log_info "DSOA Interactive Deployment Wizard"
    echo "" >&2

    # Parse arguments
    if ! parse_arguments "$@"; then
        return 1
    fi

    # Seed phase defaults from build/config-default.yml (before any prompts)
    seed_defaults_from_config

    # Derive defaults from --env before loading existing config
    # (existing config values will override these defaults)
    derive_env_defaults

    # Load existing config if provided
    load_existing_config

    # Run phases
    if ! phase1_core_config; then
        log_error "Phase 1 cancelled"
        return 1
    fi

    if ! phase2_deployment_scope; then
        log_error "Phase 2 cancelled"
        return 1
    fi

    if ! phase3_plugin_selection; then
        log_error "Phase 3 cancelled"
        return 1
    fi

    if ! phase4_advanced_config; then
        log_error "Phase 4 cancelled"
        return 1
    fi

    if ! phase5_otel_config; then
        log_error "Phase 5 cancelled"
        return 1
    fi

    # Config persistence
    if ! config_persistence; then
        return 1
    fi

    log_ok "Wizard completed successfully"
    return 0
}

##endregion

# Execute main function
main "$@"
exit $?
