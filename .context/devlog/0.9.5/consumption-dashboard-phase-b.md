# [0.9.5] — Snowflake Consumption Dashboard Phase B

## Dashboard Phase B: §1 Contract Capacity KPIs + §3 USD Consumption + Workflow Fix

**Scope**: Phase B of the org-level consumption dashboard. Appends tiles `"14"`–`"24"` to the
existing dashboard (UUID `6881ff48-0945-4e94-94af-2e4bb338724e`). Bumps version to 3.

**§1 Contract Capacity KPIs** (tiles 14–20, inserted at top via layout y=0..12):

- **Capacity Used (USD)** (tile 15, singleValue): `sum(snowflake.org.billing.amount)` over the
  selected timeframe. Uses `arraySum` to correctly total daily billing rows.
- **Remaining Capacity (USD)** (tile 16, singleValue): `last(capacity_balance) + last(rollover_balance)`.
  Uses `avg()` on both metrics (one row per org per day) then takes the last array value.
- **30-Day Run Rate (USD)** (tile 17, singleValue): `sum(billing.amount)` with explicit `from: now()-30d`
  to pin the window regardless of the dashboard timeframe selector.
- **YoY Burn Rate** (tile 18, table): Two `timeseries` pipes (current 30d and previous 30d) combined
  via `append` + `summarize` to produce `current_usd`, `previous_usd`, annualized run rates, and
  `pct_change`. DQL `join` across time windows is not supported, so `append` + aggregate is used.
- **Estimated Days to Overage** (tile 19, singleValue): Derived from 30-day balance burn:
  `balance_end / monthly_burn * 30`. Returns `-1` when burn rate is zero or negative (balance growing).
- **Projected Overage Date** (tile 20, table): Computes `days_to_overage` then formats as a timestamp
  string using `formatTimestamp(now() + toTimespan(...))`. Returns "No overage projected" when
  days_to_overage ≤ 0.

**§3 USD Consumption** (tiles 21–24, inserted after §2 at y=26..39):

- Markdown header tile (21) includes the credit-rate fallback note inline.
- Line chart (22): `billing.amount` by account over time.
- Bar chart (23): `billing.amount` summarized by service type.
- Table (24): total USD per account using `arraySum` (not `arrayAvg`) because billing rows are
  daily totals that should be summed, not averaged.

**Workflow fix** (`docs/workflows/org-contract-balance-warning/org-contract-balance-warning.yml`):
Replaced five non-existent `snowflake.org.balance.*.remaining` metric IDs with the real keys:
`snowflake.org.billing.free_usage_balance`, `capacity_balance`, `on_demand_consumption`,
`rollover_balance`, `overage`. Updated `metricsClient.query` selector from `:last` to `:avg:last`
to match the `avg()` aggregation used in the dashboard (one row per org per day).

**Layout strategy**: New §1 tiles use keys `"14"`–`"20"` at y=0..12. Existing §2 tiles (`"0"`–`"3"`)
shift to y=13..25. New §3 tiles use keys `"21"`–`"24"` at y=26..39. Existing §4–§6 tiles shift
accordingly. No tile keys were renumbered — only layout `y` coordinates changed.
