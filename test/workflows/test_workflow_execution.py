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
"""Tier 3 — Live execution validation tests for DSOA workflow YAML files.

Triggers each workflow on the tenant, waits for completion (up to 10 minutes),
and validates:

  - The workflow execution completes without fatal errors.
  - No task ends in a hard ``FAILED`` state.
  - Davis AI analyzer tasks return non-null output (empty list is OK when no
    anomaly is detected — that is a valid result, not a failure).
  - JavaScript tasks complete without unhandled exceptions.
  - For workflows that ingest Dynatrace events, the event type property
    (``anomaly.detector``) is present in the result.

Requires:
  - dtctl on PATH and authenticated (``dtctl auth login``).
  - DSOA deployed and running on the tenant so that DSOA metrics exist for
    Davis to evaluate.  For best anomaly-detection results, seed data first:
      ``snow sql -c snow_agent_test-qa -f test/tools/setup_test_workflows.sql``
      ``snow sql -c snow_agent_test-qa -f test/tools/setup_test_workflow_anomalies.sql``

Run with:
    pytest test/workflows/test_workflow_execution.py -v -m "live and slow"

All tests are marked ``live`` + ``slow`` and skipped by default.
"""

import json
import shutil
import subprocess
import time

import pytest

##region constants
_DTCTL_AVAILABLE = shutil.which("dtctl") is not None

# Maximum time (seconds) to wait for a single workflow execution to complete.
# Set to 10 minutes per plan decision.
_EXECUTION_TIMEOUT_SECONDS = 600

# Poll interval (seconds) while waiting for execution to finish.
_POLL_INTERVAL_SECONDS = 15

# Terminal execution statuses
_STATUS_SUCCESS = {"SUCCESS", "COMPLETED"}
_STATUS_FAILED = {"FAILED", "ERROR", "CANCELLED"}
_STATUS_RUNNING = {"RUNNING", "QUEUED", "IN_PROGRESS"}

# Per-workflow expected ``anomaly.detector`` event property (for behavioral assertion).
# Maps workflow directory name → expected anomaly.detector value in ingested events.
# Workflows that do not ingest events map to None.
_WORKFLOW_ANOMALY_DETECTOR: dict[str, str | None] = {
    "credits-exhaustion-prediction": "dsoa.credits_exhaustion_prediction",
    "data-volume-anomaly": "dsoa.data_volume_anomaly",
    "dynamic-table-drift": "dsoa.dynamic_table_drift",
    "long-running-queries": "dsoa.long_running_queries",
    "org-contract-balance-warning": None,  # Uses eventsClient separately
    "query-slowdown-detection": "dsoa.query_slowdown_detection",
    "security-anomaly-detection": "dsoa.security_anomaly_detection",
    "shares-broken-detection": "dsoa.shares_broken",
    "table-perf-degradation": "dsoa.table_perf_degradation",
    "warehouse-sensitive-change-alert": None,  # Uses execute-dql-query, no event ingest
}
##endregion


##region helpers
def _dtctl_authenticated() -> bool:
    """Return True if dtctl has a valid authenticated session."""
    if not _DTCTL_AVAILABLE:
        return False
    result = subprocess.run(["dtctl", "get", "workflows", "-o", "json"], capture_output=True, text=True, timeout=15)
    return result.returncode == 0 and "token is required" not in result.stderr


def _trigger_workflow(workflow_id: str) -> str | None:
    """Trigger a workflow execution and return the execution ID.

    Args:
        workflow_id: The workflow UUID to execute.

    Returns:
        Execution ID string, or None if triggering failed.
    """
    result = subprocess.run(
        ["dtctl", "exec", "workflow", workflow_id, "-o", "json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        # dtctl exec workflow returns {id: <execution_id>, ...} or similar
        return str(data.get("id") or data.get("execution_id") or "")
    except (json.JSONDecodeError, TypeError):
        # Try plain text output — some dtctl versions print the ID directly
        return result.stdout.strip() or None


def _get_execution_status(workflow_id: str, execution_id: str) -> dict:
    """Fetch the current status of a workflow execution.

    Args:
        workflow_id:  The workflow UUID.
        execution_id: The execution ID returned by dtctl exec.

    Returns:
        Dict with keys: status (str), tasks (list), raw (dict).
    """
    result = subprocess.run(
        ["dtctl", "get", "workflow", workflow_id, "--execution", execution_id, "-o", "json"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        return {"status": "UNKNOWN", "tasks": [], "raw": {}}
    try:
        data = json.loads(result.stdout)
        status = (data.get("status") or data.get("state") or "UNKNOWN").upper()
        tasks = data.get("tasks") or []
        return {"status": status, "tasks": tasks, "raw": data}
    except (json.JSONDecodeError, TypeError):
        return {"status": "UNKNOWN", "tasks": [], "raw": {}}


def _wait_for_execution(workflow_id: str, execution_id: str, timeout: int = _EXECUTION_TIMEOUT_SECONDS) -> dict:
    """Poll execution status until terminal state or timeout.

    Args:
        workflow_id:  The workflow UUID.
        execution_id: The execution ID to poll.
        timeout:      Maximum wait time in seconds.

    Returns:
        Final execution status dict from :func:`_get_execution_status`.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status_data = _get_execution_status(workflow_id, execution_id)
        status = status_data["status"]
        if status in _STATUS_SUCCESS or status in _STATUS_FAILED:
            return status_data
        time.sleep(_POLL_INTERVAL_SECONDS)
    return {"status": "TIMEOUT", "tasks": [], "raw": {}}


##endregion


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.skipif(not _DTCTL_AVAILABLE, reason="dtctl not on PATH")
class TestWorkflowExecution:
    """Tier 3 live execution validation — requires dtctl + DSOA data on tenant."""

    def test_all_workflows_execute_without_fatal_error(self, all_workflows):
        """Trigger all 10 workflows and verify none ends in FAILED/ERROR state.

        Davis AI tasks may return empty results when historical baseline data is
        insufficient — this is a valid (non-failure) outcome.  The test passes as
        long as no task ends in a hard error state.

        Executes workflows sequentially with a 10-minute timeout each.
        Total maximum wall time: ~100 minutes.
        """
        if not _dtctl_authenticated():
            pytest.skip("dtctl not authenticated — run 'dtctl auth login' first")

        results: dict[str, dict] = {}
        execution_ids: dict[str, str] = {}

        # Trigger all workflows
        for w in all_workflows:
            wf_id = str(w["content"].get("id", ""))
            if not wf_id:
                results[w["name"]] = {"status": "SKIP", "reason": "no id in YAML"}
                continue
            exec_id = _trigger_workflow(wf_id)
            if not exec_id:
                results[w["name"]] = {"status": "TRIGGER_FAILED", "reason": "dtctl exec returned no execution ID"}
            else:
                execution_ids[w["name"]] = exec_id

        # Wait for each execution
        for w in all_workflows:
            wf_name = w["name"]
            if wf_name not in execution_ids:
                continue
            wf_id = str(w["content"].get("id", ""))
            exec_id = execution_ids[wf_name]
            status_data = _wait_for_execution(wf_id, exec_id)
            results[wf_name] = status_data

        # Assert: no workflow in hard failure state
        failed = {name: data for name, data in results.items() if data.get("status") in _STATUS_FAILED or data.get("status") == "TIMEOUT"}
        assert not failed, "Workflows ended in failure or timeout:\n" + "\n".join(
            f"  {name}: status={data['status']}" for name, data in failed.items()
        )

    def test_no_task_in_error_state(self, all_workflows):
        """After execution, no individual task should be in ERROR/FAILED state.

        Triggers each workflow and checks per-task status in the execution result.
        Skips workflows that cannot be triggered or where execution details are unavailable.
        """
        if not _dtctl_authenticated():
            pytest.skip("dtctl not authenticated — run 'dtctl auth login' first")

        task_failures: dict[str, list[str]] = {}
        for w in all_workflows:
            wf_id = str(w["content"].get("id", ""))
            if not wf_id:
                continue
            exec_id = _trigger_workflow(wf_id)
            if not exec_id:
                continue
            status_data = _wait_for_execution(wf_id, exec_id)
            for task in status_data.get("tasks") or []:
                task_name = task.get("name") or str(task)
                task_status = (task.get("status") or task.get("state") or "").upper()
                if task_status in _STATUS_FAILED:
                    task_failures.setdefault(w["name"], []).append(f"{task_name}={task_status}")

        assert not task_failures, "Individual tasks in error state after workflow execution:\n" + "\n".join(
            f"  {wf}: {', '.join(tasks)}" for wf, tasks in task_failures.items()
        )

    def test_davis_tasks_return_non_null_output(self, all_workflows):
        """Davis AI analyzer tasks must return a non-null ``output`` field.

        An empty list ``[]`` is acceptable (no anomaly detected) but ``null`` or
        a missing output key indicates a Davis configuration error.
        """
        if not _dtctl_authenticated():
            pytest.skip("dtctl not authenticated — run 'dtctl auth login' first")

        _DAVIS_ACTION = "dynatrace.davis.workflow.actions:davis-analyze"
        null_outputs: dict[str, list[str]] = {}

        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            davis_task_names = [k for k, t in tasks.items() if t.get("action") == _DAVIS_ACTION]
            if not davis_task_names:
                continue

            wf_id = str(w["content"].get("id", ""))
            if not wf_id:
                continue
            exec_id = _trigger_workflow(wf_id)
            if not exec_id:
                continue
            status_data = _wait_for_execution(wf_id, exec_id)

            for task in status_data.get("tasks") or []:
                task_name = task.get("name", "")
                if task_name not in davis_task_names:
                    continue
                output = task.get("output")
                if output is None:
                    null_outputs.setdefault(w["name"], []).append(f"{task_name}: output is null")

        assert not null_outputs, "Davis AI tasks with null output (indicates configuration error, not just 'no anomaly'):\n" + "\n".join(
            f"  {wf}: {', '.join(tasks)}" for wf, tasks in null_outputs.items()
        )

    def test_event_anomaly_detector_present_on_anomaly(self, all_workflows):
        """For workflows that ingest Dynatrace events, verify ``anomaly.detector`` is set.

        This test only checks workflows that produced events (output length > 0).
        If no anomaly was detected, the test is automatically skipped for that workflow.

        Requires synthetic anomaly data from setup_test_workflow_anomalies.sql for
        reliable results.
        """
        if not _dtctl_authenticated():
            pytest.skip("dtctl not authenticated — run 'dtctl auth login' first")

        issues: dict[str, str] = {}
        for w in all_workflows:
            wf_name = w["name"]
            expected_detector = _WORKFLOW_ANOMALY_DETECTOR.get(wf_name)
            if not expected_detector:
                continue  # Workflow does not ingest events — skip

            wf_id = str(w["content"].get("id", ""))
            if not wf_id:
                continue
            exec_id = _trigger_workflow(wf_id)
            if not exec_id:
                continue
            status_data = _wait_for_execution(wf_id, exec_id)

            # Find the ingest task output (last JS task)
            tasks = status_data.get("tasks") or []
            ingest_task = next(
                (t for t in reversed(tasks) if "ingest" in (t.get("name") or "").lower()),
                None,
            )
            if not ingest_task:
                continue

            task_output = ingest_task.get("output")
            if not task_output:
                continue  # No events — no anomaly detected, skip behavioral check

            # Output should be a list of event objects or a count
            # If any events were ingested, verify anomaly.detector is in the event body
            if isinstance(task_output, list) and len(task_output) > 0:
                sample_event = task_output[0]
                props = (sample_event.get("body") or {}).get("properties") or {}
                actual_detector = props.get("anomaly.detector", "")
                if actual_detector != expected_detector:
                    issues[wf_name] = f"expected anomaly.detector='{expected_detector}', got '{actual_detector}'"

        assert not issues, f"Workflow events missing expected anomaly.detector property: {issues}"
