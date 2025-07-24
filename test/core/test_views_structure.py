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
