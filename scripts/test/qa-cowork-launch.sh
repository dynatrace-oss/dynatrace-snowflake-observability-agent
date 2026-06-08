#!/usr/bin/env bash
#
# qa-cowork-launch.sh — Launch a Claude Code QA session for a specific role and
# working directory. Supports running 4 parallel sessions across ant-* clones.
#
# Usage:
#   ./scripts/test/qa-cowork-launch.sh \
#       --workdir=/path/to/ant-N/snowagent \
#       --role=coordinator|eval-b-parallel|eval-batch-1|eval-batch-2|eval-batch-3 \
#       [--model=haiku|sonnet|opus] \
#       [--version=0.9.5] \
#       [--tmux-session=qa-cowork]
#
# Roles:
#   coordinator      Phases A + B1-B7/B11-B15 + Phase 4 + Phase 5  (uses test-qa1)
#   eval-b-parallel  B8-B10 in parallel with coordinator            (uses test-qa2)
#   eval-batch-1     Phase 3.5 Batch 2 (C1-C4 extended)            (uses dev-095, read-only)
#   eval-batch-2     Phase 3.5 Batch 3 (C5-C8)                     (uses dev-095, read-only)
#   eval-batch-3     Phase 3.5 Batch 4 (C9-C11 + cross-version)    (uses dev-095, read-only)
#
# Model recommendations:
#   coordinator      sonnet  (deploy log parsing, VISUAL reasoning, 105-item walkthrough)
#   eval-b-parallel  sonnet  (deployment reasoning + DQL failure analysis)
#   eval-batch-*     haiku   (fixed DQL templates, binary pass/fail — cost-efficient)
#
# Prerequisites:
#   - For coordinator and eval-b-parallel: DTAGENT_TOKEN must be set in the environment
#   - For eval-batch-*: No token needed (read-only DQL against existing env)
#   - All roles: claude CLI installed and authenticated
#   - Shared results directory symlinked (see test/qa/COWORK.md)
#

set -euo pipefail

WORKDIR=""
ROLE=""
MODEL=""
VERSION=""
TMUX_SESSION=""

usage() {
    cat <<EOF
Usage: $0 --workdir=<path> --role=<role> [--model=<model>] [--version=<ver>] [--tmux-session=<name>]

Roles:
  coordinator      Full QA session: Phases A, B1-B7/B11-B15, Phase 4, Phase 5
  eval-b-parallel  B8-B10 deployment scenarios (parallel with coordinator B1-B7)
  eval-batch-1     Phase 3.5 Batch 2: additional metrics, logs, spans (C1-C4 extended)
  eval-batch-2     Phase 3.5 Batch 3: events, active queries, shares, lifecycle (C5-C8)
  eval-batch-3     Phase 3.5 Batch 4: OpenPipeline, obfuscation, overload (C9-C11)

Models: haiku (default for eval-batch-*), sonnet (default for coordinator/eval-b-parallel)

Environment variables:
  DTAGENT_TOKEN   Required for coordinator and eval-b-parallel roles (test-qa deployments)

Examples:
  # Open 4 tmux panes for a full cowork session:
  $0 --workdir=~/Development/hex/ant-1/snowagent --role=coordinator --tmux-session=qa-095
  $0 --workdir=~/Development/hex/ant-2/snowagent --role=eval-b-parallel --tmux-session=qa-095
  $0 --workdir=~/Development/hex/ant-3/snowagent --role=eval-batch-2 --tmux-session=qa-095
  $0 --workdir=~/Development/hex/ant-4/snowagent --role=eval-batch-3 --tmux-session=qa-095
EOF
    exit 1
}

for arg in "$@"; do
    case "$arg" in
        --workdir=*)   WORKDIR="${arg#--workdir=}" ;;
        --role=*)      ROLE="${arg#--role=}" ;;
        --model=*)     MODEL="${arg#--model=}" ;;
        --version=*)   VERSION="${arg#--version=}" ;;
        --tmux-session=*) TMUX_SESSION="${arg#--tmux-session=}" ;;
        --help|-h)     usage ;;
        *) echo "Unknown argument: $arg" >&2; usage ;;
    esac
done

# ── Validate required args ────────────────────────────────────────────────────

if [[ -z "$WORKDIR" || -z "$ROLE" ]]; then
    echo "Error: --workdir and --role are required." >&2
    usage
fi

VALID_ROLES="coordinator eval-b-parallel eval-batch-1 eval-batch-2 eval-batch-3"
if ! echo "$VALID_ROLES" | grep -qw "$ROLE"; then
    echo "Error: unknown role '$ROLE'. Must be one of: $VALID_ROLES" >&2
    usage
fi

if [[ ! -d "$WORKDIR" ]]; then
    echo "Error: workdir '$WORKDIR' does not exist." >&2
    exit 1
fi

if [[ ! -f "$WORKDIR/src/dtagent/version.py" ]]; then
    echo "Error: '$WORKDIR' does not look like a snowagent repo (missing src/dtagent/version.py)." >&2
    exit 1
fi

# ── Token check for deployment roles ─────────────────────────────────────────

if [[ "$ROLE" == "coordinator" || "$ROLE" == "eval-b-parallel" ]]; then
    if [[ -z "${DTAGENT_TOKEN:-}" ]]; then
        echo "Error: DTAGENT_TOKEN must be set for role '$ROLE'." >&2
        echo "  export DTAGENT_TOKEN=<your-token>" >&2
        exit 1
    fi
fi

# ── Default model per role ────────────────────────────────────────────────────

if [[ -z "$MODEL" ]]; then
    case "$ROLE" in
        coordinator|eval-b-parallel)  MODEL="sonnet" ;;
        eval-batch-*)                 MODEL="haiku"  ;;
    esac
fi

# Map friendly model names to Claude model IDs
case "$MODEL" in
    haiku)  CLAUDE_MODEL="claude-haiku-4-5-20251001" ;;
    sonnet) CLAUDE_MODEL="claude-sonnet-4-6" ;;
    opus)   CLAUDE_MODEL="claude-opus-4-7" ;;
    *)      CLAUDE_MODEL="$MODEL" ;;  # pass through if already a full model ID
esac

# ── Detect version from repo if not provided ─────────────────────────────────

if [[ -z "$VERSION" ]]; then
    VERSION=$(grep '^VERSION' "$WORKDIR/src/dtagent/version.py" 2>/dev/null \
                | head -1 | sed "s/.*= *['\"]//;s/['\"].*//")
    if [[ -z "$VERSION" ]]; then
        echo "Warning: could not detect version from version.py; using 'unknown'" >&2
        VERSION="unknown"
    fi
fi

# ── Build seed prompt ─────────────────────────────────────────────────────────

case "$ROLE" in
coordinator)
    SEED_PROMPT="Load the qa-runner skill and start a QA session for DSOA ${VERSION}.
You are the COORDINATOR. Run in this order:
1. Phase 1 (version discovery, ORGADMIN detection)
2. Phase A (offline checks: make lint, pytest, dtctl dry-runs) — run all automatically
3. Phase 2 (deployment guidance for DEV-095 and DEV-094) — guide the human
4. Phase 3 (notebook deployment)
5. Phase 3.5 Batch 1 (core health checks) — run automatically
6. B-section: B1-B7 on test-qa (you have full --scope=all access via DTAGENT_TOKEN)
7. Wait for eval-b-parallel (ant-2) to complete B8-B10 and signal you
8. B-section: B11-B15 on test-qa
9. Phase 4 (interactive VISUAL walkthrough — guide the human tile by tile)
10. Phase 5 (merge all partial results from test/qa/results/ → final signoff report)
The human will signal when eval-batch agents have completed their Phase 3.5 batches."
    ;;

eval-b-parallel)
    SEED_PROMPT="Load the qa-runner skill for DSOA ${VERSION}.
You are running B-SECTION PARALLEL on test-qa2.
Your coordinator (ant-1) is running B1-B7 simultaneously on test-qa1.
Run only these scenarios, in order, on the test-qa2 environment:
  B8 — Deployment with selected plugins only
  B9 — Configuration-only update
  B10 — Disabled plugin not callable
Use the B-section guidance in the qa-runner SKILL.md for each scenario.
When done, write a summary to test/qa/results/qa-${VERSION}-b8b10-\$(date +%Y%m%d).md
Then signal the coordinator by printing: SIGNAL: B8-B10 complete on test-qa2."
    ;;

eval-batch-1)
    SEED_PROMPT="Load the qa-runner skill for DSOA ${VERSION}.
You are running PHASE 3.5 BATCH 2 (additional metrics, logs, spans).
Wait for a signal from the coordinator that DEV-095 telemetry is flowing before starting.
Then run all Phase 3.5 Batch 2 checks (AE-C1.1, AE-C2.2 through AE-C4.12) using execute_dql MCP.
Use DEV-095 as the current environment and DEV-094 as the previous environment.
Write results to test/qa/results/qa-${VERSION}-batch2-\$(date +%Y%m%d).md"
    ;;

eval-batch-2)
    SEED_PROMPT="Load the qa-runner skill for DSOA ${VERSION}.
You are running PHASE 3.5 BATCH 3 (events, active queries, shares, plugin lifecycle).
Wait for a signal from the coordinator that DEV-095 telemetry is flowing before starting.
Then run all Phase 3.5 Batch 3 checks (AE-C5.2 through AE-C8.4) using execute_dql MCP.
Use DEV-095 as the current environment and DEV-094 as the previous environment.
Write results to test/qa/results/qa-${VERSION}-batch3-\$(date +%Y%m%d).md"
    ;;

eval-batch-3)
    SEED_PROMPT="Load the qa-runner skill for DSOA ${VERSION}.
You are running PHASE 3.5 BATCH 4 (OpenPipeline, obfuscation, overload).
Wait for a signal from the coordinator that all prerequisite simulation scripts
have been run (openpipeline deployed, obfuscation setup, overload setup) before starting.
Then run all Phase 3.5 Batch 4 checks (AE-C9.1 through AE-C11.2) using execute_dql MCP.
Use DEV-095 as the current environment and DEV-094 as the previous environment.
Write results to test/qa/results/qa-${VERSION}-batch4-\$(date +%Y%m%d).md"
    ;;
esac

# ── Launch ────────────────────────────────────────────────────────────────────

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DSOA QA Cowork — ${ROLE}"
echo "  workdir: ${WORKDIR}"
echo "  model:   ${CLAUDE_MODEL}"
echo "  version: ${VERSION}"
[[ -n "$TMUX_SESSION" ]] && echo "  tmux:    ${TMUX_SESSION}:${ROLE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ -n "$TMUX_SESSION" ]]; then
    # Open a new tmux window named after the role in the given session
    if ! tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        tmux new-session -d -s "$TMUX_SESSION" -c "$WORKDIR"
        tmux rename-window -t "${TMUX_SESSION}:0" "$ROLE"
    else
        tmux new-window -t "$TMUX_SESSION" -n "$ROLE" -c "$WORKDIR"
    fi
    # Launch claude in the new window with the seed prompt
    tmux send-keys -t "${TMUX_SESSION}:${ROLE}" \
        "cd '${WORKDIR}' && claude --model '${CLAUDE_MODEL}' --print '${SEED_PROMPT}'" \
        Enter
    echo "Launched in tmux session '${TMUX_SESSION}', window '${ROLE}'."
    echo "Attach with: tmux attach -t ${TMUX_SESSION}"
else
    # Interactive: cd to workdir and launch claude
    cd "$WORKDIR"
    exec claude --model "$CLAUDE_MODEL" --print "$SEED_PROMPT"
fi
