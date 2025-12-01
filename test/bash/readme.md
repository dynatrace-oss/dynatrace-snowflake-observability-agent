# Bash Unit Tests

This directory contains unit tests for bash scripts in the main project directory.

## Requirements

- [Bats](https://github.com/bats-core/bats-core) - Bash Automated Testing System

Install Bats with:

```bash
brew install bats-core
```

## Running Tests

### Command Line

Run all tests:

```bash
./test/bash/run_tests.sh
```

Run a specific test file:

```bash
bats test/bash/test_script.bats
```

### VS Code

**Test Explorer Integration:**
The bash tests are now integrated into VS Code's Test Explorer! You'll see a test called `test_bash_scripts` in the test list alongside your Python tests.

- **Test Explorer**: The bash tests appear as `test_bash_scripts` in the Test Explorer view
- **Run/Debug**: Click the play button next to `test_bash_scripts` to run all bash tests
- **Command Palette**: `Ctrl+Shift+P` → "Tasks: Run Task" → "test bash" (alternative method)

### GitHub Actions

Bash tests are automatically run in CI as part of the `test-bash` job in `.github/workflows/ci.yml`, and also as part of the `test-core` job (via the Python wrapper).

## Test Structure

Each test file `test_script.bats` tests the corresponding `script.sh`.

Tests use temporary files and mock environments to isolate the scripts.
