"""Pytest runner that executes each bats test file as a single parametrized test."""

import os
import shutil
import subprocess
import tempfile
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
# /opt/homebrew/bin may not be in the subprocess PATH inherited by pytest, e.g. when
# launched from an IDE test runner that doesn't source the user's shell profile)
BATS_EXECUTABLE = shutil.which("bats") or next(
    (p for p in ("/opt/homebrew/bin/bats", "/usr/local/bin/bats") if os.path.isfile(p)),
    None,
)


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
    # Ensure Homebrew bin dirs are on PATH for the bats subprocess and anything it
    # shells out to (e.g. `timeout`, `gsed`), since IDE test runners may inherit a
    # sparse PATH that doesn't include them.
    homebrew_bins = [p for p in ("/opt/homebrew/bin", "/usr/local/bin") if os.path.isdir(p)]
    existing_path_entries = env.get("PATH", "").split(os.pathsep)
    env["PATH"] = os.pathsep.join(dict.fromkeys(homebrew_bins + existing_path_entries))
    if run_slow and _is_slow(bats_file):
        env["BATS_SLOW_TESTS"] = "1"

    # On macOS, mktemp ignores $TMPDIR and uses the system confdir (/var/folders/…),
    # which sandbox environments may not allow. Inject a wrapper that forces -p $TMPDIR
    # so temp files land in the sandbox-writable $TMPDIR.
    # Only adds -p when there is no positional template argument (e.g. bats itself calls
    # mktemp -d "/path/template.XXXX" which must not get an extra -p prepended).
    wrapper_dir = tempfile.mkdtemp()
    try:
        wrapper_script = os.path.join(wrapper_dir, "mktemp")
        with open(wrapper_script, "w", encoding="utf-8") as f:
            f.write(
                "#!/bin/bash\n"
                "_has_p=0; _has_template=0; _skip_next=0\n"
                'for _a in "$@"; do\n'
                "    if [[ $_skip_next -eq 1 ]]; then _skip_next=0; continue; fi\n"
                '    if [[ "$_a" == "-p" ]]; then _has_p=1; _skip_next=1; continue; fi\n'
                '    if [[ "$_a" != -* ]]; then _has_template=1; fi\n'
                "done\n"
                'if [[ $_has_p -eq 0 && $_has_template -eq 0 && -n "${TMPDIR}" && -d "${TMPDIR}" ]]; then\n'
                '    exec /usr/bin/mktemp -p "${TMPDIR}" "$@"\n'
                "fi\n"
                'exec /usr/bin/mktemp "$@"\n'
            )
        os.chmod(wrapper_script, 0o755)
        env["PATH"] = wrapper_dir + os.pathsep + env["PATH"]

        result = subprocess.run(
            [BATS_EXECUTABLE, str(bats_file)],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        shutil.rmtree(wrapper_dir, ignore_errors=True)

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
        if result.stdout:
            failure_msg += f"\nSTDOUT:\n{result.stdout}"
        if result.stderr:
            failure_msg += f"\nSTDERR:\n{result.stderr}"
        pytest.fail(failure_msg)

    # Verify bats command succeeded
    if result.returncode != 0:
        pytest.fail(f"Bats failed with exit code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
