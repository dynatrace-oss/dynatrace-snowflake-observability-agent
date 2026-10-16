## ADDED Requirements

### Requirement: Semantic Dictionary Provenance and Schema Support for `real.costs` and `snowflake.x_*`
The DSOA Semantic Dictionary exporter and `instruments-def.schema.json` SHALL support `bizevents` DQL query contexts, the `FOCUS` acronym, `__semdict: ref` references to existing `real.costs` fields, and `__semdict: new` definitions for `snowflake.x_*` and FOCUS v1.3 fields.

#### Scenario: Validating `instruments-def.yml` for `focus_costs`

- **WHEN** `pytest test/core/test_instruments_def_schema.py test/core/test_instruments_def_completeness.py` runs
- **THEN** all 33 pre-existing `focus.*` fields and envelope fields (`event.type`, `event.provider`, `event.start`, `event.end`, `cloud.provider`, `price.total.granularity`, `focus.spec.version`) pass `TestSemdicRefProvenance`, `FOCUS` passes `TestDisplayNameCasing`, and `dql_queries` with `context: ["bizevents"]` pass schema validation.

#### Scenario: Exporting `snowflake.x_*` and FOCUS 1.3 fields to Semantic Dictionary YAML

- **WHEN** `./scripts/dev/build_semantic_export.sh` runs
- **THEN** `snowflake.x_UpdatedAt`, `snowflake.x_OrganizationName`, `snowflake.x_ServiceLevel`, `snowflake.x_BalanceSource`, `snowflake.x_ContractCommitCostBalance`, `focus.HostProviderName`, and `focus.ContractApplied` are exported without schema or orphan-field violations.
