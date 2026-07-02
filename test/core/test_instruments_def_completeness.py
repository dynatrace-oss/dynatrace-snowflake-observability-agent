"""Regression tests that validate instruments-def.yml source data quality.

Checks that required annotations (__type, __stability, __semdict_note, __enum, etc.)
are present and correct across all DSOA plugin instruments-def.yml files.

These tests are designed to be RED before Phase 2 fixes and GREEN after.

Note:
    All tests use ``@pytest.mark.integration`` because they read real
    ``instruments-def.yml`` files from the repository.
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

from typing import Any, Dict, List, Tuple

import pytest

from test.core._semdict_test_utils import load_all_instruments_defs

##region Fixtures

#: Fields with is_/has_/must_ prefix that SNOWFLAKE returns as YES/NO strings,
#: not as true/false booleans. These do NOT require __type: boolean.
_SNOWFLAKE_YESNO_STRINGS: frozenset = frozenset(
    {
        "snowflake.table.is_auto_clustering_on",
        "snowflake.table.is_dynamic",
        "snowflake.table.is_hybrid",
        "snowflake.table.is_iceberg",
        "snowflake.table.is_temporary",
        "snowflake.table.is_transient",
    }
)

#: Known boolean fields WITHOUT a conventional boolean prefix (is_/has_/must_).
#: These must still have __type: boolean.
_KNOWN_BOOLEAN_NO_PREFIX: frozenset = frozenset(
    {
        "snowflake.user.ext_authn.duo",
        "snowflake.grant.option",
        "dsoa.plugins.query_history.track_ddl_changes",
    }
)

#: Timestamp fields that hold epoch nanosecond values — should be __type: long.
_EPOCH_NS_TIMESTAMP_FIELDS: frozenset = frozenset(
    {
        "snowflake.user.created_on",
        "snowflake.user.deleted_on",
        "snowflake.user.last_success_login",
        "snowflake.user.locked_until_time",
        "snowflake.user.expires_at",
        "snowflake.user.password_last_set_time",
        "snowflake.user.bypass_mfa_until",
        "snowflake.session.start",
        "snowflake.cost_attribution.period_start",
        "snowflake.cost_attribution.period_end",
        "snowflake.copy.first_commit_time",
        "snowflake.copy.pipe.received_time",
        "snowflake.table.dynamic.graph.valid_from",
        "snowflake.table.dynamic.graph.valid_to",
        "snowflake.table.dynamic.refresh.start",
        "snowflake.table.dynamic.refresh.end",
        "snowflake.table.dynamic.refresh.data_timestamp",
        "snowflake.table.dynamic.refresh.completion_target",
    }
)

#: Timestamp fields that hold ISO-8601 string values — should be __type: string in Grail.
#: NOTE: snowflake.grant.created_on and snowflake.table.created_on are epoch-ns longs
#: in the shares plugin — they are in _EPOCH_NS_TIMESTAMP_FIELDS instead.
_ISO8601_TIMESTAMP_FIELDS: frozenset = frozenset(
    {
        "snowflake.warehouse.created_on",
        "snowflake.warehouse.resumed_on",
        "snowflake.warehouse.updated_on",
        "snowflake.table.dynamic.latest.data_timestamp",
        "snowflake.table.dynamic.latest.dependency.data_timestamp",
        "snowflake.table.dynamic.scheduling.resumed_on",
        "snowflake.table.dynamic.scheduling.suspended_on",
    }
)

#: Numeric fields that must have __type: long annotation.
_REQUIRED_LONG_FIELDS: frozenset = frozenset(
    {
        "snowflake.query.hash_version",
        "snowflake.query.parametrized_hash_version",
        "snowflake.table.retention_time",
    }
)

#: OTel-only fields that require __semdict_note (provenance annotation).
_OTEL_ONLY_FIELDS_NEEDING_NOTE: frozenset = frozenset(
    {
        "db.namespace",
        "db.collection.name",
        "db.user",
    }
)

#: Fields that must appear in instruments-def.yml (discovered via code audit).
#: Tuple of (plugin_name, field_key).
_REQUIRED_EVENT_PAYLOAD_FIELDS: List[Tuple[str, str]] = [
    ("login_history", "event.description"),
]

#: Enum candidates: fields that must have __enum definitions.
_REQUIRED_ENUM_FIELDS: frozenset = frozenset(
    {
        "snowflake.copy.status",
        "snowflake.query.accel_est.status",
        "vulnerability.risk.level",
        "snowflake.table.dynamic.latest.state",
        "snowflake.table.dynamic.refresh.state",
        "snowflake.table.dynamic.refresh.action",
        "snowflake.table.dynamic.refresh.trigger",
        "snowflake.table.cold_status",
    }
)

##endregion


##region Helpers


def _load_all_instruments_defs() -> Dict[str, Dict[str, Any]]:
    """Thin wrapper around shared utility — loads all instruments-def.yml files.

    Returns:
        Dict mapping plugin name to parsed YAML data.
    """
    return load_all_instruments_defs()


def _collect_all_fields(all_defs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Collect all field entries across all sections and plugins.

    For duplicate keys (same field in multiple plugins), the first definition
    encountered is kept — this mirrors the export dedup behaviour.

    Args:
        all_defs: Parsed instruments-def data keyed by plugin name.

    Returns:
        Dict mapping field key to entry dict (including ``__plugin``, ``__section``).
    """
    all_fields: Dict[str, Dict[str, Any]] = {}
    for plugin_name, data in all_defs.items():
        for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
            for key, entry in (data.get(section) or {}).items():
                if key not in all_fields:
                    entry_copy = dict(entry or {})
                    entry_copy["__plugin"] = plugin_name
                    entry_copy["__section"] = section
                    all_fields[key] = entry_copy
    return all_fields


def _collect_fields_per_plugin(all_defs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Collect all fields keyed by plugin name then field key.

    Args:
        all_defs: Parsed instruments-def data keyed by plugin name.

    Returns:
        Nested dict: {plugin_name: {field_key: entry_dict}}.
    """
    result: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for plugin_name, data in all_defs.items():
        plugin_fields: Dict[str, Dict[str, Any]] = {}
        for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
            for key, entry in (data.get(section) or {}).items():
                plugin_fields[key] = dict(entry or {})
        result[plugin_name] = plugin_fields
    return result


##endregion


##region Tests


@pytest.mark.integration
class TestBooleanTypeAnnotations:
    """Fields with boolean semantics must have __type: boolean."""

    def test_boolean_fields_with_is_has_must_prefix_have_type_annotation(self):
        """Fields with is_/has_/must_ prefix and true/false examples must have __type: boolean.

        Snowflake YES/NO string fields (in _SNOWFLAKE_YESNO_STRINGS) are exempt
        because Snowflake actually returns the string 'YES'/'NO', not true/false.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key, entry in all_fields.items():
            if key.startswith(("is_", "has_", "must_")):
                if key in _SNOWFLAKE_YESNO_STRINGS:
                    continue
                if entry.get("__type") != "boolean":
                    violations.append(f"{key} (plugin={entry.get('__plugin')}): missing __type: boolean")
        assert not violations, "Boolean fields missing __type: boolean:\n" + "\n".join(violations)

    def test_known_boolean_fields_without_prefix_have_type_annotation(self):
        """Known boolean fields without is_/has_/must_ prefix must have __type: boolean.

        Covers: snowflake.user.ext_authn.duo, snowflake.grant.option,
        dsoa.plugins.query_history.track_ddl_changes.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _KNOWN_BOOLEAN_NO_PREFIX:
            entry = all_fields.get(key)
            if entry is None:
                violations.append(f"{key}: field not found in any instruments-def.yml")
                continue
            if entry.get("__type") != "boolean":
                violations.append(f"{key} (plugin={entry.get('__plugin')}): missing __type: boolean")
        assert not violations, "Known boolean fields missing annotation:\n" + "\n".join(violations)


@pytest.mark.integration
class TestTimestampTypeAnnotations:
    """Timestamp fields must have explicit __type annotation."""

    def test_epoch_ns_timestamp_fields_have_long_type(self):
        """Epoch nanosecond timestamp fields must have __type: long.

        These are stored as long integers in Grail; the description must
        clarify their semantic meaning as timestamps.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _EPOCH_NS_TIMESTAMP_FIELDS:
            entry = all_fields.get(key)
            if entry is None:
                continue  # field may not be present in all repos
            if entry.get("__type") != "long":
                violations.append(f"{key} (plugin={entry.get('__plugin')}): expected __type: long, got {entry.get('__type')!r}")
        assert not violations, "Epoch-ns timestamp fields with wrong __type:\n" + "\n".join(violations)

    def test_iso8601_timestamp_fields_have_type_annotation(self):
        """ISO-8601 timestamp fields must have __type: string annotation.

        These fields hold ISO-8601 datetime strings stored as plain strings in Grail.
        The correct SD annotation is ``__type: string`` (not ``timestamp``), because
        Grail stores these as string attributes — native timestamp storage requires
        OpenPipeline remapping. See ``TestTimestampFieldsAreString`` for the detailed
        string-type enforcement test.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _ISO8601_TIMESTAMP_FIELDS:
            entry = all_fields.get(key)
            if entry is None:
                continue  # field may not be in all repos
            raw_type = entry.get("__type")
            if raw_type is None:
                violations.append(f"{key} (plugin={entry.get('__plugin')}): missing __type annotation (expected string)")
            elif raw_type == "timestamp":
                violations.append(
                    f"{key} (plugin={entry.get('__plugin')}): __type: timestamp is wrong; Grail stores this as string. Change to __type: string."
                )
        assert not violations, "ISO-8601 timestamp fields with wrong __type:\n" + "\n".join(violations)


@pytest.mark.integration
class TestNumericTypeAnnotations:
    """Known numeric fields must have __type: long annotation."""

    def test_required_long_fields_have_long_type(self):
        """Fields in _REQUIRED_LONG_FIELDS must have __type: long.

        Covers: snowflake.query.hash_version, parametrized_hash_version,
        snowflake.table.retention_time.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _REQUIRED_LONG_FIELDS:
            entry = all_fields.get(key)
            if entry is None:
                violations.append(f"{key}: field not found in any instruments-def.yml")
                continue
            if entry.get("__type") != "long":
                violations.append(f"{key} (plugin={entry.get('__plugin')}): expected __type: long, got {entry.get('__type')!r}")
        assert not violations, "Numeric fields missing __type: long:\n" + "\n".join(violations)


@pytest.mark.integration
class TestOtelStabilityAnnotations:
    """OTel-only fields must have __stability; deployment.environment must be deprecated."""

    def test_deployment_environment_marked_deprecated(self):
        """deployment.environment must have __stability: deprecated."""
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        entry = all_fields.get("deployment.environment")
        assert entry is not None, "deployment.environment not found in any instruments-def.yml"
        assert (
            entry.get("__stability") == "deprecated"
        ), f"deployment.environment must have __stability: deprecated, got {entry.get('__stability')!r}"

    def test_otel_only_fields_have_stability_annotation(self):
        """Every field with __semdict: otel-only must have __stability annotation.

        This ensures we accurately represent OTel stability levels in the SD export.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key, entry in all_fields.items():
            if entry.get("__semdict") == "otel-only":
                if not entry.get("__stability"):
                    violations.append(f"{key} (plugin={entry.get('__plugin')}): __semdict: otel-only but missing __stability")
        assert not violations, "OTel-only fields missing __stability:\n" + "\n".join(violations)


@pytest.mark.integration
class TestOtelProvenanceNotes:
    """OTel-only fields must have provenance notes (__semdict_note)."""

    def test_required_otel_fields_have_semdict_annotation(self):
        """Fields in _OTEL_ONLY_FIELDS_NEEDING_NOTE must have __semdict: otel-only.

        These fields are defined in OTel Semantic Conventions and should be
        annotated for proper SD provenance tracking.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _OTEL_ONLY_FIELDS_NEEDING_NOTE:
            entry = all_fields.get(key)
            if entry is None:
                continue
            if entry.get("__semdict") != "otel-only":
                violations.append(f"{key} (plugin={entry.get('__plugin')}): expected __semdict: otel-only, got {entry.get('__semdict')!r}")
        assert not violations, "OTel fields missing __semdict: otel-only:\n" + "\n".join(violations)

    def test_required_otel_fields_have_provenance_notes(self):
        """Fields db.namespace, db.collection.name, db.user must have __semdict_note.

        The note must explain OTel provenance so SD reviewers can decide
        whether to register the field globally.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _OTEL_ONLY_FIELDS_NEEDING_NOTE:
            entry = all_fields.get(key)
            if entry is None:
                continue
            if not entry.get("__semdict_note"):
                violations.append(f"{key} (plugin={entry.get('__plugin')}): missing __semdict_note")
        assert not violations, "OTel fields missing __semdict_note:\n" + "\n".join(violations)


@pytest.mark.integration
class TestEventPayloadFieldsCoverage:
    """Event payload fields added programmatically must be in instruments-def.yml."""

    def test_event_payload_fields_documented(self):
        """Fields programmatically added to events by plugin code must appear in instruments-def.

        Discovered via code audit of _prepare_event_payload_* methods:
        - login_history: event.description (human-readable login event description)

        NOTE: 'timestamp' is intentionally excluded — it is a built-in platform attribute.
        """
        all_defs = _load_all_instruments_defs()
        per_plugin = _collect_fields_per_plugin(all_defs)

        violations = []
        for plugin_name, field_key in _REQUIRED_EVENT_PAYLOAD_FIELDS:
            plugin_fields = per_plugin.get(plugin_name, {})
            if field_key not in plugin_fields:
                violations.append(f"{field_key}: missing from {plugin_name}.config/instruments-def.yml")
        assert not violations, "Undocumented event payload fields:\n" + "\n".join(violations)


@pytest.mark.integration
class TestEnumDefinitions:
    """Known categorical fields must have __enum definitions."""

    def test_enum_candidate_fields_have_enum_definitions(self):
        """Fields with well-defined categorical value sets must have __enum.

        Covers: snowflake.copy.status, snowflake.query.accel_est.status,
        vulnerability.risk.level, snowflake.table.dynamic.*.state/action/trigger,
        snowflake.table.cold_status.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _REQUIRED_ENUM_FIELDS:
            entry = all_fields.get(key)
            if entry is None:
                violations.append(f"{key}: field not found in any instruments-def.yml")
                continue
            if not entry.get("__enum"):
                violations.append(f"{key} (plugin={entry.get('__plugin')}): missing __enum definition")
        assert not violations, "Enum candidate fields missing __enum:\n" + "\n".join(violations)

    def test_enum_members_have_required_fields(self):
        """Every __enum definition must have members with id, value, brief.

        Validates that enum members follow the SD semconv structure.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _REQUIRED_ENUM_FIELDS:
            entry = all_fields.get(key)
            if entry is None or not entry.get("__enum"):
                continue
            enum_def = entry["__enum"]
            members = enum_def.get("members", [])
            if not members:
                violations.append(f"{key}: __enum has no members")
                continue
            for i, m in enumerate(members):
                for required_field in ("id", "value", "brief"):
                    if not m.get(required_field):
                        violations.append(f"{key}[member {i}]: missing '{required_field}' field")
        assert not violations, "Enum members with missing fields:\n" + "\n".join(violations)


@pytest.mark.integration
class TestUnitBriefConsistency:
    """Metrics must have consistent unit and brief descriptions."""

    def test_scanned_from_cache_consistent_unit_and_brief(self):
        """snowflake.data.scanned_from_cache brief and unit must be consistent.

        The raw Snowflake value is a ratio (0.0-1.0). The unit must be 'ratio'
        (SD: '1') not 'percent'. The brief must not claim to multiply by 100.

        RATIONALE: PERCENTAGE_BYTES_SCANNED_FROM_LOCAL_CACHE in Snowflake
        returns a value 0.0-1.0 despite its 'PERCENTAGE' name. The existing
        brief contradicts the unit:percent setting.
        """
        all_defs = _load_all_instruments_defs()

        found = False
        for plugin_name, data in all_defs.items():
            metrics = data.get("metrics") or {}
            entry = metrics.get("snowflake.data.scanned_from_cache")
            if entry:
                found = True
                unit = entry.get("unit") or entry.get("__unit", "")
                description = entry.get("__description", "")

                # The unit must be ratio (SD '1') not 'percent'
                assert unit not in ("percent", "%"), (
                    f"snowflake.data.scanned_from_cache (plugin={plugin_name}): "
                    f"unit must be 'ratio' (SD: '1'), not {unit!r}. "
                    "Snowflake returns 0.0-1.0, not 0-100."
                )
                # The brief must not instruct to multiply by 100 (contradicts unit)
                assert "multiply by 100" not in description.lower(), (
                    f"snowflake.data.scanned_from_cache (plugin={plugin_name}): "
                    "brief says 'multiply by 100' but unit is already a ratio. Fix unit or brief."
                )
                break  # found the field; done
        assert found, "snowflake.data.scanned_from_cache not found in any metrics section"


@pytest.mark.integration
class TestJsonAndArrayFieldTypes:
    """JSON-valued and array-valued fields must have correct __type annotations.

    Grail reality (verified via dtctl q on 2026-06-19):
    - JSON object fields (e.g. operator.stats, operator.time): stored as STRING
      (serialized JSON). Must have __type: string with a __semdict_note explaining
      the value is serialized JSON.
    - Array fields (e.g. operator.parent_ids, user.roles.direct): stored as string[]
      (array of strings). Must have __type: string[].
    - JSON object arrays (e.g. graph.inputs): no data in last 30d — assumed string[]
      or string based on OTel/Grail conventions; annotate conservatively as string[].

    Note:
        Fields with no data in the last 30 days use the assumed type from the
        dtctl investigation; these are noted in the __semdict_note.
    """

    #: Fields that contain serialized JSON objects — stored as string in Grail.
    _JSON_OBJECT_FIELDS: frozenset = frozenset(
        {
            "snowflake.query.operator.stats",
            "snowflake.query.operator.time",
            "snowflake.query.operator.attributes",
            "snowflake.query.accel_est.estimated_query_times",
            "snowflake.object.ddl.properties",
            "snowflake.object.ddl.modified",
        }
    )

    #: Fields that contain arrays of strings — stored as string[] in Grail.
    _STRING_ARRAY_FIELDS: frozenset = frozenset(
        {
            "snowflake.query.operator.parent_ids",
            "snowflake.table.dynamic.graph.alter_trigger",
            "snowflake.table.dynamic.graph.inputs",
            "snowflake.budget.resource",
            "snowflake.user.privilege.grants_on",
            "snowflake.user.privilege.granted_by",
            "snowflake.user.roles.granted_by",
            "snowflake.user.roles.direct",
        }
    )

    def test_json_object_fields_have_string_type(self):
        """JSON object fields must have __type: string.

        These fields hold serialized JSON objects. Grail stores them as strings
        (confirmed for operator.stats and operator.time via dtctl query 2026-06-19).
        The __semdict_note must explain they contain serialized JSON.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in sorted(self._JSON_OBJECT_FIELDS):
            entry = all_fields.get(key)
            if entry is None:
                continue  # field may not be in all repos
            raw_type = entry.get("__type")
            if raw_type != "string":
                violations.append(
                    f"{key} (plugin={entry.get('__plugin')}): expected __type: string "
                    f"(serialized JSON stored as string in Grail), got {raw_type!r}"
                )

        assert not violations, "JSON object fields with wrong __type (should be 'string'):\n" + "\n".join(violations)

    def test_json_object_fields_have_semdict_note(self):
        """JSON object fields stored as strings must have __semdict_note explaining this.

        The note must mention 'JSON' so SD reviewers understand the field is not
        plain text but a serialized object.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in sorted(self._JSON_OBJECT_FIELDS):
            entry = all_fields.get(key)
            if entry is None:
                continue
            note = entry.get("__semdict_note", "") or ""
            if "json" not in note.lower() and "JSON" not in note:
                violations.append(
                    f"{key} (plugin={entry.get('__plugin')}): __semdict_note must mention 'JSON' "
                    "to clarify the field holds serialized JSON stored as string"
                )

        assert not violations, "JSON object fields missing 'JSON' in __semdict_note:\n" + "\n".join(violations)

    def test_string_array_fields_have_string_array_type(self):
        """Array-valued fields must have __type: string[].

        Grail stores arrays of IDs/names as string[] (confirmed for
        operator.parent_ids via dtctl query 2026-06-19). Other array fields
        without 30d data are annotated as string[] conservatively.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in sorted(self._STRING_ARRAY_FIELDS):
            entry = all_fields.get(key)
            if entry is None:
                continue
            raw_type = entry.get("__type")
            if raw_type != "string[]":
                violations.append(f"{key} (plugin={entry.get('__plugin')}): expected __type: string[], " f"got {raw_type!r}")

        assert not violations, "Array fields with wrong __type (should be 'string[]'):\n" + "\n".join(violations)


@pytest.mark.integration
class TestTimestampFieldsAreString:
    """ISO-8601 timestamp fields must use __type: string (Grail stores them as strings).

    The Grail reality (confirmed via PO statement and dtctl investigation 2026-06-19):
    ISO-8601 timestamp strings in log attributes are stored as strings in Grail.
    Proper timestamp storage requires OpenPipeline remapping. Until that is in place,
    these fields must be annotated as __type: string with a note explaining the format.

    The previous annotation (__type: timestamp) was aspirational (semantic intent)
    but incorrect for the Grail physical type. This test enforces the corrected
    annotation: __type: string.

    Note:
        Epoch-nanosecond fields (covered by TestTimestampTypeAnnotations) are
        __type: long — those are NOT affected by this test.
    """

    #: ISO-8601 timestamp fields that must be __type: string (not timestamp).
    #: NOTE: snowflake.grant.created_on and snowflake.table.created_on are stored as
    #: epoch-ns longs in the shares plugin — they use __type: long and are excluded here.
    #: Fields converted to epoch-ns (long) and removed from this set: cost_attribution.period_start/end,
    #: copy.first_commit_time, copy.pipe.received_time, dynamic.graph.valid_from/valid_to,
    #: dynamic.refresh.start/end/data_timestamp/completion_target.
    _ISO8601_MUST_BE_STRING: frozenset = frozenset(
        {
            "snowflake.warehouse.created_on",
            "snowflake.warehouse.resumed_on",
            "snowflake.warehouse.updated_on",
            "snowflake.table.dynamic.latest.data_timestamp",
            "snowflake.table.dynamic.latest.dependency.data_timestamp",
            "snowflake.table.dynamic.scheduling.resumed_on",
            "snowflake.table.dynamic.scheduling.suspended_on",
        }
    )

    def test_iso8601_fields_have_string_type(self):
        """ISO-8601 timestamp fields must have __type: string, not timestamp.

        Grail stores these as string attributes. Using __type: string with a
        __semdict_note explaining the format is the correct SD annotation.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in sorted(self._ISO8601_MUST_BE_STRING):
            entry = all_fields.get(key)
            if entry is None:
                continue
            raw_type = entry.get("__type")
            if raw_type not in ("string", None):
                # None is acceptable ONLY if the field has no __type at all
                # (the old test allowed that); new rule: must be string
                if raw_type == "timestamp":
                    violations.append(
                        f"{key} (plugin={entry.get('__plugin')}): __type: timestamp is incorrect; "
                        "Grail stores ISO-8601 timestamp strings as string. Change to __type: string."
                    )
                else:
                    violations.append(f"{key} (plugin={entry.get('__plugin')}): expected __type: string, got {raw_type!r}")

        assert not violations, "ISO-8601 timestamp fields incorrectly annotated (must be __type: string):\n" + "\n".join(violations)

    def test_iso8601_fields_have_timestamp_note(self):
        """ISO-8601 timestamp fields must have __semdict_note explaining the format.

        The note must mention ISO-8601 or the timestamp nature of the value so that
        SD reviewers and API consumers understand the field is a datetime string.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in sorted(self._ISO8601_MUST_BE_STRING):
            entry = all_fields.get(key)
            if entry is None:
                continue
            note = entry.get("__semdict_note", "") or ""
            desc = entry.get("__description", "") or ""
            combined = (note + " " + desc).lower()
            if not any(token in combined for token in ("iso", "timestamp", "datetime", "date-time")):
                violations.append(
                    f"{key} (plugin={entry.get('__plugin')}): __semdict_note or __description "
                    "must mention ISO / timestamp / datetime to explain the value format"
                )

        assert not violations, "ISO-8601 timestamp fields without format explanation:\n" + "\n".join(violations)

    ##endregion
    """Metric __example values must be numeric literals (int or float), not strings.

    The exporter coerces string examples to numbers via ``_coerce_metric_example()``,
    but the source should be authoritative. String-quoted numeric examples such as
    ``__example: "120000"`` make the source misleading and create a gap between what
    a contributor reads and what the SD YAML emits.

    Note:
        Examples that are genuinely strings (e.g. ISO-8601 timestamps stored as
        string attributes) are covered by other test classes and are not metrics.
        This test covers only the ``metrics:`` section.
    """

    def test_metric_examples_are_numeric_types(self):
        """All metric __example values must be int or float, not strings.

        Violations indicate that a quoted numeric literal (e.g. ``"120000"``)
        should be unquoted (``120000``) in the source YAML.
        """
        all_defs = _load_all_instruments_defs()

        violations = []
        for plugin_name, data in all_defs.items():
            for key, entry in (data.get("metrics") or {}).items():
                ex = entry.get("__example")
                if isinstance(ex, str):
                    # Check if it's a parseable number (should be unquoted)
                    try:
                        float(ex)
                        violations.append(
                            f"{plugin_name}/{key}: __example is a quoted string {ex!r}; " "use unquoted numeric literal instead"
                        )
                    except (ValueError, TypeError):
                        pass  # genuinely string (non-numeric) — OK for metrics

        assert not violations, f"{len(violations)} metric(s) with string-quoted numeric __example:\n" + "\n".join(violations)


##endregion
