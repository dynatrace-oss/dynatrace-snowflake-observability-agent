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
import re
import argparse
import json
import logging
from typing import List, Dict
import inflect
from src.dtagent.util import EVENT_TIMESTAMP_KEYS_PAYLOAD_NAME

LOG = logging.getLogger("SEMANTICS")
inflect_engine = inflect.engine()


def _extract_plugin_name(file_path: str) -> str:
    """Returns the name of the Dynatrace Snowflake Observability Agent plugin encoded in the file path

    Returns:
        str: plugin name or empty string
    """
    pattern = re.compile(r"plugins/([^/]+)\.(config|sql)")
    match = pattern.search(file_path)
    return match.group(1) if match else ""


def _get_telemetry_attribute(
    *, attr_name: str, attr_type: str, description_value: Dict, dimension_values: str, plugin_name: str, source: str
) -> dict:
    """Produces telemetry attribute description JSON for given attributes"""
    return {
        "name": attr_name,
        "type": attr_type,
        "dimensions": dimension_values,
        "meaning": description_value,
        "plugin": plugin_name,
        "source": source,
        "runtime": (description_value and description_value.get("__is_defined_at_runtime", False)),
    }


def _get_telemetry_attributes_from_instruments(instruments_data: str, plugin_name: str) -> List[dict]:
    """Generates a list of JSON files with telemetry attributes based on the instruments-def.yml files"""
    entries = []

    # Process metrics
    for attr_type in ("metric", "dimension", "attribute", "event_timestamp"):
        for attr_id, attr_descr in instruments_data.get(f"{attr_type}s", {}).items():
            entry = _get_telemetry_attribute(
                attr_name=attr_id,
                attr_type=attr_type.replace("_", " "),
                description_value=attr_descr,
                dimension_values=None,
                plugin_name=plugin_name,
                source="instruments",
            )
            entries.append(entry)
    return entries


def _process_instruments_file(file_path: str) -> List[Dict]:
    """Analyzes given instruments-def.yaml file for a list of metrics"""
    from build.utils import read_clean_yml_from_file

    logging.debug("Processing file: %s", file_path)

    data = read_clean_yml_from_file(file_path)
    plugin_name = _extract_plugin_name(file_path)
    entries = _get_telemetry_attributes_from_instruments(data, plugin_name)

    return entries


def _extract_attributes_from_view_def(sql_query: str, _plugin_name: str) -> List[dict]:
    """Extracts dimension and attribute names from SQL files"""
    pattern = re.compile(r"OBJECT_CONSTRUCT\((.*?)\)\s+as\s+(DIMENSIONS|ATTRIBUTES|METRICS|EVENT_TIMESTAMPS)", re.DOTALL)
    matches = pattern.findall(sql_query)
    d_matches = {match[1]: re.findall(r"'(.*?)'", match[0]) for match in matches}

    results = []

    for m_key, m_values in d_matches.items():
        category = inflect_engine.singular_noun(m_key.lower().replace("_", " "))

        LOG.debug(m_values)

        if category == "event timestamp" and any("." in string for string in m_values):
            results += [
                _get_telemetry_attribute(
                    attr_name=EVENT_TIMESTAMP_KEYS_PAYLOAD_NAME,
                    attr_type=category,
                    dimension_values=None,
                    description_value=None,
                    plugin_name=_plugin_name,
                    source="sql",
                )
            ]

        if category is not None:
            results += [
                _get_telemetry_attribute(
                    attr_name=attr_key,
                    attr_type=category,
                    dimension_values=(
                        ", ".join([dim_key for dim_key in d_matches.get("DIMENSIONS", []) if "." in dim_key])
                        if m_key == "METRICS"
                        else None
                    ),
                    description_value=None,
                    plugin_name=_plugin_name,
                    source="sql",
                )
                for attr_key in m_values
                if "." in attr_key
            ]

    LOG.debug(results)

    return results


def _process_view_def_file(file_path: str) -> List[dict]:
    """Analyzes given 000_v_XXXX.sql file for a list of attributes, dimensions, etc."""
    LOG.debug("Processing file: %s", file_path)

    with open(file_path, "r", encoding="utf-8") as file:
        sql_str = file.read()
        plugin_name = _extract_plugin_name(file_path)
        if plugin_name:
            LOG.debug("Plugin name: %s", plugin_name)
        else:
            LOG.warning("No plugin na for file: %s", file_path)

        return _extract_attributes_from_view_def(sql_str, plugin_name)

    if file_path.endswith("071_v_trust_center.sql"):
        LOG.setLevel(logging.INFO)


def _save_results(results: list, directory: str):
    # Create the build directory if it doesn't exist
    build_directory = os.path.join(directory, "build")
    os.makedirs(build_directory, exist_ok=True)

    # Define the file path
    file_path = os.path.join(build_directory, "dynatrace-snowflake-observability-agent-semantics.json")

    # Write the content to the file
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(json.dumps(results))

    print(f"Results saved to {file_path}")


def list_semantics(src_dir: str) -> List[Dict]:
    """Prepares a aggregate of semantics coming from instrumentation specs and the SQL files with views

    Args:
        src_dir (str): the root folder from where the files should be analyzed

    Returns:
        List[Dict]: the resulting dictionary
    """
    from build.utils import find_files

    results = []

    instruments_def_files = find_files(src_dir, "instruments-def.yml")
    for file in instruments_def_files:
        results.extend(_process_instruments_file(file))

    view_files = find_files(src_dir, "*_[vf]_*.sql")
    for file in view_files:
        results.extend(_process_view_def_file(file))

    return results


def main():
    LOG.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    LOG.addHandler(ch)

    parser = argparse.ArgumentParser(description="Find files with a given name in a directory and its subdirectories.")
    parser.add_argument("directory", type=str, help="The directory to search in")
    args = parser.parse_args()
    src_dir = os.path.join(args.directory, "src")

    results = list_semantics(src_dir)

    _save_results(results, args.directory)


if __name__ == "__main__":
    main()
