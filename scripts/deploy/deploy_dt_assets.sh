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
# Deploy Dynatrace dashboards, workflows, and OpenPipeline rules using dtctl.
#
# Usage:
#   ./deploy_dt_assets.sh [--scope=SCOPE] [--dry-run] [--env=ENV]
#
# Args:
#   --scope   dashboards | workflows | openpipeline | all (default: all)
#   --dry-run preview changes without applying them
#   --env     optional environment label for logging only
#

set -euo pipefail

CWD="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$CWD/../.." && pwd)"

SCOPE="all"
DRY_RUN=false
ENV_LABEL=""

# ── Argument parsing ─────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        --scope=*)
            SCOPE="${1#*=}"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --env=*)
            ENV_LABEL="${1#*=}"
            shift
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
done

# Validate scope
case "$SCOPE" in
    dashboards|workflows|openpipeline|all) ;;
    *)
        echo "ERROR: Invalid scope '$SCOPE'. Must be one of: dashboards, workflows, openpipeline, all"
        exit 1
        ;;
esac

# ── Helper functions ─────────────────────────────────────────────────────────

log_info()    { echo "[INFO]  $*"; }
log_ok()      { echo "[OK]    $*"; }
log_warn()    { echo "[WARN]  $*"; }
log_error()   { echo "[ERROR] $*" >&2; }

dtctl_available() {
    command -v dtctl &>/dev/null
}

dtctl_authenticated() {
    dtctl doctor &>/dev/null 2>&1
}

# Convert an asset YAML to a dtctl-compatible JSON envelope and write to
# a temp file.  Prints the path of the temp file on success, exits non-zero
# on failure.
#
# Args:
#   $1 - source YAML file
#   $2 - asset type: "dashboard" | "workflow"
#   $3 - human-readable asset name
convert_yaml_to_dtctl_json() {
    local yaml_file="$1"
    local asset_type="$2"
    local asset_name="$3"
    local tmp_file
    tmp_file=$(mktemp /tmp/dtctl-asset-XXXXXX.json)

    # Convert YAML → raw JSON
    local raw_json
    if ! raw_json=$("$REPO_ROOT/scripts/tools/yaml-to-json.sh" "$yaml_file" 2>/dev/null); then
        log_error "YAML→JSON conversion failed for: $yaml_file"
        rm -f "$tmp_file"
        return 1
    fi

    # Validate JSON
    if ! echo "$raw_json" | jq . &>/dev/null; then
        log_error "Invalid JSON produced from: $yaml_file"
        rm -f "$tmp_file"
        return 1
    fi

    if [[ "$asset_type" == "workflow" ]]; then
        # Workflows: dtctl apply accepts the raw workflow JSON directly.
        # The workflow JSON uses "title" (not "name") as its display name.
        # No content-envelope wrapper is needed or accepted.
        echo "$raw_json" | jq . > "$tmp_file"
    else
        # Dashboards: dtctl apply requires a {id, name, type, content} envelope.
        # id/name are popped out of content so they appear only at the top level.
        local asset_id asset_display_name

        asset_id=$(echo "$raw_json" | jq -r '.id // empty' 2>/dev/null || true)
        asset_display_name=$(echo "$raw_json" | jq -r '.name // empty' 2>/dev/null || true)

        if [[ -z "$asset_display_name" ]]; then
            asset_display_name="$asset_name"
        fi

        if [[ -n "$asset_id" ]]; then
            jq --arg id   "$asset_id" \
               --arg name "$asset_display_name" \
               --arg type "$asset_type" \
               '{id: $id, name: $name, type: $type, content: (. | del(.id) | del(.name))}' \
               <<< "$raw_json" > "$tmp_file"
        else
            jq --arg name "$asset_display_name" \
               --arg type "$asset_type" \
               '{name: $name, type: $type, content: (. | del(.id) | del(.name))}' \
               <<< "$raw_json" > "$tmp_file"
        fi
    fi

    echo "$tmp_file"
}

# Deploy a single asset file with dtctl apply.
# Prints human-readable progress (including clickable URL) to stdout.
# Writes the assigned asset ID to $4 (a file path) if deployment succeeded
# and the caller wants to capture it.
# Returns 0 on success, 1 on failure.
#
# Args:
#   $1 - path to the JSON file to apply
#   $2 - human-readable asset name (used in log messages)
#   $3 - path to a temp file where the assigned ID will be written (optional)
deploy_asset() {
    local json_file="$1"
    local asset_name="$2"
    local id_file="${3:-}"
    local dry_run_flag=""
    if $DRY_RUN; then
        dry_run_flag="--dry-run"
    fi

    local dtctl_output
    # shellcheck disable=SC2086
    if ! dtctl_output=$(dtctl apply -f "$json_file" $dry_run_flag 2>&1); then
        log_error "dtctl apply failed for: ${asset_name}"
        echo "$dtctl_output" >&2
        return 1
    fi

    # Parse the JSON output from dtctl apply to extract id, url, and action.
    local asset_id asset_url asset_action
    asset_id=$(echo "$dtctl_output" | jq -r '.result.id // empty' 2>/dev/null || true)
    asset_url=$(echo "$dtctl_output" | jq -r '.result.url // empty' 2>/dev/null || true)
    asset_action=$(echo "$dtctl_output" | jq -r '.result.action // empty' 2>/dev/null || true)

    if $DRY_RUN; then
        # Dry-run output is plain text — extract URL line if present
        asset_url=$(echo "$dtctl_output" | grep -oE 'URL.*https://[^ ]+' | grep -oE 'https://[^ ]+' | head -1 || true)
        log_info "[dry-run] ${asset_name}"
        if [[ -n "$asset_url" ]]; then
            echo "[URL]   ${asset_url}"
        fi
    else
        local action_label="${asset_action:-deployed}"
        log_ok "${action_label^}: ${asset_name}"
        if [[ -n "$asset_url" ]]; then
            echo "[URL]   ${asset_url}"
        fi
    fi

    # Write the assigned ID to the temp file so the caller can read it
    if [[ -n "$id_file" && -n "$asset_id" ]]; then
        echo "$asset_id" > "$id_file"
    fi
    return 0
}

# Deploy all assets of a given type.
# Prints per-asset success/failure and returns:
#   0 if all assets deployed successfully
#   1 if any asset failed (but continues processing remaining assets)
#
# Args:
#   $1 - asset_type: "dashboard" | "workflow"
#   $2 - source directory (e.g. docs/dashboards)
#   $3 - name comment prefix in YAML (e.g. "# DASHBOARD:")
deploy_assets_of_type() {
    local asset_type="$1"
    local source_dir="$2"
    local name_comment_prefix="$3"

    local success_count=0
    local failure_count=0

    if [[ ! -d "$source_dir" ]]; then
        log_warn "Directory not found, skipping ${asset_type}s: $source_dir"
        return 0
    fi

    # Find all YAML files one level deep (docs/dashboards/<name>/<name>.yml)
    local yaml_files=()
    while IFS= read -r -d '' f; do
        yaml_files+=("$f")
    done < <(find "$source_dir" -mindepth 2 -maxdepth 2 -name "*.yml" -print0 2>/dev/null | sort -z)

    if [[ ${#yaml_files[@]} -eq 0 ]]; then
        log_warn "No YAML files found in $source_dir"
        return 0
    fi

    log_info "Deploying ${#yaml_files[@]} ${asset_type}(s) from $source_dir"

    for yaml_file in "${yaml_files[@]}"; do
        # Extract the human-readable name from the embedded comment
        local asset_name
        asset_name=$(grep "^${name_comment_prefix}" "$yaml_file" | head -1 | sed "s|^${name_comment_prefix} *||" || true)

        if [[ -z "$asset_name" ]]; then
            # Fall back to directory name, capitalized
            asset_name=$(basename "$(dirname "$yaml_file")")
        fi

        log_info "Processing ${asset_type}: ${asset_name} (${yaml_file})"

        # Convert YAML → dtctl JSON envelope
        local tmp_json
        if ! tmp_json=$(convert_yaml_to_dtctl_json "$yaml_file" "$asset_type" "$asset_name"); then
            log_error "Skipping ${asset_name}: conversion failed"
            (( failure_count++ )) || true
            continue
        fi

        # Deploy
        local id_file
        id_file=$(mktemp /tmp/dtctl-id-XXXXXX.txt)
        if deploy_asset "$tmp_json" "$asset_name" "$id_file"; then
            (( success_count++ )) || true

            # If the YAML had no id, dtctl assigned one — save it back to the YAML
            # so future runs update rather than create a duplicate.
            if ! $DRY_RUN; then
                local assigned_id yaml_id_count
                assigned_id=$(cat "$id_file" 2>/dev/null || true)
                yaml_id_count=$(grep -c "^id:" "$yaml_file" 2>/dev/null) || yaml_id_count=0

                if [[ -n "$assigned_id" ]] && (( yaml_id_count == 0 )); then
                    # Insert id: <uuid> after the last contiguous header comment block
                    local tmp_yaml
                    tmp_yaml=$(mktemp /tmp/dtctl-yaml-XXXXXX.yml)
                    awk -v id="$assigned_id" '
                        !inserted && /^[^#]/ { print "id: " id; inserted=1 }
                        { print }
                    ' "$yaml_file" > "$tmp_yaml"
                    mv "$tmp_yaml" "$yaml_file"
                    log_info "  Saved assigned ID to YAML: ${assigned_id}"
                fi
            fi
        else
            log_error "Failed to deploy ${asset_type}: ${asset_name}"
            (( failure_count++ )) || true
        fi
        rm -f "$id_file"

        rm -f "$tmp_json"
    done

    echo ""
    log_info "${asset_type^} deployment summary: ${success_count} succeeded, ${failure_count} failed"

    if [[ $failure_count -gt 0 ]]; then
        return 1
    fi
    return 0
}

# Deploy all OpenPipeline settings files.
# OpenPipeline objects are Settings 2.0 resources (schema builtin:openpipeline.logs.pipelines).
# dtctl apply accepts YAML natively — no conversion or envelope wrapping required.
#
# Returns:
#   0 if all rules deployed successfully
#   1 if any rule failed (continues processing remaining rules)
deploy_openpipeline_rules() {
    local source_dir="$REPO_ROOT/docs/openpipeline"
    local name_comment_prefix="# OPENPIPELINE:"
    local asset_type="openpipeline"

    local success_count=0
    local failure_count=0

    if [[ ! -d "$source_dir" ]]; then
        log_warn "Directory not found, skipping ${asset_type} rules: $source_dir"
        return 0
    fi

    # Find all YAML files one level deep (docs/openpipeline/<name>/<name>.yml)
    local yaml_files=()
    while IFS= read -r -d '' f; do
        yaml_files+=("$f")
    done < <(find "$source_dir" -mindepth 2 -maxdepth 2 -name "*.yml" -print0 2>/dev/null | sort -z)

    if [[ ${#yaml_files[@]} -eq 0 ]]; then
        log_warn "No YAML files found in $source_dir"
        return 0
    fi

    log_info "Deploying ${#yaml_files[@]} ${asset_type} rule(s) from $source_dir"

    for yaml_file in "${yaml_files[@]}"; do
        # Extract the human-readable name from the embedded comment
        local asset_name
        asset_name=$(grep "^${name_comment_prefix}" "$yaml_file" | head -1 | sed "s|^${name_comment_prefix} *||" || true)

        if [[ -z "$asset_name" ]]; then
            asset_name=$(basename "$(dirname "$yaml_file")")
        fi

        log_info "Processing ${asset_type}: ${asset_name} (${yaml_file})"

        # OpenPipeline settings objects are applied as-is — dtctl apply accepts YAML natively.
        # No conversion or envelope wrapping needed (these are Settings 2.0 objects with objectid).
        local dry_run_flag=""
        if $DRY_RUN; then dry_run_flag="--dry-run"; fi

        local dtctl_output
        # shellcheck disable=SC2086
        if ! dtctl_output=$(dtctl apply -f "$yaml_file" $dry_run_flag 2>&1); then
            log_error "dtctl apply failed for: ${asset_name}"
            echo "$dtctl_output" >&2
            (( failure_count++ )) || true
        else
            local action_label
            action_label=$(echo "$dtctl_output" | jq -r '.result.action // empty' 2>/dev/null || true)
            action_label="${action_label:-deployed}"
            if $DRY_RUN; then
                log_info "[dry-run] ${asset_name}"
            else
                log_ok "${action_label^}: ${asset_name}"
            fi
            (( success_count++ )) || true
        fi
    done

    echo ""
    log_info "${asset_type^} deployment summary: ${success_count} succeeded, ${failure_count} failed"

    if [[ $failure_count -gt 0 ]]; then
        return 1
    fi
    return 0
}

# ── Pre-flight checks ────────────────────────────────────────────────────────

if [[ -n "$ENV_LABEL" ]]; then
    log_info "Deploying Dynatrace assets to environment: ${ENV_LABEL}"
fi

if $DRY_RUN; then
    log_info "Dry-run mode enabled — no changes will be applied"
fi

log_info "Scope: ${SCOPE}"

# Check required tools
if ! command -v jq &>/dev/null; then
    cat <<-'EOF'

	jq is not installed or not on PATH.
	jq is required to build the dtctl JSON envelope.
	To install jq, run:

	  brew install jq       # macOS
	  apt-get install jq    # Debian / Ubuntu
	  yum install jq        # RHEL / CentOS

	EOF
    exit 1
fi

YAML_TO_JSON_SCRIPT="$REPO_ROOT/scripts/tools/yaml-to-json.sh"
if [[ ! -x "$YAML_TO_JSON_SCRIPT" ]]; then
    cat <<-EOF

	Required script not found or not executable: $YAML_TO_JSON_SCRIPT
	This script is needed to convert YAML dashboard/workflow sources to JSON.
	Please ensure you are running from the repository root and the script exists.

	EOF
    exit 1
fi


# Check dtctl availability
if ! dtctl_available; then
    cat <<-'EOF'

	dtctl is not installed or not on PATH.
	To install dtctl, run:

	  brew install dynatrace-oss/tap/dtctl

	Then authenticate:

	  dtctl auth login

	For more details, see: https://github.com/dynatrace-oss/dtctl

	EOF
    exit 0
fi

# Check dtctl authentication
if ! dtctl_authenticated; then
    cat <<-'EOF'

	dtctl is installed but authentication failed.
	Please authenticate before deploying:

	  dtctl auth login

	Or set the DTCTL_TOKEN environment variable with a valid platform token.
	For more details, see: https://github.com/dynatrace-oss/dtctl

	EOF
    exit 1
fi

# ── Deployment ───────────────────────────────────────────────────────────────

OVERALL_STATUS=0

if [[ "$SCOPE" == "dashboards" || "$SCOPE" == "all" ]]; then
    deploy_assets_of_type "dashboard" "$REPO_ROOT/docs/dashboards" "# DASHBOARD:" || OVERALL_STATUS=1
fi

if [[ "$SCOPE" == "workflows" || "$SCOPE" == "all" ]]; then
    deploy_assets_of_type "workflow" "$REPO_ROOT/docs/workflows" "# WORKFLOW:" || OVERALL_STATUS=1
fi

if [[ "$SCOPE" == "openpipeline" || "$SCOPE" == "all" ]]; then
    deploy_openpipeline_rules || OVERALL_STATUS=1
fi

# ── Final summary ────────────────────────────────────────────────────────────

echo ""
if [[ $OVERALL_STATUS -eq 0 ]]; then
    if $DRY_RUN; then
        log_info "Dry-run complete — no assets were modified"
    else
        log_ok "All Dynatrace assets deployed successfully"
    fi
else
    log_error "One or more Dynatrace assets failed to deploy — review errors above"
fi

exit $OVERALL_STATUS
