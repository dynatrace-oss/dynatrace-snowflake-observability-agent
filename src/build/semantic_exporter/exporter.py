"""Coordinator that runs the full Semantic Dictionary export pipeline."""

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
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from build.semantic_exporter.yaml_helpers import ExportError
from build.semantic_exporter.discovery import EntryDiscoverer
from build.semantic_exporter.document_builders import DocumentBuilder
from build.semantic_exporter.schema import SchemaValidator
from build.semantic_exporter.writers import OutputWriter
from build.semantic_exporter.field_emitters import (
    SD_OWNED_GROUP_PREFIXES,
    SPAN_PLUGINS,
    _dql_for_context,
    _merge_field_entries,
    _plugin_label,
    _resolve_model_group_dql,
)

log = logging.getLogger("build.export_semantics")


class SemanticExporter:
    """Reads instruments-def.yml files and emits Semantic Dictionary YAML.

    Attributes:
        repo_root:   Absolute path to the repository root.
        output_dir:  Directory where generated YAML files are written.
        schema_path: Optional path to ``semconv.schema.json`` for validation.
    """

    def __init__(
        self,
        repo_root: Path,
        output_dir: Path,
        schema_path: Optional[Path] = None,
        sd_metadata: bool = False,
        no_display_name: bool = False,
    ) -> None:
        """Initialise the exporter.

        Args:
            repo_root:        Repository root path.
            output_dir:       Output directory (created on demand).
            schema_path:      Optional semconv JSON schema for validation.
            sd_metadata:      When ``True``, write SD metadata files alongside the YAML source:
                              ``OWNERS``, ``definitions/mapping/global_field_categories.json``,
                              and ``doc/`` model/field stubs required by the SD generator.
                              Set this only when targeting the actual SD repo checkout —
                              **not** for the regular ``make semantic-dictionary`` export to
                              ``docs/semantic-dictionary/``.
            no_display_name:  When ``True``, suppress the ``display_name`` property on all
                              emitted attribute and enum member nodes.  Use when the target
                              SD PR should not include ``display_name`` fields (e.g. when the
                              SD committee has not yet approved them for a namespace).
        """
        self.repo_root = repo_root
        self.schema_path = schema_path
        self._sd_metadata = sd_metadata
        self._no_display_name = no_display_name
        self._counters: Dict[str, int] = {
            "files": 0,
            "ref": 0,
            "new": 0,
            "deprecated_alias": 0,
            "otel_only": 0,
            "resource_fields": 0,
            "signal_fields": 0,
            "metric_fields": 0,
            "event_timestamp_fields": 0,
        }
        self._discoverer = EntryDiscoverer(repo_root)
        self._builder = DocumentBuilder(no_display_name)
        self._schema_validator = SchemaValidator(schema_path)
        self._writer = OutputWriter(repo_root, output_dir)

    @property
    def output_dir(self) -> Path:
        """Output directory, proxied to the underlying :class:`OutputWriter` (kept for test/API compatibility)."""
        return self._writer.output_dir

    @output_dir.setter
    def output_dir(self, value: Path) -> None:
        self._writer.output_dir = value

    ##region Backward-compatible delegation

    def _parse_file(self, plugin_name: str, path: Path) -> Tuple[List[str], Dict[str, Any]]:
        """Delegate to :meth:`EntryDiscoverer.parse_file` (kept for test/API compatibility)."""
        return self._discoverer.parse_file(plugin_name, path)

    def _build_attribute_node(self, key: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to :meth:`EntryDiscoverer.build_attribute_node` (kept for test/API compatibility)."""
        return EntryDiscoverer.build_attribute_node(key, meta, self._counters, self._no_display_name)

    def _build_resource_fields_yaml(self, resource_entries: Dict[str, Any]):
        """Delegate to :meth:`DocumentBuilder.build_resource_fields_yaml` (kept for test/API compatibility)."""
        return self._builder.build_resource_fields_yaml(resource_entries, self._counters)

    def _build_signal_fields_yaml(self, signal_entries: Dict[str, Any], event_ts_entries: Dict[str, Any]):
        """Delegate to :meth:`DocumentBuilder.build_signal_fields_yaml` (kept for test/API compatibility)."""
        return self._builder.build_signal_fields_yaml(signal_entries, event_ts_entries, self._counters)

    def _build_interfaces_yaml(self, all_entries: Optional[Dict[str, Any]] = None):
        """Delegate to :meth:`DocumentBuilder.build_interfaces_yaml` (kept for test/API compatibility)."""
        return self._builder.build_interfaces_yaml(all_entries)

    def _build_metric_model_yaml(
        self,
        plugin_name: str,
        metric_entries: Dict[str, Any],
        all_entries: Dict[str, Any],
        dim_plugins=None,
        dim_context_by_plugin=None,
        dql_queries=None,
    ) -> Dict[str, Any]:
        """Delegate to :meth:`DocumentBuilder.build_metric_model_yaml` (kept for test/API compatibility)."""
        return self._builder.build_metric_model_yaml(
            plugin_name, metric_entries, all_entries, self._counters, dim_plugins, dim_context_by_plugin, dql_queries
        )

    def _build_event_model_yaml(self, plugin_name: str, event_ts_entries: Dict[str, Any], dql_queries=None) -> Dict[str, Any]:
        """Delegate to :meth:`DocumentBuilder.build_event_model_yaml` (kept for test/API compatibility)."""
        return self._builder.build_event_model_yaml(plugin_name, event_ts_entries, self._counters, dql_queries)

    def _write_owners(self, content: str) -> Path:
        """Delegate to :meth:`OutputWriter.write_owners` (kept for test/API compatibility)."""
        return self._writer.write_owners(content, self._counters)

    def _build_owners_entries(self, signal_group_ids: List[str], resource_group_ids: List[str], plugin_names: List[str]) -> str:
        """Delegate to :meth:`OutputWriter.build_owners_entries` (kept for test/API compatibility)."""
        return self._writer.build_owners_entries(signal_group_ids, resource_group_ids, plugin_names)

    def _build_model_doc_stubs(self, sub_groups=None) -> Dict[str, str]:
        """Delegate to :meth:`OutputWriter.build_model_doc_stubs` (kept for test/API compatibility)."""
        return self._writer.build_model_doc_stubs(sub_groups)

    def _build_per_model_doc_stubs(self, models: List[Dict[str, Any]]) -> Dict[str, str]:
        """Delegate to :meth:`OutputWriter.build_per_model_doc_stubs` (kept for test/API compatibility)."""
        return self._writer.build_per_model_doc_stubs(models)

    def _build_per_field_doc_stubs(self, field_groups: List[Dict[str, Any]]) -> Dict[str, str]:
        """Delegate to :meth:`OutputWriter.build_per_field_doc_stubs` (kept for test/API compatibility)."""
        return self._writer.build_per_field_doc_stubs(field_groups)

    ##endregion

    def export(self) -> Dict[str, int]:
        """Run the full semantic dictionary export pipeline.

        Returns:
            Dict with counter keys: ``files``, ``ref``, ``new``,
            ``deprecated_alias``, ``otel_only``, ``resource_fields``,
            ``signal_fields``, ``metric_fields``, ``event_timestamp_fields``.

        Raises:
            ExportError: On missing metadata or parse failure.
        """
        # Step 1: Discovery
        files = self._discoverer.discover_files()
        if not files:
            raise ExportError("No instruments-def.yml files found")

        # Step 2: Parse + validate
        all_errors: List[str] = []
        all_entries: Dict[str, Any] = {}
        dim_plugins: Dict[str, Set[str]] = {}
        # Per-plugin dimension context names: {plugin_name: {dim_key: set(context_names)}}
        # This preserves each plugin's own context annotations independent of dedup winner.
        dim_context_by_plugin: Dict[str, Dict[str, Set[str]]] = {}
        # Per-plugin DQL query examples collected directly from the top-level dql_queries: key
        # in each instruments-def.yml file.  Keyed by plugin_name (or "_core").  Each entry's
        # ``context`` list routes it to the matching model type(s) via ``_dql_for_context``.
        plugin_dql_queries: Dict[str, List[Dict[str, Any]]] = {}
        for plugin_name, path in files:
            log.debug("Parsing %s (%s)", plugin_name, path)
            errors, entries = self._discoverer.parse_file(plugin_name, path)
            all_errors.extend(errors)
            # Collect top-level dql_queries from the raw YAML (separate from field entries).
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    raw_data = yaml.safe_load(fh) or {}
                raw_queries = raw_data.get("dql_queries")
                if raw_queries and isinstance(raw_queries, list):
                    plugin_dql_queries[plugin_name] = raw_queries
                    log.debug("Collected %d dql_queries from %s", len(raw_queries), plugin_name)
            except Exception as exc:  # pylint: disable=broad-except
                log.warning("Could not re-read dql_queries from %s: %s", path, exc)
            for key, meta in entries.items():
                # Track all plugins that define each dimension key (for A3 ownership)
                if meta["section"] == "dimensions":
                    dim_plugins.setdefault(key, set()).add(plugin_name)
                    ctx = set(meta["entry"].get("__context_names") or [])
                    dim_context_by_plugin.setdefault(plugin_name, {}).setdefault(key, set()).update(ctx)
                if key in all_entries:
                    all_entries[key] = _merge_field_entries(key, all_entries[key], meta)
                else:
                    all_entries[key] = meta
        if all_errors:
            raise ExportError("Validation errors found:\n" + "\n".join(all_errors))

        # Resolve model_group_dql from its dedicated tooling file (expands use_plugin_dql references).
        _mg_dql_path = self.repo_root / "scripts" / "tools" / "model-group-dql.yml"
        _core_raw: Dict[str, Any] = {}
        if _mg_dql_path.exists():
            try:
                with open(_mg_dql_path, "r", encoding="utf-8") as fh:
                    _core_raw = yaml.safe_load(fh) or {}
            except Exception as exc:  # pylint: disable=broad-except
                log.warning("Could not read model_group_dql file from %s: %s", _mg_dql_path, exc)
        else:
            log.warning("model_group_dql file not found at %s", _mg_dql_path)
        resolved_mg_dql = _resolve_model_group_dql(_core_raw.get("model_group_dql"), plugin_dql_queries)
        log.info("Resolved model_group_dql for %d group(s): %s", len(resolved_mg_dql), sorted(resolved_mg_dql))

        # Step 3: Group
        resource_entries, signal_entries, event_ts_entries, plugin_metric_entries = self._discoverer.group_entries(all_entries)
        log.info(
            "Resource: %d  Signal: %d  EventTS: %d  PluginMetricGroups: %d",
            len(resource_entries),
            len(signal_entries),
            len(event_ts_entries),
            len(plugin_metric_entries),
        )

        # Step 4: Load schema
        self._schema_validator.load_schema()

        # Step 5: resource_fields
        sf_res_doc, dsoa_res_doc = self._builder.build_resource_fields_yaml(resource_entries, self._counters)
        if sf_res_doc.get("groups"):
            p = self._writer.write_yaml(sf_res_doc, "fields/resource_fields/snowflake_resource.yaml", self._counters)
            self._schema_validator.validate_against_schema(sf_res_doc, p)
        if dsoa_res_doc.get("groups") and dsoa_res_doc["groups"][0].get("attributes"):
            p = self._writer.write_yaml(dsoa_res_doc, "fields/resource_fields/dsoa_resource.yaml", self._counters)
            self._schema_validator.validate_against_schema(dsoa_res_doc, p)

        # Step 6: signal_fields — one file per namespace group
        sig_docs = self._builder.build_signal_fields_yaml(signal_entries, event_ts_entries, self._counters)
        for rel_path, sig_doc in sig_docs.items():
            if sig_doc.get("groups"):
                p = self._writer.write_yaml(sig_doc, rel_path, self._counters)
                self._schema_validator.validate_against_schema(sig_doc, p)

        # Step 7: interfaces + model group
        dsoa_iface_doc, sf_iface_doc = self._builder.build_interfaces_yaml(all_entries)
        p = self._writer.write_yaml(dsoa_iface_doc, "metrics/interfaces_dsoa.yaml", self._counters)
        self._schema_validator.validate_against_schema(dsoa_iface_doc, p)
        p = self._writer.write_yaml(sf_iface_doc, "metrics/interfaces_snowflake.yaml", self._counters)
        self._schema_validator.validate_against_schema(sf_iface_doc, p)
        self._writer.write_yaml(
            {
                "model_group": {
                    "id": "snowflake.metrics",
                    "title": "Snowflake metrics",
                    "brief": "Metrics collected by the DSOA from Snowflake ACCOUNT_USAGE views.",
                    **({} if not resolved_mg_dql.get("snowflake.metrics") else {"dql_queries": resolved_mg_dql["snowflake.metrics"]}),
                }
            },
            "metrics/snowflake_metrics_model_group.yaml",
            self._counters,
        )

        # Step 8: per-plugin metric models
        for plugin_name in sorted(plugin_metric_entries):
            if plugin_name == "_core":
                continue
            entries = plugin_metric_entries[plugin_name]
            if not entries:
                continue
            doc = self._builder.build_metric_model_yaml(
                plugin_name,
                entries,
                all_entries,
                self._counters,
                dim_plugins,
                dim_context_by_plugin,
                dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "metrics"),
            )
            p = self._writer.write_yaml(doc, f"metrics/snowflake_metrics_{plugin_name}.yaml", self._counters)
            self._schema_validator.validate_against_schema(doc, p)

        # Step 9: per-plugin event models
        plugins_with_events: Set[str] = {meta["plugin"] for k, meta in event_ts_entries.items() if k != "snowflake.event.trigger"}
        if plugins_with_events:
            self._writer.write_yaml(
                {
                    "model_group": {
                        "id": "snowflake.events",
                        "title": "Snowflake lifecycle events",
                        "brief": "Timestamp-based state-change events emitted by DSOA plugins via the Dynatrace OpenPipeline Events API.",
                        "parent_model_group_id": "snowflake",
                        **({} if not resolved_mg_dql.get("snowflake.events") else {"dql_queries": resolved_mg_dql["snowflake.events"]}),
                    }
                },
                "model/snowflake/events/model_group_snowflake_events.yaml",
                self._counters,
            )
            for plugin_name in sorted(plugins_with_events):
                doc = self._builder.build_event_model_yaml(
                    plugin_name,
                    event_ts_entries,
                    self._counters,
                    dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "events"),
                )
                p = self._writer.write_yaml(doc, f"model/snowflake/events/snowflake.events.{plugin_name}.yaml", self._counters)
                self._schema_validator.validate_against_schema(doc, p)

        # Step 10: per-plugin log models (resolves signal field orphans)
        plugins_with_attrs: Set[str] = {
            meta["plugin"] for meta in all_entries.values() if meta["section"] == "attributes" and meta["semdict"] != "ref"
        }
        plugins_with_attrs.discard("_core")  # _core attrs are resource-level; no log model needed
        if plugins_with_attrs:
            self._writer.write_yaml(
                {
                    "model_group": {
                        "id": "snowflake.logs",
                        "title": "Snowflake log records",
                        "brief": "Log records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE and system views.",
                        "parent_model_group_id": "snowflake",
                        **({} if not resolved_mg_dql.get("snowflake.logs") else {"dql_queries": resolved_mg_dql["snowflake.logs"]}),
                    }
                },
                "model/snowflake/logs/model_group_snowflake_logs.yaml",
                self._counters,
            )
            for plugin_name in sorted(plugins_with_attrs):
                doc = self._builder.build_log_model_yaml(
                    plugin_name,
                    all_entries,
                    dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "logs"),
                )
                p = self._writer.write_yaml(doc, f"model/snowflake/logs/snowflake.logs.{plugin_name}.yaml", self._counters)
                self._schema_validator.validate_against_schema(doc, p)

        # Step 11: per-plugin span models (only for SPAN_PLUGINS)
        span_model_plugins = plugins_with_attrs & SPAN_PLUGINS
        if span_model_plugins:
            self._writer.write_yaml(
                {
                    "model_group": {
                        "id": "snowflake.spans",
                        "title": "Snowflake spans",
                        "brief": "Span records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE views.",
                        "parent_model_group_id": "snowflake",
                        **({} if not resolved_mg_dql.get("snowflake.spans") else {"dql_queries": resolved_mg_dql["snowflake.spans"]}),
                    }
                },
                "model/snowflake/spans/model_group_snowflake_spans.yaml",
                self._counters,
            )
            for plugin_name in sorted(span_model_plugins):
                doc = self._builder.build_span_model_yaml(
                    plugin_name,
                    all_entries,
                    dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "spans"),
                )
                p = self._writer.write_yaml(doc, f"model/snowflake/spans/snowflake.spans.{plugin_name}.yaml", self._counters)
                self._schema_validator.validate_against_schema(doc, p)

        # Generate span model for event_log even if it has no attributes
        # (event_log emits spans from its SQL context; span fields are tracked as dimensions)
        if "event_log" in SPAN_PLUGINS and "event_log" not in span_model_plugins:
            if not span_model_plugins:  # model_group not yet written
                self._writer.write_yaml(
                    {
                        "model_group": {
                            "id": "snowflake.spans",
                            "title": "Snowflake spans",
                            "brief": "Span records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE views.",
                            "parent_model_group_id": "snowflake",
                            **({} if not resolved_mg_dql.get("snowflake.spans") else {"dql_queries": resolved_mg_dql["snowflake.spans"]}),
                        }
                    },
                    "model/snowflake/spans/model_group_snowflake_spans.yaml",
                    self._counters,
                )
            doc = self._builder.build_span_model_yaml(
                "event_log",
                all_entries,
                dql_queries=_dql_for_context(plugin_dql_queries.get("event_log"), "spans"),
            )
            p = self._writer.write_yaml(doc, "model/snowflake/spans/snowflake.spans.event_log.yaml", self._counters)
            self._schema_validator.validate_against_schema(doc, p)

        # Step 11b: parent "snowflake" model_group — only when at least one of the
        # events/logs/spans sub-groups was actually written this run. The bullet list
        # only references subfolders that exist.
        written_sub_groups: Set[str] = set()
        if plugins_with_events:
            written_sub_groups.add("events")
        if plugins_with_attrs:
            written_sub_groups.add("logs")
        if span_model_plugins or ("event_log" in SPAN_PLUGINS and "event_log" not in span_model_plugins):
            written_sub_groups.add("spans")
        if written_sub_groups:
            bullet_labels = {
                "events": "[Lifecycle events](./events/readme.md)",
                "logs": "[Log records](./logs/readme.md)",
                "spans": "[Spans](./spans/readme.md)",
            }
            bullets = "\n".join(f"* {bullet_labels[sg]}" for sg in ("events", "logs", "spans") if sg in written_sub_groups)
            self._writer.write_yaml(
                {
                    "model_group": {
                        "id": "snowflake",
                        "title": "Snowflake",
                        "brief": (
                            "DSOA (Dynatrace Snowflake Observability Agent) telemetry models, organized by signal type:\n\n" + bullets
                        ),
                        **({} if not resolved_mg_dql.get("snowflake") else {"dql_queries": resolved_mg_dql["snowflake"]}),
                    }
                },
                "model/snowflake/model_group_snowflake.yaml",
                self._counters,
            )

        # Step 12: SD metadata — OWNERS, field categories, and doc stubs.
        # Only written when targeting the actual SD repo (--sd-metadata flag).
        # Never written for the regular 'make semantic-dictionary' export to docs/.
        if self._sd_metadata:
            signal_group_ids = [g["id"] for doc in sig_docs.values() for g in doc.get("groups", [])]
            resource_group_ids = [g["id"] for g in sf_res_doc.get("groups", [])] + [g["id"] for g in dsoa_res_doc.get("groups", [])]
            plugin_names_sorted = sorted(plugin_metric_entries.keys() - {"_core"})
            self._writer.write_owners(
                self._writer.build_owners_entries(signal_group_ids, resource_group_ids, plugin_names_sorted), self._counters
            )
            self._writer.update_field_categories(signal_group_ids, resource_group_ids, self._counters)
            for rel_path, content in self._writer.build_model_doc_stubs(sub_groups=written_sub_groups).items():
                self._writer.write_sd_root_text(content, rel_path, self._counters)

            # Per-model doc stubs (logs, events, spans) — required by the SD generator to
            # populate the ``<!-- model <id> -->`` sections (F001/F004/F025 root cause A).
            per_model_stubs: List[Dict[str, Any]] = []
            for plugin_name in sorted(plugins_with_attrs):
                per_model_stubs.append(
                    {
                        "id": f"snowflake.logs.{plugin_name}",
                        "title": f"Snowflake {_plugin_label(plugin_name)} log records",
                        "brief": f"Log records emitted by the DSOA {plugin_name} plugin from Snowflake ACCOUNT_USAGE and system views.",
                        "signal_type": "logs",
                        "has_fields": True,
                    }
                )
            for plugin_name in sorted(plugins_with_events):
                per_model_stubs.append(
                    {
                        "id": f"snowflake.events.{plugin_name}",
                        "title": f"Snowflake {_plugin_label(plugin_name)} lifecycle events",
                        "brief": f"Timestamp-based state-change events emitted by the DSOA {plugin_name} plugin via the OpenPipeline Events API.",
                        "signal_type": "events",
                        "has_fields": True,
                    }
                )
            all_span_plugins = span_model_plugins | ({"event_log"} if "event_log" in SPAN_PLUGINS else set())
            for plugin_name in sorted(all_span_plugins):
                per_model_stubs.append(
                    {
                        "id": f"snowflake.spans.{plugin_name}",
                        "title": f"Snowflake {_plugin_label(plugin_name)} spans",
                        "brief": f"Span records emitted by the DSOA {plugin_name} plugin from Snowflake ACCOUNT_USAGE views.",
                        "signal_type": "spans",
                        # A span model has an inner <plugin>.fields attribute_group only when it
                        # has attribute refs (span_model_plugins). event_log is added even without
                        # attributes and therefore has empty groups — no inner semconv reference.
                        "has_fields": plugin_name in span_model_plugins,
                    }
                )
            for rel_path, content in self._writer.build_per_model_doc_stubs(per_model_stubs).items():
                self._writer.write_sd_root_text(content, rel_path, self._counters)

            # Per-field-group doc stubs — required by the SD generator to populate the
            # ``<!-- semconv <group_id> -->`` sections in doc/fields/ (point 3 of review).
            # Titles are derived from sig_docs (Option A) to avoid re-reading YAML.
            sig_group_titles: Dict[str, str] = {g["id"]: g.get("title", "") for doc in sig_docs.values() for g in doc.get("groups", [])}
            field_stubs = [
                {"group_id": gid, "title": sig_group_titles.get(gid, ""), "is_resource": False}
                for gid in sorted(sig_group_titles)
                if any(gid == p or gid.startswith(p + ".") for p in SD_OWNED_GROUP_PREFIXES)
            ]
            # Also include resource_fields groups (dsoa, snowflake.resource_monitor.resource,
            # snowflake.warehouse.resource) — they are global groups and require a doc stub
            # so the SD generator can find them (otherwise F003 fires).  These originate from
            # the resource_fields docs, so their h2 heading carries a " resource" qualifier.
            res_group_titles: Dict[str, str] = {
                g["id"]: g.get("title", "") for res_doc in (sf_res_doc, dsoa_res_doc) for g in res_doc.get("groups", [])
            }
            for gid, title in sorted(res_group_titles.items()):
                if any(gid == p or gid.startswith(p + ".") for p in SD_OWNED_GROUP_PREFIXES):
                    field_stubs.append({"group_id": gid, "title": title, "is_resource": True})
            for rel_path, content in self._writer.build_per_field_doc_stubs(field_stubs).items():
                self._writer.write_sd_root_text(content, rel_path, self._counters)

        return dict(self._counters)
