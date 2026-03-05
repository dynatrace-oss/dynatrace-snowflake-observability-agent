# Core Tests

This directory contains tests for the core functionality of Dynatrace Snowflake Observability Agent.

## Test Files

- `test_config.py`: Tests for configuration loading, validation, and management
- `test_util.py`: Tests for utility functions and helpers
- `test_views_structure.py`: Tests for database view structure validation
- `test_connector.py`: Tests for telemetry connector functionality
- `test_bash_scripts.py`: Integration test that runs all bash script tests

## Running Tests

```bash
# Run all core tests
pytest test/core/

# Run specific test file
pytest test/core/test_config.py

# Run with verbose output
pytest test/core/ -v
```

## Test Categories

### Configuration Tests (`test_config.py`)

- Configuration file loading and parsing
- Environment variable handling
- Configuration validation
- Safe configuration for live testing

### Utility Tests (`test_util.py`)

- Helper functions and utilities
- Data processing functions
- Common utilities used across the codebase

### Views Structure Tests (`test_views_structure.py`)

- Database view definitions validation
- Schema structure testing
- View creation and modification tests

### Connector Tests (`test_connector.py`)

- Telemetry sending functionality
- API integration testing
- Connection handling

### Bash Integration Tests (`test_bash_scripts.py`)

- Runs all bash script tests using Bats framework
- Ensures bash scripts work correctly
- Integration point for bash test suite in VS Code Test Explorer

## Test Data

Core tests use mock data and don't require live Snowflake or Dynatrace connections. Some tests may use data from `test/test_data/` for validation.

## Dependencies

- `pytest` for test execution
- `pytest-mock` for mocking
- Bats framework (for bash script testing)
