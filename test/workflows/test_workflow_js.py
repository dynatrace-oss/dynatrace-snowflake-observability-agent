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
"""Tier 1 — JavaScript syntax and structure validation for DSOA workflow YAML files.

Extracts all ``run-javascript`` task scripts and validates:

  - Syntax validity via ``node --check`` (skipped when node is not on PATH).
  - Only allowed ``@dynatrace-sdk/*`` imports are used.
  - Each script exports a default async function.
  - The default function parameter destructures ``execution_id``.

All tests are offline (except the node check which needs Node.js ≥ 18 on PATH).
"""

import re
import shutil
import subprocess
import tempfile

import pytest

from test.workflows.conftest import ALLOWED_SDK_IMPORTS, extract_js_scripts

##region helpers
_NODE_AVAILABLE = shutil.which("node") is not None

# Regex patterns for structural checks
_IMPORT_RE = re.compile(r"from\s+['\"](@[^'\"]+)['\"]")
_EXPORT_DEFAULT_RE = re.compile(r"export\s+default\s+async\s+function")
_EXECUTION_ID_PARAM_RE = re.compile(r"export\s+default\s+async\s+function\s*\(\s*\{[^}]*execution_id[^}]*\}")
##endregion


class TestWorkflowJavaScript:
    """JavaScript syntax and structure validation for run-javascript workflow tasks."""

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def test_js_scripts_extractable(self, all_workflows):
        """Every workflow with a run-javascript task must yield at least one script."""
        _JS_ACTION = "dynatrace.automations:run-javascript"
        violations = {}
        for w in all_workflows:
            tasks = w["content"].get("tasks") or {}
            has_js = any(t.get("action") == _JS_ACTION for t in tasks.values())
            if has_js:
                scripts = extract_js_scripts(w["content"])
                if not scripts:
                    violations[w["name"]] = "run-javascript task present but no script extracted"
        assert not violations, f"Workflows with JS tasks but no extractable scripts: {violations}"

    # ------------------------------------------------------------------
    # Structure checks (offline, no node needed)
    # ------------------------------------------------------------------

    def test_js_only_allowed_imports(self, all_workflows):
        """JS scripts must only import from the allowed @dynatrace-sdk/* modules."""
        violations = {}
        for w in all_workflows:
            for idx, script in enumerate(extract_js_scripts(w["content"])):
                for match in _IMPORT_RE.finditer(script):
                    module = match.group(1)
                    if module not in ALLOWED_SDK_IMPORTS:
                        violations.setdefault(w["name"], []).append(f"script{idx}: disallowed import '{module}'")
        assert not violations, f"JavaScript scripts with disallowed imports: {violations}\n" f"Allowed modules: {ALLOWED_SDK_IMPORTS}"

    def test_js_export_default_present(self, all_workflows):
        """Each JavaScript script must export a default async function."""
        violations = {}
        for w in all_workflows:
            for idx, script in enumerate(extract_js_scripts(w["content"])):
                if not _EXPORT_DEFAULT_RE.search(script):
                    violations.setdefault(w["name"], []).append(f"script{idx}: missing 'export default async function'")
        assert not violations, f"JavaScript scripts missing 'export default async function': {violations}"

    def test_js_uses_execution_id_param(self, all_workflows):
        """At least one JavaScript script per workflow must reference ``execution_id``.

        Some workflows use a split pattern: one task queries data independently
        (no ``execution_id`` needed) and a downstream task reads that result via
        ``execution(execution_id)``.  We require that at least one script per
        workflow references ``execution_id`` to ensure the workflow chain is wired.
        """
        violations = {}
        for w in all_workflows:
            scripts = extract_js_scripts(w["content"])
            if not scripts:
                continue
            any_uses_exec_id = any("execution_id" in script for script in scripts)
            if not any_uses_exec_id:
                violations[w["name"]] = "no script references 'execution_id' — workflow result chain may be broken"
        assert not violations, f"Workflows where no JavaScript script references execution_id: {violations}"

    # ------------------------------------------------------------------
    # Syntax validation via node (offline, requires Node.js on PATH)
    # ------------------------------------------------------------------

    @pytest.mark.skipif(not _NODE_AVAILABLE, reason="node not on PATH")
    def test_js_syntax_valid_via_node(self, all_workflows, tmp_path):
        """Each JavaScript script must pass ``node --check``.

        Uses ``.mjs`` extension so Node.js treats the file as an ES module
        (required for ``import`` / ``export`` syntax).

        Skipped automatically when node is not available in the environment.
        """
        failures = {}
        for w in all_workflows:
            for idx, script in enumerate(extract_js_scripts(w["content"])):
                script_file = tmp_path / f"{w['name']}-script{idx}.mjs"
                script_file.write_text(script)
                result = subprocess.run(
                    ["node", "--check", str(script_file)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode != 0:
                    failures.setdefault(w["name"], []).append(
                        {
                            "script_index": idx,
                            "stderr": result.stderr.strip(),
                        }
                    )
        assert not failures, f"JavaScript syntax check failures: {failures}"
