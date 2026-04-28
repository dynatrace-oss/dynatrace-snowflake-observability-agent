#!/usr/bin/env python3
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

"""Structural validation tests for OpenPipeline metric-extraction rule YAML files."""

import glob
import os
from typing import Any, Dict, List

import yaml
import pytest

OPENPIPELINE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "openpipeline")

KNOWN_METRIC_KEYS = {
    "snowflake.login.attempts.failed",
    "snowflake.task.run.failed",
    "snowflake.task.run.cancelled",
    "snowflake.task.run.successful",
}

HIGH_CARDINALITY_DIMENSIONS = {"snowflake.task.run.id"}


def _load_all_rules() -> List[Dict[str, Any]]:
    """Load all *.yml rule files from docs/openpipeline/**/*.yml."""
    pattern = os.path.join(OPENPIPELINE_DIR, "**", "*.yml")
    rules = []
    for path in sorted(glob.glob(pattern, recursive=True)):
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        data["_source_file"] = path
        rules.append(data)
    return rules


@pytest.fixture(scope="module")
def all_rules() -> List[Dict[str, Any]]:
    """Module-scoped fixture: loads all OpenPipeline rule YAML files once."""
    loaded = _load_all_rules()
    assert loaded, f"No OpenPipeline YAML files found under {OPENPIPELINE_DIR}"
    return loaded


class TestOpenpipelineRuleStructure:
    """Validates structural constraints for each OpenPipeline rule YAML file."""

    def test_required_top_level_fields_present(self, all_rules):
        """Every rule must have id, displayName, pipeline, and processors."""
        required = {"id", "displayName", "pipeline", "processors"}
        problems = []
        for rule in all_rules:
            missing = required - set(rule.keys())
            if missing:
                problems.append(f"{rule['_source_file']}: missing top-level fields: {sorted(missing)}")
        assert not problems, "\n".join(problems)

    def test_processors_is_non_empty_list(self, all_rules):
        """The list of processors must be a non-empty."""
        problems = []
        for rule in all_rules:
            processors = rule.get("processors")
            if not isinstance(processors, list) or len(processors) == 0:
                problems.append(f"{rule['_source_file']}: 'processors' must be a non-empty list")
        assert not problems, "\n".join(problems)

    def test_each_processor_has_required_fields(self, all_rules):
        """Each processor must have type, matcher, metricKey, and dimensions."""
        required = {"type", "matcher", "metricKey", "dimensions"}
        problems = []
        for rule in all_rules:
            for idx, processor in enumerate(rule.get("processors", [])):
                missing = required - set(processor.keys())
                if missing:
                    problems.append(f"{rule['_source_file']} processor[{idx}]: " f"missing fields: {sorted(missing)}")
        assert not problems, "\n".join(problems)

    def test_each_processor_type_is_metric_extraction(self, all_rules):
        """All processors must have type == 'metricExtraction'."""
        problems = []
        for rule in all_rules:
            for idx, processor in enumerate(rule.get("processors", [])):
                if processor.get("type") != "metricExtraction":
                    problems.append(
                        f"{rule['_source_file']} processor[{idx}]: " f"type must be 'metricExtraction', got: {processor.get('type')!r}"
                    )
        assert not problems, "\n".join(problems)

    def test_metric_keys_are_in_allowlist(self, all_rules):
        """All metricKey values must be from the known allow-list."""
        problems = []
        for rule in all_rules:
            for idx, processor in enumerate(rule.get("processors", [])):
                key = processor.get("metricKey")
                if key not in KNOWN_METRIC_KEYS:
                    problems.append(
                        f"{rule['_source_file']} processor[{idx}]: " f"unknown metricKey {key!r}; " f"allowed: {sorted(KNOWN_METRIC_KEYS)}"
                    )
        assert not problems, "\n".join(problems)

    def test_dimensions_is_non_empty_list(self, all_rules):
        """Each processor's dimensions must be a non-empty list."""
        problems = []
        for rule in all_rules:
            for idx, processor in enumerate(rule.get("processors", [])):
                dims = processor.get("dimensions")
                if not isinstance(dims, list) or len(dims) == 0:
                    problems.append(f"{rule['_source_file']} processor[{idx}]: " "'dimensions' must be a non-empty list")
        assert not problems, "\n".join(problems)

    def test_no_high_cardinality_dimensions(self, all_rules):
        """No processor may use dimensions known to be high-cardinality."""
        problems = []
        for rule in all_rules:
            for idx, processor in enumerate(rule.get("processors", [])):
                dims = set(processor.get("dimensions", []))
                offending = dims & HIGH_CARDINALITY_DIMENSIONS
                if offending:
                    problems.append(
                        f"{rule['_source_file']} processor[{idx}]: " f"high-cardinality dimension(s) not allowed: {sorted(offending)}"
                    )
        assert not problems, "\n".join(problems)

    def test_matchers_contain_dsoa_run_context(self, all_rules):
        """Every processor matcher must filter on dsoa.run.context to scope the rule."""
        problems = []
        for rule in all_rules:
            for idx, processor in enumerate(rule.get("processors", [])):
                matcher = processor.get("matcher", "")
                if "dsoa.run.context" not in matcher:
                    problems.append(f"{rule['_source_file']} processor[{idx}]: " "matcher must contain 'dsoa.run.context'")
        assert not problems, "\n".join(problems)


class TestOpenpipelineRuleUniqueness:
    """Validates cross-file uniqueness constraints."""

    def test_rule_ids_are_unique(self, all_rules):
        """The id field must be unique across all rule files."""
        seen: Dict[str, str] = {}
        duplicates = []
        for rule in all_rules:
            rule_id = rule.get("id")
            if rule_id in seen:
                duplicates.append(f"Duplicate id {rule_id!r}: " f"{seen[rule_id]} and {rule['_source_file']}")
            else:
                seen[rule_id] = rule["_source_file"]
        assert not duplicates, "\n".join(duplicates)

    def test_metric_keys_are_unique_per_processor(self, all_rules):
        """Each metricKey may appear in at most one processor across all rules."""
        seen: Dict[str, str] = {}
        duplicates = []
        for rule in all_rules:
            for processor in rule.get("processors", []):
                key = processor.get("metricKey")
                if key in seen:
                    duplicates.append(f"Duplicate metricKey {key!r}: " f"{seen[key]} and {rule['_source_file']}")
                else:
                    seen[key] = rule["_source_file"]
        assert not duplicates, "\n".join(duplicates)


class TestOpenpipelineRuleCount:
    """Validates the expected number of rules is present."""

    def test_expected_rule_count(self, all_rules):
        """There must be exactly 4 OpenPipeline rules defined."""
        assert len(all_rules) == 4, (
            f"Expected 4 OpenPipeline rule files, found {len(all_rules)}: " f"{[r['_source_file'] for r in all_rules]}"
        )

    def test_all_known_metric_keys_are_covered(self, all_rules):
        """Every key in KNOWN_METRIC_KEYS must have at least one rule that produces it."""
        covered = {processor.get("metricKey") for rule in all_rules for processor in rule.get("processors", [])}
        missing = KNOWN_METRIC_KEYS - covered
        assert not missing, f"No rule found for metric key(s): {sorted(missing)}"
