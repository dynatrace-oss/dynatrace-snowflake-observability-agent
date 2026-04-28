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

"""Structural validation tests for OpenPipeline Settings 2.0 pipeline YAML files."""

import glob
import os
from typing import Any, Dict, List

import yaml
import pytest

OPENPIPELINE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "openpipeline")

# Metric keys shipped in this PR (task-run state counters).
# Login metrics (e.g. snowflake.login.attempts.failed) are deferred pending naming sign-off.
KNOWN_METRIC_KEYS = {
    "snowflake.task.run.failed",
    "snowflake.task.run.cancelled",
    "snowflake.task.run.successful",
}

HIGH_CARDINALITY_DIMENSIONS = {"snowflake.task.run.id"}


def _load_all_pipelines() -> List[Dict[str, Any]]:
    """Load all *.yml pipeline files from docs/openpipeline/**/*.yml."""
    pattern = os.path.join(OPENPIPELINE_DIR, "**", "*.yml")
    pipelines = []
    for path in sorted(glob.glob(pattern, recursive=True)):
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        data["_source_file"] = path
        pipelines.append(data)
    return pipelines


def _extract_metric_processors(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract metric-extraction processors from a Settings 2.0 pipeline object."""
    value = pipeline.get("value", {})
    metric_extraction = value.get("metricExtraction", {})
    return metric_extraction.get("processors", [])


@pytest.fixture(scope="module")
def all_pipelines() -> List[Dict[str, Any]]:
    """Module-scoped fixture: loads all OpenPipeline YAML files once."""
    loaded = _load_all_pipelines()
    assert loaded, f"No OpenPipeline YAML files found under {OPENPIPELINE_DIR}"
    return loaded


class TestOpenpipelineSettings2Structure:
    """Validates Settings 2.0 structural constraints for each OpenPipeline pipeline YAML."""

    def test_required_top_level_fields_present(self, all_pipelines):
        """Every pipeline file must have objectid, schemaid, schemaversion, and value."""
        required = {"objectid", "schemaid", "schemaversion", "value"}
        problems = []
        for pipeline in all_pipelines:
            missing = required - set(pipeline.keys())
            if missing:
                problems.append(f"{pipeline['_source_file']}: missing top-level fields: {sorted(missing)}")
        assert not problems, "\n".join(problems)

    def test_schemaid_is_openpipeline(self, all_pipelines):
        """The schemaid field must reference an openpipeline schema."""
        problems = []
        for pipeline in all_pipelines:
            schemaid = pipeline.get("schemaid", "")
            if "openpipeline" not in schemaid:
                problems.append(f"{pipeline['_source_file']}: schemaid {schemaid!r} does not reference an openpipeline schema")
        assert not problems, "\n".join(problems)

    def test_value_contains_metric_extraction(self, all_pipelines):
        """Every pipeline must have a value.metricExtraction.processors list."""
        problems = []
        for pipeline in all_pipelines:
            value = pipeline.get("value", {})
            me = value.get("metricExtraction", {})
            processors = me.get("processors")
            if not isinstance(processors, list):
                problems.append(f"{pipeline['_source_file']}: value.metricExtraction.processors must be a list")
        assert not problems, "\n".join(problems)


class TestOpenpipelineMetricProcessors:
    """Validates metric-extraction processor content within pipeline YAML files."""

    def test_task_run_metric_keys_are_present(self, all_pipelines):
        """All known task-run metric keys must have at least one processor across all pipelines."""
        covered = set()
        for pipeline in all_pipelines:
            for processor in _extract_metric_processors(pipeline):
                key = processor.get("counterMetric", {}).get("metricKey") or processor.get("metricKey")
                if key:
                    covered.add(key)
        missing = KNOWN_METRIC_KEYS - covered
        assert not missing, f"No processor found for metric key(s): {sorted(missing)}"

    def test_each_metric_processor_has_required_fields(self, all_pipelines):
        """Validate that each metric-extraction processor has id, enabled, matcher, type, and metric block."""
        required_base = {"id", "enabled", "matcher", "type"}
        problems = []
        for pipeline in all_pipelines:
            for idx, processor in enumerate(_extract_metric_processors(pipeline)):
                missing = required_base - set(processor.keys())
                if missing:
                    problems.append(f"{pipeline['_source_file']} metricExtraction.processor[{idx}]: missing fields: {sorted(missing)}")
                p_type = processor.get("type")
                if p_type not in ("counterMetric", "valueMetric"):
                    problems.append(
                        f"{pipeline['_source_file']} metricExtraction.processor[{idx}]: "
                        f"type must be 'counterMetric' or 'valueMetric', got: {p_type!r}"
                    )
        assert not problems, "\n".join(problems)

    def test_task_run_processors_have_dimensions(self, all_pipelines):
        """Task-run metric processors must specify at least one dimension."""
        problems = []
        for pipeline in all_pipelines:
            for idx, processor in enumerate(_extract_metric_processors(pipeline)):
                counter = processor.get("counterMetric", {})
                key = counter.get("metricKey")
                if key and key.startswith("snowflake.task.run."):
                    dims = counter.get("dimensions", [])
                    if not isinstance(dims, list) or len(dims) == 0:
                        problems.append(
                            f"{pipeline['_source_file']} processor[{idx}] ({key}): " "counterMetric.dimensions must be a non-empty list"
                        )
        assert not problems, "\n".join(problems)

    def test_no_high_cardinality_dimensions(self, all_pipelines):
        """No metric-extraction processor may use dimensions known to be high-cardinality."""
        problems = []
        for pipeline in all_pipelines:
            for idx, processor in enumerate(_extract_metric_processors(pipeline)):
                counter = processor.get("counterMetric", {})
                dim_names = {d.get("sourceFieldName") for d in counter.get("dimensions", [])}
                offending = dim_names & HIGH_CARDINALITY_DIMENSIONS
                if offending:
                    problems.append(
                        f"{pipeline['_source_file']} processor[{idx}]: " f"high-cardinality dimension(s) not allowed: {sorted(offending)}"
                    )
        assert not problems, "\n".join(problems)

    def test_task_run_processor_ids_are_unique(self, all_pipelines):
        """Processor ids must be unique across all pipeline files."""
        seen: Dict[str, str] = {}
        duplicates = []
        for pipeline in all_pipelines:
            for processor in _extract_metric_processors(pipeline):
                proc_id = processor.get("id")
                if proc_id and proc_id in seen:
                    duplicates.append(f"Duplicate processor id {proc_id!r}: {seen[proc_id]} and {pipeline['_source_file']}")
                elif proc_id:
                    seen[proc_id] = pipeline["_source_file"]
        assert not duplicates, "\n".join(duplicates)

    def test_task_run_processors_are_enabled(self, all_pipelines):
        """Task-run metric processors must be enabled."""
        problems = []
        for pipeline in all_pipelines:
            for idx, processor in enumerate(_extract_metric_processors(pipeline)):
                counter = processor.get("counterMetric", {})
                key = counter.get("metricKey")
                if key and key.startswith("snowflake.task.run."):
                    if not processor.get("enabled", False):
                        problems.append(f"{pipeline['_source_file']} processor[{idx}] ({key}): processor must be enabled")
        assert not problems, "\n".join(problems)
