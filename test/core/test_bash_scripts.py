import os
import shutil
import subprocess
import pytest
from pathlib import Path
from tap.parser import Parser
from tap.line import Result

# Discover all bats test files
BATS_DIR = Path(__file__).parent.parent / "bash"
BATS_FILES = sorted(BATS_DIR.glob("*.bats"))

# Bats files that contain slow build/package integration tests
SLOW_BATS_FILES = {"test_build_scripts"}

# Resolve bats executable path once at import time (handles Homebrew on macOS where
# /opt/homebrew/bin may not be in the subprocess PATH inherited by pytest)
BATS_EXECUTABLE = shutil.which("bats")


def _is_slow(bats_file: Path) -> bool:
    return bats_file.stem in SLOW_BATS_FILES


@pytest.mark.parametrize("bats_file", BATS_FILES, ids=[f.stem for f in BATS_FILES])
def test_bash_script(request, bats_file):
    """Run individual bash script test file using Bats framework.

    Uses pytest-tap to parse TAP output and report individual test cases.
    Slow build/package integration tests (test_build_scripts) are skipped by
    default; pass --run-slow to include them.
    """
    if not BATS_EXECUTABLE:
        pytest.skip("bats not found in PATH — install via 'brew install bats-core' or 'npm install -g bats'")

    run_slow = request.config.getoption("--run-slow", default=False)
    if _is_slow(bats_file) and not run_slow:
        pytest.skip("slow build/package integration test — pass --run-slow to enable")

    env = os.environ.copy()
    if run_slow and _is_slow(bats_file):
        env["BATS_SLOW_TESTS"] = "1"

    result = subprocess.run(
        [BATS_EXECUTABLE, str(bats_file)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    # Parse TAP output using pytest-tap
    parser = Parser()

    failed_tests = []
    for line in parser.parse_text(result.stdout):
        if isinstance(line, Result) and not line.ok:
            failed_tests.append(line)

    # Report failures
    if failed_tests:
        failure_msg = f"{len(failed_tests)} test(s) failed in {bats_file.name}:\n"
        for test in failed_tests:
            failure_msg += f"\n  ✗ {test.description}\n"
            if test.directive:
                failure_msg += f"    Directive: {test.directive.text}\n"
        if result.stderr:
            failure_msg += f"\nSTDERR:\n{result.stderr}"
        pytest.fail(failure_msg)

    # Verify bats command succeeded
    if result.returncode != 0:
        pytest.fail(f"Bats failed with exit code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
