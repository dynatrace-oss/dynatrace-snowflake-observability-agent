"""File-writing helpers for the Semantic Dictionary export: YAML/JSON/Markdown/OWNERS."""

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

import json
import re
import logging
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from build.semantic_exporter.yaml_helpers import _add_flow_seq_spaces, _IndentedDumper, _make_ruamel_yaml, _merge_into_ruamel
from build.semantic_exporter.field_emitters import (
    SD_FIELD_CATEGORY,
    SD_FIELD_CATEGORY_DESCRIPTION,
    SD_FIELD_CATEGORY_DISPLAY_NAME,
    SD_MAINTAINER,
    SD_OWNED_GROUP_PREFIXES,
    SD_OWNERS,
    SD_PM,
    SD_TEAM,
    _FIELD_STUB_H2_OVERRIDES,
    _make_title,
    _requote_scalars,
)

log = logging.getLogger("build.export_semantics")


class OutputWriter:
    """Writes generated YAML/JSON/Markdown documents to the SD output tree.

    Attributes:
        repo_root:  Absolute path to the repository root.
        output_dir: Absolute path to the ``source/`` output directory.
    """

    def __init__(self, repo_root: Path, output_dir: Path) -> None:
        """Initialise the writer.

        Args:
            repo_root:  Repository root path.
            output_dir: Output directory (typically ``<sd-repo>/source``).
        """
        self.repo_root = repo_root
        self.output_dir = output_dir

    @property
    def sd_root(self) -> Path:
        """Return the SD repo root directory for SD-metadata files (OWNERS, doc/, definitions/).

        When ``output_dir`` ends in ``source`` the SD root is ``output_dir.parent``
        (standard SD layout: ``<repo-root>/source/``).  Otherwise (e.g. when
        ``--output docs/semantic-dictionary`` is passed without a ``source/`` tier)
        the SD root is ``output_dir`` itself.
        """
        return self.output_dir.parent if self.output_dir.name == "source" else self.output_dir

    def write_yaml(self, doc: Dict[str, Any], rel_path: str, counters: Dict[str, int]) -> Path:
        """Write a YAML document to the output directory.

        When the target file already exists, DSOA groups are merged into it rather
        than replacing the file wholesale — preserving SD-maintained content in
        groups that DSOA does not own.

        Uses :class:`_IndentedDumper` to produce properly indented block sequences
        per Semantic Dictionary YAML conventions.

        Args:
            doc:      YAML-serialisable dict.
            rel_path: Relative path under output_dir.
            counters: Mutable export counters dict, updated in-place.

        Returns:
            Absolute path to the written file.
        """
        out_path = self.output_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _requote_scalars(doc)
        dsoa_text = yaml.dump(doc, Dumper=_IndentedDumper, default_flow_style=False, allow_unicode=True, sort_keys=False, width=4096)
        dsoa_text = _add_flow_seq_spaces(dsoa_text)
        if not out_path.exists():
            out_path.write_text(dsoa_text, encoding="utf-8")
        else:
            # Use ruamel.yaml round-trip merge so inline comments in the existing file
            # (e.g. stability: experimental # traces-in-grail) are preserved.
            ry = _make_ruamel_yaml()
            dsoa_cm = ry.load(dsoa_text)
            with open(out_path, "r", encoding="utf-8") as fh:
                existing_cm = ry.load(fh)
            _merge_into_ruamel(existing_cm, dsoa_cm)
            buf = StringIO()
            ry.dump(existing_cm, buf)
            out_path.write_text(_add_flow_seq_spaces(buf.getvalue()), encoding="utf-8")
        log.debug("Wrote %s", out_path)
        counters["files"] += 1
        return out_path

    def write_text(self, content: str, rel_path: str, counters: Dict[str, int]) -> Path:
        """Write a plain-text or Markdown file to the output directory."""
        out_path = self.output_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        log.debug("Wrote %s", out_path)
        counters["files"] += 1
        return out_path

    def write_sd_root_text(self, content: str, rel_path: str, counters: Dict[str, int]) -> Path:
        """Write a plain-text file relative to the SD repo root (see :attr:`sd_root`)."""
        out_path = self.sd_root / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        log.debug("Wrote %s", out_path)
        counters["files"] += 1
        return out_path

    def write_json(self, data: Any, rel_path: str, counters: Dict[str, int]) -> Path:
        """Write a JSON file to the output directory."""
        out_path = self.output_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        log.debug("Wrote %s", out_path)
        counters["files"] += 1
        return out_path

    def write_owners(self, content: str, counters: Dict[str, int]) -> Path:
        """Update the OWNERS file at the SD repo root with the DSOA section.

        The OWNERS file lives one level above source/ (i.e. output_dir.parent).
        An existing '## DSOA' block (from the start of that marker's own line
        through the next section header or EOF) is replaced; if none exists the
        section is appended.
        """
        owners_path = self.sd_root / "OWNERS"
        if owners_path.exists():
            existing = owners_path.read_text(encoding="utf-8")
            marker = "## DSOA"
            idx = existing.find(marker)
            if idx >= 0:
                # Back up to the start of the marker's own line so any leading
                # indentation on that line (OWNERS sections are indented, e.g.
                # "    ## DSOA") is removed together with the marker, rather than
                # left dangling as a stray whitespace-only line in `head` — that
                # stray indentation (never stripped by a plain .rstrip("\n"), which
                # only strips newlines, not spaces) is what caused a blank-ish
                # line to accumulate before "## DSOA" on every re-export.
                line_start = existing.rfind("\n", 0, idx) + 1
                head = existing[:line_start].rstrip()
                head = f"{head}\n\n" if head else ""
                # Find the next section header after the DSOA block, if any.
                # Indentation-aware ("\n[ \t]*## ") since OWNERS section headers
                # are indented — the previous "\n## " (no indentation allowed)
                # could never match, so a DSOA block followed by another section
                # would have silently deleted that section too (currently masked
                # only because DSOA happens to be the last section in the file).
                rest = existing[idx + len(marker) :]
                next_match = re.search(r"\n[ \t]*## ", rest)
                tail = rest[next_match.start() + 1 :] if next_match else ""
            else:
                head = f"{existing.rstrip()}\n\n" if existing.strip() else ""
                tail = ""
        else:
            owners_path.parent.mkdir(parents=True, exist_ok=True)
            head, tail = "", ""
        new_text = head + content.rstrip("\n") + "\n"
        if tail:
            new_text += f"\n{tail}"
        owners_path.write_text(new_text, encoding="utf-8")
        log.debug("Wrote %s", owners_path)
        counters["files"] += 1
        return owners_path

    def build_owners_entries(self, signal_group_ids: List[str], resource_group_ids: List[str], plugin_names: List[str]) -> str:
        """Generate the DSOA section of the Semantic Dictionary OWNERS file.

        Returns text suitable for pasting into OWNERS. The path list is derived
        from the groups actually generated in the current export run so it stays
        in sync with the YAML output automatically.

        Args:
            signal_group_ids:  Group IDs from the generated signal_fields docs.
            resource_group_ids: Group IDs from the generated resource_fields docs.
            plugin_names:      Sorted list of plugin names that have metrics.
        """
        paths: List[str] = []

        # Resource field source files
        sf_res_file = "source/fields/resource_fields/snowflake_resource.yaml"
        dsoa_res_file = "source/fields/resource_fields/dsoa_resource.yaml"
        if any(gid.startswith("snowflake") or gid.startswith("db") for gid in resource_group_ids):
            paths.append(sf_res_file)
        if any(gid.startswith("dsoa") or gid.startswith("deployment") for gid in resource_group_ids):
            paths.append(dsoa_res_file)

        # Signal field source files — DSOA-owned groups and shared groups we co-contribute to
        # (authentication, client, db, event are SD-shared but we write into them; they must be
        # listed in OWNERS so the F027 sanity check does not fire)
        snowflake_added = False
        dsoa_added = False
        for gid in sorted(signal_group_ids):
            if not any(gid == p or gid.startswith(p + ".") for p in SD_OWNED_GROUP_PREFIXES):
                continue
            if gid.startswith("snowflake"):
                if not snowflake_added:
                    paths.append("source/fields/signal_fields/snowflake.yaml")
                    snowflake_added = True
            elif gid == "dsoa" or gid.startswith("dsoa."):
                if not dsoa_added:
                    paths.append("source/fields/signal_fields/dsoa.yaml")
                    dsoa_added = True
            else:
                filename = gid.replace(".", "_") + ".yaml"
                paths.append(f"source/fields/signal_fields/{filename}")

        # Shared signal field files we merge DSOA fields into (not DSOA-exclusive but co-owned)
        for shared_group in sorted({"authentication", "client", "db", "event"}):
            shared_path = f"source/fields/signal_fields/{shared_group}.yaml"
            if shared_path not in paths:
                paths.append(shared_path)

        # Metrics files
        paths.append("source/metrics/snowflake_metrics_**")
        paths.append("source/metrics/interfaces_dsoa.yaml")
        paths.append("source/metrics/interfaces_snowflake.yaml")

        # Model files
        paths.append("source/model/snowflake/**")

        # doc/fields files for DSOA-owned groups. snowflake.* groups (signal and resource)
        # are consolidated into a single doc/fields/snowflake.md, and dsoa/dsoa.* groups
        # (signal and resource) into a single doc/fields/dsoa.md — add each once.
        snowflake_doc_added = False
        dsoa_doc_added = False
        for gid in sorted(signal_group_ids) + sorted(resource_group_ids):
            if not any(gid == p or gid.startswith(p + ".") for p in SD_OWNED_GROUP_PREFIXES):
                continue
            if gid == "snowflake" or gid.startswith("snowflake."):
                if not snowflake_doc_added:
                    paths.append("doc/fields/snowflake.md")
                    snowflake_doc_added = True
            elif gid == "dsoa" or gid.startswith("dsoa."):
                if not dsoa_doc_added:
                    paths.append("doc/fields/dsoa.md")
                    dsoa_doc_added = True
            else:
                md_name = gid.replace(".", "_") + ".md"
                doc_path = f"doc/fields/{md_name}"
                if doc_path not in paths:
                    paths.append(doc_path)

        # doc/model
        paths.append("doc/model/snowflake/**")

        # Format as OWNERS syntax
        lines = ["    ## DSOA - Dynatrace Snowflake Observability Agent"]
        indent = "        "
        lines.append("    path " + (", \\\n" + indent).join(paths))
        for owner in SD_OWNERS:
            lines.append(f"        {owner}")
        lines.append("")
        return "\n".join(lines)

    def update_field_categories(self, signal_group_ids: List[str], resource_group_ids: List[str], counters: Dict[str, int]) -> None:
        """Merge the DSOA entry into definitions/mapping/global_field_categories.json.

        Reads the existing SD file at the SD repo root (if present), otherwise falls back
        to the seed copy at ``scripts/tools/global_field_categories.json``.  Injects the
        DSOA category under ``SD_FIELD_CATEGORY`` and writes the result in-place to the
        SD repo root path so all other categories are preserved.
        """
        gfc_path = self.sd_root / "definitions" / "mapping" / "global_field_categories.json"
        seed_path = self.repo_root / "scripts" / "tools" / "global_field_categories.json"
        existing: Dict[str, Any] = {}
        if gfc_path.exists():
            with open(gfc_path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        elif seed_path.exists():
            log.debug("global_field_categories.json not found at SD root; using seed from %s", seed_path)
            with open(seed_path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        existing[SD_FIELD_CATEGORY] = {
            "display_name": SD_FIELD_CATEGORY_DISPLAY_NAME,
            "description": SD_FIELD_CATEGORY_DESCRIPTION,
            "signal_groups": sorted(signal_group_ids),
            "resource_groups": sorted(resource_group_ids),
        }
        gfc_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gfc_path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        log.debug("Wrote %s", gfc_path)
        counters["files"] += 1

    def build_model_doc_stubs(self, sub_groups: Optional[set] = None) -> Dict[str, str]:
        """Generate doc/model/snowflake/{logs,events,spans}/readme.md stubs.

        These Markdown files are required by the SD generator (model_group tags).
        Also emits the parent doc/model/snowflake/readme.md stub (group id
        ``snowflake``) when at least one sub-group was written this run — its
        ``<!-- model_group snowflake -->`` block links to whichever of the
        logs/events/spans readmes actually exist.

        Args:
            sub_groups: Subset of ``{"logs", "events", "spans"}`` identifying which
                        sub-group model_groups were actually written this run. When
                        None (default), all three are assumed present (back-compat).

        Returns:
            Dict mapping relative output path → file content. Update
            SD_PM / SD_MAINTAINER / SD_TEAM constants at the top of this module
            to change the ownership table.
        """
        all_stubs = {
            "snowflake.logs": (
                "Snowflake log records",
                "Log records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE and system views.",
            ),
            "snowflake.events": (
                "Snowflake lifecycle events",
                "Timestamp-based state-change events emitted by DSOA plugins via the Dynatrace OpenPipeline Events API.",
            ),
            "snowflake.spans": ("Snowflake spans", "Span records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE views."),
        }
        if sub_groups is None:
            sub_groups = {"logs", "events", "spans"}
        stubs = {gid: info for gid, info in all_stubs.items() if gid.split(".")[1] in sub_groups}
        result: Dict[str, str] = {}
        for group_id, (title, description) in stubs.items():
            subdir = group_id.split(".")[1]  # logs, events, spans
            content = (
                f"<!-- model_group {group_id} -->\n"
                "<!-- The content between the markdown start and end comments (tags) is generated. Please do not edit manually. -->\n"
                "\n"
                f"## {title}\n"
                "\n"
                f"{description}\n"
                "\n"
                "<!-- end_model_group -->\n"
                "\n"
                "<!-- dynatrace_internal -->\n"
                "| Responsible PM | Maintainer | Team |\n"
                "|---|---|---|\n"
                f"| {SD_PM} | {SD_MAINTAINER} | {SD_TEAM} |\n"
                "<!-- end_dynatrace_internal -->\n"
            )
            result[f"doc/model/snowflake/{subdir}/readme.md"] = content
        if sub_groups:
            content = (
                "<!-- model_group snowflake -->\n"
                "<!-- The content between the markdown start and end comments (tags) is generated. Please do not edit manually. -->\n"
                "\n"
                "## Snowflake\n"
                "\n"
                "<!-- end_model_group -->\n"
                "\n"
                "<!-- dynatrace_internal -->\n"
                "| Responsible PM | Maintainer | Team |\n"
                "|---|---|---|\n"
                f"| {SD_PM} | {SD_MAINTAINER} | {SD_TEAM} |\n"
                "<!-- end_dynatrace_internal -->\n"
            )
            result["doc/model/snowflake/readme.md"] = content
        return result

    def build_per_model_doc_stubs(self, models: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate per-model doc/model/snowflake/<type>/<plugin>.md stub files.

        The SD generator reads these stubs and fills in the ``<!-- model <id> -->``
        sections with the generated attribute tables and DQL examples.  Without them
        the generator has nothing to populate and the F001 / F004 / F025 sanity
        checks fire for every undefined model.

        Each stub contains the ``<!-- model <id> --> … <!-- end_model -->`` block
        (populated by the generator with the model description and DQL examples) plus,
        when the model has an inner ``attribute_group``, a ``<!-- semconv <id>.fields -->``
        reference for it.  The inner-group reference is required — without it F025
        ("unused domain-specific groups") fires for every ``<model_id>.fields`` group,
        because the ``<!-- model -->`` tag documents the model itself but not its
        attribute groups.  This mirrors well-formed SD model docs (e.g. the Davis
        models, which reference each inner group with its own ``<!-- semconv -->`` tag).
        Models without an inner group (``has_fields`` False, e.g. the attribute-less
        ``event_log`` span model) omit the reference to avoid a dangling-group error.

        Args:
            models: List of dicts with keys ``id`` (model ID, e.g.
                    ``snowflake.logs.metering``), ``title``, ``brief``,
                    ``signal_type`` (``logs``, ``events``, ``spans``), and
                    ``has_fields`` (whether the model has an inner ``.fields`` group).

        Returns:
            Dict mapping relative output path (``doc/model/snowflake/…``) → content.
        """
        result: Dict[str, str] = {}
        for model in models:
            model_id = model["id"]
            title = model["title"]
            brief = model.get("brief", "")
            signal_type = model["signal_type"]  # logs | events | spans
            has_fields = model.get("has_fields", True)
            plugin = model_id.split(".")[-1]  # last segment is the plugin name
            # The model's inner attribute_group is always ``<model_id>.fields`` (see
            # build_*_model_yaml). It must be referenced with its own semconv tag so
            # F025 does not flag it as an unused domain-specific group — but only when
            # the model actually declares that group.
            fields_ref = f"<!-- semconv {model_id}.fields -->\n<!-- end_semconv -->\n\n" if has_fields else ""
            content = (
                f"<!-- model {model_id} -->\n"
                "<!-- The content between the markdown start and end comments (tags) is generated. Please do not edit manually. -->\n"
                "\n"
                f"## {title}\n"
                "\n"
                f"{brief}\n"
                "\n"
                "<!-- end_model -->\n"
                "\n"
                f"{fields_ref}"
                "<!-- dynatrace_internal -->\n"
                "| Responsible PM | Maintainer | Team |\n"
                "|---|---|---|\n"
                f"| {SD_PM} | {SD_MAINTAINER} | {SD_TEAM} |\n"
                "<!-- end_dynatrace_internal -->\n"
            )
            result[f"doc/model/snowflake/{signal_type}/{plugin}.md"] = content
        return result

    def build_per_field_doc_stubs(self, field_groups: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate doc/fields/<group_id_normalized>.md stubs for DSOA-owned signal field groups.

        The SD generator reads these stubs and fills in the ``<!-- semconv <group_id> -->``
        sections with rendered attribute tables.  Without them, field groups have no
        documentation entry in the SD and the F001/F004/F025 sanity checks can fire for
        any signal_fields file that depends on them.

        Each stub is minimal — a heading and the semconv marker.  The generator replaces
        everything between ``<!-- semconv <id> -->`` and ``<!-- end_semconv -->`` with the
        rendered attribute table and description.

        The filename is the group ID with dots replaced by underscores, matching the SD
        convention (e.g. ``snowflake.account`` → ``doc/fields/snowflake_account.md``).

        Exception: any group whose id is ``snowflake``/``dsoa`` or starts with
        ``snowflake.``/``dsoa.`` (both signal-field groups and their respective
        resource-field groups) is routed into a single consolidated
        ``doc/fields/snowflake.md`` / ``doc/fields/dsoa.md`` file instead — one
        shared ``## <Domain>`` h2 followed by one ``### <title>`` + semconv block per
        group, mirroring the multi-block-per-file pattern used by
        ``doc/fields/azure_resource.md`` in the SD repo.

        The ``## h2`` heading uses the namespace name in sentence case — no ``fields``
        or ``resource`` suffix, matching the SD doc convention seen in
        ``doc/fields/host.md``, ``doc/fields/app.md`` (e.g. ``## Snowflake warehouse``).
        Groups with a ``.resource`` id suffix have that part stripped before titling.
        The YAML ``title:`` (with the "fields" suffix) is rendered as the ``### h3``
        heading inside the semconv block by the SD generator itself.

        Args:
            field_groups: List of dicts with keys ``group_id`` (e.g.
                          ``snowflake.account``), ``title`` (e.g.
                          ``Snowflake account signal fields``), and ``is_resource``
                          (``True`` for resource_fields-origin groups).

        Returns:
            Dict mapping relative output path (``doc/fields/…``) → stub content.
        """
        # Domains consolidated into a single doc/fields/<domain>.md file: keyed by the
        # domain's group-id prefix, mapping to (output filename, ## h2 heading text).
        # The h2 heading intentionally uses the full override text (e.g. the full
        # product name for "dsoa" — kept unabbreviated per PR #1964 reviewer feedback),
        # matching the SD's own multi-block-per-file convention (doc/fields/azure_resource.md).
        _consolidated_domains: Dict[str, Tuple[str, str]] = {
            "snowflake": ("snowflake.md", "Snowflake"),
            "dsoa": ("dsoa.md", _FIELD_STUB_H2_OVERRIDES.get("dsoa") or "DSOA"),
        }

        def _consolidated_domain(group_id: str) -> Optional[str]:
            """Return the consolidation domain prefix `group_id` belongs to, if any."""
            for prefix in _consolidated_domains:
                if group_id == prefix or group_id.startswith(prefix + "."):
                    return prefix
            return None

        result: Dict[str, str] = {}
        consolidated_groups: Dict[str, List[Dict[str, Any]]] = {}
        for fg in field_groups:
            group_id = fg["group_id"]
            domain = _consolidated_domain(group_id)
            if domain is not None:
                consolidated_groups.setdefault(domain, []).append(fg)
                continue
            # h2 heading: sentence-case namespace, no "fields" or "resource" suffix.
            # Strip any ".resource" id suffix so "snowflake.warehouse.resource" → "## Snowflake warehouse".
            ns_key = group_id[: -len(".resource")] if group_id.endswith(".resource") else group_id
            h2_title = _FIELD_STUB_H2_OVERRIDES.get(ns_key) or _make_title(ns_key)
            filename = group_id.replace(".", "_") + ".md"
            content = (
                f"## {h2_title}\n"
                "\n"
                f"<!-- semconv {group_id} -->\n"
                "<!-- end_semconv -->\n"
                "\n"
                "<!-- dynatrace_internal -->\n"
                "| Responsible PM | Maintainer | Team |\n"
                "|---|---|---|\n"
                f"| {SD_PM} | {SD_MAINTAINER} | {SD_TEAM} |\n"
                "<!-- end_dynatrace_internal -->\n"
            )
            result[f"doc/fields/{filename}"] = content

        for domain, groups in consolidated_groups.items():
            # Consolidate all <domain> / <domain>.* groups into a single doc/fields/<domain>.md
            # file: one shared "## <Domain>" h2, then one semconv stub block per group (sorted
            # by group_id for determinism), and one shared ownership table at the end —
            # mirroring doc/fields/azure_resource.md's multi-block-per-file pattern. The SD
            # generator fills in each block's own "### <title>" heading from the YAML title —
            # no manual h3 is emitted here (matching the azure_resource.md stub shape exactly).
            filename, h2_title = _consolidated_domains[domain]
            blocks: List[str] = [f"## {h2_title}\n"]
            for fg in sorted(groups, key=lambda x: x["group_id"]):
                group_id = fg["group_id"]
                blocks.append(f"\n<!-- semconv {group_id} -->\n<!-- end_semconv -->\n")
            content = "".join(blocks) + (
                "\n<!-- dynatrace_internal -->\n"
                "| Responsible PM | Maintainer | Team |\n"
                "|---|---|---|\n"
                f"| {SD_PM} | {SD_MAINTAINER} | {SD_TEAM} |\n"
                "<!-- end_dynatrace_internal -->\n"
            )
            result[f"doc/fields/{filename}"] = content
        return result
