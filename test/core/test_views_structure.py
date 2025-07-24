#!/usr/bin/env python3
#
#
# These materials contain confidential information and
# trade secrets of Dynatrace LLC.  You shall
# maintain the materials as confidential and shall not
# disclose its contents to any third party except as may
# be required by law or regulation.  Use, disclosure,
# or reproduction is prohibited without the prior express
# written permission of Dynatrace LLC.
#
# All Compuware products listed within the materials are
# trademarks of Dynatrace LLC.  All other company
# or product names are trademarks of their respective owners.
#
# Copyright (c) 2024 Dynatrace LLC.  All rights reserved.
#
#

import glob
import re


class TestViews:
    def test_timestamp_columns(self):
        base_sql_path = "src/dtagent/plugins/*.sql/*.sql"
        create_view_pattern = r"CREATE .* VIEW (DTAGENT_DB\.)?APP\.V_.*_INSTRUMENTED"
        for filepath in glob.iglob(base_sql_path):
            with open(filepath) as f:
                content = f.read()

        if re.search(create_view_pattern, content, re.IGNORECASE):
            print(filepath)
            assert "AS TIMESTAMP" in content.upper(), f"Missing TIMESTAMP column in {filepath}"
