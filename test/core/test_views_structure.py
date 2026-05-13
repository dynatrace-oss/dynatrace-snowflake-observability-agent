#!/usr/bin/env python3
"""Structural tests for DSOA SQL view definitions."""

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

import glob
import re


def _strip_sql_comments(content):
    """Remove SQL block comments (/* ... */) and single-line comments (-- ...) from content.

    Preserves conditional markers (--%PLUGIN, --%OPTION) which are not true comments.
    """
    # Remove block comments (non-greedy, handles multi-line)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    # Remove single-line comments, but keep conditional markers (--%PLUGIN, --%OPTION)
    content = re.sub(r"--(?!%PLUGIN|%OPTION|%:PLUGIN|%:OPTION).*", "", content)
    return content


class TestViews:
    """Structural tests for DSOA SQL view definitions."""

    def test_timestamp_columns(self):
        """Ensure all instrumented views define a TIMESTAMP column."""
        base_sql_path = "src/dtagent/plugins/*.sql/*.sql"
        create_view_pattern = r"CREATE .* VIEW (DTAGENT_DB\.)?APP\.V_.*_INSTRUMENTED"
        for filepath in glob.iglob(base_sql_path):
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            if re.search(create_view_pattern, content, re.IGNORECASE):
                assert "AS TIMESTAMP" in content.upper(), f"Missing TIMESTAMP column in {filepath}"

    def test_no_select_star_from_snowflake_views(self):
        """Ensure no SQL file uses SELECT * or SELECT alias.* from SNOWFLAKE.* system views.

        BCR-2275: Snowflake may add columns to ACCOUNT_USAGE / INFORMATION_SCHEMA views
        without notice. DSOA must use explicit column lists at the system-view boundary.
        """
        base_sql_path = "src/dtagent/plugins/*.sql/*.sql"
        # Strategy: find every FROM clause that references SNOWFLAKE.*, then look
        # backwards to the nearest SELECT to check if it uses * or alias.*.
        # This avoids false positives where SELECT * from an internal CTE appears
        # in the same file as a separate query that references SNOWFLAKE.
        from_snowflake = re.compile(r"\bFROM\s+SNOWFLAKE\.", re.IGNORECASE)
        select_star = re.compile(
            r"\bSELECT\s+"
            r"(?:[a-z_][a-z0-9_]*\.)?\*"  # * or alias.*
            r"\s*(?:,|\bFROM\b)",  # followed by comma (more columns) or FROM
            re.IGNORECASE,
        )

        violations = []
        for filepath in glob.iglob(base_sql_path):
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            active_content = _strip_sql_comments(content)
            # For each FROM SNOWFLAKE. reference, extract the enclosing SELECT..FROM block
            for match in from_snowflake.finditer(active_content):
                # Walk backwards from the FROM SNOWFLAKE. to find the nearest SELECT
                preceding = active_content[: match.start()]
                last_select = preceding.rfind("SELECT")
                if last_select == -1:
                    last_select = preceding.rfind("select")
                if last_select == -1:
                    continue
                select_block = active_content[last_select : match.end()]
                if select_star.search(select_block):
                    violations.append(filepath)
                    break  # one violation per file is enough

        assert not violations, (
            "SELECT * from SNOWFLAKE.* system views found (BCR-2275 violation).\n"
            "Use explicit column lists instead.\n"
            "Affected files:\n" + "\n".join(f"  - {v}" for v in sorted(violations))
        )
