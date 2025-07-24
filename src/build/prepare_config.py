"""
Refactors config files to 3 levels of nesting (path, value, type) and redirects it to build/.
Excludes keys starting with _ prefix.
Args:
    sys.argv[1:] (str): path to config files, specified when running `deploy.sh`
"""

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

import json
import sys
import os
from typing import Any


def _get_config(config_path: str, first_entry_only: bool = True) -> dict:
    """Returns dictionary based on the JSON content of given file - or an empty dictionary

    Args:
        config_path (str): path to the file to load JSON into dict
        first_entry_only (boolean): if the config file contains a list of configs, indicate if return first or entire list.

    Returns:
        Optional[dict]: dictionary based on the JSON content of the given file
    """
    config = {}

    if os.path.isfile(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f) or {}
        if isinstance(config, list) and first_entry_only and len(config) > 0:
            return config[0]
    return config


def _prepare_config_for_ingest(config_data: dict) -> list:
    """Converts configuration in a form of a dictionary, just like in config/config-template.json

       In order to properly load the data into table with 3 columns (path, value, type) we need to flatten the json to one level of nesting.
       This will allow for inputting json key as context, nested json key as key and nested json value as value into CONFIG.CONFIGURATIONS.
       To get the desired values of keys from the structure of the config json, we need to combine some of the keys into one.
       So we use stack to iterate over each key and prepare the combined key.

    Args:
        config_data (dict): Configuration dictionary

    Returns:
        list: configuration flattened into a list of three-column objects to make it easier to load into Snowflake
    """
    config_as_list = []

    def __recurse(config_element: Any, path: str = "") -> None:
        """We need to traverse the dictionary to the primitive elements or lists

        Args:
            config_element (Any): an element of config we analyze at this point
            path (str, optional): path leading to this element over dictionary keys separated by ".". Defaults to "" for the top level keys.
        """
        if isinstance(config_element, dict):
            for key, value in config_element.items():
                if key[0] != "_":
                    sub_path = f"{path}.{key}" if path else key
                    __recurse(value, sub_path)
        else:
            config_as_list.append(
                {"PATH": path.lower(), "TYPE": type(config_element).__name__, "VALUE": config_element}
            )

    __recurse(config_data)

    return config_as_list


def _merge_json_files(*file_names: str) -> list:
    """Enables to load given files with configuration JSONs one by one, and keep overriding existing keys (path)

    Returns:
        list: the result is a merge of multiple configurations with values from last files in the list overriding those in previous positions
    """
    merged: dict[Any, Any] = {}

    for file_name in file_names:
        d_config = _get_config(file_name)
        if d_config:
            l_config = _prepare_config_for_ingest(d_config)
            m_config = {item["PATH"]: item for item in l_config}

            merged |= m_config

    return sorted(merged.values(), key=lambda x: x["PATH"])


def main():
    """
    Refactors config files to 3 levels of nesting (path, value, type) and redirects it to build/.
    Excludes keys starting with _ prefix.
    Args:
        sys.argv[1:] (str): path to config files, specified when running `deploy.sh`
    """
    with open("build/config.json", "w", encoding="utf-8") as f:
        l_config = _merge_json_files(*sys.argv[1:])
        json.dump(l_config, f, indent=2)


if __name__ == "__main__":
    main()
