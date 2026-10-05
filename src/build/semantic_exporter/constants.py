"""Shared constants for the Semantic Dictionary export pipeline.

Holds constants needed by more than one module in this package. Kept in a
standalone module (with no imports from sibling modules) so that no two
modules in this package need to import each other just to share a constant —
avoiding circular imports between e.g. ``yaml_helpers`` and ``field_emitters``.
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

#: Group ID prefixes that DSOA owns exclusively in the Semantic Dictionary.
#: Used to decide which signal_fields files and doc/fields/*.md entries go
#: into the OWNERS section (shared fields like db, client, authentication are excluded).
SD_OWNED_GROUP_PREFIXES: frozenset = frozenset({"snowflake", "dsoa", "anomaly", "observed_timestamp"})
