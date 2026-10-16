## ADDED Requirements

### Requirement: Deterministic CloudEvents ID and Null Stripping in `BizEvents`
`BizEvents._pack_event_data()` SHALL preserve a caller-supplied `event.id` or `id` in the CloudEvents top-level `id` attribute and strip `None` values from event data before packing.

#### Scenario: Preserving deterministic `event.id` in CloudEvents envelope

- **WHEN** `BizEvents._pack_event_data()` is called with `event_data` containing `"event.id": "abc123..."`
- **THEN** the returned CloudEvent dictionary has top-level `"id": "abc123..."` instead of a random UUID, while retaining `"event.id": "abc123..."` in `"data"`.

#### Scenario: Stripping `None` values from BizEvent payload

- **WHEN** `BizEvents._pack_event_data()` is called with `event_data` containing keys with `None` values (such as nullable SQL columns)
- **THEN** keys with `None` values are omitted from the packed `"data"` dictionary.

### Requirement: `decimal.Decimal` Serialization in `_cleanup_data` and `_cleanup_dict`
`_cleanup_data()` and `_cleanup_dict()` in `src/dtagent/util.py` SHALL convert Python `decimal.Decimal` instances to native `int` (when integral with zero scale) or `float` so that Snowpark `NUMBER(38,9)` values serialize as native JSON numbers.

#### Scenario: Cleaning `Decimal` values from Snowpark rows

- **WHEN** `_cleanup_data()` or `_cleanup_dict()` processes a dictionary containing `Decimal("31.250000000")`
- **THEN** the value is converted to `float` `31.25` and `json.dumps()` succeeds without raising `TypeError`.

### Requirement: First-Class `biz_events` Routing in `Plugin._log_entries` and Test Harness
`Plugin._log_entries()` and `test/_utils.py::execute_telemetry_test()` SHALL support `biz_events` as a primary plugin telemetry channel.

#### Scenario: Plugin execution with `biz_events` enabled and disabled

- **WHEN** a plugin using `_report_via_bizevents` runs across `disabled_telemetry` combinations `[]`, `["biz_events"]`, `["logs"]`, and `["logs", "spans", "metrics", "events", "biz_events"]`
- **THEN** `biz_events` are emitted and flushed when `"biz_events"` is enabled, suppressed when `"biz_events"` is disabled, and `dsoa.run.results.<context>.biz_events` accurately reports the count of emitted business events.
