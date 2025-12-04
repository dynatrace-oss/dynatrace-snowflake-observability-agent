# Dynatrace Snowflake Observability Agent Tests

This directory contains comprehensive test suites for Dynatrace Snowflake Observability Agent, covering all aspects of the codebase from core functionality to individual plugins.

## Test Suite Overview

### 🏗️ Core Tests (`test/core/`)
Tests for core functionality, configuration management, utilities, and database structures.

**Key areas:**

- Configuration loading and validation
- Utility functions and helpers
- Database view structure validation
- Telemetry connector functionality
- Bash script integration testing

### 📊 OpenTelemetry Tests (`test/otel/`)
Tests for OpenTelemetry integration and telemetry functionality.

**Key areas:**

- Business event handling and sending
- OpenTelemetry manager configuration
- Telemetry pipeline setup
- Metric and span processing

### 🔌 Plugin Tests (`test/plugins/`)
Tests for individual monitoring plugins.

**Key areas:**

- Active queries monitoring
- Budget and cost tracking
- Data schema and volume analysis
- Dynamic table monitoring
- Event log and usage tracking
- Login history monitoring
- Query history analysis
- Resource monitor tracking
- Share monitoring
- Task monitoring
- Trust center validation
- User monitoring
- Warehouse usage tracking

### 🐚 Bash Script Tests (`test/bash/`)
Tests for bash scripts using the Bats framework.

**Key areas:**

- Build and compilation scripts
- Configuration processing
- Deployment preparation
- SQL script generation
- Utility scripts

## Running Tests

### All Tests at Once

```bash
# Run all Python tests
pytest

# Run all bash tests
./test/bash/run_tests.sh

# Run everything (requires VS Code Test Explorer or custom script)
```

### Individual Test Suites

```bash
# Core tests
pytest test/core/

# OTel tests
pytest test/otel/

# Plugin tests
pytest test/plugins/

# Bash tests
./test/bash/run_tests.sh
```

### VS Code Integration

- **Test Explorer**: All Python tests + bash tests appear in VS Code's Test Explorer
- **Run Task**: Use "test bash" task for bash-specific testing
- **Debug**: Individual tests can be debugged directly from the Test Explorer

## Test Execution Modes

### Local Mode (Default)

- Uses mocked APIs and test data
- No live Snowflake/Dynatrace connections required
- Fast execution, suitable for development

### Live Mode

- Requires `test/credentials.yaml` configuration
- Connects to actual Snowflake and Dynatrace environments
- Sends real telemetry data
- Useful for end-to-end validation

## Test Data Management

### Regenerating Plugin Test Data

```bash
# Single plugin
./test.sh test_plugin_name -p

# All plugins
./test.sh -a -p
```

### Test Data Locations

- **Input data**: `test/test_data/` (pickle files)
- **Expected results**: `test/test_results/` (text files)
- **Reference data**: NDJSON files for inspection

## Dependencies

### Python Packages

- `pytest` - Test framework
- `pytest-mock` - Mocking utilities
- OpenTelemetry packages
- Snowflake connectors

### System Dependencies

- `bats` - Bash testing framework
- `jq` - JSON processor (for bash tests)

## Configuration

### Test Environment Setup

1. Copy `test/credentials.template.yaml` to `test/credentials.yaml` (for live mode)
2. Generate config: `pytest test/core/test_config.py::TestConfig::test_init --pickle_conf y`
3. Run tests in local mode (recommended for development)

### CI/CD Integration

Tests run automatically in GitHub Actions:

- **test-bash**: Bash script validation
- **test-core**: Core functionality tests
- **test-otel**: OpenTelemetry tests
- **test-plugins**: Plugin functionality tests

## Contributing

When adding new functionality:

1. **Core changes**: Add tests to `test/core/`
2. **OTel changes**: Add tests to `test/otel/`
3. **New plugins**: Create `test/plugins/test_new_plugin.py`
4. **Bash scripts**: Add tests to `test/bash/`
5. **Regenerate test data** for any data collection changes

See individual README files in each test directory for detailed information.
