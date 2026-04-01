# Skill: Dashboard and Workflow Documentation

Use this skill whenever you create or update a dashboard or workflow.
Documentation is a first-class deliverable — never skip it.

## Files to Produce

For every dashboard:

```text
docs/dashboards/<name>/readme.md       ← main documentation (you write this)
docs/dashboards/<name>/img/.gitkeep   ← placeholder until screenshots are taken
docs/dashboards/README.md             ← index (update the table)
```

For every workflow:

```text
docs/workflows/<name>/readme.md
docs/workflows/<name>/img/.gitkeep
docs/workflows/README.md
```

---

## `readme.md` Structure

Follow this exact structure. Look at existing dashboards
(`docs/dashboards/costs-monitoring/readme.md`,
`docs/dashboards/self-monitoring/readme.md`) for tone and level of detail.

```markdown
# <Dashboard / Workflow Title>

<One-paragraph description: what it monitors, who it is for, and why it matters.>

## Use Cases Covered

| # | Use Case               | Theme                                                 | Plugin(s)  |
|---|------------------------|-------------------------------------------------------|------------|
| 1 | <use case description> | Operations / Costs / Performance / Quality / Security | `<plugin>` |
| 2 | ...                    | ...                                                   | ...        |

## Prerequisites

- DSOA deployed with the following plugins enabled: `<plugin-a>`, `<plugin-b>`
- Data must be flowing for at least one collection cycle before tiles populate:
  - Fast-mode tiles (e.g. pipe status, active queries): ~5 minutes
  - Deep-mode tiles (e.g. copy history, usage history): ~1–2 hours

## Dashboard Variables

| Variable    | Purpose                                                | Default   |
|-------------|--------------------------------------------------------|-----------|
| `$Accounts` | Filter by Snowflake account (`deployment.environment`) | `*` (all) |
| `$<Other>`  | <description>                                          | <default> |

## Sections and Tiles

### Section 1 — <Name>

Brief description of what this section shows and the decision it supports.

| Tile         | Visualisation                                                    | Metric / Source          | Notes         |
|--------------|------------------------------------------------------------------|--------------------------|---------------|
| <Tile title> | `singleValue` / `lineChart` / `barChart` / `honeycomb` / `table` | `snowflake.<metric.key>` | <any caveats> |

### Section 2 — <Name>

...

## Filtering to a Specific Use Case

Explain how to narrow the dashboard to answer a specific question.
Example:

> To monitor only pipes loading CSV files from S3, set `$Pipe` to a pattern
> matching your pipe names (e.g. `%.S3_INGEST.%`) and narrow `$Accounts` to
> the relevant Snowflake account.

## Known Limitations

- List any deferred tiles, data gaps, or latency caveats.
- Reference any follow-up tickets if applicable.

## Screenshots

<!-- Screenshots are added after manual validation in Dynatrace UI -->

| File                     | What to capture                                      |
|--------------------------|------------------------------------------------------|
| `img/overview.png`       | Full dashboard at default zoom, all sections visible |
| `img/section-<name>.png` | <section> with representative data                   |
| `img/<tile-name>.png`    | Close-up of a specific tile if it needs explanation  |
```

---

## Updating `docs/dashboards/README.md`

Add a row to the dashboards table after the closest related entry.
Keep the table sorted by domain/theme, not alphabetically.

```markdown
| [<Title>](dashboards/<name>/readme.md) | <one-line description> | `<plugin-a>`, `<plugin-b>` |
```

Same pattern for `docs/workflows/README.md`.

---

## Screenshot Requests

At the end of every dashboard/workflow delivery, output a **Screenshot Checklist**
in this exact format so the human reviewer knows exactly what to capture:

```text
## 📸 Screenshot Checklist — <Dashboard Name>

Please open the dashboard at:
  <Dynatrace URL>

Set variables: $Accounts = <dev environment name>, $<Other> = <value>

Capture and save to docs/dashboards/<name>/img/:

  [ ] overview.png
      Full dashboard scrolled to show all sections, time range = last 2h

  [ ] section-<name>.png
      <Section title> — zoom in so tile labels are readable

  [ ] <tile-name>.png
      <Specific tile> — should show <what representative data looks like>

  (repeat for each meaningful section / tile)
```

This checklist must be the **last output** of any dashboard implementation task,
after the git commit.

---

## Commit Scope

The git commit for a dashboard or workflow delivery must include **all** of:

```text
docs/dashboards/<name>/<name>.yml       ← YAML source (with id: field added)
docs/dashboards/<name>/readme.md        ← documentation
docs/dashboards/<name>/img/.gitkeep     ← placeholder
docs/dashboards/README.md               ← updated index
test/tools/setup_test_<plugin>.sql      ← synthetic setup (if new or updated)
```

For workflows, replace `docs/dashboards/` with `docs/workflows/`.

Commit message format:

```text
feat(dashboards): add <dashboard-name> monitoring dashboard

Covers use cases: <comma-separated list from readme Use Cases table>
Dashboard ID: <uuid from dtctl>
Synthetic setup: test/tools/setup_test_<plugin>.sql
```

---

## Implemented Use Cases — Final Summary

After the git commit, output a **Use Cases Summary** so the human can
verify scope coverage:

```markdown
## ✅ Implemented Use Cases — <Dashboard Name>

| # | Use Case   | Theme   | Tile         | Status                |
|---|------------|---------|--------------|-----------------------|
| 1 | <use case> | <theme> | <tile title> | ✅ Implemented         |
| 2 | <use case> | <theme> | <tile title> | ✅ Implemented         |
| 3 | <use case> | <theme> | —            | ⏭ Deferred (<reason>) |
```

This summary must appear **after** the Screenshot Checklist.
