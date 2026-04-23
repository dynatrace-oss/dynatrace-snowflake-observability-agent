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
# This is a script for deploying / updating the whole or part of Dynatrace Snowflake Observability Agent
# Call as ./deploy.sh --env=$ENV [--scope=$SCOPE] [--from-version=$VERSION] [--options=$OPTIONS] [--interactive] [--defaults]
#
# Args:
# * --env          [REQUIRED] - environment identifier (config-$ENV.yml must exist or will be created)
# * $ENV           [DEPRECATED] - positional environment (backward compat, use --env= instead)
# * --scope        [OPTIONAL] - deployment scope (default: all):
#                               init, admin, setup, plugins, config, agents, apikey, all, teardown, upgrade, or file_part
#                               Multiple scopes can be specified as comma-separated list (e.g., setup,plugins,config,agents,apikey)
#                               Note: teardown and all cannot be combined with other scopes
# * --from-version [OPTIONAL] - version number for upgrade scope (required if scope=upgrade)
# * --output-file  [OPTIONAL] - output file path for manual mode (default: dsoa-deploy-script-{ENV}-{TIMESTAMP}.sql)
# * --options      [OPTIONAL] - comma-separated: manual, service_user, skip_confirm, no_dep
# * --interactive  [OPTIONAL] - launch interactive wizard (auto-triggered if config missing)
# * --defaults     [OPTIONAL] - generate minimal config non-interactively

#

ENV=""
INTERACTIVE=0
DEFAULTS=0
SCOPE="all"
FROM_VERSION=""
OUTPUT_FILE=""
OPTIONS_STR=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env=*)
            ENV="${1#*=}"
            shift
            ;;
        --interactive)
            INTERACTIVE=1
            shift
            ;;
        --defaults)
            DEFAULTS=1
            shift
            ;;
        --scope=*)
            SCOPE="${1#*=}"
            shift
            ;;
        --from-version=*)
            FROM_VERSION="${1#*=}"
            shift
            ;;
        --output-file=*)
            OUTPUT_FILE="${1#*=}"
            shift
            ;;
        --options=*)
            OPTIONS_STR="${1#*=}"
            shift
            ;;
        --help|-h)
            cat >&2 <<'HELP'
Usage: deploy.sh --env=<ENV> [--scope=<SCOPE>] [--from-version=<VERSION>] [--output-file=<FILE>] [--options=<OPTIONS>]

Required:
  --env=<ENV>              Environment name — must match conf/config-<ENV>.yml

Optional:
  --scope=<SCOPE>          Deployment scope (default: all)
                           Values: init, admin, setup, plugins, config, agents, apikey,
                                   all, teardown, upgrade, dt_assets, or a file pattern
                           Multiple: comma-separated (e.g. setup,plugins,config,agents)
  --from-version=<VER>     Required when --scope=upgrade (e.g. 0.9.2)
  --output-file=<FILE>     Output file path for --options=manual mode
  --options=<OPTIONS>      Comma-separated flags:
                             manual        Generate SQL script without executing
                             skip_confirm  Skip confirmation prompt
                             no_dep        Skip deployment BizEvents
                             dry_run       Dry-run for dt_assets scope
  --interactive            Launch interactive configuration wizard
  --defaults               Generate minimal config file non-interactively
  -h, --help               Show this help message

Examples:
  deploy.sh --env=prod                                     # Full deploy
  deploy.sh --env=prod --scope=plugins,config,agents       # Partial deploy
  deploy.sh --env=prod --scope=upgrade --from-version=0.9.2
  deploy.sh --env=prod --options=manual --output-file=my.sql
  deploy.sh --env=prod --options=skip_confirm              # No confirmation prompt
  deploy.sh --env=prod --defaults                          # Generate config skeleton
HELP
            exit 0
            ;;
        *)
            # Check if it's a positional ENV argument (backward compat)
            if [[ -z "$ENV" && ! "$1" =~ ^-- ]]; then
                ENV="$1"
                echo "⚠ WARNING: Positional environment argument is deprecated. Use --env=$ENV instead." >&2
                shift
            else
                echo "Unknown parameter: $1"
                exit 1
            fi
            ;;
    esac
done

# Parse options into array
IFS=',' read -ra OPTIONS <<< "$OPTIONS_STR"

# Check if option is present
has_option() {
    local opt=$1
    for item in "${OPTIONS[@]}"; do
        [[ "$item" == "$opt" ]] && return 0
    done
    return 1
}

# Handle interactive wizard
CWD=$(dirname "$0")
CONFIG_FILE="conf/config-$ENV.yml"

if [[ -z "$ENV" ]]; then
    echo "ERROR: --env=<ENV> is required." >&2
    echo "       Example: deploy.sh --env=production" >&2
    echo "       Run deploy.sh --help for full usage." >&2
    exit 1
fi

# Early build artifact check — must happen before wizard and before setup.sh.
# Skipped for:
#   dt_assets    — no build files needed for dashboard/workflow deploys
#   --interactive — wizard collects config, actual deploy runs later
#   --defaults without existing config — only generates config, no build artifacts required
_skip_build_check=0
if [[ "$SCOPE" == "dt_assets" || $INTERACTIVE -eq 1 ]]; then
    _skip_build_check=1
elif [[ $DEFAULTS -eq 1 && ! -f "$CONFIG_FILE" ]]; then
    _skip_build_check=1
fi
if [[ $_skip_build_check -eq 0 ]]; then
    if [[ ! -d "build" ]] || [[ -z "$(ls -A build 2>/dev/null)" ]]; then
        echo "ERROR: Build artifacts are missing. Run the following command first:" >&2
        echo "       ./scripts/dev/build.sh" >&2
        exit 1
    fi
fi

# Auto-trigger wizard if config missing and not using --defaults
if [[ ! -f "$CONFIG_FILE" && $DEFAULTS -eq 0 ]]; then
    INTERACTIVE=1
fi

# Run interactive wizard if requested
if [[ $INTERACTIVE -eq 1 ]]; then
    if [[ $DEFAULTS -eq 1 ]]; then
        echo "ERROR: --interactive and --defaults are mutually exclusive" >&2
        exit 1
    fi

    # Check if config exists for edit mode
    EXISTING_CONFIG=""
    if [[ -f "$CONFIG_FILE" ]]; then
        EXISTING_CONFIG="$CONFIG_FILE"
    fi

    # Run wizard
    if [[ -n "$EXISTING_CONFIG" ]]; then
        "$CWD/interactive_wizard.sh" --env="$ENV" --existing-config="$EXISTING_CONFIG"
    else
        "$CWD/interactive_wizard.sh" --env="$ENV"
    fi

    if [[ $? -ne 0 ]]; then
        echo "Wizard cancelled or failed" >&2
        exit 1
    fi
fi

# Generate minimal config if --defaults specified
if [[ $DEFAULTS -eq 1 ]]; then
    if [[ ! -f "$CONFIG_FILE" ]]; then
        # Generate config from environment variables
        if [[ -z "${DSOA_DT_TENANT:-}" ]]; then
            echo "ERROR: --defaults requires DSOA_DT_TENANT env var (Dynatrace tenant address)" >&2
            exit 1
        fi

        _deploy_env="${DSOA_DEPLOYMENT_ENV:-${ENV^^}}"
        _sf_account="${DSOA_SF_ACCOUNT:-CHANGE_ME}"

        mkdir -p conf
        yq -n \
            ".core.dynatrace_tenant_address = \"${DSOA_DT_TENANT}\" |
             .core.deployment_environment = \"${_deploy_env}\" |
             .core.snowflake.account_name = \"${_sf_account}\" |
             .core.log_level = \"WARN\" |
             .core.procedure_timeout = 3600 |
             .plugins.deploy_disabled_plugins = true" \
            > "$CONFIG_FILE"

        echo "Config generated at: $CONFIG_FILE" >&2
        echo "Run deploy.sh --env=$ENV to deploy." >&2
        exit 0
    else
        echo "Config file already exists: $CONFIG_FILE — using as-is" >&2
    fi

    # --defaults implies skip_confirm
    if ! has_option "skip_confirm"; then
        OPTIONS_STR="${OPTIONS_STR:+${OPTIONS_STR},}skip_confirm"
        IFS=',' read -ra OPTIONS <<< "$OPTIONS_STR"
    fi
fi

# Display warning when bizevent send fails
show_bizevent_warning() {
    local stage=$1  # "STARTED" or "FINISHED"
    local status_msg="Deployment will continue, but telemetry will not be sent to Dynatrace."

    if [ "$stage" == "FINISHED" ]; then
        status_msg="Deployment completed, but telemetry was not sent to Dynatrace."
    fi

    cat <<-EOH

	╔══════════════════════════════════════════════════════════════════════════════════╗
	║                                   ⚠️  WARNING  ⚠️                                 ║
	╠══════════════════════════════════════════════════════════════════════════════════╣
	║                                                                                  ║
	║  Failed to send deployment bizevent to Dynatrace!                                ║
	║                                                                                  ║
	║  This may indicate issues with:                                                  ║
	║    • Dynatrace API token (DTAGENT_TOKEN) - check if valid and not expired        ║
	║    • Network connectivity to Dynatrace tenant                                    ║
	║    • API token permissions (requires bizevents.ingest scope)                     ║
	║                                                                                  ║
	║  $status_msg          ║
	║                                                                                  ║
	╚══════════════════════════════════════════════════════════════════════════════════╝

	EOH
    sleep 3
}

if has_option "manual"; then
    IS_MANUAL="true"
    "$CWD/setup.sh"
else
    IS_MANUAL="false"
    "$CWD/setup.sh" $ENV
fi

echo "Deploying Dynatrace Snowflake Observability Agent with [$ENV] configuration, using SCOPE=[$SCOPE]"

if [ "$ENV" == '' ]; then
    echo "Needs environment name to proceed"
    exit 1
fi

if [ "$SCOPE" == '' ]; then
    echo "Needs --scope parameter to proceed"
    exit 1
fi

if [ "$SCOPE" == "upgrade" ] && [ "$FROM_VERSION" == '' ]; then
    echo "--from-version parameter is required when scope=upgrade"
    exit 1
fi



DEFAULT_CONFIG_FILE="build/config-default.yml"
CONFIG_FILE="conf/config-$ENV.yml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "There is no configuration file [conf/config-$ENV.yml]"
    #%DEV:
    # we could just exit if config file doesn't exist and we either do not want to deploy at all or want to deploy through jenkins

    if ! has_option "no_dep"; then
        #%:DEV
        exit 1
        #%DEV:
    fi
    #%:DEV
fi

export BUILD_CONFIG_FILE="build/config.json"

DEPLOYMENT_ID=$(uuidgen)

$CWD/prepare_config.sh "${DEFAULT_CONFIG_FILE}" "${CONFIG_FILE}"

# Validate and fix dynatrace_tenant_address if it uses deprecated .apps.dynatrace.com domain
TENANT_ADDRESS="$($CWD/get_config_key.sh core.dynatrace_tenant_address)"
if [[ "$TENANT_ADDRESS" == *".apps.dynatrace.com"* ]]; then
    # Replace .apps.dynatrace.com with .live.dynatrace.com in the config file
    FIXED_TENANT_ADDRESS="${TENANT_ADDRESS//.apps.dynatrace.com/.live.dynatrace.com}"

    # Update the JSON config file
    jq --arg old_val "$TENANT_ADDRESS" --arg new_val "$FIXED_TENANT_ADDRESS" \
        'map(if .PATH == "core.dynatrace_tenant_address" then .VALUE = $new_val else . end)' \
        "$BUILD_CONFIG_FILE" > "${BUILD_CONFIG_FILE}.tmp" && mv "${BUILD_CONFIG_FILE}.tmp" "$BUILD_CONFIG_FILE"

    cat <<-EOH

	╔══════════════════════════════════════════════════════════════════════════════════╗
	║                                   ⚠️  WARNING  ⚠️                                  ║
	╠══════════════════════════════════════════════════════════════════════════════════╣
	║                                                                                  ║
	║  The dynatrace_tenant_address uses incorrect domain for API:                     ║
	║  .apps.dynatrace.com                                                             ║
	║                                                                                  ║
	║  Current value: $TENANT_ADDRESS                                      ║
	║                                                                                  ║
	║  This will be automatically replaced with: $FIXED_TENANT_ADDRESS           ║
	║                                                                                  ║
	╚══════════════════════════════════════════════════════════════════════════════════╝

	EOH
    sleep 5
fi

DEPLOYMENT_ENV="$($CWD/get_config_key.sh core.deployment_environment)"
CONNECTION_ENV="${DEPLOYMENT_ENV,,}" # convert to lower case
NOW_TS=$(date '+%Y%m%d-%H%M%S')

if $IS_MANUAL; then
    if [ -n "$OUTPUT_FILE" ]; then
        INSTALL_SCRIPT_SQL="$OUTPUT_FILE"
    else
        INSTALL_SCRIPT_SQL="dsoa-deploy-script-${DEPLOYMENT_ENV}-${NOW_TS}.sql"
    fi
else
    INSTALL_SCRIPT_SQL=$(mktemp -p build)
    # clean up this way, because rm did not always work
    # shellcheck disable=SC2064
    trap " rm -f ${INSTALL_SCRIPT_SQL} " EXIT
fi

# Early check: build directory must exist for SQL-based scopes
if [[ "$SCOPE" != "dt_assets" && "$SCOPE" != "apikey" ]]; then
    if [[ ! -d "build" ]]; then
        echo "" >&2
        echo "ERROR: Build artifacts are missing. Run the following command first:" >&2
        echo "       ./scripts/dev/build.sh" >&2
        echo "" >&2
        exit 1
    fi
fi

# preparing one big deployment script
$CWD/prepare_deploy_script.sh "${INSTALL_SCRIPT_SQL}" "${ENV}" "${SCOPE}" "${FROM_VERSION}" "${IS_MANUAL}" "${OPTIONS_STR}"
if [ $? -ne 0 ]; then
    echo "ERROR: Deploy preparation failed"
    exit 1
fi

if [ -s "$INSTALL_SCRIPT_SQL" ] && ! $IS_MANUAL; then

    SNOWFLAKE_ACCOUNT_NAME="$($CWD/get_config_key.sh core.snowflake.account_name)"

    INSTALL_SCRIPT_LOG="dsoa-deploy-log-$DEPLOYMENT_ENV-${NOW_TS}.sql"
    #%DEV:
    mkdir -p .logs 2>/dev/null
    INSTALL_SCRIPT_LOG=".logs/$INSTALL_SCRIPT_LOG"
    #%:DEV
    echo -e "\n\n--------\n"
    cat "$INSTALL_SCRIPT_SQL"
    echo -e "\n--------\n\n"

    echo -e "Deploying to Snowflake with the snow_agent_$CONNECTION_ENV connection profile and as the $DEPLOYMENT_ENV deployment environment\n"

    if ! $IS_MANUAL && ! has_option "skip_confirm" && [ -t 0 ]; then
        read -p "Press Enter if you wish to continue deployment with script above or Ctrl+C to exit" </dev/tty
    fi

    if ! has_option "no_dep"; then
        if ! $CWD/send_bizevent.sh "${SCOPE}" "STARTED" "${DEPLOYMENT_ID}"; then
            show_bizevent_warning "STARTED"
        fi
    fi

    # When SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER env vars are both set, use temporary-connection
    # (e.g. CI/CD environments with key-pair auth). Otherwise use named connection profile.
    if [[ -n "${SNOWFLAKE_ACCOUNT:-}" && -n "${SNOWFLAKE_USER:-}" ]]; then
        pushd build || exit 1
        snow sql --temporary-connection \
            --account "${SNOWFLAKE_ACCOUNT}" \
            --user "${SNOWFLAKE_USER}" \
            --filename "$(basename "${INSTALL_SCRIPT_SQL}")"
        popd || exit 1
    else
        #%DEV:
        pushd build || exit 1
        snow sql --connection "snow_agent_$CONNECTION_ENV" \
            --filename "$(basename "${INSTALL_SCRIPT_SQL}")"
        popd || exit 1
        #%:DEV
    fi

    cat "$INSTALL_SCRIPT_SQL" >>"$INSTALL_SCRIPT_LOG"

    rm ${INSTALL_SCRIPT_SQL}

elif $IS_MANUAL; then
    echo "Skipping automated deployment"
    echo "Deployment script generated at: ${INSTALL_SCRIPT_SQL}"
else
    echo "No scripts matching requested deploy filter: $SCOPE"
fi

if ! has_option "no_dep"; then
    if ! $CWD/send_bizevent.sh "${SCOPE}" "FINISHED" "${DEPLOYMENT_ID}"; then
        show_bizevent_warning "FINISHED"
    fi
fi

# Dynatrace asset deployment (dashboards + workflows) via dtctl.
# Triggered only when scope explicitly includes "dt_assets" — never part of "all"
# since dtctl is an optional dependency.
# Use exact token matching (split on commas) to avoid false positives like "foo_dt_assets_bar".
_has_dt_assets_scope=false
IFS=',' read -ra _scope_tokens <<< "$SCOPE"
for _token in "${_scope_tokens[@]}"; do
    _token=$(echo "$_token" | xargs)
    if [[ "$_token" == "dt_assets" ]]; then
        _has_dt_assets_scope=true
        break
    fi
done
if $_has_dt_assets_scope; then
    echo ""
    echo "Deploying Dynatrace assets (dashboards and workflows) via dtctl..."
    DRY_RUN_FLAG=""
    if has_option "dry_run"; then
        DRY_RUN_FLAG="--dry-run"
    fi
    # shellcheck disable=SC2086
    "$CWD/deploy_dt_assets.sh" --scope=all --env="${DEPLOYMENT_ENV}" $DRY_RUN_FLAG
fi
