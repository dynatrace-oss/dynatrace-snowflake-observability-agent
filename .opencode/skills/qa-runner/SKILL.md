---
name: qa-runner
description: >
  AI-guided QA walkthrough for DSOA releases. Automates version detection,
  deployment commands, notebook deployment, and interactive test walkthrough.
  Use when a QA engineer needs to execute the DSOA release test suite.
license: MIT
compatibility: opencode
metadata:
  audience: qa-engineers, developers
---

# Skill: DSOA Release QA Runner

Use this skill when asked to:

- Start the QA process for a DSOA release
- Walk a QA engineer through the release test suite
- Deploy and open the QA test notebook
- Generate a QA signoff summary

---

## Overview

The QA runner executes in five sequential phases. Complete each phase fully
before moving to the next. Do not skip phases.

| Phase | Name                | Who acts                     | Output                               |
|-------|---------------------|------------------------------|--------------------------------------|
| 1     | Version discovery   | AI (automated)               | Verified version tags + config files |
| 2     | Deployment guidance | Human (AI provides commands) | Both environments running            |
| 3     | Notebook deployment | AI (runs script)             | Notebook URL                         |
| 4     | Test walkthrough    | Interactive                  | Pass/fail per checklist item         |
| 5     | QA signoff          | AI                           | Summary report                       |

---

## Phase 1 — Version Discovery

Run all of the following automatically without waiting for the human.

### 1a. Determine current version

```bash
grep '^VERSION' src/dtagent/version.py | head -1
```

Store as `CURR_VERSION` (e.g. `0.9.4`).

### 1b. Derive version tags

The 3-digit tag is: `printf "%03d" $((minor * 10 + patch))`

```bash
bash -c '
v="'"${CURR_VERSION}"'"
minor=$(echo "$v" | cut -d. -f2)
patch=$(echo "$v" | cut -d. -f3)
printf "%03d\n" $(( minor * 10 + patch ))
'
```

Store as `CURR_TAG` (e.g. `094`). The deployment environment is `DEV-${CURR_TAG}`.

### 1c. Determine previous version

**Default rule:** decrement the patch component of `CURR_VERSION` by 1.
Example: `0.9.4` → `0.9.3` → tag `093`.

**Override:** If the human specifies a different previous version
(e.g. because the previous release was a hotfix like `0.9.3.1`), use that
version instead. Ask:

> "The default previous version is `{auto_prev}`. Is that correct, or should I
> use a different version (e.g. `0.9.3.1`)? Type the version or press Enter to
> accept the default."

Store as `PREV_VERSION` and derive `PREV_TAG` using the same algorithm.

### 1d. Verify config files

```bash
ls conf/config-dev-{CURR_TAG}.yml conf/config-dev-{PREV_TAG}.yml 2>&1
```

- If `conf/config-dev-{CURR_TAG}.yml` is **missing**: stop and instruct the human
  to create it (pointing to the current Snowflake account and Dynatrace tenant).
- If `conf/config-dev-{PREV_TAG}.yml` is **missing**: warn the human that
  cross-version comparison tiles will show only the current environment. Ask
  whether to proceed or to create the file first.

### 1e. Extract tenant info

```bash
yq '.core.dynatrace_tenant_address' conf/config-dev-{CURR_TAG}.yml
yq '.core.deployment_environment'   conf/config-dev-{CURR_TAG}.yml
yq '.core.dynatrace_tenant_address' conf/config-dev-{PREV_TAG}.yml
yq '.core.deployment_environment'   conf/config-dev-{PREV_TAG}.yml
```

Verify both configs point to the same `dynatrace_tenant_address`. If they
differ, warn the human — both environments must send data to the same tenant for
comparison tiles to work.

### Phase 1 output

Report the following before proceeding:

```text
Current version:   {CURR_VERSION}  (tag: {CURR_TAG},  env: DEV-{CURR_TAG})
Previous version:  {PREV_VERSION}  (tag: {PREV_TAG},  env: DEV-{PREV_TAG})
Dynatrace tenant:  {TENANT_ADDR}
Config files:      conf/config-dev-{CURR_TAG}.yml  ✓
                   conf/config-dev-{PREV_TAG}.yml  ✓ / ⚠ missing
```

Ask the human to confirm before proceeding to Phase 2.

---

## Phase 2 — Deployment Guidance

Instruct the human to run the following commands. Both use `--scope=all` for a
fresh, complete deployment of the agent into each environment.

### Deploy the current version

```bash
./scripts/deploy/deploy.sh dev-{CURR_TAG} --scope=all --options=skip_confirm
```

### Deploy the previous version

```bash
./scripts/deploy/deploy.sh dev-{PREV_TAG} --scope=all --options=skip_confirm
```

**Important notes to share:**

- Both deployments must target the same Snowflake account (different schemas/roles
  differentiated by `deployment_environment` tag, not by database name).
- Both deployments must target the same Dynatrace tenant.
- Wait for each deployment to complete and the Snowflake task scheduler to run at
  least one execution cycle before proceeding.
- Typical first-run latency: 2–5 minutes after deploy before telemetry appears.

After both deploys, ask:

> "Have both deployments completed successfully and is telemetry appearing in
> Dynatrace? (yes / no / need help)"

If the human says "need help":
- Check Snowflake task history for the DTAGENT task
- Check agent operational logs: `fetch logs | filter dsoa.run.context == "self_monitoring"`
- Check for ERROR-level log entries from the agent

---

## Phase 3 — Notebook Deployment

Run the deploy script:

```bash
./scripts/test/deploy_test_notebook.sh \
    --curr-version={CURR_VERSION} \
    --prev-version={PREV_VERSION}
```

The script:
1. Reads `conf/config-dev-{CURR_TAG}.yml` to get the tenant address
2. Finds the matching dtctl context
3. Converts `test/qa/test-suite/test-suite.yml` → JSON and injects the notebook name
4. Deploys via `dtctl apply` and prints the notebook URL
5. Writes the assigned notebook ID back into the YAML for future runs

If `dtctl` is not authenticated, instruct the human to run:

```bash
dtctl auth login
```

Then retry the script.

After a successful deploy, share the notebook URL with the human and ask them to
confirm it opens in Dynatrace. If the notebook ID needs to be committed to the
YAML, remind the human to do so after the QA session.

---

## Phase 4 — Test Walkthrough

Walk through `test/qa/RELEASE-CHECKLIST.md` section by section. For each item:

- State the item description clearly
- For Section A (offline): ask `[PASS]`, `[FAIL]`, or `[SKIP reason]`
- For Section B (deployment): provide the exact command, ask the human to run it,
  then confirm the result
- For Section C (live telemetry): name the **exact notebook tile** to check, note
  whether it is a `[COMPARE]` tile (both DEV-{PREV} and DEV-{CURR} expected), and
  ask for the result

Keep a running tally in memory. Only proceed to the next item after recording
the current item's result.

### Tile navigation hints

Tell the human to open the notebook at the URL from Phase 3. The tiles are
grouped by test theme matching the checklist sections. Within each group tiles
appear in checklist order.

For `[COMPARE]` tiles, both series must be visible. If only one series appears,
it likely means the other environment has not completed a run yet — ask the
human to wait and refresh.

### Handling failures

When a test fails:

1. Ask the human to describe what they see
2. Suggest the most likely investigation steps (e.g. check logs for that plugin,
   verify the Snowflake view exists, check task is not suspended)
3. Record the failure with a brief note
4. Continue to the next item — do not block the session on a single failure

---

## Phase 5 — QA Signoff

Generate the result summary table:

```text
Section              | Pass | Fail | Skip | Total
---------------------|------|------|------|------
A — Offline          |      |      |      |   5
B — Deployment       |      |      |      |  10
C1 — Data Volume     |      |      |      |   8
C2 — Metrics         |      |      |      |   8
C3 — Logs            |      |      |      |   6
C4 — Spans           |      |      |      |   9
C5 — Events          |      |      |      |   7
C6 — Active Queries  |      |      |      |   4
C7 — Shares          |      |      |      |   4
C8 — Plugin Lifecycle|      |      |      |   2
Total                |      |      |      |  63
```

List all failed and skipped items with the human's notes.

Generate the signoff line:

```text
DSOA {CURR_VERSION} QA — {DATE} — {PASS}/{TOTAL} items passed
Tester: {human name or "QA"}
Notebook: {NOTEBOOK_URL}
```

Offer to write the full results to a file:

```bash
mkdir -p test/qa/results
# write to test/qa/results/qa-{CURR_VERSION}-{YYYYMMDD}.md
```

The results file should contain the signoff line, the summary table, the full
list of failed/skipped items with notes, and the notebook URL.

---

## Helper Reference

### Version-to-tag algorithm (bash)

```bash
version_to_tag() {
    local version="$1"
    local minor patch
    minor=$(echo "$version" | cut -d. -f2)
    patch=$(echo "$version" | cut -d. -f3)
    printf "%03d" $(( minor * 10 + patch ))
}
```

Examples: `0.9.4` → `094` | `0.9.3.1` → `093` | `0.9.10` → `100`

### Key file paths

| Path | Purpose |
|---|---|
| `src/dtagent/version.py` | Source of truth for current version |
| `conf/config-dev-{TAG}.yml` | Per-environment configuration |
| `test/qa/RELEASE-CHECKLIST.md` | Full checklist with all items |
| `test/qa/test-suite/test-suite.yml` | Notebook YAML template |
| `scripts/test/deploy_test_notebook.sh` | Notebook deploy script |
| `test/qa/results/` | QA result files (create as needed) |

### Deploy commands quick reference

```bash
# Deploy both environments (fresh)
./scripts/deploy/deploy.sh dev-{CURR_TAG} --scope=all --options=skip_confirm
./scripts/deploy/deploy.sh dev-{PREV_TAG} --scope=all --options=skip_confirm

# Deploy the test notebook
./scripts/test/deploy_test_notebook.sh \
    --curr-version={CURR_VERSION} \
    --prev-version={PREV_VERSION}

# Preview notebook deploy without applying
./scripts/test/deploy_test_notebook.sh --dry-run
```
