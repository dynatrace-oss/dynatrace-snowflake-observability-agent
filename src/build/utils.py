#!/usr/bin/env python3
"""Utility functions for building and testing the agent."""
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
import os
import logging
import fnmatch
from typing import Any, Generator, Dict, List, Optional, Callable, Tuple


def find_files(directory: str, filename_pattern: str) -> List[str]:
    """Lists all files with given name in the given directory
    Returns:
        list: List of file paths
    """

    matches = []
    for root, _, files in os.walk(directory):
        for filename in fnmatch.filter(files, filename_pattern):
            matches.append(os.path.join(root, filename))
    return matches


def read_clean_yml_from_file(file_path: str) -> Dict[str, Any]:
    """Reads given file into a dictionary.

    Args:
        file_path (str): path to the file with yaml content

    Returns:
        Dict[str, Any]: dictionary based on the content of the YML/YAML file
    """
    import yaml

    logging.debug("Reading clean yml file: %s", file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

        return data

    return {}


def get_metric_semantics(gen_metric_description_line: bool = False) -> Dict[str, str]:
    """Reads the metric semantics from the instruments-def.yml files.

    Args:
        gen_metric_description_line (bool): whether to generate the metric description line

    Returns:
        Dict[str, str]: Dictionary with metric semantics
    """
    all_metrics = {}
    for file_path in find_files("src/", "instruments-def.yml"):
        instruments_data = read_clean_yml_from_file(file_path)
        if "metrics" in instruments_data:
            if gen_metric_description_line:
                from dtagent.otel.semantics import Semantics

                for k, v in instruments_data["metrics"].items():
                    line = Semantics.gen_metric_definition_line(k, v)
                    all_metrics[k] = line
            else:
                all_metrics.update(instruments_data["metrics"])

    return all_metrics
