"""Builders for Semantic Dictionary field-definition, interface, and model YAML documents."""

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

from typing import Any, Dict, List, Optional, Set, Tuple

from build.semantic_exporter.discovery import EntryDiscoverer
from build.semantic_exporter.field_emitters import (
    INTERFACE_DATABASE_KEYS,
    INTERFACE_WAREHOUSE_KEYS,
    RESOURCE_ATTRIBUTE_KEYS,
    GROUP_TITLE_OVERRIDES,
    RES_NS,
    SIG_NS,
    emit_metric_entry,
    make_display_name,
    make_title,
    ns_group,
    plugin_label,
)


class DocumentBuilder:
    """Builds resource/signal field, interface, and model YAML document dicts.

    Attributes:
        no_display_name: When ``True``, suppress ``display_name`` on emitted nodes.
    """

    def __init__(self, no_display_name: bool = False) -> None:
        """Initialise the document builder.

        Args:
            no_display_name: When ``True``, suppress the ``display_name`` property on
                             all emitted attribute and enum member nodes.
        """
        self._no_display_name = no_display_name

    def build_resource_fields_yaml(
        self, resource_entries: Dict[str, Any], counters: Dict[str, int]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Build resource_fields/snowflake_resource.yaml and resource_fields/dsoa_resource.yaml.

        Ref entries (``semdict == "ref"``) are intentionally excluded from both output files.
        They belong exclusively in the ``i.dsoa_resource`` interface (emitted by
        ``build_interfaces_yaml``), which already declares ``{"ref": key}`` for every key
        in ``RESOURCE_ATTRIBUTE_KEYS``.  Including refs here would produce duplicate ``ref:``
        nodes in field definition files, which is incorrect SD structure.

        Args:
            resource_entries: All resource-classified entries.
            counters:         Mutable export counters dict, updated in-place.

        Returns:
            Tuple of (snowflake_resource_doc, dsoa_resource_doc).
        """
        # Route to dsoa.yaml: DSOA/deployment-namespaced fields only.
        # Refs go ONLY to the interface (already in build_interfaces_yaml) — never to field files.
        dsoa_keys = {
            k: v for k, v in resource_entries.items() if (k.startswith("dsoa.") or k.startswith("deployment.")) and v["semdict"] != "ref"
        }
        snowflake_keys = {k: v for k, v in resource_entries.items() if k not in dsoa_keys and v["semdict"] != "ref"}

        sf_groups: Dict[str, Dict[str, Any]] = {}
        for key in sorted(snowflake_keys):
            group_id, group_type = ns_group(key, RES_NS, "snowflake.resource", "resource")
            if group_id not in sf_groups:
                sf_groups[group_id] = {"type": group_type, "attrs": []}
            sf_groups[group_id]["attrs"].append(
                EntryDiscoverer.build_attribute_node(key, snowflake_keys[key], counters, self._no_display_name)
            )
            counters["resource_fields"] += 1

        sf_group_list = [
            {
                "id": gid,
                "type": sf_groups[gid]["type"],
                "title": make_title(gid[: -len(".resource")] if gid.endswith(".resource") else gid) + " resource fields",
                "brief": f"Resource-level fields describing {make_title(gid[:-len('.resource')] if gid.endswith('.resource') else gid)} resource entities.",
                "attributes": sf_groups[gid]["attrs"],
            }
            for gid in sorted(sf_groups)
        ]

        dsoa_attrs = []
        for key in sorted(dsoa_keys):
            dsoa_attrs.append(EntryDiscoverer.build_attribute_node(key, dsoa_keys[key], counters, self._no_display_name))
            counters["resource_fields"] += 1

        return (
            {"groups": sf_group_list},
            {
                "groups": [
                    {
                        "id": "dsoa",
                        "type": "resource",
                        "title": "DSOA resource fields",
                        "brief": "Resource-level DSOA execution metadata and deployment context.",
                        "attributes": dsoa_attrs,
                    }
                ]
            },
        )

    def build_signal_fields_yaml(
        self, signal_entries: Dict[str, Any], event_ts_entries: Dict[str, Any], counters: Dict[str, int]
    ) -> Dict[str, Dict[str, Any]]:
        """Build one signal_fields YAML file per namespace group.

        Each namespace group (snowflake.query, snowflake.user, etc.) gets its own
        file under ``fields/signal_fields/`` for easier review and future maintenance.
        Groups that share no natural prefix fall into ``snowflake_misc.yaml``. All
        ``snowflake``/``snowflake.*`` groups are consolidated into a single
        ``snowflake.yaml``, and all ``dsoa``/``dsoa.*`` groups into a single
        ``dsoa.yaml`` (mirroring the same domain-file convention).

        Args:
            signal_entries:   Signal-classified entries.
            event_ts_entries: Event-timestamp entries (excluding trigger key).
            counters:         Mutable export counters dict, updated in-place.

        Returns:
            Dict mapping relative path → YAML doc dict.
        """
        all_signal = dict(signal_entries)
        for key, meta in event_ts_entries.items():
            if key != "snowflake.event.trigger":
                all_signal[key] = meta

        groups_map: Dict[str, Dict[str, Any]] = {}
        for key in sorted(all_signal):
            # Skip ref: entries — they belong in interfaces only, not in field definition files.
            # Refs are included via i.dsoa_resource and related interfaces by build_interfaces_yaml().
            if all_signal[key]["semdict"] == "ref":
                continue
            group_id, group_type = ns_group(key, SIG_NS, "snowflake.misc", "attribute_group")
            if group_id not in groups_map:
                groups_map[group_id] = {"type": group_type, "attrs": []}
            groups_map[group_id]["attrs"].append(
                EntryDiscoverer.build_attribute_node(key, all_signal[key], counters, self._no_display_name)
            )
            counters["signal_fields"] += 1

        # One file per group_id — snowflake_* groups are combined into a single snowflake.yaml,
        # and dsoa_* groups are combined into a single dsoa.yaml (mirroring the same pattern
        # for consistency: source/fields/resource_fields/snowflake_resource.yaml already
        # establishes the "<domain>.yaml" signal + "<domain>_resource.yaml" resource
        # convention this dsoa consolidation now also follows).
        docs: Dict[str, Dict[str, Any]] = {}
        for gid in sorted(groups_map):
            brief_subject = "observed timestamp" if gid == "observed_timestamp" else make_title(gid)
            group_entry = {
                "id": gid,
                "type": groups_map[gid]["type"],
                "title": (GROUP_TITLE_OVERRIDES.get(gid) or make_title(gid)) + " signal fields",
                "brief": f"Signal-level fields for {brief_subject} telemetry.",
                "attributes": groups_map[gid]["attrs"],
            }
            if gid.startswith("snowflake"):
                rel_path = "fields/signal_fields/snowflake.yaml"
                if rel_path in docs:
                    docs[rel_path]["groups"].append(group_entry)
                else:
                    docs[rel_path] = {"groups": [group_entry]}
            elif gid == "dsoa" or gid.startswith("dsoa."):
                rel_path = "fields/signal_fields/dsoa.yaml"
                if rel_path in docs:
                    docs[rel_path]["groups"].append(group_entry)
                else:
                    docs[rel_path] = {"groups": [group_entry]}
            else:
                filename = gid.replace(".", "_") + ".yaml"
                docs[f"fields/signal_fields/{filename}"] = {"groups": [group_entry]}
        return docs

    def build_interfaces_yaml(self, all_entries: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Build interfaces_dsoa.yaml and interfaces_snowflake.yaml.

        Args:
            all_entries: All parsed field entries keyed by field key. When provided,
                         ``__interface_note`` values are read from each entry to annotate
                         ``ref:`` attributes in ``i.dsoa_resource`` with contextual notes.

        Returns:
            Tuple of (dsoa_doc, snowflake_doc) — semconv-compliant YAML doc dicts.
            dsoa_doc      → ``metrics/interfaces_dsoa.yaml``     (i.dsoa_resource)
            snowflake_doc → ``metrics/interfaces_snowflake.yaml`` (i.snowflake_warehouse, i.snowflake_database)
        """

        def _ref_entry(key: str) -> Dict[str, Any]:
            """Build a ref: attribute entry with optional note: from __interface_note."""
            entry: Dict[str, Any] = {"ref": key}
            if all_entries:
                meta = all_entries.get(key)
                if meta:
                    note = (meta.get("entry") or meta).get("__interface_note", "")
                    if note:
                        entry["note"] = str(note).strip()
            return entry

        dsoa_doc = {
            "groups": [
                {
                    "id": "i.dsoa_resource",
                    "type": "interface",
                    "title": "DSOA resource fields",
                    "brief": "Fields present on all DSOA telemetry records. Synced with config.py RESOURCE_ATTRIBUTES.",
                    "attributes": [_ref_entry(k) for k in sorted(RESOURCE_ATTRIBUTE_KEYS)],
                },
            ]
        }
        snowflake_doc = {
            "groups": [
                {
                    "id": "i.snowflake_warehouse",
                    "type": "interface",
                    "title": "Snowflake warehouse dimensions",
                    "brief": "Common warehouse dimensions for per-warehouse metrics.",
                    "attributes": [{"ref": "snowflake.warehouse.name"}, {"ref": "snowflake.warehouse.id"}],
                },
                {
                    "id": "i.snowflake_database",
                    "type": "interface",
                    "title": "Snowflake database dimensions",
                    "brief": "Common database/schema dimensions for per-database metrics.",
                    "attributes": [{"ref": "db.namespace"}, {"ref": "snowflake.schema.name"}],
                },
            ]
        }
        return dsoa_doc, snowflake_doc

    def select_interfaces(
        self,
        metric_entries: Dict[str, Any],
        all_entries: Dict[str, Any],
        dim_plugins: Optional[Dict[str, Set[str]]] = None,
        dim_context_by_plugin: Optional[Dict[str, Dict[str, Set[str]]]] = None,
    ) -> List[str]:
        """Determine which DSOA interfaces to declare for a metric model.

        Args:
            metric_entries:        Per-plugin metric entries.
            all_entries:           All parsed entries (for dimension lookup).
            dim_plugins:           Map of dimension key → set of all plugins that define it.
            dim_context_by_plugin: Per-plugin map of dim_key → context name set.
            dim_plugins:           Map of dimension key → set of all plugins that define it.
                                   When provided, a dim without ``__context_names`` is accepted
                                   for a plugin if that plugin is in ``dim_plugins[dim_key]``,
                                   not only if the dedup winner happened to be that plugin.
            dim_context_by_plugin: Per-plugin map of dim_key → context name set.

        Returns:
            Ordered list of interface IDs.
        """
        uses_warehouse = uses_database = False
        for _mk, m_meta in metric_entries.items():
            mc_names = set(m_meta["entry"].get("__context_names") or [])
            m_plugin = m_meta["plugin"]
            # Use dim_plugins as authoritative source (same logic as build_metric_model_yaml).
            dim_source = sorted(dim_plugins.keys()) if dim_plugins is not None else all_entries.keys()
            for dim_key in dim_source:
                if dim_plugins is not None:
                    if m_plugin not in dim_plugins.get(dim_key, set()):
                        continue
                else:
                    dim_meta = all_entries.get(dim_key)
                    if not dim_meta or dim_meta["section"] != "dimensions":
                        continue
                    if dim_meta["plugin"] != m_plugin:
                        continue
                # Use per-plugin context names when available (avoids dedup winner mismatch).
                if dim_context_by_plugin is not None:
                    dc_names: Set[str] = dim_context_by_plugin.get(m_plugin, {}).get(dim_key, set())
                else:
                    dim_meta = all_entries.get(dim_key)
                    dc_names = set(dim_meta["entry"].get("__context_names") or []) if dim_meta else set()
                if dc_names and not dc_names.intersection(mc_names):
                    continue
                if dim_key in INTERFACE_WAREHOUSE_KEYS:
                    uses_warehouse = True
                if dim_key in INTERFACE_DATABASE_KEYS:
                    uses_database = True
        interfaces = ["i.dsoa_resource"]
        if uses_warehouse:
            interfaces.append("i.snowflake_warehouse")
        if uses_database:
            interfaces.append("i.snowflake_database")
        return interfaces

    def build_metric_model_yaml(
        self,
        plugin_name: str,
        metric_entries: Dict[str, Any],
        all_entries: Dict[str, Any],
        counters: Dict[str, int],
        dim_plugins: Optional[Dict[str, Set[str]]] = None,
        dim_context_by_plugin: Optional[Dict[str, Dict[str, Set[str]]]] = None,
        dql_queries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build a per-plugin metric model YAML document.

        Args:
            plugin_name:           Plugin name.
            metric_entries:        Plugin's metric entries.
            all_entries:           All parsed entries for dimension resolution.
            counters:               Mutable export counters dict, updated in-place.
            dim_plugins:           Map of dimension key → set of all plugins that define it.
                                   When provided, dimensions are resolved by ownership across all
                                   plugin definitions, not just the dedup winner.
            dim_context_by_plugin: Per-plugin map of dim_key → context name set.
            dql_queries:           Optional list of DQL query dicts from instruments-def.yml.

        Returns:
            Semconv-compliant YAML document dict with ``model:`` envelope.
        """
        interfaces = self.select_interfaces(metric_entries, all_entries, dim_plugins, dim_context_by_plugin)
        covered: Set[str] = set(RESOURCE_ATTRIBUTE_KEYS)
        if "i.snowflake_warehouse" in interfaces:
            covered |= INTERFACE_WAREHOUSE_KEYS
        if "i.snowflake_database" in interfaces:
            covered |= INTERFACE_DATABASE_KEYS

        groups = []
        for metric_key in sorted(metric_entries):
            m_meta = metric_entries[metric_key]
            mc_names = set(m_meta["entry"].get("__context_names") or [])
            m_plugin = m_meta["plugin"]
            dim_refs = []
            # Use dim_plugins as the canonical source for which keys are dimensions.
            # This handles the case where cross-plugin dedup promotes an "attributes"-section
            # definition as the winning entry, masking the "dimensions"-section definition
            # from another plugin.  Iterating over dim_plugins ensures all dimension keys
            # are considered for metric attribute lists regardless of which plugin won dedup.
            dim_source = sorted(dim_plugins.keys()) if dim_plugins is not None else sorted(all_entries.keys())
            for dim_key in dim_source:
                if dim_plugins is not None:
                    # Skip if the current metric's plugin didn't define this as a dimension
                    if m_plugin not in dim_plugins.get(dim_key, set()):
                        continue
                else:
                    # Fallback: use section check on all_entries
                    dim_meta = all_entries.get(dim_key)
                    if not dim_meta or dim_meta["section"] != "dimensions":
                        continue
                    if dim_meta["plugin"] != m_plugin:
                        continue
                if dim_key in covered:
                    continue
                # Use per-plugin context names when available (avoids dedup winner mismatch
                # where shares.inbound_shares wins over table_health.table_clustering).
                if dim_context_by_plugin is not None:
                    dc_names: Set[str] = dim_context_by_plugin.get(m_plugin, {}).get(dim_key, set())
                else:
                    dim_meta = all_entries.get(dim_key)
                    dc_names = set(dim_meta["entry"].get("__context_names") or []) if dim_meta else set()
                # A dim with context_names is applicable only when it overlaps the metric.
                if dc_names and not dc_names.intersection(mc_names):
                    continue
                dim_refs.append({"ref": dim_key})
            metric_node = emit_metric_entry(metric_key, m_meta["entry"])
            if dim_refs:
                metric_node["attributes"] = dim_refs
            groups.append(metric_node)
            counters["metric_fields"] += 1

        model_doc: Dict[str, Any] = {
            "id": f"snowflake.metrics.{plugin_name}",
            "title": f"Snowflake {plugin_label(plugin_name)} metrics",
            "brief": f"Metrics collected by the DSOA {plugin_name} plugin from Snowflake ACCOUNT_USAGE views.",
            "model_group_id": "snowflake.metrics",
            "data_object": "metric",
            "interfaces": interfaces,
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        model_doc["groups"] = groups
        return {"model": model_doc}

    def build_event_model_yaml(
        self,
        plugin_name: str,
        event_ts_entries: Dict[str, Any],
        counters: Dict[str, int],
        dql_queries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build a per-plugin event model YAML document.

        Args:
            plugin_name:      Plugin name.
            event_ts_entries: All event_timestamp entries across all plugins.
            counters:         Mutable export counters dict, updated in-place.
            dql_queries:      Optional list of DQL query dicts from instruments-def.yml.

        Returns:
            Semconv-compliant YAML document dict with ``model:`` envelope.
        """
        plugin_ts_keys = sorted(
            k for k, meta in event_ts_entries.items() if meta["plugin"] == plugin_name and k != "snowflake.event.trigger"
        )
        attrs = [{"ref": "snowflake.event.type"}] + [{"ref": k} for k in plugin_ts_keys]
        for _ in plugin_ts_keys:
            counters["event_timestamp_fields"] += 1
        model_doc: Dict[str, Any] = {
            "id": f"snowflake.events.{plugin_name}",
            "title": f"Snowflake {plugin_label(plugin_name)} lifecycle events",
            "brief": f"Timestamp-based state-change events emitted by the DSOA {plugin_name} plugin via the OpenPipeline Events API.",
            "model_group_id": "snowflake.events",
            "data_object": "events",
            "interfaces": ["i.dsoa_resource"],
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        model_doc["groups"] = [
            {
                "id": f"snowflake.events.{plugin_name}.fields",
                "type": "attribute_group",
                "title": f"{plugin_label(plugin_name, cap_first=True)} event fields",
                "attributes": attrs,
            }
        ]
        return {"model": model_doc}

    def collect_plugin_attribute_refs(
        self,
        plugin_name: str,
        all_entries: Dict[str, Any],
        context_name: Optional[str] = None,
        exclude_span_only: bool = False,
    ) -> List[Dict[str, str]]:
        """Collect all attribute field refs for a plugin (optionally for one context).

        Collects all entries from ``attributes`` section that belong to ``plugin_name``
        (either as the dedup winner or as a definition registered in ``all_entries``).
        Entries with ``__context_names`` are included only if ``context_name`` is None
        or if the context matches.

        ``ref``-classified entries are excluded (they belong in SD interfaces only).

        Note: ``__context_names`` is a general per-field annotation also used (by many
        other plugins) to scope a field to a specific source SQL view/context — e.g.
        ``task_history`` vs. ``task_versions`` — not specifically log-vs-span. Passing a
        ``context_name`` here only has an effect on fields that opt in via their own
        ``__context_names`` list; callers must not assume it differentiates log/span
        models on its own. Log/span differentiation instead uses
        the dedicated ``exclude_span_only`` flag, driven by the ``__span_only``
        annotation, to avoid colliding with the pre-existing SQL-view-scoping use of
        ``__context_names``.

        Args:
            plugin_name:       Plugin name.
            all_entries:       All parsed entries (dedup-resolved).
            context_name:      If provided, only include fields applicable to this context.
            exclude_span_only: If True, skip fields annotated with ``__span_only: true``
                                (fields reported only on span records, e.g. span-event
                                payloads) — used to build the plugin's log model.

        Returns:
            Sorted list of ``{"ref": key}`` dicts.
        """
        refs = []
        for key, meta in all_entries.items():
            if meta["section"] != "attributes":
                continue
            if meta["plugin"] != plugin_name:
                continue
            if meta["semdict"] == "ref":
                continue
            if exclude_span_only and meta["entry"].get("__span_only"):
                continue
            # Filter by context if requested
            if context_name is not None:
                ctx_names = set(meta["entry"].get("__context_names") or [])
                if ctx_names and context_name not in ctx_names:
                    continue
            refs.append(key)
        return [{"ref": k} for k in sorted(refs)]

    def build_log_model_yaml(
        self, plugin_name: str, all_entries: Dict[str, Any], dql_queries: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Build a per-plugin log record model YAML document.

        Creates a log model that references all attribute fields for the plugin via
        a ``ref:`` list in a dedicated model group, resolving signal-field orphans.

        Fields annotated with ``__span_only: true`` are excluded here even though they
        are still collected for the span model, e.g., span-event
        payload fields (``snowflake.query.step.*``) that only apply to the span
        representation of a plugin's records.

        Args:
            plugin_name:  Plugin name.
            all_entries:  All parsed entries (dedup-resolved).
            dql_queries:  Optional list of DQL query dicts from instruments-def.yml.

        Returns:
            Semconv-compliant YAML document dict with ``model:`` envelope.
        """
        attr_refs = self.collect_plugin_attribute_refs(plugin_name, all_entries, exclude_span_only=True)
        model_doc: Dict[str, Any] = {
            "id": f"snowflake.logs.{plugin_name}",
            "title": f"Snowflake {plugin_label(plugin_name)} log records",
            "brief": f"Log records emitted by the DSOA {plugin_name} plugin.",
            "model_group_id": "snowflake.logs",
            "data_object": "logs",
            "interfaces": ["i.dsoa_resource"],
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        if attr_refs:
            model_doc["groups"] = [
                {
                    "id": f"snowflake.logs.{plugin_name}.fields",
                    "type": "attribute_group",
                    "title": f"{plugin_label(plugin_name, cap_first=True)} log record fields",
                    "brief": f"Attribute fields for {make_display_name(plugin_name)} log records.",
                    "attributes": attr_refs,
                }
            ]
        else:
            model_doc["groups"] = []
        return {"model": model_doc}

    def build_span_model_yaml(
        self, plugin_name: str, all_entries: Dict[str, Any], dql_queries: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Build a per-plugin span model YAML document.

        Only generated for plugins in ``SPAN_PLUGINS``. Unlike the log model, no
        ``__span_only`` filtering is applied here — span-only fields
        are ordinary attributes from the span model's perspective and are included
        alongside every other field the plugin defines.

        Args:
            plugin_name:  Plugin name (must be in SPAN_PLUGINS).
            all_entries:  All parsed entries (dedup-resolved).
            dql_queries:  Optional list of DQL query dicts from instruments-def.yml.

        Returns:
            Semconv-compliant YAML document dict with ``model:`` envelope.
        """
        attr_refs = self.collect_plugin_attribute_refs(plugin_name, all_entries)
        model_doc: Dict[str, Any] = {
            "id": f"snowflake.spans.{plugin_name}",
            "title": f"Snowflake {plugin_label(plugin_name)} spans",
            "brief": f"Span records emitted by the DSOA {plugin_name} plugin.",
            "model_group_id": "snowflake.spans",
            "data_object": "spans",
            "interfaces": ["i.dsoa_resource"],
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        if attr_refs:
            model_doc["groups"] = [
                {
                    "id": f"snowflake.spans.{plugin_name}.fields",
                    "type": "attribute_group",
                    "title": f"{plugin_label(plugin_name, cap_first=True)} span fields",
                    "brief": f"Attribute fields for {make_display_name(plugin_name)} spans.",
                    "attributes": attr_refs,
                }
            ]
        else:
            model_doc["groups"] = []
        return {"model": model_doc}
