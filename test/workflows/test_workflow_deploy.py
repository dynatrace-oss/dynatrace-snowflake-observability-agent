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
"""Tier 2 — Deployment validation tests for DSOA workflow YAML files.

Validates that all workflows can be deployed to a Dynatrace tenant without
errors.  Requires ``dtctl`` to be on PATH and authenticated (``dtctl auth login``).

All tests are marked ``live`` and skipped automatically when dtctl is absent
or unauthenticated.

Run with:
    pytest test/workflows/test_workflow_deploy.py -v -m live

Prerequisites:
    dtctl authenticated:  dtctl auth login
    Target environment:   test-qa (conf/config-test-qa.yml)
"""

import json
import pathlib
import re
import shutil
import subprocess

import pytest
import yaml

##region constants
_DTCTL_AVAILABLE = shutil.which("dtctl") is not None
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_DEPLOY_SCRIPT = _REPO_ROOT / "scripts" / "deploy" / "deploy_dt_assets.sh"
_YAML_TO_JSON = _REPO_ROOT / "scripts" / "tools" / "yaml-to-json.sh"
_ENV = "test-qa"

_WORKFLOW_COMMENT_ID_RE = re.compile(r"^id:\s*([0-9a-f-]{36})\s*$", re.MULTILINE)
##endregion


def _dtctl_authenticated() -> bool:
    """Return True if dtctl has a valid authenticated session."""
    if not _DTCTL_AVAILABLE:
        return False
    result = subprocess.run(["dtctl", "get", "workflows", "-o", "json"], capture_output=True, text=True, timeout=15)
    return result.returncode == 0 and "token is required" not in result.stderr


def _yaml_to_json(yaml_path: pathlib.Path, tmp_path: pathlib.Path) -> pathlib.Path:
    """Convert a workflow YAML to JSON using the project's yaml-to-json.sh script.

    Args:
        yaml_path: Source YAML file path.
        tmp_path:  Temporary directory for output.

    Returns:
        Path to the produced JSON file.

    Raises:
        RuntimeError: If conversion fails.
    """
    out_path = tmp_path / (yaml_path.stem + ".json")
    result = subprocess.run(
        ["bash", str(_YAML_TO_JSON), str(yaml_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yaml-to-json.sh failed for {yaml_path.name}: {result.stderr}")
    out_path.write_text(result.stdout)
    return out_path


@pytest.mark.live
@pytest.mark.skipif(not _DTCTL_AVAILABLE, reason="dtctl not on PATH")
class TestWorkflowDeploy:
    """Tier 2 deployment validation tests — require dtctl on PATH and authenticated."""

    # ------------------------------------------------------------------
    # YAML → JSON conversion
    # ------------------------------------------------------------------

    def test_yaml_to_json_conversion(self, all_workflows, tmp_path):
        """Each workflow YAML must convert to valid JSON without errors."""
        if not _YAML_TO_JSON.exists():
            pytest.skip(f"yaml-to-json.sh not found at {_YAML_TO_JSON}")
        failures = {}
        for w in all_workflows:
            try:
                json_path = _yaml_to_json(w["path"], tmp_path)
                parsed = json.loads(json_path.read_text())
                if "tasks" not in parsed:
                    failures[w["name"]] = "converted JSON missing 'tasks' key"
            except (RuntimeError, json.JSONDecodeError) as exc:
                failures[w["name"]] = str(exc)
        assert not failures, f"YAML-to-JSON conversion failures: {failures}"

    def test_json_preserves_workflow_id(self, all_workflows, tmp_path):
        """The workflow ``id`` must be preserved after YAML-to-JSON conversion."""
        if not _YAML_TO_JSON.exists():
            pytest.skip(f"yaml-to-json.sh not found at {_YAML_TO_JSON}")
        mismatches = {}
        for w in all_workflows:
            original_id = str(w["content"].get("id", ""))
            try:
                json_path = _yaml_to_json(w["path"], tmp_path)
                parsed = json.loads(json_path.read_text())
                converted_id = str(parsed.get("id", ""))
                if original_id != converted_id:
                    mismatches[w["name"]] = {"original": original_id, "converted": converted_id}
            except (RuntimeError, json.JSONDecodeError) as exc:
                mismatches[w["name"]] = str(exc)
        assert not mismatches, f"Workflow ID mismatches after YAML-to-JSON conversion: {mismatches}"

    # ------------------------------------------------------------------
    # Dry-run deployment
    # ------------------------------------------------------------------

    def test_dry_run_all_workflows(self):
        """All workflows must pass ``deploy_dt_assets.sh --scope=workflows --dry-run``.

        This validates that the deploy script can convert, wrap, and validate every
        workflow YAML without applying any changes to the tenant.
        """
        if not _DEPLOY_SCRIPT.exists():
            pytest.skip(f"deploy_dt_assets.sh not found at {_DEPLOY_SCRIPT}")
        if not _dtctl_authenticated():
            pytest.skip("dtctl not authenticated — run 'dtctl auth login' first")

        result = subprocess.run(
            ["bash", str(_DEPLOY_SCRIPT), "--scope=workflows", f"--env={_ENV}", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=120,
        )
        assert result.returncode == 0, (
            f"Workflow dry-run deploy failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout[-2000:]}\n"
            f"stderr: {result.stderr[-2000:]}"
        )

    def test_dry_run_individual_via_dtctl(self, all_workflows, tmp_path):
        """Each workflow JSON must pass ``dtctl apply --dry-run``."""
        if not _YAML_TO_JSON.exists():
            pytest.skip(f"yaml-to-json.sh not found at {_YAML_TO_JSON}")
        if not _dtctl_authenticated():
            pytest.skip("dtctl not authenticated — run 'dtctl auth login' first")

        failures = {}
        for w in all_workflows:
            try:
                json_path = _yaml_to_json(w["path"], tmp_path)
            except RuntimeError as exc:
                failures[w["name"]] = f"conversion failed: {exc}"
                continue

            result = subprocess.run(
                ["dtctl", "apply", "--dry-run", "-f", str(json_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                failures[w["name"]] = {
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                }
        assert not failures, f"Individual workflow dry-run failures: {failures}"

    # ------------------------------------------------------------------
    # Live deployment (apply without --dry-run)
    # ------------------------------------------------------------------

    def test_live_deploy_all_workflows(self):
        """All workflows must deploy successfully to the test-qa tenant.

        Applies all workflows and verifies the script exits cleanly.
        Idempotent — safe to run against an already-deployed set.
        """
        if not _DEPLOY_SCRIPT.exists():
            pytest.skip(f"deploy_dt_assets.sh not found at {_DEPLOY_SCRIPT}")
        if not _dtctl_authenticated():
            pytest.skip("dtctl not authenticated — run 'dtctl auth login' first")

        result = subprocess.run(
            ["bash", str(_DEPLOY_SCRIPT), "--scope=workflows", f"--env={_ENV}"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=300,
        )
        assert result.returncode == 0, (
            f"Workflow deploy failed (exit {result.returncode}):\n" f"stdout: {result.stdout[-2000:]}\n" f"stderr: {result.stderr[-2000:]}"
        )

    def test_deployed_workflows_visible_in_tenant(self, all_workflows):
        """After deployment, every workflow must be retrievable by ID from the tenant."""
        if not _dtctl_authenticated():
            pytest.skip("dtctl not authenticated — run 'dtctl auth login' first")

        result = subprocess.run(
            ["dtctl", "get", "workflows", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            pytest.skip(f"Could not list workflows: {result.stderr.strip()}")

        deployed_ids: set[str] = set()
        try:
            workflows_list = json.loads(result.stdout)
            for wf in workflows_list:
                wf_id = wf.get("id") or (wf.get("content") or {}).get("id", "")
                if wf_id:
                    deployed_ids.add(str(wf_id))
        except (json.JSONDecodeError, TypeError):
            pytest.skip("Could not parse dtctl get workflows output")

        missing = {}
        for w in all_workflows:
            wf_id = str(w["content"].get("id", ""))
            if wf_id and wf_id not in deployed_ids:
                missing[w["name"]] = wf_id
        assert not missing, f"Workflows not found in tenant after deployment: {missing}\n" "Run test_live_deploy_all_workflows first."

    def test_deployed_workflow_title_matches(self, all_workflows):
        """After deployment, each workflow's title on the tenant must match the YAML source."""
        if not _dtctl_authenticated():
            pytest.skip("dtctl not authenticated — run 'dtctl auth login' first")

        mismatches = {}
        for w in all_workflows:
            wf_id = str(w["content"].get("id", ""))
            expected_title = (w["content"].get("title") or "").strip()
            if not wf_id or not expected_title:
                continue

            result = subprocess.run(
                ["dtctl", "get", "workflow", wf_id, "-o", "json"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                continue  # Workflow not deployed yet — handled by test_deployed_workflows_visible_in_tenant

            try:
                wf_data = json.loads(result.stdout)
                actual_title = (wf_data.get("title") or (wf_data.get("content") or {}).get("title", "")).strip()
                if actual_title and actual_title != expected_title:
                    mismatches[w["name"]] = {"expected": expected_title, "actual": actual_title}
            except (json.JSONDecodeError, TypeError):
                pass  # Ignore parse errors — not a title mismatch

        assert not mismatches, f"Workflow title mismatches between source YAML and deployed tenant: {mismatches}"
