#!/usr/bin/env python3
"""
Assemble metric semantics from instruments-def.yml files.
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

import yaml
import os
from dtagent.otel.semantics import Semantics
from build.utils import find_files, read_clean_yml_from_file, get_metric_semantics


def main():
    """Main function to assemble metric semantics."""

    # Generate the file
    with open("build/_metric_semantics.txt", "w", encoding="utf-8") as fh:
        all_metrics = get_metric_semantics(gen_metric_description_line=True)

        for k, line in all_metrics.items():
            fh.write(f"\"{k}\": '{line}',\n")


if __name__ == "__main__":
    main()
