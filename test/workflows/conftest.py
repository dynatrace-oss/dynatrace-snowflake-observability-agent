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
"""Shared fixtures and helpers for DSOA workflow tests.

Provides:
    all_workflow_paths    — sorted list of Path objects for every workflow YAML.
    all_workflows         — parsed list of {path, name, content, raw_text} dicts.
    workflow_by_name      — dict keyed by workflow directory name.

Helper functions (importable):
    extract_dql_queries(content)  — list of DQL strings from Davis + JS tasks.
    extract_js_scripts(content)   — list of JS code strings from run-javascript tasks.
"""

import pathlib
import re

import pytest
import yaml

##region constants
WORKFLOWS_DIR = pathlib.Path(__file__).parent.parent.parent / "docs" / "workflows"
INSTRUMENTS_DEF = pathlib.Path(__file__).parent.parent.parent / "docs" / "instruments-def.yml"

# Davis analyzer action identifier
_DAVIS_ACTION = "dynatrace.davis.workflow.actions:davis-analyze"
# JavaScript action identifier
_JS_ACTION = "dynatrace.automations:run-javascript"
# Known allowed SDK imports
ALLOWED_SDK_IMPORTS = {
    "@dynatrace-sdk/automation-utils",
    "@dynatrace-sdk/client-classic-environment-v2",
    "@dynatrace-sdk/client-automation",
    "@dynatrace-sdk/client-metrics",
}
##endregion


##region helper functions
def extract_dql_queries(content: dict) -> list[str]:
    """Extract all DQL query strings embedded in a workflow.

    Looks in:
      - Davis analyzer tasks: ``input.body.timeSeriesData``
      - JavaScript tasks: ``timeseries`` / ``fetch`` / ``events`` DQL patterns
        inside script source (multi-line template literal extraction).

    Args:
        content: Parsed workflow YAML dict.

    Returns:
        List of DQL query strings found in the workflow.
    """
    queries: list[str] = []
    tasks = content.get("tasks") or {}
    for task in tasks.values():
        action = task.get("action", "")
        task_input = task.get("input") or {}

        # Davis analyzer: timeSeriesData field
        if action == _DAVIS_ACTION:
            body = task_input.get("body") or {}
            dql = body.get("timeSeriesData", "")
            if dql and dql.strip():
                queries.append(dql.strip())

        # JavaScript: scan for embedded DQL strings
        if action == _JS_ACTION:
            script = task_input.get("script", "")
            if script:
                # Look for backtick-delimited template literals containing DQL keywords
                for match in re.finditer(
                    r"`([^`]*?(?:timeseries|fetch events|fetch logs|fetch spans|fetch bizevents)[^`]*?)`", script, re.DOTALL
                ):
                    candidate = match.group(1).strip()
                    if candidate:
                        queries.append(candidate)

    return queries


def extract_js_scripts(content: dict) -> list[str]:
    """Extract all JavaScript source code strings from run-javascript tasks.

    Args:
        content: Parsed workflow YAML dict.

    Returns:
        List of JavaScript source strings.
    """
    scripts: list[str] = []
    tasks = content.get("tasks") or {}
    for task in tasks.values():
        if task.get("action") == _JS_ACTION:
            script = (task.get("input") or {}).get("script", "")
            if script and script.strip():
                scripts.append(script.strip())
    return scripts


##endregion


##region session fixtures
@pytest.fixture(scope="session")
def all_workflow_paths() -> list[pathlib.Path]:
    """All workflow YAML file paths, sorted by directory name."""
    return sorted(WORKFLOWS_DIR.glob("*/*.yml"))


@pytest.fixture(scope="session")
def all_workflows(all_workflow_paths) -> list[dict]:
    """All workflow YAML contents parsed into structured dicts.

    Each entry:
        path    (Path)  — absolute path to the YAML file.
        name    (str)   — workflow directory name (e.g. 'data-volume-anomaly').
        content (dict)  — parsed YAML dict.
        raw_text (str)  — raw file text (for comment-header checks).
    """
    workflows = []
    for path in all_workflow_paths:
        raw_text = path.read_text()
        content = yaml.safe_load(raw_text)
        workflows.append(
            {
                "path": path,
                "name": path.parent.name,
                "content": content,
                "raw_text": raw_text,
            }
        )
    return workflows


@pytest.fixture(scope="session")
def workflow_by_name(all_workflows) -> dict[str, dict]:
    """Dict keyed by workflow directory name.

    Args:
        all_workflows: Session-scoped list from :func:`all_workflows`.

    Returns:
        Mapping of directory name → workflow entry dict.
    """
    return {w["name"]: w for w in all_workflows}


@pytest.fixture(scope="session")
def known_metric_names() -> set[str]:
    """Set of known DSOA metric names from instruments-def.yml.

    Returns:
        Set of metric key strings (e.g. 'snowflake.data.rows').
        Returns empty set if instruments-def.yml is not found.
    """
    if not INSTRUMENTS_DEF.exists():
        return set()
    raw = yaml.safe_load(INSTRUMENTS_DEF.read_text())
    metrics: set[str] = set()
    for instrument in raw.get("instruments", []):
        name = instrument.get("name") or instrument.get("metric")
        if name:
            metrics.add(name)
    return metrics


##endregion
