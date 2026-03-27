---
name: dashboard-docs
description: Create and update dashboard and workflow documentation
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

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

Use a **narrative-first, use-case-oriented** style. The canonical reference is
`docs/dashboards/snowpipes-monitoring/readme.md` and
`docs/dashboards/tasks-pipelines/readme.md` — read one of them before writing.

**Rules:**

- Open with one paragraph explaining what it monitors, who it is for, and why it matters.
- Place the **overview screenshot immediately after the opening paragraph**, before any sections.
- Organise the body by **dashboard section**, not by tile. Each section gets its own `##` heading.
- **Embed the section screenshot at the top of each section**, before the prose.
- Write **narrative prose** for each section: open with the question(s) the section answers,
  then describe each tile in terms of what it reveals and what action it drives.
  Avoid bare bullet lists of tile names — explain the "so what".
- Use bullet points only for compact per-tile detail (e.g. what a colour means, a data latency caveat).
- Inline a **close-up screenshot** for any tile whose visual requires explanation (e.g. honeycomb).
- Tables are acceptable for **Dashboard Variables** and **Known Limitations** — but not as a
  substitute for section prose.
- End with **Required Plugins**, **Dashboard Variables** (table), and **Known Limitations**.
- Do **not** include a "Use Cases Covered" table or a "Filtering to a Specific Use Case" section
  as separate headings — weave filtering guidance naturally into the relevant section prose.

```markdown
# Dashboard: <Title>

<One paragraph: what it monitors, who it is for, and why it matters.>

![<Title> dashboard overview](img/overview.png)

## <Section 1 Name>

![<Section 1 Name>](img/section-<name>.png)

<Open with the question(s) this section answers. Then describe tiles in narrative form,
explaining what each reveals and what action it drives. Use bullets only for compact
per-tile detail.>

## <Section 2 Name>

![<Section 2 Name>](img/section-<name>.png)

<Narrative prose ...>

  <!-- Embed close-up for a tile that needs it: -->
  ![<Tile name> close-up](img/<tile-name>.png)

## Dashboard Variables

| Variable    | Type  | Default | Description |
|-------------|-------|---------|-------------|
| `$Accounts` | query | all     | Filter by Snowflake account (`deployment.environment`) |
| `$<Other>`  | query | all     | <description> |

<One sentence on multi-select behaviour and typical filtering patterns.>

## Required Plugin(s)

<Which plugins must be enabled, what contexts they produce, collection cadence,
and data latency summary.>

## Known Limitations

- <Data gap, latency caveat, or deferred tile — one bullet per issue.>
- Reference telemetry issue IDs (e.g. TI-004) where applicable.
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
## Screenshot Checklist — <Dashboard Name>

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

Once the human drops the image files into `img/`, update `readme.md` to embed them
inline (replacing any placeholder table or comment) using `![alt](img/file.png)` at
the top of each relevant section, as described in the `readme.md` Structure above.

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

**Commit message rules:**

- Do **not** include ticket or issue numbers (e.g. `BDX-1234`, `JIRA-567`) in
  commit messages unless they are GitHub issue/PR numbers (e.g. `#83`).
- Do **not** open a pull request. After committing, push the branch and inform
  the human — PR creation is the human's responsibility.

---

## Implemented Use Cases — Final Summary

After the git commit and push, output a **Use Cases Summary** so the human can
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
