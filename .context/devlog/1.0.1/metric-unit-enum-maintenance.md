# metric-unit-enum-maintenance — how the MetricUnit enum is kept in sync

## What

`scripts/tools/instruments-def.schema.json`'s `$defs/MetricUnit` enum enumerates every
value DSOA is allowed to send as `dt.meta.unit` to the Dynatrace Metrics API. It tracks
the recognized `universal-units` UCUM vocabulary plus a small DSOA allowlist of
domain-specific free-text nouns (credits, currency, files, partitions, rows, clusters,
warehouses, queries).

## Maintenance

This enum is maintained by Dynatrace-internal tooling and regenerated whenever the
recognized `dt.meta.unit` vocabulary changes. Dynatrace engineers: use the internal
`dsoa-units-sync` skill to regenerate it.

After regenerating, review the printed UCUM-vs-Semantic-Dictionary divergences and
update `UNIT_MAP` in `src/build/semantic_exporter/` if a new divergence needs an
explicit translation for the Semantic Dictionary export.

## Note

`instruments-def.schema.json` is the only file that changes as part of this process —
no other snowagent files are involved.
