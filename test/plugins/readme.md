# Plugin Tests

This directory contains tests for individual plugins in Dynatrace Snowflake Observability Agent.

## Test Files

Each plugin has a corresponding test file following the pattern `test_*.py`. Current plugin tests include:

- `test_active_queries.py`: Tests for active queries monitoring
- `test_budgets.py`: Tests for budget monitoring
- `test_data_schemas.py`: Tests for data schema monitoring
- `test_data_volume.py`: Tests for data volume monitoring
- `test_dynamic_tables.py`: Tests for dynamic table monitoring
- `test_event_log.py`: Tests for event log monitoring
- `test_event_usage.py`: Tests for event usage monitoring
- `test_login_history.py`: Tests for login history monitoring
- `test_query_history.py`: Tests for query history monitoring
- `test_resource_monitors.py`: Tests for resource monitor tracking
- `test_shares.py`: Tests for share monitoring
- `test_tasks.py`: Tests for task monitoring
- `test_trust_center.py`: Tests for trust center monitoring
- `test_users.py`: Tests for user monitoring
- `test_warehouse_usage.py`: Tests for warehouse usage monitoring

## Running Tests

```bash
# Run all plugin tests
pytest test/plugins/

# Run specific plugin test
pytest test/plugins/test_active_queries.py

# Run with verbose output
pytest test/plugins/ -v

# Run using the legacy test script
./test.sh test_active_queries
```

## Test Execution Modes

Plugin tests support two execution modes:

### 1. Local Mode (Mocked APIs)

- Runs without live Snowflake/Dynatrace connections
- Uses pickled test data from `test/test_data/`
- Validates against expected results in `test/test_results/`
- **Default mode** when `test/credentials.yml` is not present

### 2. Live Mode (Actual APIs)

- Requires `test/credentials.yml` to be present
- Connects to actual Snowflake and Dynatrace environments
- Sends real telemetry data
- Useful for end-to-end validation

## Test Data Management

### Regenerating Test Data
When adding new plugins or changing data collection logic:

```bash
# Regenerate test data for a specific plugin
./test.sh test_plugin_name -p

# Regenerate all plugin test data
./test.sh -a -p
```

This creates new pickle files in `test/test_data/` and result files in `test/test_results/`.

### Test Data Structure

- **Input data**: Pickle files (`.pkl`) in `test/test_data/`
- **Expected results**: Text files in `test/test_results/`
- **Reference data**: NDJSON files for human-readable inspection

## Plugin Test Structure

Each plugin test typically includes:

1. **Setup**: Mock configuration and dependencies
2. **Data loading**: Load test data from pickle files
3. **Execution**: Run plugin logic with test data
4. **Validation**: Compare results against expected output
5. **Teardown**: Clean up mock objects

## Dependencies

- `pytest` for test execution
- `pytest-mock` for API and dependency mocking
- Plugin-specific dependencies (Snowflake connectors, etc.)
- Bats framework (for bash script testing integration)

## Configuration

Plugin tests use:

- Default plugin configurations from `src/dtagent.conf/`
- Test-specific overrides in `test/conf/`
- Environment variables for live testing mode
