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
# 5. Telemetry settings (optional)
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
CI_EXPORT=""

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
# Discover all plugin names from the source tree or build artifacts.
#
# Primary:  Scans src/dtagent/plugins/*.config/ directories relative to the
#           repo root (two levels up from this script).
# Fallback: When the source tree is absent (e.g. inside the Docker image),
#           derives plugin names from build/30_plugins/*.sql basenames.
#
# Returns plugin names sorted alphabetically, one per line.
#
# Returns:
#   0 always
#
# Outputs:
#   Sorted plugin names, one per line
##
discover_plugin_names() {
    local plugins_dir="${SCRIPT_DIR}/../../src/dtagent/plugins"
    if [[ -d "$plugins_dir" ]]; then
        local d name
        for d in "$plugins_dir"/*.config/; do
            [[ -d "$d" ]] || continue
            name=$(basename "$d" .config)
            echo "$name"
        done | sort
        return 0
    fi

    # Fallback: derive plugin names from compiled SQL artifacts in build/30_plugins/
    local build_plugins_dir="${SCRIPT_DIR}/../../build/30_plugins"
    if [[ -d "$build_plugins_dir" ]]; then
        local f name
        for f in "$build_plugins_dir"/*.sql; do
            [[ -f "$f" ]] || continue
            name=$(basename "$f" .sql)
            echo "$name"
        done | sort
        return 0
    fi
}

##
# Get a one-line description for a plugin.
#
# Reads the first non-empty, non-heading line from the plugin's readme.md.
# Falls back to the plugin name if readme is absent or empty.
#
# Args:
#   $1: Plugin name
#
# Returns:
#   0 always
#
# Outputs:
#   Short description string (max 70 chars)
##
plugin_description() {
    local name="$1"
    local readme="${SCRIPT_DIR}/../../src/dtagent/plugins/${name}.config/readme.md"
    if [[ -f "$readme" ]]; then
        local line
        while IFS= read -r line; do
            # Skip blank lines and markdown headings
            [[ -z "$line" || "$line" == \#* ]] && continue
            # Truncate to 70 chars
            echo "${line:0:70}"
            return 0
        done < "$readme"
    fi
    echo "$name"
}

##
# Read a default value from build/config-default.yml.
#
# When config-default.yml is absent (e.g. Docker image built without running
# build.sh first, or local dev environment), falls back to reading the value
# directly from the individual plugin config file for paths under plugins.<name>.
#
# Args:
#   $1: yq key path (e.g. "core.log_level" or "plugins.active_queries.schedule")
#   $2: Fallback value if file absent or key missing
#
# Returns:
#   0 always
#
# Outputs:
#   Value from default config, plugin config, or fallback
##
read_default() {
    local key_path="$1"
    local fallback="$2"

    if ! command -v yq >/dev/null 2>&1; then
        echo "$fallback"
        return 0
    fi

    # Primary: read from build/config-default.yml
    if [[ -f "$DEFAULT_CONFIG" ]]; then
        local val
        val=$(yq eval ".${key_path}" "$DEFAULT_CONFIG" 2>/dev/null || true)
        if [[ -n "$val" && "$val" != "null" ]]; then
            echo "$val"
            return 0
        fi
    fi

    # Fallback: for plugins.<name>.<key> paths, read from the plugin's own config file.
    # This handles environments where config-default.yml has not been generated yet
    # (e.g. Docker images built without running build.sh, or local dev trees).
    if [[ "$key_path" == plugins.* ]]; then
        local plugin_name key_name
        # Strip leading "plugins." prefix, then split on first "."
        local rest="${key_path#plugins.}"
        plugin_name="${rest%%.*}"
        key_name="${rest#*.}"
        local plugin_cfg="${SCRIPT_DIR}/../../src/dtagent/plugins/${plugin_name}.config/${plugin_name}-config.yml"
        if [[ -f "$plugin_cfg" ]]; then
            local val
            val=$(yq eval ".${key_path}" "$plugin_cfg" 2>/dev/null || true)
            if [[ -n "$val" && "$val" != "null" ]]; then
                echo "$val"
                return 0
            fi
        fi
    fi

    echo "$fallback"
    return 0
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
            --ci-export=*)
                CI_EXPORT="${1#*=}"
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

    # Dynatrace API token — read silently so it is not echoed to the terminal
    while true; do
        printf "  Dynatrace API token: " >&2
        read -rs DT_TOKEN </dev/tty 2>/dev/null || DT_TOKEN=$(prompt_input "Dynatrace API token" "") || return 1
        echo "" >&2
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
    # Per-plugin customization knobs. Each plugin defines which settings are
    # user-facing. Keys match config-default.yml paths under plugins.<name>.
    # Format: "key1 key2 ..." — schedule is always offered when present.

    log_info "--- Plugin Customization ---"
    log_info "Press Enter to accept the default value shown in [brackets]."
    echo "" >&2

    # Determine which plugins to customize
    local plugins_to_customize=()
    if [[ "$PLUGINS_MODE" == "selected" && ${#SELECTED_PLUGINS[@]} -gt 0 ]]; then
        plugins_to_customize=("${SELECTED_PLUGINS[@]}")
    else
        while IFS= read -r p; do
            plugins_to_customize+=("$p")
        done < <(discover_plugin_names)
    fi

    # Per-plugin knob definitions (beyond schedule which is always shown)
    # Format: plugin_name:knob1,knob2,...
    declare -A PLUGIN_KNOBS
    PLUGIN_KNOBS[event_log]="lookback_hours,max_entries,cross_tenant_monitoring"
    PLUGIN_KNOBS[data_schemas]="lookback_hours"
    PLUGIN_KNOBS[budgets]="quota,monitored_budgets"
    PLUGIN_KNOBS[users]="is_hashed,retain_email_hash_map"
    PLUGIN_KNOBS[login_history]="lookback_hours"
    PLUGIN_KNOBS[trust_center]="log_details"
    PLUGIN_KNOBS[warehouse_usage]="lookback_hours"
    PLUGIN_KNOBS[resource_monitors]=""
    PLUGIN_KNOBS[dynamic_tables]=""
    PLUGIN_KNOBS[tasks]="lookback_hours"
    PLUGIN_KNOBS[event_usage]="lookback_hours"
    PLUGIN_KNOBS[snowpipes]="lookback_hours"
    PLUGIN_KNOBS[shares]=""
    PLUGIN_KNOBS[active_queries]="fast_mode"
    PLUGIN_KNOBS[query_history]="slow_queries_threshold,slow_queries_to_analyze_limit"
    PLUGIN_KNOBS[data_volume]=""

    local plugin
    for plugin in "${plugins_to_customize[@]}"; do
        echo "  Plugin: $plugin" >&2

        # Schedule (always offered if plugin has one)
        local def_schedule
        def_schedule=$(read_default "plugins.${plugin}.schedule" "")
        if [[ -n "$def_schedule" ]]; then
            local schedule_input
            schedule_input=$(prompt_input "    schedule" "$def_schedule") || return 1
            [[ -z "$schedule_input" ]] && schedule_input="$def_schedule"
            if [[ "$schedule_input" != "$def_schedule" ]]; then
                PLUGIN_OVERRIDES["$plugin"]="${PLUGIN_OVERRIDES[$plugin]:-} schedule=${schedule_input}"
            fi
        fi

        # Plugin-specific knobs
        local knobs_str="${PLUGIN_KNOBS[$plugin]:-}"
        if [[ -n "$knobs_str" ]]; then
            IFS=',' read -ra knobs <<< "$knobs_str"
            local knob
            for knob in "${knobs[@]}"; do
                local def_val
                def_val=$(read_default "plugins.${plugin}.${knob}" "")
                if [[ -z "$def_val" || "$def_val" == "null" ]]; then
                    continue
                fi
                local knob_input
                knob_input=$(prompt_input "    ${knob}" "$def_val") || return 1
                [[ -z "$knob_input" ]] && knob_input="$def_val"
                if [[ "$knob_input" != "$def_val" ]]; then
                    PLUGIN_OVERRIDES["$plugin"]="${PLUGIN_OVERRIDES[$plugin]:-} ${knob}=${knob_input}"
                fi
            done
        fi

        # Trim leading space from overrides
        if [[ -n "${PLUGIN_OVERRIDES[$plugin]:-}" ]]; then
            PLUGIN_OVERRIDES["$plugin"]="${PLUGIN_OVERRIDES[$plugin]# }"
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
    local q1_options=("All" "None" "Selected")
    PLUGINS_MODE=$(prompt_select_one "Which plugins to enable?" "All" "${q1_options[@]}") || return 1

    case "$PLUGINS_MODE" in
        "All")
            PLUGINS_MODE="all"
            log_ok "All plugins enabled"
            ;;
        "None")
            PLUGINS_MODE="none"
            log_ok "No plugins enabled"
            ;;
        "Selected")
            PLUGINS_MODE="selected"
            log_info "Select which plugins to enable:"
            echo "" >&2

            # Build plugin list dynamically from source tree
            local all_plugins=()
            local pname pdesc
            while IFS= read -r pname; do
                pdesc=$(plugin_description "$pname")
                all_plugins+=("${pname} — ${pdesc}")
            done < <(discover_plugin_names)

            local selected_lines
            selected_lines=$(prompt_select_multi "Enable plugins:" "${all_plugins[@]}") || return 1

            # Extract plugin names (before " — ")
            SELECTED_PLUGINS=()
            while IFS= read -r line; do
                [[ -z "$line" ]] && continue
                local pname="${line%% —*}"
                SELECTED_PLUGINS+=("$pname")
            done <<< "$selected_lines"

            if [[ ${#SELECTED_PLUGINS[@]} -eq 0 ]]; then
                log_warn "No plugins selected — switching to 'none' mode"
                PLUGINS_MODE="none"
            else
                log_ok "Selected ${#SELECTED_PLUGINS[@]} plugin(s): ${SELECTED_PLUGINS[*]}"
            fi
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
    if ! prompt_yesno "Configure telemetry settings?" "n"; then
        log_info "Skipping telemetry configuration"
        return 0
    fi

    log_info "=== Phase 5: Telemetry Configuration ==="
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
    log_ok "Telemetry configuration collected"
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
    [[ -n "$OTEL_LOGS_DISABLED" ]]    && _otel_line "logs"       "is_disabled" "$(bool_to_yaml "$OTEL_LOGS_DISABLED")"
    [[ -n "$OTEL_SPANS_DISABLED" ]]   && _otel_line "spans"      "is_disabled" "$(bool_to_yaml "$OTEL_SPANS_DISABLED")"
    [[ -n "$OTEL_METRICS_DISABLED" ]] && _otel_line "metrics"    "is_disabled" "$(bool_to_yaml "$OTEL_METRICS_DISABLED")"
    [[ -n "$OTEL_EVENTS_DISABLED" ]]  && _otel_line "events"     "is_disabled" "$(bool_to_yaml "$OTEL_EVENTS_DISABLED")"
    [[ -n "$OTEL_BIZ_EVENTS_DISABLED" ]] && _otel_line "biz_events" "is_disabled" "$(bool_to_yaml "$OTEL_BIZ_EVENTS_DISABLED")"

    # Plugins section
    cat >> "$output_file" << EOF

plugins:
  deploy_disabled_plugins: $(bool_to_yaml "$DEPLOY_DISABLED_PLUGINS")
EOF

    # When "selected" mode, explicitly enable/disable plugins
    if [[ "$PLUGINS_MODE" == "selected" ]]; then
        local all_known_plugins=()
        while IFS= read -r p; do
            all_known_plugins+=("$p")
        done < <(discover_plugin_names)
        local p is_selected
        for p in "${all_known_plugins[@]}"; do
            is_selected=0
            for sp in "${SELECTED_PLUGINS[@]}"; do
                [[ "$sp" == "$p" ]] && { is_selected=1; break; }
            done
            local def_disabled
            def_disabled=$(read_default "plugins.${p}.is_disabled" "false")
            if [[ $is_selected -eq 1 && "$def_disabled" == "true" ]]; then
                # Plugin is disabled by default but user selected it — enable
                # Ensure plugin section exists (may already exist from overrides)
                if [[ -z "${PLUGIN_OVERRIDES[$p]:-}" ]]; then
                    echo "  ${p}:" >> "$output_file"
                    echo "    is_disabled: false" >> "$output_file"
                else
                    # Will be written below with overrides; prepend is_disabled
                    PLUGIN_OVERRIDES["$p"]="is_disabled=false ${PLUGIN_OVERRIDES[$p]}"
                fi
            elif [[ $is_selected -eq 0 && "$def_disabled" != "true" ]]; then
                # Plugin is enabled by default but user did NOT select it — disable
                if [[ -z "${PLUGIN_OVERRIDES[$p]:-}" ]]; then
                    echo "  ${p}:" >> "$output_file"
                    echo "    is_disabled: true" >> "$output_file"
                else
                    PLUGIN_OVERRIDES["$p"]="is_disabled=true ${PLUGIN_OVERRIDES[$p]}"
                fi
            fi
        done
    elif [[ "$PLUGINS_MODE" == "none" ]]; then
        # Disable all plugins
        local all_known_plugins=()
        while IFS= read -r p; do
            all_known_plugins+=("$p")
        done < <(discover_plugin_names)
        local p
        for p in "${all_known_plugins[@]}"; do
            local def_disabled
            def_disabled=$(read_default "plugins.${p}.is_disabled" "false")
            if [[ "$def_disabled" != "true" ]]; then
                echo "  ${p}:" >> "$output_file"
                echo "    is_disabled: true" >> "$output_file"
            fi
        done
    fi

    # Per-plugin overrides
    local plugin
    for plugin in "${!PLUGIN_OVERRIDES[@]}"; do
        local overrides="${PLUGIN_OVERRIDES[$plugin]}"
        echo "  ${plugin}:" >> "$output_file"
        local pair
        for pair in $overrides; do
            local k="${pair%%=*}"
            local v="${pair#*=}"
            # Normalise boolean fields to YAML true/false
            case "$k" in
                is_disabled|disabled_by_default)
                    v=$(bool_to_yaml "$v") ;;
            esac
            echo "    ${k}: ${v}" >> "$output_file"
        done
    done

    # Add environment variable hint for token (placeholder only — never write the actual token)
    cat >> "$output_file" << 'EOF'

# Set DTAGENT_TOKEN environment variable before deployment:
# export DTAGENT_TOKEN="<your-dynatrace-api-token>"
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

    # --dry-run: print generated config to stdout, do not write any file
    if [[ $DRY_RUN -eq 1 ]]; then
        log_info "Dry-run mode: printing config to stdout (no file written)"
        generate_config_yaml /dev/stdout
        return 0
    fi

    # --output=<file>: write directly to the specified path, skip menu
    if [[ -n "$OUTPUT_FILE" ]]; then
        generate_config_yaml "$OUTPUT_FILE"
        log_ok "Configuration written to $OUTPUT_FILE"
        return 0
    fi

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
            if prompt_yesno "Config printed above. Continue to deployment?" "n"; then
                return 0
            fi
            log_info "Exiting without deployment."
            return 1
            ;;
        "Discard")
            log_info "Configuration discarded. Exiting."
            return 1
            ;;
    esac

    return 0
}

##endregion

##region CI Export

##
# Export a GitHub Actions deployment workflow and secrets setup guide.
#
# Reads version from build/config-default.yml (falls back to "latest").
# Substitutes __ENV__, __VERSION__, and __SF_USER__ in templates.
# Writes .github/workflows/dsoa-deploy.yml and GITHUB_SECRETS_SETUP.md.
#
# Returns:
#   0 on success, 1 on error
##
export_github_ci() {
    local env="$1"
    local sf_user="CHANGE_ME"

    # Determine version from build/config-default.yml
    local version="latest"
    local default_cfg="${SCRIPT_DIR}/../../build/config-default.yml"
    if [[ -f "$default_cfg" ]]; then
        local v
        v=$(yq eval '.version // ""' "$default_cfg" 2>/dev/null || true)
        [[ -n "$v" ]] && version="v${v}"
    fi

    local template_dir="${SCRIPT_DIR}/../../src/assets/ci-templates/github"
    local workflow_template="${template_dir}/dsoa-deploy.yml.template"
    local secrets_template="${template_dir}/GITHUB_SECRETS_SETUP.md.template"

    if [[ ! -f "$workflow_template" ]]; then
        log_error "CI template not found: $workflow_template"
        return 1
    fi
    if [[ ! -f "$secrets_template" ]]; then
        log_error "CI template not found: $secrets_template"
        return 1
    fi

    # Write workflow file
    local workflow_dir=".github/workflows"
    mkdir -p "$workflow_dir"
    local workflow_out="${workflow_dir}/dsoa-deploy.yml"
    sed -e "s/__ENV__/${env}/g" \
        -e "s/__VERSION__/${version}/g" \
        -e "s/__SF_USER__/${sf_user}/g" \
        "$workflow_template" > "$workflow_out"

    # Write secrets setup guide
    local secrets_out="GITHUB_SECRETS_SETUP.md"
    sed -e "s/__ENV__/${env}/g" \
        -e "s/__VERSION__/${version}/g" \
        -e "s/__SF_USER__/${sf_user}/g" \
        "$secrets_template" > "$secrets_out"

    log_ok "GitHub Actions workflow written to: $workflow_out"
    log_ok "Secrets setup guide written to: $secrets_out"
    echo "" >&2
    log_info "Next steps:"
    echo "  1. Commit $workflow_out to your deployment repository" >&2
    echo "  2. Follow $secrets_out to configure GitHub secrets" >&2
    echo "  3. Trigger the workflow via GitHub Actions UI" >&2

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

    # Guard: interactive wizard requires a TTY on stdin.
    # Without a TTY (e.g. Docker without -it, CI pipelines) every read call
    # returns EOF immediately, causing cryptic "Phase N cancelled" errors.
    if [[ ! -t 0 ]]; then
        log_error "Interactive mode requires a TTY — stdin is not a terminal."
        echo "" >&2
        echo "  If you are running inside Docker, add the -it flags:" >&2
        echo "    docker run -it dsoa-deploy:local --env=${WIZARD_ENV}" >&2
        echo "" >&2
        echo "  For non-interactive deployments use one of:" >&2
        echo "    --defaults   (generate config from env vars, then deploy)" >&2
        echo "    --scope=...  (deploy with an existing conf/config-${WIZARD_ENV}.yml)" >&2
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

    # CI export (if requested)
    if [[ -n "$CI_EXPORT" ]]; then
        case "$CI_EXPORT" in
            github)
                if ! export_github_ci "$WIZARD_ENV"; then
                    return 1
                fi
                ;;
            *)
                log_error "Unknown --ci-export value: '$CI_EXPORT'. Supported: github"
                return 1
                ;;
        esac
    fi

    log_ok "Wizard completed successfully"
    return 0
}

##endregion

# Execute main function only when run directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
    exit $?
fi
