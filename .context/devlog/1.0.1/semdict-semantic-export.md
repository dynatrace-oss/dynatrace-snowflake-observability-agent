# Semantic Dictionary Export Pipeline (Structural Rewrite)

## Problem Statement

The initial implementation of `export_semantics.py` produced structurally incorrect output.
Research of actual SD source files revealed fundamental errors:

1. All fields were emitted into a single flat `snowflake_global.yaml` file, not split by
   resource/signal classification.
2. Metrics used `type: metric_group` + flat `type: metric` groups — not the SD-required
   `model:` envelope with `interfaces:` declaration.
3. No support for interface abstraction (`i.dsoa_resource`, `i.dsoa_warehouse`, `i.dsoa_database`).
4. No enum emission — categorical fields emitted `type: string` instead of `type: {allow_custom_values, members}`.
5. `event_timestamps` section ignored — no event lifecycle models produced.
6. Fields were not classified by source section (dimensions → resource; attributes → signal).

## Rewrite Summary

### New output structure

```
build/_semdict/source/
├── fields/
│   ├── resource_fields/
│   │   ├── snowflake_resource.yaml   # dimensions + __field_type:resource attributes
│   │   │                              # grouped by namespace prefix (≥3 groups)
│   │   └── dsoa.yaml                 # DSOA execution metadata (dsoa.run.*, deployment.*)
│   └── signal_fields/
│       └── snowflake.yaml            # attributes + __field_type:signal dimensions
│                                     # grouped by namespace prefix (≥10 groups)
├── metrics/
│   ├── interfaces_dsoa.yaml          # i.dsoa_resource / i.dsoa_warehouse / i.dsoa_database
│   ├── dsoa_metrics_model_group.yaml # model_group: dsoa.metrics
│   └── dsoa_metrics_<plugin>.yaml    # one per plugin, model: envelope + interfaces
└── model/
    └── dsoa/
        ├── model_group_dsoa_events.yaml
        └── dsoa.events.<plugin>.yaml  # one per plugin with event_timestamps
```

### Field classification rules

| instruments-def section | `__field_type` | SD output    |
|-------------------------|----------------|--------------|
| `dimensions`            | (absent)       | resource     |
| `dimensions`            | `signal`       | signal       |
| `attributes`            | (absent)       | signal       |
| `attributes`            | `resource`     | resource     |
| `metrics`               | any            | metric model |
| `event_timestamps`      | any            | event model  |

### New instrument-def annotations added

**`__field_type` overrides** (bidirectional classification override):

- `__field_type: signal` added to `snowflake.warehouse.event.name`,
  `snowflake.warehouse.event.state` — they describe events, not resources.
- `__field_type: resource` added to warehouse resource identifiers:
  `snowflake.warehouse.size`, `snowflake.warehouse.type`, `snowflake.warehouse.id`,
  `snowflake.warehouse.cluster.number`, `snowflake.warehouse.clusters.count`,
  `snowflake.warehouse.execution_state`, `snowflake.warehouse.has_query_acceleration_enabled`,
  `snowflake.warehouse.is_auto_resume`, `snowflake.warehouse.is_auto_suspend`,
  `snowflake.warehouse.owner`, `snowflake.warehouse.owner.role_type`,
  `snowflake.warehouse.scaling_policy`, `snowflake.resource_monitor.frequency`,
  `snowflake.resource_monitor.level`.

**`__enum` definitions** added to ~16 categorical fields:

- `snowflake.warehouse.event.name` — WAREHOUSE_START/SUSPEND/RESUME/RESIZE_WAREHOUSE
- `snowflake.warehouse.event.state` — STARTED/COMPLETED/FAILED
- `snowflake.warehouse.event.reason` — USER_REQUEST/AUTO_SUSPEND/AUTO_RESUME/SCHEDULER
- `snowflake.warehouse.size` — X-SMALL through 6X-LARGE
- `snowflake.warehouse.type` — STANDARD/SNOWPARK_OPTIMIZED
- `snowflake.warehouse.scaling_policy` — STANDARD/ECONOMY
- `snowflake.warehouse.execution_state` — RUNNING/SUSPENDED/RESUMING/SUSPENDING/STARTED
- `snowflake.resource_monitor.level` — ACCOUNT/WAREHOUSE (allow_custom_values: false)
- `snowflake.resource_monitor.frequency` — DAILY/WEEKLY/MONTHLY/YEARLY/NEVER
- `snowflake.query.execution_status` — SUCCESS/FAIL/INCIDENT_QUEUE
- `snowflake.user.type` — PERSON/SERVICE/LEGACY_SERVICE/SNOWFLAKE_SERVICE (in query_history + users)
- `snowflake.object.type` — Table/View/Schema/Database/Procedure
- `snowflake.object.ddl.operation` — CREATE/ALTER/DROP/UNDROP/REPLACE
- `db.operation.name` — SELECT/INSERT/UPDATE/DELETE/MERGE/CREATE/ALTER/DROP/GRANT/REVOKE/CALL/COPY/PUT/GET
- `snowflake.table.type` — BASE TABLE/TEMPORARY TABLE/EXTERNAL TABLE/VIEW/MATERIALIZED VIEW

### Interface and model structure

**`interfaces_dsoa.yaml`** defines:

- `i.dsoa_resource`: 10 keys synced with `config.py RESOURCE_ATTRIBUTES`
- `i.dsoa_warehouse`: snowflake.warehouse.name + snowflake.warehouse.id
- `i.dsoa_database`: db.namespace + snowflake.schema.name

**Metric model files**: `model:` envelope with `interfaces:` list + per-metric
`attributes:` resolved via `__context_names` overlap, excluding interface-covered dims.

**Event model files**: one per plugin that has `event_timestamps`; excludes `snowflake.event.trigger`
(the trigger key) from the event model attributes list.

## Key Technical Decisions

### Deduplication and context_names matching
Fields appearing in multiple plugins are de-duplicated at parse time (first occurrence wins).
Dimension → metric context matching uses `__context_names` overlap: a dim with no
`__context_names` is treated as globally applicable; a dim with context_names must have at
least one overlap with the metric's context_names to appear in the metric's attributes list.

### Namespace grouping
Both resource and signal field files group by namespace prefix within a single file. This
makes the semantic structure clear while keeping future per-file splitting trivial.

### `__type` missing on many metrics
~130 metrics across plugins default to `gauge` instrument because they lack `__type`.
This is pre-existing debt. A follow-up should annotate all metrics with explicit `__type`.

## Files Created/Modified

| File                                                               | Change                                           |
|--------------------------------------------------------------------|--------------------------------------------------|
| `src/build/export_semantics.py`                                    | REWRITTEN — 938 lines, pylint 10.00/10           |
| `test/core/test_export_semantics.py`                               | REWRITTEN — 83 tests                             |
| `test/test_data/instruments-def-mock.yml`                          | EXTENDED — __field_type,__enum, event_timestamps |
| `src/dtagent/plugins/warehouse_usage.config/instruments-def.yml`   | `__field_type` + `__enum` annotations            |
| `src/dtagent/plugins/resource_monitors.config/instruments-def.yml` | `__field_type` + `__enum` annotations            |
| `src/dtagent/plugins/query_history.config/instruments-def.yml`     | `__enum` annotations                             |
| `src/dtagent/plugins/data_volume.config/instruments-def.yml`       | `__enum` annotation (table.type)                 |
| `src/dtagent/plugins/users.config/instruments-def.yml`             | `__enum` annotation (user.type)                  |
| `docs/CHANGELOG.md`                                                | Added rewrite entry                              |

## Test Results

83 tests pass (previously 42). New test classes:

- `TestFieldClassification` — 6 tests for `_classify_field`
- `TestNamespaceGrouping` — 4 tests for `_ns_group`
- `TestEnumEmission` — 5 tests for `_build_type_node` and enum in `_emit_id_entry`
- `TestExportPipelineMock` — 11 integration tests against mock fixture
- `TestSemanticExporterIntegration` — 14 tests against real codebase
  (15 integration tests, replaces old 5 tests)
