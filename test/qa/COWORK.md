# DSOA QA Cowork Setup Guide

Run up to 5 Claude sessions in parallel across 4 ant-* clones to compress the
full QA cycle. The coordinator handles sequential work; 3 eval agents run
Phase 3.5 DQL batches simultaneously.

---

## Prerequisites

### 1. Snowflake environments

| Profile name | Purpose                                  | Notes                            |
|--------------|------------------------------------------|----------------------------------|
| `dev-095`    | Current release (C-section telemetry)    | Human deploys init/admin         |
| `dev-094`    | Previous release (cross-version compare) | Human deploys init/admin         |
| `test-qa`    | B-section scenarios 1-7, 11-15           | AI has full `--scope=all` access |
| `test-qa2`   | B8-B10 parallel scenarios                | Needs separate Snowflake schema  |

**test-qa2 one-time setup**: Create a second config `conf/config-test-qa2.yml`
pointing to a separate Snowflake schema with `deployment_environment: TEST-QA2`.
Both test-qa and test-qa2 can point to the same DT test tenant.

### 2. Shared results directory

Results from all agents are written to a single shared directory. Set this up
once (per machine):

```bash
mkdir -p ~/Development/qa-results-shared
for n in 1 2 3 4; do
    rm -rf ~/Development/hex/ant-$n/snowagent/test/qa/results
    ln -s ~/Development/qa-results-shared \
          ~/Development/hex/ant-$n/snowagent/test/qa/results
done
```

The `test/qa/results/` directory is in `.gitignore` — result files are local only.

### 3. DTAGENT_TOKEN

Export the deployment token before launching the coordinator and eval-b-parallel:

```bash
export DTAGENT_TOKEN=<your-token>
```

### 4. Claude CLI

All 4 clones must have `claude` in PATH and authenticated (`claude auth`).

---

## Role assignment (4 clones → 5 roles; ant-2 does double duty)

```text
ant-1  →  coordinator       (sonnet)   Phases A, B1-B7/B11-B15, 3.5 Batch 1, Phase 4, Phase 5
ant-2  →  eval-b-parallel   (sonnet)   B8-B10 on test-qa2, THEN eval-batch-1 (Batch 2)
ant-3  →  eval-batch-2      (haiku)    Phase 3.5 Batch 3 (C5-C8)
ant-4  →  eval-batch-3      (haiku)    Phase 3.5 Batch 4 (C9-C11)
```

> Any ant-* clone can take any role — nothing is hardcoded. Use `--workdir` to
> specify which clone runs which role.

---

## Launching with tmux

The launcher script can create named tmux windows automatically:

```bash
# Create tmux session and open coordinator pane
./scripts/test/qa-cowork-launch.sh \
    --workdir=~/Development/hex/ant-1/snowagent \
    --role=coordinator \
    --tmux-session=qa-095

# Open remaining panes (run each in a separate terminal, or chain them)
./scripts/test/qa-cowork-launch.sh \
    --workdir=~/Development/hex/ant-2/snowagent \
    --role=eval-b-parallel \
    --tmux-session=qa-095

./scripts/test/qa-cowork-launch.sh \
    --workdir=~/Development/hex/ant-3/snowagent \
    --role=eval-batch-2 \
    --tmux-session=qa-095

./scripts/test/qa-cowork-launch.sh \
    --workdir=~/Development/hex/ant-4/snowagent \
    --role=eval-batch-3 \
    --tmux-session=qa-095

# Attach and switch between panes
tmux attach -t qa-095
# Switch windows: Ctrl+B then n (next) / p (prev) / 0-4 (by number)
```

---

## Sequencing and coordination

There is no automatic inter-agent communication. **You are the orchestrator.**
Watch pane output and manually signal agents when prerequisites are met.

```text
TIME      COORDINATOR (ant-1)          ANT-2                   ANT-3 / ANT-4
────────────────────────────────────────────────────────────────────────────
T+0       Phase 1 (version, ORGADMIN)
T+5m      Phase A (offline checks)     B8-B10 on test-qa2
T+30m     Deploy DEV-095/DEV-094       B8-B10 running
          (human deploys init/admin)
T+45m     B1-B7 on test-qa             ── B8-B10 complete ──
T+1h      3.5 Batch 1 (core health)    [Signal ant-2 to start Batch 2]
                                       Phase 3.5 Batch 2     Batches 3, 4 start
T+2h      B11-B15 on test-qa           Batch 2 running       Batches 3,4 running
T+3h      Phase 4 (VISUAL walkthrough) ─── write results ──── write results ───
T+4h      Phase 5 (merge + signoff)
```

### Signaling between panes

Agents only communicate via files. The coordinator watches for:

```bash
ls ~/Development/qa-results-shared/
# When these files appear, the corresponding agents are done:
# qa-0.9.5-b8b10-YYYYMMDD.md    → B8-B10 complete; coordinator can start B11-B15
# qa-0.9.5-batch2-YYYYMMDD.md   → eval-batch-1 done
# qa-0.9.5-batch3-YYYYMMDD.md   → eval-batch-2 done
# qa-0.9.5-batch4-YYYYMMDD.md   → eval-batch-3 done
```

Tell the coordinator pane: *"B8-B10 is complete, please continue with B11."*
Tell eval-batch panes: *"DEV-095 telemetry is flowing, start your batch now."*

---

## Running without Cowork (single session)

Use the standard `qa-runner` skill in any single clone. All 4 batches run
sequentially in one session. The coordinator role is the default single-session
behavior.

---

## Merging results (Phase 5)

The coordinator reads all partial result files and merges them:

```bash
ls ~/Development/qa-results-shared/qa-0.9.5-*.md
# Paste each batch result into the final signoff report
```

Tell the coordinator pane:
> "All batch agents are done. Merge test/qa/results/qa-0.9.5-batch*.md into the
> final Phase 5 report."

---

## Troubleshooting

**Claude CLI model flag**: if `--model haiku` is rejected, use the full model ID:

```bash
claude --model claude-haiku-4-5-20251001
```

**MCP rate limit**: Phase 3.5 DQL checks pause automatically between batches of 5.
If you see rate-limit errors, wait 20 seconds and ask the agent to retry.

**test-qa2 missing**: If `test-qa2` config is not set up yet, skip `eval-b-parallel`
and run B8-B10 sequentially from the coordinator after B1-B7.

**ORGADMIN skip**: If the account lacks ORGADMIN, the coordinator reports
`HAS_ORGADMIN: false` in Phase 1 output and eval-batch-1 auto-skips C2.13-C2.14.
