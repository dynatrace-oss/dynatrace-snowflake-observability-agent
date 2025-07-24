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

from typing import Dict, List


class TestDocumentation:

    def _aggregate_data(self, data: List[Dict]) -> List[Dict]:
        """Aggregates given list of objects by 'name' and 'type' keys, merging other keys (dimensions, plugin, source) as comma separated values

        Args:
            data (List[Dict]): List of field/metric documentation objects

        Returns:
            List[Dict]: Merged documentation
        """
        from collections import defaultdict

        aggregated = defaultdict(lambda: {"dimensions": set(), "plugin": set(), "source": set(), "runtime": set()})

        for item in data:
            key = (item["name"], item["type"])
            aggregated[key]["dimensions"].update((item["dimensions"] or "").split(", "))
            aggregated[key]["plugin"].add(item["plugin"])
            aggregated[key]["source"].add(item["source"])
            aggregated[key]["runtime"].add(item["runtime"])

        result = []
        for key, value in aggregated.items():
            result.append(
                {
                    "name": key[0],
                    "type": key[1],
                    "dimensions": ", ".join(value["dimensions"]),
                    "plugin": ", ".join(value["plugin"]),
                    "source": ", ".join(value["source"]),
                    "runtime": any(value["runtime"]),
                }
            )

        return result

    def test_check_missing_file(self):
        import glob
        import os

        for directory in glob.glob("src/dtagent/plugins/*.config"):
            if any(os.scandir(directory)):  # exclude empty dirs
                for file in ["info.md", "instruments-def.yml", "bom.yml"]:
                    full_path = f"{directory}/{file}"

                assert os.path.isfile(full_path), f"Documentation file {full_path} is missing"

                assert os.path.getsize(full_path), f"Documentation file {full_path} seems to be empty"

    def test_matching_documentation(self, pickle_conf: str):
        from test.list_semantics import list_semantics
        from dtagent import context
        from test._utils import get_config

        c = get_config(pickle_conf)

        data = list_semantics("src")
        semantics = self._aggregate_data(data)

        missing_docs = [
            entry
            for entry in semantics
            if entry["source"] == "sql" and entry["type"] in ("metric", "dimension", "attribute", "event timestamp")
        ]
        missing_docs_listed = "\n".join([f'{data["type"]}: {data["name"]} [{data["source"]}] [{data["plugin"]}]' for data in missing_docs])
        assert not missing_docs, f"We are missing documentation for semantics:\n {missing_docs_listed}"

        missing_sql = [
            entry
            for entry in semantics
            if entry["source"] == "instruments"
            and entry["type"] in ("metric", "dimension", "attribute", "event timestamp")
            and entry["plugin"] != ""
            and not entry["runtime"]
        ]
        missing_sql_listed = "\n".join([f'{data["type"]}: {data["name"]} [{data["source"]}] [{data["plugin"]}]' for data in missing_sql])
        assert not missing_sql, f"We have documentation for fields not reported in telemetry:\n {missing_sql_listed}"

        found_core_attribute = [
            entry for entry in semantics if entry["name"] == context.CONTEXT_NAME and entry["plugin"] == "" and entry["type"] == "attribute"
        ]
        assert found_core_attribute, f"Did not find core attribute <{context.CONTEXT_NAME}>"

        core_dimensions = set(c.get(key="resource.attributes").keys())
        found_core_dimensions = set(
            [
                entry["name"]
                for entry in semantics
                if entry["name"] in core_dimensions and entry["plugin"] == "" and entry["type"] == "dimension"
            ]
        )
        assert (
            core_dimensions == found_core_dimensions
        ), f"Problem with core dimensions for resource.attributes, should be {core_dimensions}, is {found_core_dimensions}"

    def test_clean_field_description(self):
        """This test will ensure we do not have any forbidden characters in the body of description or other non-private fields in instrumentation semantics"""
        from test._utils import find_files

        problems = []
        instruments_def_files = find_files("src", "instruments-def.yml")

        for file in instruments_def_files:
            from test._utils import read_clean_yml_from_file

            d_inst = read_clean_yml_from_file(file)

            for sem_type, d_type_inst in d_inst.items():
                if hasattr(d_type_inst, "items"):
                    for attr_key, attr_description in d_type_inst.items():
                        if hasattr(attr_description, "items"):
                            for desc_key, desc_value in attr_description.items():
                                if desc_key[:2] != "__" and '"' in desc_value:
                                    problems.append(
                                        f"Values of {sem_type}.{attr_key}.{desc_key} contains forbidden character:\n{desc_value}"
                                    )
        report_problems = "\n".join(problems)
        assert not problems, f"Following problems with instrumentation definitions were discovered:\n{report_problems}"

    def test_check_required_fields(self):
        """Testing for description, __example, unit, and displayName"""

        from test._utils import find_files, is_blank

        problems = []
        instruments_def_files = find_files("src", "instruments-def.yml")

        def __is_unit_name_correct(unit: str) -> bool:
            """Only uppercase and lowercase letters, digits and characters '%', '[', ']', '{', '}', '/' and '_' are allowed in units.

            Args:
                unit (str): units name to test

            Returns:
                bool: True if units value is correct
            """
            import re

            p_unit = r"^[a-zA-Z0-9%\[\]\{\}/_]+$"
            return re.match(p_unit, unit)

        for file in instruments_def_files:
            from test._utils import read_clean_yml_from_file

            d_inst = read_clean_yml_from_file(file)

            fields_without_context = set()
            fields_with_context_cnt = 0

            for sem_type, d_type_inst in d_inst.items():
                if hasattr(d_type_inst, "items"):
                    for attr_key, attr_description in d_type_inst.items():

                        if isinstance(attr_description, dict):
                            if is_blank(attr_description.get("__description", None)):
                                problems.append(f"Missing <__description> for {sem_type}: {attr_key} = {attr_description}")
                            if "__example" not in attr_description:
                                problems.append(f"Missing <__example> for {sem_type}: {attr_key} = {attr_description}")
                            if sem_type == "metrics":
                                if is_blank(attr_description.get("unit", None)):
                                    problems.append(f"Missing <unit> for {sem_type}: {attr_key} = {attr_description}")
                                if not __is_unit_name_correct(attr_description.get("unit", "")):
                                    problems.append(f"Value <unit> for {sem_type}: {attr_key} = {attr_description} is incorrect")
                                if is_blank(attr_description.get("displayName", None)):
                                    problems.append(f"Missing <displayName> for {sem_type}: {attr_key} = {attr_description}")
                            if (
                                "__context_names" not in attr_description
                                or not isinstance(attr_description["__context_names"], list)
                                or len(attr_description["__context_names"]) == 0
                            ):
                                fields_without_context.add(attr_key)
                            else:
                                fields_with_context_cnt += 1

            if len(fields_without_context) > 0 and fields_with_context_cnt > 0:
                problems.append(f"Context names are not provided for some fields: {', '.join(fields_without_context)}.")

        report_problems = "\n".join(problems)
        assert not problems, f"Following problems with semantic definitions were discovered:\n{report_problems}"
