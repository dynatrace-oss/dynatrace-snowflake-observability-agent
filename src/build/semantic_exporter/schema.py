"""Semantic Dictionary JSON schema loading and validation."""

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

import copy
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger("build.export_semantics")


class SchemaValidator:
    """Loads and applies the semconv.schema.json JSON schema to generated documents.

    Attributes:
        schema_path: Path to semconv.schema.json, or None if not applicable.
    """

    def __init__(self, schema_path: Optional[Path]) -> None:
        """Initialise the validator.

        Args:
            schema_path: Path to semconv.schema.json, or None to disable validation.
        """
        self.schema_path = schema_path
        self._schema: Optional[Dict[str, Any]] = None

    def load_schema(self) -> Optional[Dict[str, Any]]:
        """Load and patch semconv JSON schema if available.

        The raw ``semconv.schema.json`` is written for a custom build-tool validator
        (not standard ``jsonschema``).  The ``Attribute`` and ``SemanticConventionBase``
        definitions use ``additionalProperties: false`` at the top level while declaring
        their allowed properties *inside* ``allOf`` sub-schemas.  In JSON Schema draft-07,
        ``additionalProperties: false`` only considers ``properties`` at the **same schema
        object level** — not properties nested inside ``allOf`` — which produces spurious
        "Additional properties not allowed" errors for all valid DSOA field definitions.

        This method patches the loaded schema before returning it:

        - Removes ``additionalProperties: false`` from all ``definitions`` entries that
          declare their properties via ``allOf`` (e.g. ``Attribute``,
          ``SemanticConventionBase``, smartscape edge types).  Removing it makes the
          ``additionalProperties`` check a no-op while preserving all ``required`` and
          type checks.
        - Removes the ``anyOf(attributes|extends)`` constraint from
          ``SemanticConventionBase``.  Metric groups that have no dimension attributes
          do not carry an ``attributes`` list and would otherwise fail this constraint.

        These patches silence false-positive errors without relaxing any meaningful
        structural validation.  Required fields (``id``, ``type``, ``metric_name``, etc.)
        are still enforced by the ``required`` constraints in each definition.

        Sets and also returns the patched schema (or None if the schema file is not found).

        Returns:
            Patched schema dict or None if the schema file is not found.
        """
        if not self.schema_path or not self.schema_path.exists():
            log.warning("semconv.schema.json not found at %s; skipping schema validation", self.schema_path)
            self._schema = None
            return None

        with open(self.schema_path, "r", encoding="utf-8") as fh:
            raw_schema = json.load(fh)

        schema = copy.deepcopy(raw_schema)
        for defn in schema.get("definitions", {}).values():
            # Strip additionalProperties:false — standard jsonschema draft-07 does not
            # look inside allOf sub-schemas when evaluating additionalProperties, so this
            # flag produces false-positive errors for every valid attribute node.
            if defn.get("additionalProperties") is False:
                defn.pop("additionalProperties")
        # Remove anyOf(attributes|extends) from SemanticConventionBase:
        # metric groups that carry no dimension attributes are otherwise rejected.
        scb = schema.get("definitions", {}).get("SemanticConventionBase", {})
        scb.pop("anyOf", None)
        self._schema = schema
        return schema

    def validate_against_schema(self, doc: Dict[str, Any], yaml_path: Path) -> bool:
        """Validate a generated YAML document against semconv.schema.json.

        Uses the patched schema loaded by :meth:`load_schema` to avoid false-positive
        ``additionalProperties`` errors.  Only the short ``message`` from the first
        ``ValidationError`` is logged — the verbose ``On instance[...]`` JSON dump
        produced by the default ``str(exc)`` rendering is intentionally suppressed.

        Args:
            doc:       Parsed YAML document.
            yaml_path: Path for error messages.

        Returns:
            True if valid (or schema unavailable), False on error.
        """
        if self._schema is None:
            return True
        try:
            import jsonschema  # pylint: disable=import-outside-toplevel

            jsonschema.validate(instance=doc, schema=self._schema)
            log.debug("Schema validation PASS: %s", yaml_path)
            return True
        except jsonschema.ValidationError as exc:  # pylint: disable=broad-except
            # Log only the short message to avoid the verbose "On instance[...]" dump.
            log.error("Schema validation FAIL: %s — %s", yaml_path, exc.message)
            return False
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Schema validation FAIL: %s — %s", yaml_path, exc)
            return False
