# [0.9.5] — Snowflake Consumption Dashboard Phase C

## Dashboard: §7 Department / BU View

**Scope**: Phase C of the org-level consumption dashboard. Appends §7 Department / BU View
(tiles "25"–"29") to `docs/dashboards/org-costs-observability/org-costs-observability.yml`.
Coordinates with Phase B (tiles "14"–"24") which landed concurrently.

**Changes**:

- **§7 Department / BU View** (5 tiles):
  - Markdown header with inline usage note for `$bu_mapping` variable.
  - Bar chart: credits by account (`snowflake.org.credits.used`, summarized, `bu = "Unassigned"`).
  - Bar chart: USD billing by account (`snowflake.org.billing.amount`, `arraySum`, `bu = "Unassigned"`).
  - Bar chart: storage by account (`snowflake.org.storage.bytes`, avg, bytes `unitsOverrides`, `bu = "Unassigned"`).
  - Table: account-to-BU mapping view (account + bu columns, sorted by account).
- **Layout**: tiles placed at y=67–81 (after §6 Billing at y=60–67). Three bar charts side-by-side
  (8 cols each), table full-width below.
- **`readme.md`** updated: §7 tile inventory table added; BU Mapping Configuration section added
  with JSON format, example, and v1 limitation note.

## v1 BU mapping design decision

DQL does not support dynamic JSON key-indexing against a variable string at query time. The
`$bu_mapping` variable holds a JSON object `{"ACCOUNT": "BU"}`, but there is no native DQL
operator to look up a field value as a key in that JSON at runtime. Options considered:

1. **Hardcoded `if/matchesRegex` chain** — requires dashboard edits per customer; not scalable.
2. **Grail lookup tables** — not yet available in DSOA's target tenant tier; planned for a
   future release.
3. **`fieldsAdd bu = "Unassigned"` (chosen for v1)** — all accounts show as "Unassigned" by
   default. Customers who need BU grouping can use the `$bu_mapping` variable as documentation
   of intent and wait for the lookup-table enhancement, or apply OpenPipeline enrichment rules
   externally to add a `bu` attribute to the metric data.

The `$bu_mapping` variable is retained in the dashboard as a placeholder and configuration
anchor. Pattern-based mapping (SQL LIKE / regex) is tracked as a future enhancement.
