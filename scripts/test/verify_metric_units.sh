#!/usr/bin/env bash
#
# Manual QA script: verify that units sent via dt.meta.unit are recognized by Dynatrace.
#
# Ingests test/qa/fixtures/all_metrics_ingest_payload.txt (one data line + one
# #<metric> gauge dt.meta.unit="..." metadata line per metric defined across all
# instruments-def.yml files — see scripts/dev/gen_metric_fixture.py) into a live
# Dynatrace tenant, waits for propagation, then queries each metric back via
# `dtctl query` and compares Dynatrace's reported unit to the unit we sent.
#
# NOT part of CI. Requires a live tenant, an ingest-capable API token, and
# dtctl authenticated against that same tenant. Run manually during a QA pass
# (see .opencode/skills/qa-runner/SKILL.md).
#
# Usage:
#   export DT_API_TOKEN=dt0c01.XXXX.YYYY   # classic API token, scopes: metrics.ingest
#   ./scripts/test/verify_metric_units.sh --env=dev-095
#   ./scripts/test/verify_metric_units.sh --tenant=abc12345.live.dynatrace.com
#   ./scripts/test/verify_metric_units.sh --env=dev-095 --sleep=60 --fixture=path/to/fixture.txt
#
# Prerequisites:
#   - dtctl on PATH and authenticated against the target tenant (`dtctl auth login`)
#   - DT_API_TOKEN env var set to a token with the "Ingest metrics" (metrics.ingest) scope
#   - curl, jq on PATH
#
# The API token is NEVER read from a config file or hardcoded — it must come from
# the DT_API_TOKEN environment variable and is never printed or logged.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FIXTURE="${REPO_ROOT}/test/qa/fixtures/all_metrics_ingest_payload.txt"
ENV_TAG=""
TENANT=""
SLEEP_SECONDS=120

usage() {
    cat <<'EOF'
Usage: verify_metric_units.sh (--env=<dev-XXX> | --tenant=<tenant-address>) [options]

Options:
  --env=<tag>         Environment tag matching conf/config-<tag>.yml (reads
                       core.dynatrace_tenant_address from it via yq).
  --tenant=<address>  Dynatrace tenant address directly, e.g. abc12345.live.dynatrace.com
                       (overrides --env).
  --fixture=<path>    Path to the ingest fixture (default: test/qa/fixtures/all_metrics_ingest_payload.txt)
  --sleep=<seconds>   Seconds to wait between ingest and query-back (default: 120)
  -h, --help          Show this help.

Requires the DT_API_TOKEN environment variable (classic API token, metrics.ingest scope)
and an authenticated dtctl session against the same tenant (metrics read via DQL).
EOF
}

for arg in "$@"; do
    case "$arg" in
        --env=*) ENV_TAG="${arg#--env=}" ;;
        --tenant=*) TENANT="${arg#--tenant=}" ;;
        --fixture=*) FIXTURE="${arg#--fixture=}" ;;
        --sleep=*) SLEEP_SECONDS="${arg#--sleep=}" ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown parameter: $arg" >&2; usage; exit 1 ;;
    esac
done

if [[ -z "$TENANT" && -n "$ENV_TAG" ]]; then
    CONFIG_FILE="${REPO_ROOT}/conf/config-${ENV_TAG}.yml"
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo "ERROR: config file not found: $CONFIG_FILE" >&2
        exit 1
    fi
    if ! command -v yq >/dev/null 2>&1; then
        echo "ERROR: yq is required to read --env config files (or pass --tenant directly)" >&2
        exit 1
    fi
    TENANT="$(yq '.core.dynatrace_tenant_address' "$CONFIG_FILE")"
fi

if [[ -z "$TENANT" ]]; then
    echo "ERROR: must supply --env=<tag> or --tenant=<address>" >&2
    usage
    exit 1
fi

if [[ -z "${DT_API_TOKEN:-}" ]]; then
    echo "ERROR: DT_API_TOKEN environment variable is not set." >&2
    echo "       export DT_API_TOKEN=dt0c01.XXXX.YYYY   # token with metrics.ingest scope" >&2
    exit 1
fi

if [[ ! -f "$FIXTURE" ]]; then
    echo "ERROR: fixture not found: $FIXTURE (run 'python scripts/dev/gen_metric_fixture.py' first)" >&2
    exit 1
fi

for tool in curl jq dtctl; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: required tool not on PATH: $tool" >&2
        exit 1
    fi
done

echo "════════════════════════════════════════════════════════════════"
echo " Metric unit-recognition QA check"
echo " Tenant:  $TENANT"
echo " Fixture: $FIXTURE"
echo "════════════════════════════════════════════════════════════════"

##region ── Step 1: Ingest the fixture ──────────────────────────────────────

echo ""
echo "--- Step 1: Ingesting fixture..."

HTTP_STATUS=$(curl -sS -o /tmp/verify_metric_units_response.json -w "%{http_code}" \
    -X POST "https://${TENANT}/api/v2/metrics/ingest" \
    -H "Authorization: Api-Token ${DT_API_TOKEN}" \
    -H "Content-Type: text/plain; charset=utf-8" \
    --data-binary @"$FIXTURE")

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

##endregion

##region ── Step 2: Wait for propagation ────────────────────────────────────

echo ""
echo "--- Step 2: Waiting ${SLEEP_SECONDS}s for metric metadata to propagate..."
sleep "$SLEEP_SECONDS"

##endregion

##region ── Step 3: Query each metric back and compare units ───────────────

echo ""
echo "--- Step 3: Querying recognized units via dtctl..."
echo ""
printf "%-55s %-15s %-15s %-6s\n" "METRIC" "EXPECTED" "DYNATRACE" "RESULT"
printf "%-55s %-15s %-15s %-6s\n" "------" "--------" "---------" "------"

PASS_COUNT=0
FAIL_COUNT=0
FAILURES=()

# Extract metric names + expected units directly from the fixture's own
# metadata lines (avoids re-parsing instruments-def.yml in bash).
while IFS= read -r meta_line; do
    metric_name="${meta_line#\#}"
    metric_name="${metric_name%% *}"
    expected_unit="$(echo "$meta_line" | grep -oE 'dt\.meta\.unit="[^"]*"' | sed -E 's/dt\.meta\.unit="([^"]*)"/\1/')"
    [[ -z "$expected_unit" ]] && continue

    query_json="$(dtctl query "timeseries sum(${metric_name}), from: -30m" -o json 2>/tmp/verify_metric_units_query_err.txt || true)"
    if [[ -z "$query_json" ]]; then
        printf "%-55s %-15s %-15s %-6s\n" "$metric_name" "$expected_unit" "ERROR" "FAIL"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILURES+=("$metric_name: dtctl query failed — $(cat /tmp/verify_metric_units_query_err.txt)")
        continue
    fi

    dt_unit="$(echo "$query_json" | jq -r --arg m "$metric_name" \
        '[.metadata.metrics[]? | select(."metric.key" == $m) | .unit] | first // "NOT_FOUND"')"

    if [[ "$dt_unit" == "$expected_unit" ]]; then
        printf "%-55s %-15s %-15s %-6s\n" "$metric_name" "$expected_unit" "$dt_unit" "PASS"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        printf "%-55s %-15s %-15s %-6s\n" "$metric_name" "$expected_unit" "$dt_unit" "FAIL"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILURES+=("$metric_name: expected '$expected_unit', Dynatrace reported '$dt_unit'")
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
