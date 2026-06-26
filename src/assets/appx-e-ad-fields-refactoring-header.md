<a name="appendix-e-sec"></a>

## Appendix E: Migrating anomaly-detection field names to version 1.0.0 or higher

Version 1.0.0 renames the four `ad.*` event properties emitted by DSOA anomaly-detection
workflows to Semantic Dictionary-aligned names. The `ad.source` field is additionally
renamed in the `login_history` plugin (the source value `snowflake_security` becomes
`dsoa.failed_login_detection`; all other `anomaly.detector` values are unchanged).

To update existing dashboards, workflows, notebooks, or other Dynatrace assets that
reference the old field names, run the `refactor_field_names.sh` script included in the
package with the `appx-e-ad-fields-refactoring.csv` mapping file:

```bash
./scripts/deploy/refactor_field_names.sh appx-e-ad-fields-refactoring.csv <exported-assets-folder>
```

For DQL queries that filter on the old field names, update them manually. Example migration:

```dql
// Before
| filter isNotNull(`ad.source`) | filter `ad.source` == "dsoa.data_volume_anomaly"
// After
| filter isNotNull(`anomaly.detector`) | filter `anomaly.detector` == "dsoa.data_volume_anomaly"
```

The table below lists the four field renames.

### Field Name Mapping

| old name | new name |
|----------|----------|
