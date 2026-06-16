#!/usr/bin/env bash
#
#
# Copyright (c) 2025 Dynatrace Open Source
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#
# CI lint: validates all instruments-def.yml files for required semdict metadata.
#
# Fails (exit 1) if any entry is missing __description or __example.
# Warns (exit 0) if any metric entry is missing __unit.
# Warns (exit 0) if any entry with __semdict: ref is not in the known-refs list.
#
# Uses .venv/bin/python for YAML parsing (not raw grep).
#
# Usage:
#   ./scripts/dev/validate_semantics.sh [--warn-only]
#
# Options:
#   --warn-only   Downgrade FAIL to WARN (exit 0 even on missing __description/__example)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
WARN_ONLY=false

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --warn-only)
            WARN_ONLY=true
            shift
            ;;
        --help|-h)
            grep "^#" "${BASH_SOURCE[0]}" | grep -v "^#!" | sed 's/^# *//' | head -20
            exit 0
            ;;
        *)
            echo "[ERROR] Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Main validation via inline Python
# ---------------------------------------------------------------------------
WARN_ONLY_FLAG=""
if [[ "${WARN_ONLY}" == "true" ]]; then
    WARN_ONLY_FLAG="--warn-only"
fi

cd "${PROJECT_ROOT}"
PYTHONPATH="${PROJECT_ROOT}/src" "${VENV_PYTHON}" - "${WARN_ONLY_FLAG}" <<'PYEOF'
"""Validate instruments-def.yml files for CI."""
import sys
import yaml
from pathlib import Path

KNOWN_REFS = {
    "db.system",
    "host.name",
    "service.name",
    "telemetry.exporter.name",
    "telemetry.exporter.version",
    "db.query.text",
    "event.id",
    "authentication.type",
}

warn_only = "--warn-only" in sys.argv

repo_root = Path(__file__).resolve().parent if "__file__" in dir() else Path.cwd()
# Find repo root by locating pyproject.toml or setup.cfg
for candidate in [Path.cwd()] + list(Path.cwd().parents):
    if (candidate / "src").is_dir():
        repo_root = candidate
        break

fail_count = 0
warn_count = 0
file_count = 0


def emit(level, msg):
    """Print a log message and update counters."""
    global fail_count, warn_count  # pylint: disable=global-statement
    print(f"[{level}] {msg}", file=sys.stderr)
    if level == "FAIL":
        fail_count += 1
    elif level == "WARN":
        warn_count += 1


# Find all instruments-def.yml files
instruments_files = sorted(
    list(repo_root.glob("src/dtagent.conf/instruments-def.yml"))
    + list(repo_root.glob("src/dtagent/plugins/*.config/instruments-def.yml"))
)

if not instruments_files:
    emit("WARN", "No instruments-def.yml files found")
    sys.exit(0)

for file_path in instruments_files:
    file_count += 1
    print(f"[INFO] Checking {file_path.relative_to(repo_root)}...", file=sys.stderr)

    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception as exc:
        emit("FAIL", f"{file_path}: failed to parse YAML: {exc}")
        continue

    if not data:
        emit("WARN", f"{file_path}: empty file")
        continue

    for section in ("attributes", "dimensions", "metrics"):
        section_data = data.get(section) or {}
        for key, raw_entry in section_data.items():
            entry = raw_entry or {}

            # Required: __description
            if not entry.get("__description"):
                level = "WARN" if warn_only else "FAIL"
                emit(level, f"{file_path.name}::{section}.{key}: missing __description")

            # Required: __example (value 0 is allowed)
            if entry.get("__example") is None:
                level = "WARN" if warn_only else "FAIL"
                emit(level, f"{file_path.name}::{section}.{key}: missing __example")

            # Warn: metric without __unit or unit
            if section == "metrics":
                if not entry.get("__unit") and not entry.get("unit"):
                    emit("WARN", f"{file_path.name}::{section}.{key}: metric missing unit/__unit")

            # Warn: __semdict: ref but not in known refs
            semdict = entry.get("__semdict")
            if semdict == "ref" and key not in KNOWN_REFS:
                emit("WARN", f"{file_path.name}::{section}.{key}: __semdict: ref but not in KNOWN_REFS")


# Summary
print(f"[INFO] Checked {file_count} files", file=sys.stderr)
if fail_count > 0:
    print(f"[ERROR] Validation FAILED: {fail_count} error(s), {warn_count} warning(s)", file=sys.stderr)
    sys.exit(1)
elif warn_count > 0:
    print(f"[WARN] Validation passed with {warn_count} warning(s)", file=sys.stderr)
else:
    print("[INFO] Validation PASSED", file=sys.stderr)
PYEOF
