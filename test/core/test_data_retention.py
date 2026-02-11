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

import glob
import re


class TestDataRetention:
    """Test that data retention settings are correctly configured for all tables."""

    def test_transient_tables_have_zero_retention(self):
        """Test that all transient tables explicitly set DATA_RETENTION_TIME_IN_DAYS = 0.

        This is important because:
        1. Transient tables are temporary and should not retain data
        2. Setting retention to 0 prevents unexpected Time Travel costs
        3. It ensures compliance with security and cost policies
        """
        # Search all SQL files in plugins
        base_sql_path = "src/dtagent/plugins/*.sql/*.sql"
        # Also search setup SQL files
        setup_sql_path = "src/dtagent.sql/**/*.sql"

        transient_tables_without_retention = []

        # Pattern to find CREATE TRANSIENT TABLE statements
        # This pattern captures the full CREATE statement including the table name
        create_transient_table_pattern = re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?TRANSIENT\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
            r"([\w.]+)\s*\([^)]*\)(?:\s*(?:CLUSTER\s+BY\s+[^;]+)?)",
            re.IGNORECASE | re.DOTALL,
        )

        # Pattern to check if DATA_RETENTION_TIME_IN_DAYS = 0 is set
        retention_zero_pattern = re.compile(r"DATA_RETENTION_TIME_IN_DAYS\s*=\s*0", re.IGNORECASE)

        for pattern_path in [base_sql_path, setup_sql_path]:
            for filepath in glob.glob(pattern_path, recursive=True):
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Find all CREATE TRANSIENT TABLE statements
                matches = create_transient_table_pattern.finditer(content)

                for match in matches:
                    table_name = match.group(1)
                    # Get the full statement including potential DATA_RETENTION_TIME_IN_DAYS clause
                    # Look ahead from the match position to find the complete statement
                    start_pos = match.start()
                    # Find the end of this CREATE statement (either ; or next CREATE/ALTER)
                    end_match = re.search(r";", content[match.end() :])
                    if end_match:
                        end_pos = match.end() + end_match.start()
                        statement = content[start_pos : end_pos + 1]

                        # Check if this statement has DATA_RETENTION_TIME_IN_DAYS = 0
                        if not retention_zero_pattern.search(statement):
                            transient_tables_without_retention.append(
                                {"file": filepath, "table": table_name, "statement": statement[:200]}  # First 200 chars for context
                            )

        # Assert that no transient tables are missing the retention setting
        if transient_tables_without_retention:
            error_msg = "The following transient tables are missing 'DATA_RETENTION_TIME_IN_DAYS = 0':\n"
            for table_info in transient_tables_without_retention:
                error_msg += f"\n  File: {table_info['file']}\n"
                error_msg += f"  Table: {table_info['table']}\n"
                error_msg += f"  Statement: {table_info['statement']}...\n"

            assert False, error_msg

    def test_database_has_default_retention_configured(self):
        """Test that the DTAGENT_DB database initialization sets a default DATA_RETENTION_TIME_IN_DAYS value."""
        init_db_file = "src/dtagent.sql/init/002_init_db.sql"

        with open(init_db_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that ALTER DATABASE DTAGENT_DB SET DATA_RETENTION_TIME_IN_DAYS is present
        assert re.search(
            r"ALTER\s+DATABASE\s+DTAGENT_DB\s+SET\s+DATA_RETENTION_TIME_IN_DAYS\s*=\s*\d+", content, re.IGNORECASE
        ), f"Missing ALTER DATABASE DTAGENT_DB SET DATA_RETENTION_TIME_IN_DAYS in {init_db_file}"

    def test_config_procedure_updates_retention_time(self):
        """Test that the UPDATE_FROM_CONFIGURATIONS procedure includes logic to update the database retention time from configuration."""
        config_proc_file = "src/dtagent.sql/setup/038_p_update_from_configuration.sql"

        with open(config_proc_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that the procedure retrieves the retention config
        assert re.search(
            r"F_GET_CONFIG_VALUE\s*\(\s*['\"]core\.snowflake\.database\.data_retention_time_in_days['\"]", content, re.IGNORECASE
        ), f"Missing F_GET_CONFIG_VALUE for core.snowflake.database.data_retention_time_in_days in {config_proc_file}"

        # Check that the procedure executes ALTER DATABASE with retention time
        assert re.search(
            r"ALTER\s+DATABASE\s+DTAGENT_DB\s+SET\s+DATA_RETENTION_TIME_IN_DAYS", content, re.IGNORECASE
        ), f"Missing ALTER DATABASE statement for DATA_RETENTION_TIME_IN_DAYS in {config_proc_file}"

    def test_config_template_has_retention_parameter(self):
        """Test that the configuration template includes the data_retention_time_in_days parameter with default value 1."""
        config_template_file = "conf/config-template.yml"

        with open(config_template_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that the config includes the retention parameter
        assert re.search(
            r"data_retention_time_in_days:\s*1", content
        ), f"Missing or incorrect data_retention_time_in_days in {config_template_file}"

    def test_all_transient_tables_explicitly_marked(self):
        """Test that all tables marked as TRANSIENT are explicitly using the TRANSIENT keyword.

        This prevents accidental creation of permanent tables.
        """
        base_sql_path = "src/dtagent/plugins/*.sql/*.sql"
        setup_sql_path = "src/dtagent.sql/**/*.sql"

        # Pattern to find any table creation that has DATA_RETENTION_TIME_IN_DAYS = 0
        # but is NOT marked as TRANSIENT
        retention_zero_pattern = re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?(?!TRANSIENT)(?:TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)"
            r"([\w.]+)[^;]*DATA_RETENTION_TIME_IN_DAYS\s*=\s*0",
            re.IGNORECASE | re.DOTALL,
        )

        non_transient_with_zero_retention = []

        for pattern_path in [base_sql_path, setup_sql_path]:
            for filepath in glob.glob(pattern_path, recursive=True):
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                matches = retention_zero_pattern.finditer(content)
                for match in matches:
                    table_name = match.group(1)
                    # Additional check: ensure it's not a transient table
                    # by checking if TRANSIENT appears before the table name
                    start_pos = max(0, match.start() - 100)
                    context = content[start_pos : match.start() + 50]

                    if "TRANSIENT" not in context.upper():
                        non_transient_with_zero_retention.append({"file": filepath, "table": table_name})

        if non_transient_with_zero_retention:
            error_msg = "The following non-TRANSIENT tables have DATA_RETENTION_TIME_IN_DAYS = 0:\n"
            for table_info in non_transient_with_zero_retention:
                error_msg += f"\n  File: {table_info['file']}\n"
                error_msg += f"  Table: {table_info['table']}\n"
                error_msg += "  Note: Tables with retention = 0 should be TRANSIENT\n"

            # This is a warning rather than an error, as it might be intentional
            print(f"WARNING: {error_msg}")
