"""
Compiles all bom.yml files into a single Bill of Material (BOM) for SnowAgent
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


import os
import yaml
import fnmatch
from collections import OrderedDict


def merge_bom_yaml_files(directory):
    """Generates a single BOM file from those delivered by core and plugins"""

    merged_data = {"delivers": [], "references": []}

    for root, _, files in os.walk(directory):
        for file in fnmatch.filter(files, "bom.yml"):
            plugin_name = "core" if "plugins" not in root else os.path.basename(root).split(".")[0]

            with open(os.path.join(root, file), "r") as f:
                data = yaml.safe_load(f)
                for _k in merged_data.keys():
                    for item in data.get(_k, []):
                        ordered_item = OrderedDict()
                        ordered_item["name"] = item["name"]
                        for k, v in item.items():
                            if k != "name":
                                ordered_item[k] = v
                        ordered_item["plugins"] = [plugin_name]
                        merged_data[_k].append(ordered_item)

    # Combine duplicates from different plugins
    final_data = {key: [] for key in merged_data}
    for key, items in merged_data.items():
        merged_dict = {}

        for d in items:
            _k = "|".join(f"{k}:{str(v)}" for k, v in d.items() if k != "plugins")

            if _k in merged_dict:
                merged_dict[_k]["plugins"].extend(d["plugins"])
            else:
                merged_dict[_k] = d

        final_data[key] = list(merged_dict.values())

    return final_data


def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwargs):
    """Ensures that the resulting YAML is always properly structured"""

    class OrderedDumper(Dumper):
        def increase_indent(self, flow=False, indentless=False):
            return super(OrderedDumper, self).increase_indent(flow, False)

    def _dict_representer(dumper, data):
        return dumper.represent_dict(data.items())

    def _str_representer(dumper, data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|" if "\n" in data else None)

    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    OrderedDumper.add_representer(str, _str_representer)
    return yaml.dump(data, stream, Dumper=OrderedDumper, **kwargs)


def write_csv(data, filename):
    # Extract the keys from the first dictionary as the header
    header = (
        ["name", "type"]
        + list({key for d in data for key in d.keys() if key not in ["name", "type", "comment"]})
        + ["comment"]
    )

    # Open the CSV file for writing
    with open(filename, "w", newline="") as csvfile:
        import csv

        writer = csv.DictWriter(csvfile, fieldnames=header, delimiter="\t")

        # Write the header
        writer.writeheader()

        # Write the data rows
        for row in data:
            # Convert list values to comma-separated strings
            for key, value in row.items():
                if isinstance(value, list):
                    row[key] = ",".join(map(str, value))
            writer.writerow(row)


merged_yaml = merge_bom_yaml_files("src")

with open("build/bom.yml", "w") as f:
    ordered_dump(merged_yaml, f, default_flow_style=False, indent=2, width=200)

print("Merged BOM YAML files have been saved to build/bom.yml.")

for key, value in merged_yaml.items():
    write_csv(value, f"build/bom_{key}.csv")

print("BOM written into separate CSV files in build.")
