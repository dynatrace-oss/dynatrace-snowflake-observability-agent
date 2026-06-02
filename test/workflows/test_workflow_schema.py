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
"""Tier 1 — Structural schema validation for DSOA workflow YAML files.

Validates that every workflow YAML under docs/workflows/ conforms to the
expected Dynatrace Automation Workflow schema (schemaVersion 4) and that
internal references (predecessors, condition states) are consistent.

All tests are offline — no Dynatrace tenant or dtctl authentication required.
"""

import re
import uuid

import pytest

##region helpers
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

_REQUIRED_TOP_LEVEL = {"id", "title", "schemaVersion", "trigger", "tasks"}
_REQUIRED_TASK_FIELDS = {"name", "action", "active", "position", "input"}
_KNOWN_ACTIONS = {
    "dynatrace.davis.workflow.actions:davis-analyze",
    "dynatrace.automations:run-javascript",
    "dynatrace.automations:execute-dql-query",
    "dynatrace.automations:http-function",
}
##endregion


class TestWorkflowSchema:
    """Structural and schema-conformance tests for workflow YAML files."""

    # ------------------------------------------------------------------
    # Top-level fields
    # ------------------------------------------------------------------

    def test_required_top_level_fields(self, all_workflows):
        """Every workflow must have the mandatory top-level fields."""
        missing = {}
        for w in all_workflows:
            absent = _REQUIRED_TOP_LEVEL - set(w["content"].keys())
            if absent:
                missing[w["name"]] = sorted(absent)
        assert not missing, f"Workflows missing required fields: {missing}"

    def test_id_is_valid_uuid(self, all_workflows):
        """The 'id' field must be a valid UUID (lowercase hyphenated form)."""
        invalid = {}
        for w in all_workflows:
            wf_id = str(w["content"].get("id", ""))
            try:
                uuid.UUID(wf_id)
            except (ValueError, AttributeError):
                invalid[w["name"]] = wf_id
        assert not invalid, f"Workflows with invalid UUIDs: {invalid}"

    def test_schema_version(self, all_workflows):
        """Schema version must be 4 (current Dynatrace Automation Workflow version)."""
        wrong = {w["name"]: w["content"].get("schemaVersion") for w in all_workflows if w["content"].get("schemaVersion") != 4}
        assert not wrong, f"Workflows with wrong schemaVersion (expected 4): {wrong}"

    def test_title_is_non_empty_string(self, all_workflows):
        """Workflow title must be a non-empty string."""
        invalid = {w["name"] for w in all_workflows if not isinstance(w["content"].get("title"), str) or not w["content"]["title"].strip()}
        assert not invalid, f"Workflows with missing or empty title: {invalid}"

    # ------------------------------------------------------------------
    # Trigger structure
    # ------------------------------------------------------------------

    def test_trigger_schedule_present(self, all_workflows):
        """trigger.schedule must be present for all workflows."""
        missing = {}
        for w in all_workflows:
            trigger = w["content"].get("trigger") or {}
            if "schedule" not in trigger:
                missing[w["name"]] = "trigger.schedule absent"
        assert not missing, f"Workflows missing trigger.schedule: {missing}"

    def test_trigger_schedule_type_is_interval(self, all_workflows):
        """trigger.schedule.trigger.type must be 'interval'."""
        wrong = {}
        for w in all_workflows:
            trigger = w["content"].get("trigger") or {}
            sched = trigger.get("schedule") or {}
            sched_trigger = sched.get("trigger") or {}
            t_type = sched_trigger.get("type")
            if t_type != "interval":
                wrong[w["name"]] = t_type
        assert not wrong, f"Workflows with unexpected trigger type (expected 'interval'): {wrong}"

    def test_trigger_interval_minutes_positive(self, all_workflows):
        """trigger.schedule.trigger.intervalMinutes must be a positive integer."""
        invalid = {}
        for w in all_workflows:
            trigger = w["content"].get("trigger") or {}
            sched = trigger.get("schedule") or {}
            sched_trigger = sched.get("trigger") or {}
            interval = sched_trigger.get("intervalMinutes")
            if not isinstance(interval, int) or interval <= 0:
                invalid[w["name"]] = interval
        assert not invalid, f"Workflows with invalid intervalMinutes: {invalid}"

    def test_trigger_is_active(self, all_workflows):
        """trigger.schedule.isActive should be True for deployed workflows."""
        inactive = {w["name"] for w in all_workflows if not (w["content"].get("trigger") or {}).get("schedule", {}).get("isActive", True)}
        assert not inactive, f"Workflows with isActive=False (will never run after deploy): {inactive}"

    # ------------------------------------------------------------------
    # Task-level fields
    # ------------------------------------------------------------------

    def test_tasks_not_empty(self, all_workflows):
        """Every workflow must have at least two tasks."""
        too_few = {w["name"]: len(w["content"].get("tasks") or {}) for w in all_workflows if len(w["content"].get("tasks") or {}) < 2}
        assert not too_few, f"Workflows with fewer than 2 tasks: {too_few}"

    def test_task_required_fields(self, all_workflows):
        """Every task must have the mandatory task-level fields."""
        violations = {}
        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            for task_key, task in tasks.items():
                absent = _REQUIRED_TASK_FIELDS - set(task.keys())
                if absent:
                    violations[f"{w['name']}.{task_key}"] = sorted(absent)
        assert not violations, f"Tasks missing required fields: {violations}"

    def test_task_name_matches_key(self, all_workflows):
        """task.name must match the task's dict key."""
        mismatches = {}
        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            for task_key, task in tasks.items():
                if task.get("name") != task_key:
                    mismatches[f"{w['name']}.{task_key}"] = task.get("name")
        assert not mismatches, f"Tasks where name != dict key: {mismatches}"

    def test_task_action_is_known(self, all_workflows):
        """Every task action must be one of the known Dynatrace action identifiers."""
        unknown = {}
        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            for task_key, task in tasks.items():
                action = task.get("action", "")
                if action not in _KNOWN_ACTIONS:
                    unknown[f"{w['name']}.{task_key}"] = action
        assert not unknown, f"Tasks using unknown action identifiers: {unknown}"

    def test_task_active_is_boolean(self, all_workflows):
        """task.active must be a boolean."""
        invalid = {}
        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            for task_key, task in tasks.items():
                if not isinstance(task.get("active"), bool):
                    invalid[f"{w['name']}.{task_key}"] = task.get("active")
        assert not invalid, f"Tasks where 'active' is not a boolean: {invalid}"

    # ------------------------------------------------------------------
    # Task graph integrity
    # ------------------------------------------------------------------

    def test_predecessors_reference_existing_tasks(self, all_workflows):
        """Every entry in task.predecessors must reference an existing task name."""
        violations = {}
        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            task_names = set(tasks.keys())
            for task_key, task in tasks.items():
                for pred in task.get("predecessors") or []:
                    if pred not in task_names:
                        violations.setdefault(w["name"], []).append(f"{task_key}.predecessors → '{pred}' not found")
        assert not violations, f"Workflows with broken predecessor references: {violations}"

    def test_conditions_states_reference_existing_tasks(self, all_workflows):
        """Every key in task.conditions.states must reference an existing task name."""
        violations = {}
        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            task_names = set(tasks.keys())
            for task_key, task in tasks.items():
                states = (task.get("conditions") or {}).get("states") or {}
                for state_key in states:
                    if state_key not in task_names:
                        violations.setdefault(w["name"], []).append(f"{task_key}.conditions.states → '{state_key}' not found")
        assert not violations, f"Workflows with broken conditions.states references: {violations}"

    def test_no_self_referential_predecessor(self, all_workflows):
        """A task must not list itself as a predecessor."""
        violations = {}
        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            for task_key, task in tasks.items():
                if task_key in (task.get("predecessors") or []):
                    violations.setdefault(w["name"], []).append(task_key)
        assert not violations, f"Tasks referencing themselves as predecessors: {violations}"

    # ------------------------------------------------------------------
    # Comment header (required by deploy_dt_assets.sh for name extraction)
    # ------------------------------------------------------------------

    def test_workflow_comment_header_present(self, all_workflows):
        """Every workflow YAML must start with a '# WORKFLOW:' comment header."""
        missing = {w["name"] for w in all_workflows if not w["raw_text"].startswith("# WORKFLOW:")}
        assert not missing, f"Workflows missing '# WORKFLOW:' comment header: {missing}"

    def test_title_consistent_with_comment_header(self, all_workflows):
        """The workflow title must appear in the '# WORKFLOW:' comment header."""
        violations = {}
        for w in all_workflows:
            title = (w["content"].get("title") or "").strip()
            first_line = w["raw_text"].splitlines()[0]
            # Extract the name part after '# WORKFLOW:'
            header_name = first_line[len("# WORKFLOW:") :].strip()
            if title and header_name and title != header_name:
                violations[w["name"]] = {"comment": header_name, "title": title}
        assert not violations, f"Workflows where title != WORKFLOW comment: {violations}"
