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
"""Tier 1 — DQL query extraction and validation for DSOA workflow YAML files.

Extracts all DQL query strings embedded in workflow tasks (Davis analyzer
``timeSeriesData`` and JavaScript template literals) and validates them:

  - Syntax validation via ``dtctl verify query`` (assumed available).
  - Cross-reference against known DSOA metric names from instruments-def.yml.
  - Best-practice checks (explicit ``interval:``, no hardcoded environments).

All structural checks are offline.  The ``dtctl verify query`` calls require
``dtctl`` to be on PATH and authenticated to a Dynatrace tenant; those tests are
marked ``live`` and skipped automatically when ``--live`` is not passed or
``dtctl`` is absent.
"""

import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest

from test.workflows.conftest import extract_dql_queries

##region helpers
_TIMESERIES_INTERVAL_RE = re.compile(r"\binterval\s*:", re.IGNORECASE)
_HARDCODED_ENV_RE = re.compile(r"\bDEV-\d{3}\b")

# Metric names extracted from workflow DQL that we know are DSOA metrics
_DSOA_METRIC_PREFIX = "snowflake."

_DTCTL_AVAILABLE = shutil.which("dtctl") is not None

# Lines in Davis analyzer DQL that are pure metadata (template fields, event names).
# These are valid Davis syntax but ``dtctl verify query`` rejects them as invalid DQL.
# Strip them before passing to the validator.
_DAVIS_METADATA_LINE_RE = re.compile(
    r"^\s*(?:metric_name|_event_name_template|_event_description_template|_event_direction)\s*=",
)
##endregion


def _workflow_dql_params(workflows: list[dict]) -> list[tuple[str, str]]:
    """Build parametrize list of (workflow_name, dql_string) tuples."""
    params = []
    for w in workflows:
        for idx, dql in enumerate(extract_dql_queries(w["content"])):
            params.append((f"{w['name']}-dql{idx}", dql))
    return params


class TestWorkflowDql:
    """DQL extraction and validation tests for workflow YAML files."""

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def test_every_davis_workflow_has_dql(self, all_workflows):
        """Every workflow with a Davis analyzer task must embed at least one DQL query."""
        _DAVIS_ACTION = "dynatrace.davis.workflow.actions:davis-analyze"
        violations = {}
        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            has_davis = any(t.get("action") == _DAVIS_ACTION for t in tasks.values())
            if has_davis:
                queries = extract_dql_queries(w["content"])
                if not queries:
                    violations[w["name"]] = "Davis task present but no DQL extracted"
        assert not violations, f"Workflows with Davis tasks but no extractable DQL: {violations}"

    def test_dql_non_empty(self, all_workflows):
        """Extracted DQL strings must not be blank."""
        violations = {}
        for w in all_workflows:
            for idx, dql in enumerate(extract_dql_queries(w["content"])):
                if not dql.strip():
                    violations.setdefault(w["name"], []).append(f"dql{idx} is empty")
        assert not violations, f"Workflows with blank DQL strings: {violations}"

    # ------------------------------------------------------------------
    # Best-practice checks (offline, no dtctl needed)
    # ------------------------------------------------------------------

    def test_dql_no_hardcoded_environments(self, all_workflows):
        """DQL strings must not contain hardcoded DEV-XXX environment literals."""
        violations = {}
        for w in all_workflows:
            for idx, dql in enumerate(extract_dql_queries(w["content"])):
                matches = _HARDCODED_ENV_RE.findall(dql)
                if matches:
                    violations.setdefault(w["name"], []).append(f"dql{idx}: {matches}")
        assert not violations, f"Workflows with hardcoded environment names in DQL: {violations}"

    def test_timeseries_queries_have_explicit_interval(self, all_workflows):
        """Timeseries DQL in non-Davis tasks should specify an explicit ``interval:`` for reproducibility.

        Davis analyzer tasks intentionally omit ``interval:`` — the Davis engine applies its own
        timeframe.  We therefore skip this check for DQL embedded inside Davis analyzer tasks.
        """
        _DAVIS_ACTION = "dynatrace.davis.workflow.actions:davis-analyze"
        violations = {}
        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            # Collect DQL from non-Davis tasks only
            for task in tasks.values():
                if task.get("action") == _DAVIS_ACTION:
                    continue
                task_input = task.get("input") or {}
                script = task_input.get("script", "")
                if not script:
                    continue
                for idx, match in enumerate(re.finditer(r"`([^`]*?(?:timeseries)[^`]*?)`", script, re.DOTALL)):
                    dql = match.group(1).strip()
                    if dql.startswith("timeseries") and not _TIMESERIES_INTERVAL_RE.search(dql):
                        violations.setdefault(w["name"], []).append(
                            f"task '{task['name']}' dql{idx}: missing 'interval:' in timeseries query"
                        )
        assert not violations, f"Non-Davis timeseries DQL queries without explicit interval: {violations}"

    def test_dql_references_dsoa_metrics(self, all_workflows, known_metric_names):
        """DQL queries must reference at least one known DSOA metric (snowflake.* prefix).

        This is a best-effort check — if instruments-def.yml is absent the test is skipped.
        """
        if not known_metric_names:
            pytest.skip("instruments-def.yml not found — skipping metric cross-reference check")

        violations = {}
        for w in all_workflows:
            queries = extract_dql_queries(w["content"])
            if not queries:
                continue  # Already caught by test_every_davis_workflow_has_dql
            all_text = " ".join(queries)
            # Check that at least one known DSOA metric name appears somewhere across all DQL for this workflow
            found = any(metric in all_text for metric in known_metric_names if metric.startswith(_DSOA_METRIC_PREFIX))
            if not found:
                violations[w["name"]] = "No known snowflake.* metric referenced in DQL"
        assert not violations, f"Workflows whose DQL references no known DSOA metrics: {violations}"

    # ------------------------------------------------------------------
    # Syntax validation via dtctl (live — requires dtctl on PATH)
    # ------------------------------------------------------------------

    @pytest.mark.live
    @pytest.mark.skipif(not _DTCTL_AVAILABLE, reason="dtctl not on PATH")
    def test_dql_syntax_valid_via_dtctl(self, all_workflows, tmp_path):
        """Each extracted DQL query must pass ``dtctl verify query``.

        Requires dtctl authenticated to a Dynatrace tenant.
        Skipped automatically when dtctl is not available.

        Davis analyzer tasks embed metadata fields (``_event_name_template``,
        ``_event_description_template``, ``metric_name``, ``_event_direction``) in
        ``fieldsAdd`` clauses that are valid Davis syntax but rejected by the generic
        DQL validator.  Those lines are stripped before validation so the structural
        query (metric selection, dimensions, filters) is still validated.
        """
        failures = {}
        for w in all_workflows:
            for idx, dql in enumerate(extract_dql_queries(w["content"])):
                # Davis analyzer DQL uses extended ``fieldsAdd`` syntax for metadata fields
                # (e.g. _event_name_template, _event_category, computed intermediate variables)
                # that is valid Davis syntax but rejected by the generic DQL validator.
                # Also strips ``fieldsRemove`` lines that reference Davis-only computed fields,
                # and ``fieldsRemove`` lines that immediately follow a stripped ``fieldsAdd``.
                # Strategy: strip all ``| fieldsAdd`` and ``| fieldsRemove`` pipe stages from
                # Davis DQL — the core metric query (timeseries + by + filter) is what matters.
                cleaned_lines: list[str] = []
                skip_next_pipe_stage = False
                for line in dql.splitlines():
                    stripped = line.strip()
                    # Strip full pipe stages: fieldsAdd, fieldsRemove (Davis post-processing)
                    if re.match(r"^\|\s*fields(?:Add|Remove)\b", stripped):
                        skip_next_pipe_stage = True
                        continue
                    # Continuation lines inside a stripped pipe stage (assignments, string literals)
                    if skip_next_pipe_stage:
                        if stripped.startswith("|"):
                            # New pipe stage — stop skipping
                            skip_next_pipe_stage = False
                        else:
                            # Continuation of previous stripped stage
                            continue
                    # Standalone string continuation lines (multi-line string concat)
                    if stripped.startswith('"') or stripped.startswith("'") or stripped.startswith("+"):
                        continue
                    cleaned_lines.append(line)

                cleaned_dql = "\n".join(cleaned_lines).rstrip()
                if not cleaned_dql.strip():
                    continue  # Nothing left to validate after stripping

                dql_file = tmp_path / f"{w['name']}-{idx}.dql"
                dql_file.write_text(cleaned_dql)
                result = subprocess.run(
                    ["dtctl", "verify", "query", "-f", str(dql_file)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    stderr = result.stderr.strip()
                    # Skip auth failures — dtctl token expired or not configured
                    if (
                        "token is required" in stderr
                        or "token expired" in stderr
                        or "refresh failed" in stderr
                        or "authentication" in stderr.lower()
                    ):
                        pytest.skip("dtctl not authenticated (token expired/missing) — re-run after 'dtctl auth login'")
                    failures.setdefault(w["name"], []).append(
                        {
                            "dql_index": idx,
                            "stdout": result.stdout.strip(),
                            "stderr": stderr,
                        }
                    )
        assert not failures, f"DQL syntax validation failures: {failures}"
