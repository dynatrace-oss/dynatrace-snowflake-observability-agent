#!/usr/bin/env bash
#
# Manual QA script: verify that units sent via dt.meta.unit are recognized by Dynatrace.
#
# Ingests test/qa/fixtures/all_metrics_ingest_payload.txt (one data line + one
# #<metric> gauge dt.meta.unit="..." metadata line per metric defined across all
# instruments-def.yml files — see scripts/dev/gen_metric_fixture.py) into a live
# Dynatrace tenant, waits for propagation, then queries each metric's recognized
# unit back via the Grail Query API's ?enrich=metric-metadata parameter (run
# through scripts/test/query_metric_metadata.js via `dtctl exec function`) and
# compares it to the unit we sent.
#
# NOTE: neither `dtctl query`'s DQL "timeseries" JSON (only has records[].interval/
# timeframe) nor the classic Metrics API v2 metric descriptor (only echoes back the
# raw symbol we sent) expose what Dynatrace's unit system actually resolved a unit
# to (e.g. "MiBy" -> "MebiByte"). Only the Grail Query API's ?enrich=metric-metadata
# parameter does, and dtctl does not (yet) expose it as a flag — hence the ad-hoc
# `dtctl exec function` workaround, which runs in the App Engine sandbox with
# automatic platform (OAuth) auth, no token handling required for this step.
#
# The target tenant is whichever one `dtctl` is currently authenticated against
# (`dtctl config current-context` / `dtctl doctor`) — there is no separate
# --tenant/--env selector, since ingesting to one tenant while dtctl points at
# another would silently produce bogus results. Run `dtctl auth login` first if
# you need to switch tenants.
#
# NOT part of CI. Requires a live tenant and an ingest-capable API token.
# Run manually during a QA pass (see .opencode/skills/qa-runner/SKILL.md).
#
# Usage:
#   dtctl auth login                       # make sure dtctl points at the target tenant
#   ./scripts/test/verify_metric_units.sh  # prompts for the token (input hidden) if
#                                           # DT_API_TOKEN is not already exported
#   export DT_API_TOKEN=dt0c01.XXXX.YYYY   # classic API token, scope: metrics.ingest
#   ./scripts/test/verify_metric_units.sh --sleep=60 --fixture=path/to/fixture.txt
#
# Prerequisites:
#   - dtctl on PATH and authenticated against the target tenant (`dtctl auth login`);
#     its OAuth session already covers the app-engine:functions:run scope needed
#     for the query-back step
#   - a classic API token with the "Ingest metrics" (metrics.ingest) scope, either
#     exported as DT_API_TOKEN or entered at the interactive prompt (needed only
#     for the ingest step)
#   - curl, jq on PATH
#
# The API token is NEVER read from a config file or hardcoded — it must come from
# the DT_API_TOKEN environment variable or the interactive prompt, and is never
# printed or logged.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FIXTURE="${REPO_ROOT}/test/qa/fixtures/all_metrics_ingest_payload.txt"
SLEEP_SECONDS=120
SKIP_INGEST=0

usage() {
    cat <<'EOF'
Usage: verify_metric_units.sh [options]

The target tenant is always dtctl's current context (dtctl config current-context /
dtctl doctor) — run 'dtctl auth login' first to switch tenants, there is no
--tenant/--env override.

Options:
  --fixture=<path>    Path to the ingest fixture (default: test/qa/fixtures/all_metrics_ingest_payload.txt)
  --sleep=<seconds>   Seconds to wait between ingest and query-back (default: 120)
  --skip-ingest       Skip Step 1 (ingest) and Step 2 (wait) — jump straight to Step 3
                      (query-back). Use this to re-run just the query-back step against
                      data already ingested by a previous run; no DT_API_TOKEN needed.
  -h, --help          Show this help.

Requires a classic API token (metrics.ingest scope) for the ingest step, either
exported as DT_API_TOKEN or entered at the interactive prompt this script shows if unset.
The query-back step uses `dtctl exec function` (dtctl's own OAuth session).
EOF
}

for arg in "$@"; do
    case "$arg" in
        --fixture=*) FIXTURE="${arg#--fixture=}" ;;
        --sleep=*) SLEEP_SECONDS="${arg#--sleep=}" ;;
        --skip-ingest) SKIP_INGEST=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown parameter: $arg" >&2; usage; exit 1 ;;
    esac
done

for tool in curl jq dtctl; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: required tool not on PATH: $tool" >&2
        exit 1
    fi
done

##region ── Derive the tenant from dtctl's active context ──────────────────

DTCTL_CONFIG_JSON="$(dtctl config view -o json 2>/dev/null)" || {
    echo "ERROR: 'dtctl config view' failed — is dtctl installed and configured?" >&2
    exit 1
}
CURRENT_CTX="$(echo "$DTCTL_CONFIG_JSON" | jq -r '.CurrentContext // empty')"
if [[ -z "$CURRENT_CTX" ]]; then
    echo "ERROR: dtctl has no active context. Run 'dtctl auth login' first." >&2
    exit 1
fi
ENVIRONMENT_URL="$(echo "$DTCTL_CONFIG_JSON" | jq -r --arg ctx "$CURRENT_CTX" \
    '.Contexts[] | select(.Name == $ctx) | .Context.Environment // empty')"
if [[ -z "$ENVIRONMENT_URL" ]]; then
    echo "ERROR: could not determine environment for dtctl context '$CURRENT_CTX'." >&2
    exit 1
fi
TENANT="${ENVIRONMENT_URL#https://}"
TENANT="${TENANT#http://}"
TENANT="${TENANT%/}"

# dtctl's Environment is the platform/UI domain (*.apps.*), but classic REST
# APIs like /api/v2/metrics/ingest live on a different domain — normalize the
# same way scripts/deploy/lib.sh's validate_dt_tenant does.
if [[ "$TENANT" == *".apps.dynatrace.com"* ]]; then
    TENANT="${TENANT//.apps.dynatrace.com/.live.dynatrace.com}"
elif [[ "$TENANT" == *".apps.dynatracelabs.com"* ]]; then
    TENANT="${TENANT//.apps.dynatracelabs.com/.dynatracelabs.com}"
fi

if ! dtctl doctor >/dev/null 2>&1; then
    echo "ERROR: dtctl is not authenticated against context '$CURRENT_CTX'. Run 'dtctl auth login'." >&2
    exit 1
fi

##endregion

if [[ "$SKIP_INGEST" -eq 0 && -z "${DT_API_TOKEN:-}" ]]; then
    if [[ -t 0 ]]; then
        read -rsp "Enter Dynatrace API token for ${TENANT} (metrics.ingest scope, input hidden): " DT_API_TOKEN
        echo
        export DT_API_TOKEN
    fi
    if [[ -z "${DT_API_TOKEN:-}" ]]; then
        echo "ERROR: no API token provided (set DT_API_TOKEN or enter it at the prompt)." >&2
        exit 1
    fi
fi

if [[ ! -f "$FIXTURE" ]]; then
    echo "ERROR: fixture not found: $FIXTURE (run 'python scripts/dev/gen_metric_fixture.py' first)" >&2
    exit 1
fi

echo "════════════════════════════════════════════════════════════════"
echo " Metric unit-recognition QA check"
echo " Tenant:  $TENANT"
echo " Fixture: $FIXTURE"
echo "════════════════════════════════════════════════════════════════"

##region ── Step 1: Ingest the fixture ──────────────────────────────────────

if [[ "$SKIP_INGEST" -eq 1 ]]; then
    echo ""
    echo "--- Step 1: Skipped (--skip-ingest) — assuming the fixture was already ingested."
else

echo ""
echo "--- Step 1: Ingesting fixture..."

ingest_fixture() {
    curl -sS -o /tmp/verify_metric_units_response.json -w "%{http_code}" \
        -X POST "https://${TENANT}/api/v2/metrics/ingest" \
        -H "Authorization: Api-Token ${DT_API_TOKEN}" \
        -H "Content-Type: text/plain; charset=utf-8" \
        --data-binary @"$FIXTURE"
}

HTTP_STATUS="$(ingest_fixture)"

TOKEN_RETRIES=0
while [[ "$HTTP_STATUS" == "401" && $TOKEN_RETRIES -lt 3 ]]; do
    echo "ERROR: ingest request failed (HTTP 401 — token authentication failed)." >&2
    cat /tmp/verify_metric_units_response.json >&2
    echo "" >&2
    if [[ ! -t 0 ]]; then
        echo "ERROR: not an interactive terminal, cannot prompt for a new token." >&2
        exit 1
    fi
    TOKEN_RETRIES=$((TOKEN_RETRIES + 1))
    read -rsp "Token rejected. Re-enter Dynatrace API token for ${TENANT} (metrics.ingest scope, input hidden): " DT_API_TOKEN
    echo
    export DT_API_TOKEN
    if [[ -z "$DT_API_TOKEN" ]]; then
        echo "ERROR: no token provided, aborting." >&2
        exit 1
    fi
    HTTP_STATUS="$(ingest_fixture)"
done

if [[ "$HTTP_STATUS" != "202" ]]; then
    echo "ERROR: ingest request failed (HTTP $HTTP_STATUS)" >&2
    cat /tmp/verify_metric_units_response.json >&2
    exit 1
fi

LINES_OK=$(jq -r '.linesOk // 0' /tmp/verify_metric_units_response.json)
LINES_INVALID=$(jq -r '.linesInvalid // 0' /tmp/verify_metric_units_response.json)
echo "  Ingest response: linesOk=$LINES_OK linesInvalid=$LINES_INVALID"
if [[ "$LINES_INVALID" != "0" ]]; then
    echo "  WARNING: some lines were rejected:"
    jq -r '.warnings // [] | .[]' /tmp/verify_metric_units_response.json
fi

fi

##endregion

##region ── Step 2: Wait for propagation ────────────────────────────────────

if [[ "$SKIP_INGEST" -eq 1 ]]; then
    echo ""
    echo "--- Step 2: Skipped (--skip-ingest)."
else
    echo ""
    echo "--- Step 2: Waiting ${SLEEP_SECONDS}s for metric metadata to propagate..."
    sleep "$SLEEP_SECONDS"
fi

##endregion

##region ── Step 3: Query each metric back and compare units ───────────────

echo ""
echo "--- Step 3: Querying recognized units via Grail's metric-metadata enrichment..."
echo ""
printf "%-55s %-15s %-20s %-6s\n" "METRIC" "SENT" "DYNATRACE" "RESULT"
printf "%-55s %-15s %-20s %-6s\n" "------" "----" "---------" "------"

PASS_COUNT=0
FAIL_COUNT=0
FAILURES=()

METADATA_SCRIPT="${REPO_ROOT}/scripts/test/query_metric_metadata.js"

# Extract metric names + expected units directly from the fixture's own
# metadata lines (avoids re-parsing instruments-def.yml in bash).
#
# NOTE: dtctl query's DQL "timeseries" output has no metadata.metrics[].unit
# field at all (verified empirically — its JSON only has records[].interval/
# timeframe), and the classic Metrics API v2 descriptor only echoes back the
# raw symbol we sent, not what Dynatrace's unit system actually resolved it
# to. The real recognition check requires the Grail Query API's
# ?enrich=metric-metadata parameter, which dtctl does not (yet) expose as a
# flag, so scripts/test/query_metric_metadata.js is run via
# `dtctl exec function` (App Engine sandbox, automatic platform auth — no
# token needed) to call it directly. Dynatrace returns the *canonical
# display name* (e.g. "MiBy" -> "MebiByte", "%" -> "Percent"), not the raw
# symbol, so PASS means "Dynatrace resolved some unit for this metric" —
# a human should still glance at the DYNATRACE column to sanity-check the
# resolved name actually matches the intended meaning of what was sent.
while IFS= read -r meta_line; do
    metric_name="${meta_line#\#}"
    metric_name="${metric_name%% *}"
    expected_unit="$(echo "$meta_line" | { grep -oE 'dt\.meta\.unit="[^"]*"' || true; } | sed -E 's/dt\.meta\.unit="([^"]*)"/\1/')"
    [[ -z "$expected_unit" ]] && continue

    exec_json="$(dtctl exec function -f "$METADATA_SCRIPT" \
        --payload "{\"metricKey\":\"${metric_name}\"}" -o json </dev/null \
        2>/tmp/verify_metric_units_query_err.txt || true)"
    dt_unit="$(echo "$exec_json" | jq -r '.result.unit // "NOT_FOUND"' 2>/dev/null || echo "NOT_FOUND")"

    if [[ "$dt_unit" != "NOT_FOUND" && "$dt_unit" != "null" ]]; then
        printf "%-55s %-15s %-20s %-6s\n" "$metric_name" "$expected_unit" "$dt_unit" "PASS"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        printf "%-55s %-15s %-20s %-6s\n" "$metric_name" "$expected_unit" "$dt_unit" "FAIL"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILURES+=("$metric_name: sent '$expected_unit', Dynatrace did not resolve a unit — $(cat /tmp/verify_metric_units_query_err.txt)")
    fi
done < <(grep '^#' "$FIXTURE")

##endregion

echo ""
echo "════════════════════════════════════════════════════════════════"
echo " Result: $PASS_COUNT passed, $FAIL_COUNT failed"
echo "════════════════════════════════════════════════════════════════"

if [[ ${#FAILURES[@]} -gt 0 ]]; then
    echo ""
    echo "Failures:"
    for f in "${FAILURES[@]}"; do
        echo "  - $f"
    done
    exit 1
fi

exit 0
