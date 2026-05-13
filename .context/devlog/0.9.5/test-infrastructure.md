# Test Infrastructure — Technical Details

## Resource.attributes Included in Protobuf Baseline Comparison

- **Root cause**: `_decode_object_from_protobuf` in `test/_mocks/telemetry.py` iterated
  `resource_logs`/`resource_spans` entries and extracted only record-level and scope-level attributes.
  The `resource.resource.attributes` block on each entry was never accessed, so `db.system`,
  `service.name`, `deployment.environment`, `host.name`, and all `telemetry.*` / `telemetry.sdk.*`
  resource attributes were silently discarded. Tests could pass even if these fields were missing
  or incorrect in exported telemetry.
- **Fix**: Before iterating scope entries, the decoder now reads `resource.resource.attributes`
  (guarded for `None`) and stores them as a `"resource_attributes"` key on every decoded record dict.
  The existing `__cleanup_telemetry_dict` already recurses into nested dicts and already strips
  `telemetry.exporter.version` — no changes to the cleanup function were needed.
- **Baseline update strategy**: Golden baselines (`test/test_results/**/logs.json` and
  `test/test_results/**/spans.json`) cannot be regenerated without a live Snowflake connection
  (see `docs/CONTRIBUTING.md`). All 33 affected files were updated programmatically to inject a
  stable `resource_attributes` block. The injected values match the deterministic test config in
  `test/_utils.py` (`sf_name = "test.dsoa2025"`, `deployment.environment = "TEST"`) plus the
  OTel SDK auto-populated attributes (`telemetry.sdk.*`). The OTel SDK is pinned to `1.39.1`
  in `requirements.txt`, so `telemetry.sdk.version` is stable across environments.
- **Mutation coverage verified**: Changing `db.system` from `"snowflake"` to `"mysql"` in one
  baseline causes the corresponding test to fail, confirming the new key is actively asserted.
- **Files changed**: `test/_mocks/telemetry.py`, all 30 `logs.json` + 3 `spans.json` baselines.
