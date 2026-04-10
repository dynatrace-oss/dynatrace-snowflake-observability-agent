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
# Deploy the DSOA QA test notebook to a Dynatrace tenant.
#
# Reads the current and previous version tags, locates the matching conf/ files,
# derives the Dynatrace tenant URL, converts the YAML notebook template to JSON,
# and deploys it via dtctl apply.
#
# After a successful deploy the notebook ID is written back into the YAML template
# as a comment so future runs update the same notebook rather than creating a new one.
#
# Args:
#   --curr-version=X.Y.Z   Current DSOA version (default: read from src/dtagent/version.py)
#   --prev-version=X.Y.Z   Previous DSOA version (default: X.Y.(Z-1); "none" to skip check)
#   --dry-run               Print what would be done without deploying
#   --help                  Show this help and exit
#
# Examples:
#   ./scripts/test/deploy_test_notebook.sh
#   ./scripts/test/deploy_test_notebook.sh --curr-version=0.9.4 --prev-version=0.9.3
#   ./scripts/test/deploy_test_notebook.sh --curr-version=0.9.4 --prev-version=0.9.3.1
#   ./scripts/test/deploy_test_notebook.sh --curr-version=0.9.4 --prev-version=none
#   ./scripts/test/deploy_test_notebook.sh --dry-run

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NOTEBOOK_YAML="${REPO_ROOT}/test/qa/test-suite/test-suite.yml"
VERSION_FILE="${REPO_ROOT}/src/dtagent/version.py"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log_info()  { echo "[INFO]  $*"; }
log_warn()  { echo "[WARN]  $*" >&2; }
log_error() { echo "[ERROR] $*" >&2; }

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Deploy the DSOA QA test notebook to a Dynatrace tenant.

Options:
  --curr-version=X.Y.Z   Current DSOA version (default: read from src/dtagent/version.py)
  --prev-version=X.Y.Z   Previous DSOA version (default: X.Y.(Z-1); "none" skips the check)
  --dry-run               Print what would be done — no dtctl apply
  --help                  Show this help and exit

Version-to-tag mapping:
  The 3-digit tag is derived as: printf "%03d" \$((minor * 10 + patch))
  Examples:  0.9.4  -> 094   0.9.3.1 -> 093   0.9.10 -> 100   0.8.3 -> 083

Config files required:
  conf/config-dev-{CURR_TAG}.yml   — must exist (fatal if missing)
  conf/config-dev-{PREV_TAG}.yml   — should exist (warning only if missing)

EOF
}

# Derive 3-digit numeric tag from a version string X.Y.Z[.W]
# Uses only the first three dot-separated parts; ignores any hotfix suffix.
version_to_tag() {
    local version="$1"
    local minor patch
    minor=$(echo "$version" | cut -d. -f2)
    patch=$(echo "$version" | cut -d. -f3)
    printf "%03d" $(( minor * 10 + patch ))
}

# Compute default previous version: decrement patch of X.Y.Z (ignores hotfix suffix)
auto_prev_version() {
    local curr="$1"
    local major minor patch
    major=$(echo "$curr" | cut -d. -f1)
    minor=$(echo "$curr" | cut -d. -f2)
    patch=$(echo "$curr" | cut -d. -f3)
    if [[ "$patch" -gt 0 ]]; then
        echo "${major}.${minor}.$((patch - 1))"
    else
        echo ""
    fi
}

# Convert a bare dynatrace_tenant_address (e.g. aym57094.sprint.dynatracelabs.com)
# into the full apps URL used by the Dynatrace UI and dtctl contexts.
tenant_addr_to_apps_url() {
    local addr="$1"
    local tenant_id="${addr%%.*}"
    local remainder="${addr#*.}"
    # Replace .dynatracelabs.com / .live.dynatrace.com suffix with .apps equivalent
    case "$remainder" in
        live.dynatrace.com | *.live.dynatrace.com)
            # abc12345.live.dynatrace.com -> https://abc12345.apps.dynatrace.com
            echo "https://${tenant_id}.apps.dynatrace.com"
            ;;
        *.sprint.dynatracelabs.com | *.dev.dynatracelabs.com | *.dynatracelabs.com)
            # Sprint/dev lab environments
            local sub="${remainder%.dynatracelabs.com}"
            echo "https://${tenant_id}.${sub}.apps.dynatracelabs.com"
            ;;
        *)
            # Fallback: assume it's already a usable hostname
            echo "https://${addr}"
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

CURR_VERSION=""
PREV_VERSION=""
DRY_RUN=false

for arg in "$@"; do
    case "$arg" in
        --curr-version=*)   CURR_VERSION="${arg#*=}" ;;
        --prev-version=*)   PREV_VERSION="${arg#*=}" ;;
        --dry-run)          DRY_RUN=true ;;
        --help|-h)          usage; exit 0 ;;
        *)
            log_error "Unknown argument: $arg"
            usage
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Resolve current version
# ---------------------------------------------------------------------------

if [[ -z "$CURR_VERSION" ]]; then
    if [[ ! -f "$VERSION_FILE" ]]; then
        log_error "Cannot auto-detect version: $VERSION_FILE not found."
        log_error "Pass --curr-version=X.Y.Z explicitly."
        exit 1
    fi
    CURR_VERSION=$(grep '^VERSION' "$VERSION_FILE" | head -1 | cut -d'"' -f2)
    if [[ -z "$CURR_VERSION" ]]; then
        log_error "Could not parse VERSION from $VERSION_FILE."
        exit 1
    fi
    log_info "Auto-detected current version: ${CURR_VERSION}"
else
    log_info "Using specified current version: ${CURR_VERSION}"
fi

CURR_TAG=$(version_to_tag "$CURR_VERSION")
log_info "Current version tag: ${CURR_TAG}  (env: DEV-${CURR_TAG})"

# ---------------------------------------------------------------------------
# Resolve previous version
# ---------------------------------------------------------------------------

if [[ "$PREV_VERSION" == "none" ]]; then
    log_info "Previous version check skipped (--prev-version=none)."
    PREV_TAG=""
else
    if [[ -z "$PREV_VERSION" ]]; then
        PREV_VERSION=$(auto_prev_version "$CURR_VERSION")
        if [[ -z "$PREV_VERSION" ]]; then
            log_warn "Cannot auto-detect previous version (patch is 0 in ${CURR_VERSION})."
            log_warn "Pass --prev-version=X.Y.Z or --prev-version=none to suppress this warning."
            PREV_TAG=""
        else
            log_info "Auto-detected previous version: ${PREV_VERSION}"
            PREV_TAG=$(version_to_tag "$PREV_VERSION")
        fi
    else
        log_info "Using specified previous version: ${PREV_VERSION}"
        PREV_TAG=$(version_to_tag "$PREV_VERSION")
    fi
    if [[ -n "$PREV_TAG" ]]; then
        log_info "Previous version tag: ${PREV_TAG}  (env: DEV-${PREV_TAG})"
    fi
fi

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

preflight_ok=true

check_command() {
    local cmd="$1" install_hint="$2"
    if ! command -v "$cmd" &>/dev/null; then
        log_error "'${cmd}' is not installed or not on PATH."
        if [[ -n "$install_hint" ]]; then
            log_error "  Install hint: ${install_hint}"
        fi
        preflight_ok=false
    fi
}

check_command "jq"  "brew install jq"
check_command "yq"  "brew install yq"
check_command "dtctl" "brew install dynatrace-oss/tap/dtctl  (then: dtctl auth login)"

if [[ "$preflight_ok" == "false" ]]; then
    exit 1
fi

# dtctl authenticated?
if ! dtctl doctor &>/dev/null 2>&1; then
    log_error "dtctl is not authenticated. Run: dtctl auth login"
    exit 1
fi

# Notebook YAML
if [[ ! -f "$NOTEBOOK_YAML" ]]; then
    log_error "Notebook YAML not found: ${NOTEBOOK_YAML}"
    exit 1
fi

# Current config
CURR_CONF="${REPO_ROOT}/conf/config-dev-${CURR_TAG}.yml"
if [[ ! -f "$CURR_CONF" ]]; then
    log_error "Current version config not found: ${CURR_CONF}"
    log_error "Create conf/config-dev-${CURR_TAG}.yml before running this script."
    exit 1
fi

# Previous config (warning only)
if [[ -n "$PREV_TAG" ]]; then
    PREV_CONF="${REPO_ROOT}/conf/config-dev-${PREV_TAG}.yml"
    if [[ ! -f "$PREV_CONF" ]]; then
        log_warn "Previous version config not found: ${PREV_CONF}"
        log_warn "Cross-version comparison tiles in the notebook will show only the current environment."
        log_warn "Create conf/config-dev-${PREV_TAG}.yml and deploy that environment to enable comparisons."
    fi
fi

# ---------------------------------------------------------------------------
# Read tenant info from config
# ---------------------------------------------------------------------------

TENANT_ADDR=$(yq '.core.dynatrace_tenant_address' "$CURR_CONF")
DEPLOY_ENV=$(yq '.core.deployment_environment' "$CURR_CONF")

if [[ -z "$TENANT_ADDR" || "$TENANT_ADDR" == "null" ]]; then
    log_error "Could not read core.dynatrace_tenant_address from ${CURR_CONF}"
    exit 1
fi
if [[ -z "$DEPLOY_ENV" || "$DEPLOY_ENV" == "null" ]]; then
    log_error "Could not read core.deployment_environment from ${CURR_CONF}"
    exit 1
fi

TENANT_APPS_URL=$(tenant_addr_to_apps_url "$TENANT_ADDR")
TENANT_ID="${TENANT_ADDR%%.*}"

log_info "Tenant address:  ${TENANT_ADDR}"
log_info "Apps URL:        ${TENANT_APPS_URL}"
log_info "Deploy env:      ${DEPLOY_ENV}"

# ---------------------------------------------------------------------------
# Find matching dtctl context
# ---------------------------------------------------------------------------

DTCTL_CONTEXT=""
CONTEXTS_JSON=$(dtctl ctx 2>/dev/null || true)

if [[ -n "$CONTEXTS_JSON" ]]; then
    DTCTL_CONTEXT=$(echo "$CONTEXTS_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tenant_id = '${TENANT_ID}'
for ctx in d.get('result', []):
    env_url = ctx.get('Environment', '')
    name = ctx.get('Name', '')
    if tenant_id in env_url:
        print(name)
        break
" 2>/dev/null || true)
fi

if [[ -n "$DTCTL_CONTEXT" ]]; then
    log_info "Matched dtctl context: ${DTCTL_CONTEXT}"
    DTCTL_CONTEXT_FLAG="--context=${DTCTL_CONTEXT}"
else
    log_warn "No dtctl context matched tenant ID '${TENANT_ID}'."
    log_warn "Proceeding with the current active context."
    DTCTL_CONTEXT_FLAG=""
fi

# ---------------------------------------------------------------------------
# Prepare notebook JSON
# ---------------------------------------------------------------------------

NOTEBOOK_NAME="DSOA Test Suite (${DEPLOY_ENV}_DEV)"
TMP_JSON=$(mktemp /tmp/dsoa-test-suite-XXXXXX.json)
trap 'rm -f "$TMP_JSON"' EXIT

log_info "Converting notebook YAML to JSON..."

# Convert YAML to JSON, then inject the notebook name.
# The 'name' field is not stored in the YAML template (it's set at deploy time).
# The notebook content fields (version, defaultTimeframe, sections...) go directly
# into the top-level object — dtctl apply for notebooks does not need a content envelope.
yq -o json "$NOTEBOOK_YAML" \
    | jq --arg name "$NOTEBOOK_NAME" '. + {name: $name}' \
    > "$TMP_JSON"

# Strip comment-only keys that yq may have emitted (lines starting with '#' in YAML
# become null keys in some yq versions — clean them up just in case).
jq 'del(.["#"])' "$TMP_JSON" > "${TMP_JSON}.clean" && mv "${TMP_JSON}.clean" "$TMP_JSON"

log_info "Notebook name:   ${NOTEBOOK_NAME}"

# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == "true" ]]; then
    log_info "--- DRY RUN --- (no dtctl apply will be executed)"
    log_info "Would run:"
    echo ""
    echo "  dtctl apply -f ${TMP_JSON} ${DTCTL_CONTEXT_FLAG} -o json"
    echo ""
    log_info "Notebook JSON preview (first 40 lines):"
    head -40 "$TMP_JSON"
    exit 0
fi

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

log_info "Deploying notebook via dtctl apply..."

DTCTL_OUTPUT=""
# shellcheck disable=SC2086
if ! DTCTL_OUTPUT=$(dtctl apply -f "$TMP_JSON" $DTCTL_CONTEXT_FLAG -o json 2>&1); then
    log_error "dtctl apply failed:"
    echo "$DTCTL_OUTPUT" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Extract notebook ID and URL
# ---------------------------------------------------------------------------

NOTEBOOK_ID=""
NOTEBOOK_URL=""

# Try to parse structured JSON output from dtctl
NOTEBOOK_ID=$(echo "$DTCTL_OUTPUT" | python3 -c "
import sys, json
raw = sys.stdin.read().strip()
# dtctl may emit one JSON object per line, or a wrapper object
for line in raw.splitlines():
    try:
        d = json.loads(line)
        # Handle dtctl --agent envelope: {result: {id: ...}}
        nid = d.get('result', {}).get('id') or d.get('id') or ''
        if nid:
            print(nid)
            break
    except json.JSONDecodeError:
        pass
" 2>/dev/null || true)

if [[ -z "$NOTEBOOK_ID" ]]; then
    # Fallback: grep for a UUID-shaped string in the output
    NOTEBOOK_ID=$(echo "$DTCTL_OUTPUT" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1 || true)
fi

if [[ -n "$NOTEBOOK_ID" ]]; then
    NOTEBOOK_URL="${TENANT_APPS_URL}/ui/document/${NOTEBOOK_ID}"
    echo ""
    log_info "Notebook deployed successfully."
    echo ""
    echo "  [ID]  ${NOTEBOOK_ID}"
    echo "  [URL] ${NOTEBOOK_URL}"
    echo ""
else
    log_warn "Could not extract notebook ID from dtctl output."
    log_warn "dtctl output was:"
    echo "$DTCTL_OUTPUT" >&2
fi

# ---------------------------------------------------------------------------
# Write ID back into the YAML template
# ---------------------------------------------------------------------------

if [[ -n "$NOTEBOOK_ID" ]]; then
    # Replace the placeholder "# id:" comment line with the actual ID
    # If it already has an ID from a previous run, update it.
    if grep -q '^# id:' "$NOTEBOOK_YAML"; then
        # Update existing ID comment
        sed -i '' "s|^# id:.*|# id: ${NOTEBOOK_ID}|" "$NOTEBOOK_YAML"
    else
        log_warn "Could not find '# id:' placeholder in ${NOTEBOOK_YAML}."
        log_warn "Notebook ID for future reference: ${NOTEBOOK_ID}"
    fi
    log_info "Notebook ID written back to: ${NOTEBOOK_YAML}"
fi
