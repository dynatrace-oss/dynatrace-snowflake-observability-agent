"""Shared helpers for semdict regression tests.

Provides utilities for loading instruments-def.yml files and generated
Semantic Dictionary YAML output for use across test_instruments_def_completeness.py,
test_semantics_quality.py, test_semdict_export_completeness.py, and
test_semdict_output_compliance.py.
"""

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

import re
from pathlib import Path
from typing import Any, Dict, Set

import pytest
import yaml

#: Repository root (two levels above this file: test/core/ → test/ → repo root).
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: Path to generated Semantic Dictionary source files.
SEMDICT_SOURCE: Path = REPO_ROOT / "build" / "_semdict" / "source"

#: Raw unit strings that must NOT appear in the final SD output — they must be
#: translated by UNIT_MAP before writing. Shared by test_semantics_quality and
#: test_semdict_output_compliance.
INVALID_SD_UNITS: frozenset = frozenset(
    {
        "bytes",
        "Byte",
        "percent",
        "seconds",
        "days",
        "rows",
        "files",
        "clusters",
        "queries",
        "warehouses",
        "partitions",
        "credits",
        "currency",
        "factor",
    }
)


def load_all_instruments_defs() -> Dict[str, Dict[str, Any]]:
    """Load all instruments-def.yml files from core and all plugin configs.

    Returns:
        Dict mapping plugin name (or ``_core``) to parsed YAML data.
    """
    result: Dict[str, Dict[str, Any]] = {}
    core_file = REPO_ROOT / "src" / "dtagent.conf" / "instruments-def.yml"
    if core_file.exists():
        with open(core_file, "r", encoding="utf-8") as fh:
            result["_core"] = yaml.safe_load(fh) or {}
    for path in sorted(REPO_ROOT.glob("src/dtagent/plugins/*.config/instruments-def.yml")):
        plugin_name = path.parent.name.replace(".config", "")
        with open(path, "r", encoding="utf-8") as fh:
            result[plugin_name] = yaml.safe_load(fh) or {}
    return result


def require_semdict_source() -> None:
    """Skip the calling test if build/_semdict/source/ does not exist.

    Raises:
        pytest.skip: If the output directory is missing.
    """
    if not SEMDICT_SOURCE.exists():
        pytest.skip("build/_semdict/source/ not found — run export_semantics.py first")


def load_all_generated_yaml() -> Dict[str, Dict[str, Any]]:
    """Load all generated YAML files from build/_semdict/source/.

    Skips the calling test if the directory does not exist.

    Returns:
        Dict mapping relative path (str) to parsed YAML content.
    """
    require_semdict_source()
    result: Dict[str, Dict[str, Any]] = {}
    for yaml_file in sorted(SEMDICT_SOURCE.rglob("*.yaml")):
        rel = str(yaml_file.relative_to(SEMDICT_SOURCE))
        with open(yaml_file, "r", encoding="utf-8") as fh:
            result[rel] = yaml.safe_load(fh) or {}
    return result


def collect_signal_field_ids(generated_docs: Dict[str, Dict[str, Any]]) -> Set[str]:
    """Collect all ``id:`` keys from signal_fields/*.yaml files in the generated output.

    Args:
        generated_docs: All parsed generated YAML docs (from ``load_all_generated_yaml``).

    Returns:
        Set of field id strings found in signal_fields/ files.
    """
    ids: Set[str] = set()
    for rel_path, doc in generated_docs.items():
        if "signal_fields" not in rel_path:
            continue
        for group in doc.get("groups", []):
            for attr in group.get("attributes", []):
                if "id" in attr:
                    ids.add(attr["id"])
    return ids


def _discover_model_plugins(glob_pattern: str, base_dir: Path, filename_regex: str) -> Set[str]:
    """Discover plugin names from generated per-plugin model YAML files.

    Only files whose parsed document has a truthy top-level ``model:`` key are
    considered real per-plugin models — this excludes ``model_group:`` container
    files (e.g. ``model_group_dsoa_logs.yaml``) and non-model files (e.g.
    ``interfaces_dsoa.yaml``, which has a top-level ``groups:`` key instead).

    Args:
        glob_pattern: Glob pattern (relative to ``base_dir``) matching candidate files.
        base_dir: Directory to search (e.g. ``SEMDICT_SOURCE / "model" / "dsoa"``).
        filename_regex: Regex with a named ``plugin`` group to extract the plugin name
            from the filename stem.

    Returns:
        Set of discovered plugin name strings.
    """
    require_semdict_source()
    pattern = re.compile(filename_regex)
    plugins: Set[str] = set()
    for yaml_file in sorted(base_dir.glob(glob_pattern)):
        with open(yaml_file, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
        if not doc.get("model"):
            continue
        match = pattern.match(yaml_file.name)
        if match:
            plugins.add(match.group("plugin"))
    return plugins


def discover_log_model_plugins() -> Set[str]:
    """Discover all plugins that emit a log model in the generated output.

    Returns:
        Set of plugin name strings (derived from ``dsoa.logs.<plugin>.yaml`` filenames).
    """
    return _discover_model_plugins(
        "dsoa.logs.*.yaml",
        SEMDICT_SOURCE / "model" / "dsoa",
        r"dsoa\.logs\.(?P<plugin>.+)\.yaml",
    )


def discover_event_model_plugins() -> Set[str]:
    """Discover all plugins that emit an event model in the generated output.

    Returns:
        Set of plugin name strings (derived from ``dsoa.events.<plugin>.yaml`` filenames).
    """
    return _discover_model_plugins(
        "dsoa.events.*.yaml",
        SEMDICT_SOURCE / "model" / "dsoa",
        r"dsoa\.events\.(?P<plugin>.+)\.yaml",
    )


def discover_metric_model_plugins() -> Set[str]:
    """Discover all plugins that emit a metric model in the generated output.

    Excludes ``dsoa_metrics_model_group.yaml`` (a ``model_group:`` container, not
    a per-plugin ``model:``) via the same truthy-``model``-key check applied to
    log/event discovery.

    Returns:
        Set of plugin name strings (derived from ``dsoa_metrics_<plugin>.yaml`` filenames).
    """
    return _discover_model_plugins(
        "dsoa_metrics_*.yaml",
        SEMDICT_SOURCE / "metrics",
        r"dsoa_metrics_(?P<plugin>.+)\.yaml",
    )


def collect_model_referenced_fields(generated_docs: Dict[str, Dict[str, Any]]) -> Set[str]:
    """Collect all field keys referenced by any model or interface in the generated output.

    Collects ``ref:`` entries from both top-level groups (interfaces) and
    model-nested groups (model attributes).

    Args:
        generated_docs: All parsed generated YAML docs (from ``load_all_generated_yaml``).

    Returns:
        Set of field key strings that are referenced somewhere.
    """
    referenced: Set[str] = set()
    for doc in generated_docs.values():
        for group in doc.get("groups", []):
            for attr in group.get("attributes", []):
                if "ref" in attr:
                    referenced.add(attr["ref"])
        model = doc.get("model", {})
        for group in model.get("groups", []):
            for attr in group.get("attributes", []):
                if "ref" in attr:
                    referenced.add(attr["ref"])
    return referenced
