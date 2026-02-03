import subprocess
import pytest
from pathlib import Path
from tap.parser import Parser
from tap.line import Result


# Discover all bats test files
BATS_DIR = Path(__file__).parent.parent / "bash"
BATS_FILES = sorted(BATS_DIR.glob("*.bats"))


@pytest.mark.parametrize("bats_file", BATS_FILES, ids=[f.stem for f in BATS_FILES])
def test_bash_script(bats_file):
    """Run individual bash script test file using Bats framework.

    Uses pytest-tap to parse TAP output and report individual test cases.
    """
    result = subprocess.run(["bats", str(bats_file)], capture_output=True, text=True, check=False)

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
