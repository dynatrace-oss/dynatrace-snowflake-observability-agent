import subprocess
import pytest


def test_bash_scripts():
    """Run all bash script tests using Bats framework."""
    result = subprocess.run(["./test/bash/run_tests.sh"], capture_output=True, text=True, cwd=".", check=False)

    # Print output for debugging (only on failure)
    if result.returncode != 0:
        print("STDOUT:")
        print(result.stdout)
        print("STDERR:")
        print(result.stderr)

    # Check that the command succeeded
    assert result.returncode == 0, f"Bash tests failed with return code {result.returncode}"

    # Verify that we got some test output (basic sanity check)
    assert "ok" in result.stdout, "Expected test results in output"
