"""Discovery and parsing of instruments-def.yml files into classified field entries."""

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

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from build.semantic_exporter.yaml_helpers import ExportError
from build.semantic_exporter.field_emitters import (
    KNOWN_REFS,
    VALID_SEMDICT_FLAGS,
    classify_field,
    emit_id_entry,
    emit_ref_entry,
    validate_entry,
)

log = logging.getLogger("build.export_semantics")


class EntryDiscoverer:
    """Discovers, parses, and groups instruments-def.yml field entries.

    Attributes:
        repo_root: Absolute path to the repository root.
    """

    def __init__(self, repo_root: Path) -> None:
        """Initialise the discoverer.

        Args:
            repo_root: Repository root path.
        """
        self.repo_root = repo_root

    def discover_files(self) -> List[Tuple[str, Path]]:
        """Glob all instruments-def.yml files. Returns list of (plugin_name, path)."""
        files: List[Tuple[str, Path]] = []
        core_file = self.repo_root / "src" / "dtagent.conf" / "instruments-def.yml"
        if core_file.exists():
            files.append(("_core", core_file))
        else:
            log.warning("Core instruments-def.yml not found at %s", core_file)
        for path in sorted(self.repo_root.glob("src/dtagent/plugins/*.config/instruments-def.yml")):
            plugin_name = path.parent.name.replace(".config", "")
            files.append((plugin_name, path))
        log.info("Found %d instruments-def.yml files", len(files))
        return files

    def parse_file(self, plugin_name: str, path: Path) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """Parse a single instruments-def.yml file.

        Args:
            plugin_name: Plugin name for error messages.
            path:        Path to the file.

        Returns:
            Tuple of (errors, entries).

        Raises:
            ExportError: If the file cannot be parsed.
        """
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except Exception as exc:
            raise ExportError(f"Failed to parse {path}: {exc}") from exc
        if not data:
            log.warning("Empty instruments-def.yml: %s", path)
            return [], {}
        errors: List[str] = []
        entries: Dict[str, Dict[str, Any]] = {}
        for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
            for key, raw_entry in (data.get(section) or {}).items():
                entry = raw_entry or {}
                if not isinstance(entry, dict):
                    log.warning("[%s] %s.%s: skipping non-dict entry", plugin_name, section, key)
                    continue
                semdict_flag = entry.get("__semdict", "new")
                if semdict_flag not in VALID_SEMDICT_FLAGS:
                    log.warning("[%s] %s.%s: unknown __semdict '%s'; treating as 'new'", plugin_name, section, key, semdict_flag)
                    semdict_flag = "new"
                if semdict_flag != "ref":
                    errors.extend(validate_entry(key, entry, section, str(path)))
                if semdict_flag == "ref" and key not in KNOWN_REFS:
                    log.warning("[%s] %s.%s: __semdict: ref but key not in KNOWN_REFS", plugin_name, section, key)
                entries[key] = {
                    "section": section,
                    "semdict": semdict_flag,
                    "plugin": plugin_name,
                    "entry": entry,
                    "classification": classify_field(key, section, entry.get("__field_type")),
                }
        return errors, entries

    def group_entries(
        self, all_entries: Dict[str, Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """Separate entries into resource/signal/event_timestamp/metric buckets.

        Args:
            all_entries: All parsed entries keyed by field key.

        Returns:
            Tuple of (resource_entries, signal_entries, event_ts_entries, plugin_metric_entries).
        """
        resource_entries: Dict[str, Any] = {}
        signal_entries: Dict[str, Any] = {}
        event_ts_entries: Dict[str, Any] = {}
        plugin_metric_entries: Dict[str, Dict[str, Any]] = {}
        for key, meta in all_entries.items():
            classification = meta["classification"]
            if classification == "metric":
                plugin_metric_entries.setdefault(meta["plugin"], {})[key] = meta
            elif classification == "event_timestamp":
                event_ts_entries[key] = meta
            elif classification == "resource":
                resource_entries[key] = meta
            else:
                signal_entries[key] = meta
        return resource_entries, signal_entries, event_ts_entries, plugin_metric_entries

    @staticmethod
    def build_attribute_node(key: str, meta: Dict[str, Any], counters: Dict[str, int], no_display_name: bool = False) -> Dict[str, Any]:
        """Build a ref: or id: attribute node.

        Args:
            key:             Field key.
            meta:            Entry metadata dict.
            counters:        Mutable export counters dict, updated in-place.
            no_display_name: When ``True``, suppress the ``display_name`` property.

        Returns:
            Semconv-compliant attribute dict.
        """
        semdict_flag = meta["semdict"]
        entry = meta["entry"]
        if semdict_flag == "ref":
            counters["ref"] += 1
            return emit_ref_entry(key, entry)
        node = emit_id_entry(key, entry, semdict_flag, no_display_name=no_display_name)
        counters["deprecated_alias" if semdict_flag == "deprecated-alias" else "otel_only" if semdict_flag == "otel-only" else "new"] += 1
        return node
