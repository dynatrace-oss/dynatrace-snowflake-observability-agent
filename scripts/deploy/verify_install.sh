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
# Verify DSOA installation completeness — Phase A (Snowflake), B (Dynatrace), C (report)
# Called by: deploy.sh --scope=verify
# Usage:     verify_install.sh <ENV>
# Output:    JSON report on stdout; human-readable summary on stderr
# Exit:      0 = PASS or WARN-only; 1 = any FAIL

CWD=$(dirname "$0")
ENV="${1:-}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
CHECKS=()
OVERALL_STATUS="PASS"
INSTALLED_VERSION="unknown"

# ---- Config ----------------------------------------------------------------

DB_NAME="$("$CWD/get_config_key.sh" core.snowflake.database.name 2>/dev/null)"
if [[ -z "$DB_NAME" || "$DB_NAME" == "null" || "$DB_NAME" == "-" ]]; then
    TAG="$("$CWD/get_config_key.sh" core.tag 2>/dev/null)"
    if [[ -n "$TAG" && "$TAG" != "null" && "$TAG" != "-" ]]; then
        DB_NAME="DTAGENT_${TAG}_DB"
    else
        DB_NAME="DTAGENT_DB"
    fi
fi

DEPLOYMENT_ENV="$("$CWD/get_config_key.sh" core.deployment_environment 2>/dev/null)"
CONNECTION_ENV="${DEPLOYMENT_ENV,,}"
DT_ADDRESS="$("$CWD/get_config_key.sh" core.dynatrace_tenant_address 2>/dev/null)"

# ---- Tool check ------------------------------------------------------------

if ! command -v snow &>/dev/null; then
    echo "ERROR: Snowflake CLI (snow) not found. Run: ./setup.sh ${ENV}" >&2
    exit 1
fi
if ! command -v jq &>/dev/null; then
    echo "ERROR: jq not found. Run: ./setup.sh ${ENV}" >&2
    exit 1
fi

# ---- Snowflake connection args ---------------------------------------------

if [[ -n "${SNOWFLAKE_ACCOUNT:-}" && -n "${SNOWFLAKE_USER:-}" ]]; then
    SNOW_ARGS=(--temporary-connection --account "$SNOWFLAKE_ACCOUNT" --user "$SNOWFLAKE_USER")
else
    SNOW_ARGS=(--connection "snow_agent_${CONNECTION_ENV}")
fi

# ---- Helpers ---------------------------------------------------------------

run_sf_query() {
    snow sql "${SNOW_ARGS[@]}" -q "$1" --format=json 2>/dev/null || echo "[]"
}

add_check() {
    local name="$1" status="$2" details="$3"
    CHECKS+=("$(jq -cn --arg n "$name" --arg s "$status" --arg d "$details" '{name:$n,status:$s,details:$d}')")
    [[ "$status" == "FAIL" ]] && OVERALL_STATUS="FAIL"
    [[ "$status" == "WARN" && "$OVERALL_STATUS" == "PASS" ]] && OVERALL_STATUS="WARN"
    printf "  [%s] %s: %s\n" "$status" "$name" "$details" >&2
}

# ---- Header ----------------------------------------------------------------

printf "\n=== DSOA Installation Verification ===\n" >&2
printf "Environment : %s\n" "${DEPLOYMENT_ENV:-$ENV}" >&2
printf "Database    : %s\n" "$DB_NAME" >&2
printf "Timestamp   : %s\n\n" "$TIMESTAMP" >&2
printf "--- Snowflake checks ---\n" >&2

# ---- Check 1: database_exists ----------------------------------------------

DB_RESULT=$(run_sf_query "SELECT COUNT(*) AS C FROM INFORMATION_SCHEMA.DATABASES WHERE DATABASE_NAME = '${DB_NAME}'")
DB_COUNT=$(echo "$DB_RESULT" | jq -r '.[0].C // "0"' 2>/dev/null || echo "0")
if [[ "${DB_COUNT}" -ge 1 ]] 2>/dev/null; then
    add_check "database_exists" "PASS" "${DB_NAME} found"
else
    add_check "database_exists" "FAIL" "${DB_NAME} not found — check deployment or core.snowflake.database.name config"
fi

# ---- Check 2: stored_procedures --------------------------------------------

PROC_RESULT=$(run_sf_query "SELECT COUNT(*) AS C FROM ${DB_NAME}.INFORMATION_SCHEMA.PROCEDURES WHERE PROCEDURE_SCHEMA = 'AGENTS'")
PROC_COUNT=$(echo "$PROC_RESULT" | jq -r '.[0].C // "0"' 2>/dev/null || echo "0")
if [[ "${PROC_COUNT}" -ge 1 ]] 2>/dev/null; then
    add_check "stored_procedures" "PASS" "${PROC_COUNT} procedures in AGENTS schema"
else
    add_check "stored_procedures" "FAIL" "No stored procedures found in ${DB_NAME}.AGENTS — run setup+agents scopes"
fi

# ---- Check 3: tasks_running ------------------------------------------------

TASKS_RESULT=$(run_sf_query "SHOW TASKS IN SCHEMA ${DB_NAME}.APP")
TASK_STARTED=$(echo "$TASKS_RESULT" | jq '[.[] | select((.state // .STATE // "") | ascii_downcase == "started")] | length' 2>/dev/null || echo "0")
TASK_SUSPENDED=$(echo "$TASKS_RESULT" | jq '[.[] | select((.state // .STATE // "") | ascii_downcase == "suspended")] | length' 2>/dev/null || echo "0")
TASK_TOTAL=$(( TASK_STARTED + TASK_SUSPENDED ))
if [[ "$TASK_TOTAL" -eq 0 ]] 2>/dev/null; then
    add_check "tasks_running" "FAIL" "No tasks found in ${DB_NAME}.APP — run agents scope deployment"
elif [[ "$TASK_STARTED" -ge 1 ]] 2>/dev/null; then
    add_check "tasks_running" "PASS" "${TASK_STARTED} started, ${TASK_SUSPENDED} suspended"
else
    add_check "tasks_running" "WARN" "0 started, ${TASK_SUSPENDED} suspended — all plugins may be disabled"
fi

# ---- Check 4: config_populated ---------------------------------------------

CONFIG_RESULT=$(run_sf_query "SELECT COUNT(*) AS C FROM ${DB_NAME}.CONFIG.CONFIGURATIONS")
CONFIG_COUNT=$(echo "$CONFIG_RESULT" | jq -r '.[0].C // "0"' 2>/dev/null || echo "0")
if [[ "${CONFIG_COUNT}" -ge 1 ]] 2>/dev/null; then
    add_check "config_populated" "PASS" "${CONFIG_COUNT} configuration rows"
else
    add_check "config_populated" "FAIL" "CONFIG.CONFIGURATIONS is empty — run config scope deployment"
fi

# ---- Check 5: installed_version --------------------------------------------

VERSION_RESULT=$(run_sf_query "SELECT VALUE::STRING AS V FROM ${DB_NAME}.CONFIG.CONFIGURATIONS WHERE PATH = 'core.agent.version'")
INSTALLED_VERSION=$(echo "$VERSION_RESULT" | jq -r '.[0].V // "unknown"' 2>/dev/null || echo "unknown")
if [[ -n "$INSTALLED_VERSION" && "$INSTALLED_VERSION" != "unknown" && "$INSTALLED_VERSION" != "null" ]]; then
    add_check "installed_version" "PASS" "${INSTALLED_VERSION}"
else
    add_check "installed_version" "WARN" "unknown — version persisted after first run on 0.9.5+ (BDX-1417)"
    INSTALLED_VERSION="unknown"
fi

# ---- Phase B: Dynatrace checks ---------------------------------------------

printf "\n--- Dynatrace checks ---\n" >&2
DT_VERSION="unknown"

if [[ -z "${DTAGENT_TOKEN:-}" || ! "${DTAGENT_TOKEN}" =~ ^dt0c[0-9]{0,2}\.[a-zA-Z0-9]{24}\.[a-zA-Z0-9]{64}$ ]]; then
    add_check "dt_telemetry_received" "WARN" "DTAGENT_TOKEN not set or invalid — Dynatrace checks skipped"
    add_check "dt_version_match" "WARN" "DTAGENT_TOKEN not set or invalid — skipped"
else
    DT_QUERY="fetch bizevents | filter app.id == \"dynatrace.snowagent\" | filter matchesValue(\`deployment.environment\`, \"${DEPLOYMENT_ENV}\") | sort timestamp desc | limit 1 | fields timestamp, \`telemetry.exporter.version\`"
    DT_REQUEST=$(jq -cn --arg q "$DT_QUERY" '{"query":$q,"defaultTimeframeStart":"-2h"}')

    DT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
        "https://${DT_ADDRESS}/platform/storage/query/v1/query:execute" \
        -H "Authorization: Api-Token ${DTAGENT_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$DT_REQUEST" 2>/dev/null)
    DT_HTTP_CODE=$(echo "$DT_RESPONSE" | tail -1)
    DT_BODY=$(echo "$DT_RESPONSE" | head -n -1)

    if [[ "$DT_HTTP_CODE" == "403" || "$DT_HTTP_CODE" == "401" ]]; then
        add_check "dt_telemetry_received" "WARN" "Token lacks storage:events:read scope — add it to enable DT checks"
        add_check "dt_version_match" "WARN" "Token lacks storage:events:read scope — skipped"
    elif [[ "$DT_HTTP_CODE" != "200" ]]; then
        add_check "dt_telemetry_received" "FAIL" "Dynatrace API error (HTTP ${DT_HTTP_CODE:-unknown}) — check tenant address and token"
        add_check "dt_version_match" "FAIL" "Dynatrace API unavailable — skipped"
    else
        DT_TS=$(echo "$DT_BODY" | jq -r '.results[0].timestamp // empty' 2>/dev/null || echo "")
        DT_VERSION=$(echo "$DT_BODY" | jq -r '.results[0]["telemetry.exporter.version"] // "unknown"' 2>/dev/null || echo "unknown")

        if [[ -n "$DT_TS" ]]; then
            add_check "dt_telemetry_received" "PASS" "Latest bizevent: ${DT_TS}, version ${DT_VERSION}"
        else
            add_check "dt_telemetry_received" "FAIL" "No DSOA bizevents found for ${DEPLOYMENT_ENV} in the last 2h"
        fi

        if [[ "$INSTALLED_VERSION" == "unknown" || "$DT_VERSION" == "unknown" || -z "$DT_TS" ]]; then
            add_check "dt_version_match" "WARN" "Cannot compare — Snowflake=${INSTALLED_VERSION}, Dynatrace=${DT_VERSION}"
        elif [[ "$INSTALLED_VERSION" == "${DT_VERSION}"* || "$DT_VERSION" == "${INSTALLED_VERSION}"* ]]; then
            add_check "dt_version_match" "PASS" "Snowflake=${INSTALLED_VERSION}, Dynatrace=${DT_VERSION}"
        else
            add_check "dt_version_match" "WARN" "Version mismatch — Snowflake=${INSTALLED_VERSION}, Dynatrace=${DT_VERSION}"
        fi
    fi
fi

# ---- Phase C: JSON report + exit -------------------------------------------

printf "\nOverall: %s\n\n" "$OVERALL_STATUS" >&2

CHECKS_ARRAY=$(printf '%s\n' "${CHECKS[@]}" | jq -s '.')
jq -n \
    --arg ts "$TIMESTAMP" \
    --arg env "${DEPLOYMENT_ENV:-$ENV}" \
    --arg ver "$INSTALLED_VERSION" \
    --arg status "$OVERALL_STATUS" \
    --argjson checks "$CHECKS_ARRAY" \
    '{timestamp:$ts,environment:$env,installed_version:$ver,overall_status:$status,checks:$checks}'

[[ "$OVERALL_STATUS" == "FAIL" ]] && exit 1
exit 0
