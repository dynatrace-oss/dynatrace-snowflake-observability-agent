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
"""Keep test/qa/fixtures/all_metrics_ingest_payload.txt in sync with instruments-def.yml.

This test does NOT call the network — it only regenerates the fixture content
in-memory via scripts/dev/gen_metric_fixture.py and diffs it against the
checked-in file. The live unit-recognition check that actually POSTs this
fixture to a Dynatrace tenant lives in scripts/test/verify_metric_units.sh
and is run manually by a QA engineer (see .opencode/skills/qa-runner/SKILL.md).
"""

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GENERATOR = _REPO_ROOT / "scripts" / "dev" / "gen_metric_fixture.py"
_FIXTURE = _REPO_ROOT / "test" / "qa" / "fixtures" / "all_metrics_ingest_payload.txt"


@pytest.mark.integration
class TestMetricIngestFixtureSync:
    """The checked-in fixture must always match what gen_metric_fixture.py would produce."""

    def test_fixture_in_sync_with_instruments_def(self):
        """Fail if any instruments-def.yml metrics: change without regenerating the fixture.

        Run 'python scripts/dev/gen_metric_fixture.py' to fix.
        """
        result = subprocess.run(
            [sys.executable, str(_GENERATOR), "--check"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, (
            "Metric ingest fixture is out of sync with instruments-def.yml sources.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            "Run: python scripts/dev/gen_metric_fixture.py"
        )

    def test_fixture_exists(self):
        """The fixture file must exist (generated at least once and checked in)."""
        assert _FIXTURE.exists(), f"{_FIXTURE} not found — run 'python scripts/dev/gen_metric_fixture.py'"

    def test_every_metric_has_a_recognized_unit_in_metadata_line(self):
        """Every #<metric> metadata line's dt.meta.unit value must be schema-valid.

        Cross-checks the fixture against the same MetricUnit enum used by
        test_instruments_def_schema.py, so a stale fixture with an unrecognized
        unit is caught here too (belt-and-suspenders with the --check regen diff).
        """
        import json
        import re

        schema_path = _REPO_ROOT / "scripts" / "tools" / "instruments-def.schema.json"
        with open(schema_path, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
        valid_units = set(schema["$defs"]["MetricUnit"]["enum"])

        content = _FIXTURE.read_text(encoding="utf-8")
        violations = []
        for line in content.splitlines():
            if not line.startswith("#") or "dt.meta.unit=" not in line:
                continue
            match = re.search(r'dt\.meta\.unit="([^"]*)"', line)
            if not match:
                continue
            unit = match.group(1)
            if unit not in valid_units:
                violations.append(f"{line.split(' ', 1)[0][1:]}: unit {unit!r} not in MetricUnit enum")
        assert not violations, "Fixture metadata lines with unrecognized dt.meta.unit:\n" + "\n".join(violations)
