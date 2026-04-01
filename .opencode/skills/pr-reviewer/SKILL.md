---
name: pr-reviewer
description: Review a pull request and process review comments left by others
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

# Skill: Pull Request Review and Comment Processing

Use this skill when asked to:

- **Review a PR** — read the diff, assess quality, post a structured review.
- **Process review comments** — fetch comments left by others, triage them, and act on them.

## Required Input

| Input | Required | Description |
|---|---|---|
| PR number | yes | The GitHub pull request number (e.g. `80`) |
| Product improvement notes | no | Feature/improvement brief that motivated this PR |
| Implementation plan | no | Ordered task list describing what the PR is supposed to do |

If the product improvement or implementation plan are not supplied, infer intent
from the PR title, body, and diff — but note the gap when reporting findings.

---

## Phase 1 — Gather Context

Run all reads in parallel where possible to minimise latency.

### 1a. Identify the repository

```bash
gh repo view --json nameWithOwner
# → { "nameWithOwner": "dynatrace-oss/dynatrace-snowflake-observability-agent" }
```

Store `OWNER` and `REPO` for all subsequent calls.

### 1b. Fetch PR metadata and diff

```bash
gh pr view <PR#> --json number,title,body,baseRefName,headRefName,state,author,labels,milestone

gh pr diff <PR#>
```

The diff is the primary artefact for a review. Read it fully before drawing
any conclusions.

### 1c. Fetch all review threads (open **and** resolved)

Use the GitHub GraphQL API to get rich thread data including file paths, line
numbers, diff hunks, and resolution status. Request enough nodes to cover all
threads — increase the `first:` value if the PR is large.

```bash
gh api graphql -f query='
{
  repository(owner: "<OWNER>", name: "<REPO>") {
    pullRequest(number: <PR#>) {
      title
      body
      reviewThreads(first: 50) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          diffHunk
          comments(first: 10) {
            nodes {
              databaseId
              author { login }
              body
              createdAt
              updatedAt
              minimizedReason
            }
          }
        }
      }
      reviews(first: 20) {
        nodes {
          author { login }
          state
          body
          submittedAt
        }
      }
    }
  }
}'
```

Pipe through `python3 -m json.tool` for readable output. Store the result — it
is the source of truth for all comment-processing decisions.

### 1d. Read relevant source files for context

For every file mentioned in review threads or the diff, read the surrounding
context using the `Read` tool (not `cat`). For large files, use offset + limit
or the `Grep` tool to jump to the relevant region.

```bash
# Example: read lines 220-260 of a file referenced in a thread
# Use the Read tool with offset=220, limit=40
```

Do **not** guess at context. Read the actual file before forming an opinion.

---

## Phase 2 — Analyse

### 2a. Classify each review thread

For every thread from the GraphQL result, assign:

| Field | Values |
|---|---|
| Status | `open` / `resolved` / `outdated` |
| Severity | `critical` / `important` / `minor` / `nit` |
| Category | `correctness` / `style` / `docs` / `tests` / `perf` / `security` / `architecture` |
| Action | `fix` / `address-in-comment` / `defer` / `disagree` / `already-done` |

**Severity guide:**

- `critical` — bug, data loss, security issue, broken contract, test that does not catch what it claims to catch.
- `important` — meaningful quality regression, misleading naming, incomplete coverage.
- `minor` — improvement that is clearly better but not blocking.
- `nit` — style, spelling, personal preference with no functional impact.

### 2b. Cross-reference against the implementation plan

If an implementation plan was provided, verify:

1. Every task in the plan has a corresponding change in the diff.
2. No task introduces unintended side effects visible in the diff.
3. Out-of-scope changes are flagged (scope creep).

### 2c. Run your own independent assessment

Beyond the existing comments, check for:

- Lint compliance (`make lint`, pylint **10.00/10**, black, flake8, sqlfluff).
- Missing or incorrect tests (see `docs/PLUGIN_DEVELOPMENT.md` for the plugin
  test pattern).
- Missing docstrings (Google style, all public symbols).
- Missing BOM or `instruments-def.yml` updates for new plugins or metrics.
- Backward compatibility concerns (procedure signature changes need upgrade
  scripts, see copilot-instructions §Anti-Patterns).
- Copyright headers in new files.
- `CHANGELOG.md` / `DEVLOG.md` updates where required.

**Before concluding that something is broken or missing, consult the actual
source files.** Do not flag issues based on the diff alone when the answer
might be in an unchanged file.

---

## Phase 3 — Prepare an Improvement Plan

Produce a structured plan in this format:

```markdown
## PR #<N> — Improvement Plan

### Summary
<One paragraph: overall assessment, whether the PR is ready to merge, and the
main concerns.>

### Action Items

| # | Thread / Finding | File | Line | Severity | Category | Action | Notes |
|---|---|---|---|---|---|---|---|
| 1 | <thread id or "own"> | `path/to/file.py` | 123 | critical | correctness | fix | <what to do> |
| 2 | ... | | | | | | |

### Out-of-scope changes detected
<List any diff hunks that appear unrelated to the PR goal, or "None".>

### Deferred items
<Items that are valid but should be handled in a separate PR.>
```

**Consult the human before acting on any item that would:**

- Change public API or stored procedure signatures.
- Alter plugin behaviour or output schema.
- Modify configuration format or defaults.
- Touch files outside the PR's stated scope.

Present the plan to the human and wait for approval before moving to Phase 4.

---

## Phase 4 — Implement Fixes

Work through the approved action items one at a time:

1. Mark the item `in_progress` in the TodoWrite tool.
2. Read the relevant file(s) with the `Read` tool.
3. Apply the change with the `Edit` tool.
4. Run `make lint` and `.venv/bin/pytest` after each change — do not batch.
5. Mark the item `completed` only after tests and lint are green.
6. Move to the next item.

### Lint and test commands

```bash
make lint                                      # full lint suite
.venv/bin/pytest                               # full test suite
.venv/bin/pytest test/plugins/test_<X>.py -v  # single plugin
```

If a test fails, diagnose the root cause and fix it. Never "fix" a test by
adjusting expected values to match wrong output — fix the code.

---

## Phase 5 — Post Review (when acting as reviewer)

After completing all fixes, post a structured review using the GitHub CLI or
the GitHub MCP tool.

### Option A — CLI (prefer for full reviews)

```bash
# Approve
gh pr review <PR#> --approve --body "<review body>"

# Request changes
gh pr review <PR#> --request-changes --body "<review body>"

# Comment only
gh pr review <PR#> --comment --body "<review body>"
```

### Option B — GitHub MCP (for inline comments on specific lines)

Use `github_create_pull_request_review` with `comments` array for line-level
annotations. Each comment needs `path`, `line`, and `body`.

### Review body template

```markdown
## Review — PR #<N>: <title>

### Overall Assessment
<APPROVE / REQUEST_CHANGES / COMMENT> — <one sentence why>

### Critical Issues
<numbered list, or "None">

### Important Issues
<numbered list, or "None">

### Minor / Nit
<numbered list, or "None">

### Positive Observations
<what is done well — be specific>
```

---

## Phase 6 — Respond to Others' Comments

When processing comments left by other reviewers (human or bot):

1. For every `open` thread: decide `fix`, `address-in-comment`, or `defer`.
2. For `resolved` threads: verify the fix is actually present in the diff —
   do not trust the resolved flag blindly.
3. For bot comments (e.g. `copilot-pull-request-reviewer`): evaluate on merit,
   not authority. Bots can be wrong.
4. **Always reply to every thread you act on** — whether you fixed, deferred, or disagreed.
   Use the first comment's `databaseId` from the GraphQL result:

```bash
# Reply to a specific review thread (requires the thread's first comment databaseId)
gh api repos/<OWNER>/<REPO>/pulls/<PR#>/comments/<comment-id>/replies \
  -f body="<your reply>"
```

   Reply template:
   - **Fixed**: `"Fixed in commit <sha>. <one sentence describing what changed and why.>"`
   - **Deferred**: `"Acknowledged. Deferred to a follow-up — <brief rationale>."`
   - **Disagreed**: `"Disagree: <technical reasoning>. Leaving as-is."`
   - **Already done**: `"This is already handled in <file>:<line> — <brief explanation>."`

   Run all replies in parallel (one `gh api` call per thread) — do not wait between replies.

---

## Quick Reference — Common GraphQL Snippets

### List unresolved threads only

```bash
gh api graphql -f query='
{
  repository(owner: "<OWNER>", name: "<REPO>") {
    pullRequest(number: <PR#>) {
      reviewThreads(first: 50) {
        nodes {
          isResolved
          path
          line
          comments(first: 5) {
            nodes { author { login } body }
          }
        }
      }
    }
  }
}' | python3 -c "
import json, sys
data = json.load(sys.stdin)
threads = data['data']['repository']['pullRequest']['reviewThreads']['nodes']
open_threads = [t for t in threads if not t['isResolved']]
print(f'{len(open_threads)} open thread(s)')
for t in open_threads:
    print(f\"  {t['path']}:{t['line']} — {t['comments']['nodes'][0]['body'][:80]}\")
"
```

### Get PR files changed

```bash
gh pr view <PR#> --json files --jq '.files[].path'
```

### Read a specific context window around a line in a file

Use the `Read` tool with `offset` and `limit` parameters — do not use `sed -n`
or `head`/`tail`.

---

## Pitfalls to Avoid

- **Never resolve a thread without actually fixing the issue.** Resolved status
  is set by the comment author, not by code presence — verify manually.
- **Do not fabricate test data.** If a test result file needs updating, re-run
  the test in live mode (`-p` flag) to regenerate fixtures from real output.
- **Do not make unrelated changes.** Note scope-creep findings in the plan and
  defer them.
- **Do not post a review before the human approves the improvement plan.**
- **Do not change procedure signatures without an upgrade script.** See
  copilot-instructions §Anti-Patterns.
- **Always use `.venv/bin/python` / `.venv/bin/pytest`.** Never system Python.
