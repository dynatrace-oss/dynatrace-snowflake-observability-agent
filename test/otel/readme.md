# OpenTelemetry (OTel) Tests

This directory contains tests for the OpenTelemetry integration and telemetry functionality of Dynatrace Snowflake Observability Agent.

## Test Files

- `test_events.py`: Tests for business event handling and sending
- `test_otel_manager.py`: Tests for the OpenTelemetry manager and configuration

## Running Tests

```bash
# Run all OTel tests
pytest test/otel/

# Run specific test file
pytest test/otel/test_events.py

# Run with verbose output
pytest test/otel/ -v
```

## Test Categories

### Events Tests (`test_events.py`)

- Business event creation and formatting
- Event sending to Dynatrace APIs
- Event payload validation
- Error handling for event transmission

### OTel Manager Tests (`test_otel_manager.py`)

- OpenTelemetry manager initialization
- Configuration loading and validation
- Telemetry pipeline setup
- Metric and span handling

## Test Data

OTel tests use mock data and don't require live Dynatrace connections. Tests validate:

- Event payload structure
- API request formatting
- Configuration parameter handling
- Error scenarios and edge cases

## Dependencies

- `pytest` for test execution
- `pytest-mock` for API mocking
- OpenTelemetry Python packages
- Dynatrace API client libraries

## Configuration

OTel tests use configuration from:

- `src/dtagent.conf/otel-config.yml` for default settings
- Mock configurations for test scenarios
- Environment variable overrides where applicable
