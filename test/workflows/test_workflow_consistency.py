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
"""Tier 1 — Cross-workflow consistency tests.

Validates uniqueness, completeness, and index consistency across all 10
workflow YAML files. All checks are offline — no credentials required.
"""

import pathlib
import re

##region constants
_WORKFLOWS_DIR = pathlib.Path(__file__).parent.parent.parent / "docs" / "workflows"
_README_PATH = _WORKFLOWS_DIR / "README.md"
##endregion


class TestWorkflowConsistency:
    """Cross-workflow consistency and completeness checks."""

    def test_unique_workflow_ids(self, all_workflows):
        """No two workflows may share the same 'id' UUID."""
        seen: dict[str, list[str]] = {}
        for w in all_workflows:
            wf_id = str(w["content"].get("id", ""))
            seen.setdefault(wf_id, []).append(w["name"])
        duplicates = {wf_id: names for wf_id, names in seen.items() if len(names) > 1}
        assert not duplicates, f"Duplicate workflow IDs found: {duplicates}"

    def test_unique_workflow_titles(self, all_workflows):
        """No two workflows may share the same 'title'."""
        seen: dict[str, list[str]] = {}
        for w in all_workflows:
            title = (w["content"].get("title") or "").strip()
            seen.setdefault(title, []).append(w["name"])
        duplicates = {title: names for title, names in seen.items() if len(names) > 1}
        assert not duplicates, f"Duplicate workflow titles found: {duplicates}"

    def test_readme_exists_per_workflow(self, all_workflows):
        """Each workflow directory must contain a readme.md file."""
        missing = {w["name"] for w in all_workflows if not (w["path"].parent / "readme.md").exists()}
        assert not missing, f"Workflow directories missing readme.md: {missing}"

    def test_workflows_listed_in_index(self, all_workflows):
        """Every workflow directory name must appear in docs/workflows/README.md."""
        if not _README_PATH.exists():
            return  # README itself is missing — covered by a separate test
        readme_text = _README_PATH.read_text()
        missing = {w["name"] for w in all_workflows if w["name"] not in readme_text}
        assert not missing, f"Workflows not referenced in docs/workflows/README.md: {missing}"

    def test_index_readme_exists(self):
        """docs/workflows/README.md must exist."""
        assert _README_PATH.exists(), "docs/workflows/README.md is missing"

    def test_minimum_task_count(self, all_workflows):
        """Every workflow must have at least two tasks (Davis + at least one JS)."""
        too_few = {w["name"]: len(w["content"].get("tasks") or {}) for w in all_workflows if len(w["content"].get("tasks") or {}) < 2}
        assert not too_few, f"Workflows with fewer than 2 tasks: {too_few}"

    def test_workflow_count_matches_readme(self, all_workflows):
        """The number of discovered workflow directories must match expected count.

        Expected: 10 workflows (all added in 0.9.5).
        Update this constant when new workflows are added.
        """
        expected_count = 10
        actual_count = len(all_workflows)
        assert actual_count == expected_count, (
            f"Expected {expected_count} workflows, found {actual_count}. "
            "Update expected_count in test_workflow_count_matches_readme when adding new workflows."
        )

    def test_yaml_file_name_matches_directory(self, all_workflows):
        """The YAML filename (without extension) must match the parent directory name."""
        mismatches = {w["name"]: w["path"].stem for w in all_workflows if w["path"].stem != w["name"]}
        assert not mismatches, f"YAML filename does not match directory name: {mismatches}"

    def test_no_duplicate_yaml_per_directory(self):
        """Each workflow directory must contain exactly one .yml file."""
        violations = {}
        for workflow_dir in sorted(_WORKFLOWS_DIR.iterdir()):
            if not workflow_dir.is_dir() or workflow_dir.name.startswith("."):
                continue
            yamls = list(workflow_dir.glob("*.yml"))
            if len(yamls) != 1:
                violations[workflow_dir.name] = [y.name for y in yamls]
        assert not violations, f"Workflow directories with != 1 YAML file: {violations}"

    def test_workflow_comment_tags_non_empty(self, all_workflows):
        """The '# TAGS:' comment header must be present and non-empty."""
        violations = {}
        for w in all_workflows:
            tags_line = next((line for line in w["raw_text"].splitlines() if line.startswith("# TAGS:")), None)
            if not tags_line:
                violations[w["name"]] = "missing '# TAGS:' header"
                continue
            tags_value = tags_line[len("# TAGS:") :].strip()
            if not tags_value:
                violations[w["name"]] = "empty '# TAGS:' header"
        assert not violations, f"Workflows with missing or empty TAGS header: {violations}"

    def test_workflow_plugins_comment_present(self, all_workflows):
        """The '# PLUGINS:' comment header must be present and non-empty."""
        violations = {}
        for w in all_workflows:
            plugins_line = next((line for line in w["raw_text"].splitlines() if line.startswith("# PLUGINS:")), None)
            if not plugins_line:
                violations[w["name"]] = "missing '# PLUGINS:' header"
                continue
            plugins_value = plugins_line[len("# PLUGINS:") :].strip()
            if not plugins_value:
                violations[w["name"]] = "empty '# PLUGINS:' header"
        assert not violations, f"Workflows with missing or empty PLUGINS header: {violations}"

    def test_no_hardcoded_tenant_urls(self, all_workflows):
        """Workflow YAMLs must not contain hardcoded tenant URLs."""
        # Matches patterns like https://xyz.live.dynatrace.com or https://abc.sprint.apps.dynatracelabs.com
        tenant_url_re = re.compile(r"https://[a-z0-9]+\.(live|sprint|apps)\.dynatrace(labs)?\.com", re.IGNORECASE)
        violations = {}
        for w in all_workflows:
            matches = tenant_url_re.findall(w["raw_text"])
            if matches:
                violations[w["name"]] = matches
        assert not violations, f"Workflows with hardcoded tenant URLs: {violations}"

    def test_no_hardcoded_environment_names(self, all_workflows):
        """DQL in workflow YAMLs must not reference hardcoded DEV-XXX environment names."""
        env_re = re.compile(r"\bDEV-\d{3}\b")
        violations = {}
        for w in all_workflows:
            matches = env_re.findall(w["raw_text"])
            if matches:
                violations[w["name"]] = list(set(matches))
        assert not violations, f"Workflows with hardcoded DEV-XXX environment names: {violations}"
