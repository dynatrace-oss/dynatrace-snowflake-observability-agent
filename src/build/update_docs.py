"""Parses and builds the documentation from all instruments-def.yml, readme.md, config.md, and the default config files."""

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
from typing import Dict, Tuple, List
import re
import yaml


def _read_file(file_path) -> str:
    """Function to read file content

    Args:
        file_path (str): path to the file to read

    Returns:
        str: text content of the file
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist.")

    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def _lower_headers_one_level(md: str) -> str:
    """Updating given markdown document by moving each header one level below, e.g, h1->h2

    Args:
        md (str): markdown text

    Returns:
        str: updated markdown text
    """

    def repl(m):
        return "#" + m.group(0)

    return re.sub(r"^#{1,6}\s", repl, md, flags=re.MULTILINE)


def _turn_header_into_link(md: str) -> str:
    """Takes first nonempty line and turns into a markdown link

    Args:
        md (str): markdown text to get a link to

    Returns:
        str: markdown link
    """

    return "#" + re.sub(r"^[#]+\s+", "", md.lstrip().splitlines()[0].lower()).replace(" ", "-")


def _get_plugin_name(plugin_folder: str) -> str:
    """Extracts plugin name from its .config or .sql folder"""
    return plugin_folder.split(".")[0]


def _get_plugin_title(plugin_name: str) -> str:
    """Returns plugin name from its file name."""
    return plugin_name.replace("_", " ").title()


def _get_clean_description(details: dict) -> str:
    """Rephrases descriptions to be properly displayed in columns."""
    description = details.get("__description", "")
    return description.replace("\n", " ").replace("-", "<br>-")


def _generate_markdown_table(columns: List[str], rows_data: List[List]) -> str:
    """Generates a Markdown table with left-aligned columns based on max content length.

    Args:
        columns: List of column header strings.
        rows_data: List of rows, each row is a list of cell values.

    Returns:
        Markdown table string.
    """
    # Calculate column widths
    column_widths = []
    for i, header in enumerate(columns):
        max_len = len(header)
        for row in rows_data:
            max_len = max(max_len, len(str(row[i])))
        column_widths.append(max_len)

    # Generate header
    header = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(columns, column_widths)) + " |\n"
    separator = "| " + " | ".join("-" * w for w in column_widths) + " |\n"

    # Generate rows
    rows = ""
    for row_data in rows_data:
        row = "| " + " | ".join(f"{str(cell):<{w}}" for cell, w in zip(row_data, column_widths)) + " |\n"
        rows += row

    return header + separator + rows + "\n"


def _generate_semantics_tables(json_data: Dict, plugin_name: str, no_global_context_name: bool) -> str:
    """Generates tables with semantics."""
    __tables = ""
    for key in ["dimensions", "attributes", "metrics", "event_timestamps"]:
        if key in json_data and len(json_data[key]):
            __tables += f"### {key.replace('_', ' ').capitalize()} at the `{plugin_name}` plugin\n\n"

            # Define columns based on key
            if key == "metrics":
                columns = ["Identifier", "Name", "Unit", "Description", "Example"]
            else:
                columns = ["Identifier", "Description", "Example"]
            if no_global_context_name:
                columns.append("Context Name")

            # Prepare rows data
            rows_data = []
            for key_id, details in sorted(json_data[key].items()):
                key_id = key_id.replace(".", ".&#8203;")  # Replace "." with ".&#8203;" to avoid breaking links
                description = _get_clean_description(details)
                example = details.get("__example", "")
                if isinstance(example, str) and ("@" in example or "* *" in example):
                    example = f"`{example}`"
                if key == "metrics":
                    name = details.get("displayName", "")
                    unit = details.get("unit", "")
                    row = [key_id, name, unit, description, example]
                else:
                    row = [key_id, description, example]
                if no_global_context_name:
                    context_names = ", ".join(details.get("__context_names", []))
                    row.append(context_names)
                rows_data.append(row)

            __tables += _generate_markdown_table(columns, rows_data)
    return __tables


def _generate_bom_tables(bom_data: Dict, plugin_name: str, scope: str) -> str:
    """Generates tables with bom information."""
    if scope not in bom_data or not bom_data[scope]:
        return ""

    items = bom_data[scope]

    # Fixed column order
    columns = ["name", "type", "privileges", "granted to", "language", "comment"]
    # Filter to only include columns that have data in at least one item
    present_columns = [col for col in columns if any(col in item for item in items)]
    column_headers = [col.capitalize() for col in present_columns]

    # Prepare rows data
    rows_data = []
    for item in items:
        row = []
        for key in present_columns:
            value = item.get(key, "")

            # Enhance comment field with optional/config_key information
            if key == "comment":
                comment = str(value) if value else ""
                # Add optional indicator if not already mentioned in comment
                if item.get("optional") and "optional" not in comment.lower():
                    config_key = item.get("config_key", "")
                    optional_info = "Optional"
                    if config_key:
                        optional_info += f" (controlled by {config_key})"
                    comment = f"{optional_info}. {comment}" if comment else optional_info
                value = comment

            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            value = str(value).replace("|", "/").replace("\n", " ")
            row.append(value)
        rows_data.append(row)

    return _generate_markdown_table(column_headers, rows_data)


def _generate_plugins_info(dtagent_plugins_path: str, dtagent_conf_path: str) -> Tuple[str, List]:
    """Gathers plugin info from readme.md files and their default config files."""

    __content = ""
    __plugins_toc = []

    # Add the core BOM section first
    core_bom_path = os.path.join(dtagent_conf_path, "bom.yml")
    if os.path.isfile(core_bom_path):
        core_bom_sec = "core_bom_sec"
        __plugins_toc.append(f"- [Core Objects](#{core_bom_sec})")

        __content += f'<a name="{core_bom_sec}"></a>\n\n## Core Snowflake Objects\n\n'
        __content += "The Dynatrace Snowflake Observability Agent creates and uses the following Snowflake objects.\n\n"

        bom_data = yaml.safe_load(_read_file(core_bom_path))

        __content += "### Objects delivered by the agent\n\n"
        __content += _generate_bom_tables(bom_data, "core", "delivers")

        __content += "### Objects referenced by the agent\n\n"
        __content += _generate_bom_tables(bom_data, "core", "references")

    # Iterate over each plugin folder in src/dtagent/plugins
    for plugin_folder in sorted(os.listdir(dtagent_plugins_path)):
        plugin_path = os.path.join(dtagent_plugins_path, plugin_folder)
        if os.path.isdir(plugin_path):

            f_info_md = os.path.join(plugin_path, "readme.md")
            f_config_md = os.path.join(plugin_path, "config.md")
            f_bom_yml = os.path.join(plugin_path, "bom.yml")
            config_file_name = f"{plugin_folder.split('.')[0]}-config.yml"
            config_file_path = os.path.join(plugin_path, config_file_name)

            if os.path.isfile(f_info_md) or os.path.isfile(f_config_md) or os.path.isfile(config_file_path) or os.path.isfile(f_bom_yml):
                plugin_name = _get_plugin_name(plugin_folder)
                plugin_title = _get_plugin_title(plugin_name)
                plugin_info_sec = f"{plugin_name}_info_sec"
                __plugins_toc.append(f"- [{plugin_title}](#{plugin_info_sec})")

                __content += f'<a name="{plugin_info_sec}"></a>\n\n## The {plugin_title} plugin\n'

                if os.path.isfile(f_info_md):
                    __content += _read_file(f_info_md) + "\n"

                __content += f"[Show semantics for this plugin](#{plugin_name}_semantics_sec)\n\n"

                if os.path.isfile(config_file_path) or os.path.isfile(f_config_md):
                    __content += f"### {plugin_title} default configuration\n\n"
                    __content += (
                        "To disable this plugin, set `IS_DISABLED` to `true`.\n\n"
                        "In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, "
                        "you need to explicitly set `IS_ENABLED` to `true` to enable selected plugins; `IS_DISABLED` is not checked then."
                        "\n\n"
                    )
                    __content += "```json\n" + _read_file(config_file_path) + "\n```\n\n"
                    if os.path.isfile(f_config_md):
                        __content += _read_file(f_config_md) + "\n"

                if os.path.isfile(f_bom_yml):
                    bom_data = yaml.safe_load(_read_file(f_bom_yml))

                    __content += f"### {plugin_title} Bill of Materials\n\n"
                    __content += "The following tables list the Snowflake objects that this plugin delivers data from or references.\n\n"

                    __content += f"#### Objects delivered by the `{plugin_title}` plugin\n\n"
                    __content += _generate_bom_tables(bom_data, plugin_name, "delivers")

                    __content += f"#### Objects referenced by the `{plugin_title}` plugin\n\n"
                    __content += _generate_bom_tables(bom_data, plugin_name, "references")

    return __content, __plugins_toc


def _generate_semantics_section(dtagent_conf_path: str, dtagent_plugins_path: str) -> Tuple[str, List]:
    """Generates semantics sections for .md file."""

    from src.dtagent.context import RUN_CONTEXT_KEY

    def __contains_key(d: Dict, key: str) -> bool:
        """Returns True if there is at least on key with given name

        Args:
            d (Dict): _description_
            key (str): _description_

        Returns:
            bool: _description_
        """
        if key in d:
            return True
        for _, v in d.items():
            if isinstance(v, dict):
                if __contains_key(v, key):
                    return True
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and __contains_key(item, key):
                        return True
        return False

    __content = ""
    __plugins_toc = []

    # Add the core semantics
    core_semantics_path = os.path.join(dtagent_conf_path, "instruments-def.yml")
    with open(core_semantics_path, "r", encoding="utf-8") as file:
        core_semantics = yaml.safe_load(file)
        core_semantics_sec = "core_semantics_sec"
        __plugins_toc.append(f"- [Shared semantics](#{core_semantics_sec})")

        __content += f'<a name="{core_semantics_sec}"></a>\n\n## Dynatrace Snowflake Observability Agent `core` semantics\n\n'
        __content += _generate_semantics_tables(core_semantics, "core", False)

    # Add the semantics for each plugin
    for plugin_folder in sorted(os.listdir(dtagent_plugins_path)):
        plugin_path = os.path.join(dtagent_plugins_path, plugin_folder)
        if os.path.isdir(plugin_path):
            semantics_path = os.path.join(plugin_path, "instruments-def.yml")
            if os.path.isfile(semantics_path):
                with open(semantics_path, "r", encoding="utf-8") as file:
                    plugin_name = _get_plugin_name(plugin_folder)
                    plugin_title = _get_plugin_title(plugin_name)
                    plugin_input = yaml.safe_load(file)

                    no_global_context_name = __contains_key(plugin_input, "__context_names")

                    plugin_semantics = _generate_semantics_tables(plugin_input, plugin_title, no_global_context_name)
                    if plugin_semantics:
                        plugin_semantics_sec = f"{plugin_name}_semantics_sec"
                        __plugins_toc.append(f"- [{plugin_title}](#{plugin_semantics_sec})")

                        __content += f'<a name="{plugin_semantics_sec}"></a>\n\n## The `{plugin_title}` plugin semantics\n\n'
                        __content += f"[Show plugin description](#{plugin_name}_info_sec)\n\n"

                        if no_global_context_name:
                            __content += (
                                "This plugin delivers telemetry in multiple contexts. "
                                f"To filter by one of plugin's context names (reported as `{RUN_CONTEXT_KEY}`), "
                                "please check the `Context Name` column below.\n\n"
                            )
                        else:
                            __content += (
                                f'All telemetry delivered by this plugin is reported as `{RUN_CONTEXT_KEY} == "{plugin_name}"`.\n\n'
                            )

                        __content += plugin_semantics

    return __content, __plugins_toc


def _generate_appendix(appx_name: str) -> str:
    """Function to generate the appendix section for README.md

    Args:
        appx_name (str): Prefix for the appendix, e.g., "appx-a-appendix-name"

    Returns:
        content of the appendix section as a string
    """
    appendix_content = _read_file(f"{appx_name}-header.md")

    csv_file_name = f"{appx_name}.csv"
    if os.path.isfile(csv_file_name):
        csv_file = _read_file(csv_file_name)
        csv_lines = [line.split(";") for line in csv_file.split("\n")]
        rows = [row for row in csv_lines[1:] if len(row) == 2 and row[0] != row[1]]

        processed_rows = []
        group_value = None
        group_pattern = r"(\(.*?\)\?)"
        for row in rows:
            match = re.search(group_pattern, row[0])
            if match:
                group_value = match.group(1)
                old_name = re.sub(group_pattern, "`*`", row[0])
            else:
                old_name = row[0]
            new_name = row[1]
            processed_rows.append((old_name, new_name))

        for old_name, new_name in processed_rows:
            appendix_content += f"| {old_name} | {new_name} |\n"

        if group_value is not None:
            group_name_cleaned = re.sub(r"\\\.", ".", group_value)[:-1]
            appendix_content += (
                f"\n`*` represents possible values that might be present as part of the field name: `{group_name_cleaned}`\n"
            )

    return appendix_content + "\n"


def _extract_appendix_info(header_file_path: str) -> Tuple[str, str]:
    """Extract appendix title and anchor from header markdown file.

    Args:
        header_file_path (str): Path to the header markdown file

    Returns:
        Tuple[str, str]: (title, anchor) extracted from the header file
    """
    header_content = _read_file(header_file_path)

    # Extract anchor from <a name="..."></a> tag
    anchor_match = re.search(r'<a name="([^"]+)"></a>', header_content)
    anchor = anchor_match.group(1) if anchor_match else ""

    # Extract title from the first ## header
    title_match = re.search(r"^## (.+)$", header_content, re.MULTILINE)
    title = title_match.group(1) if title_match else ""

    return title, anchor


def generate_readme_content(dtagent_conf_path: str, dtagent_plugins_path: str) -> Tuple[str, str, str, str, str]:
    """Generates readme from sources

    Returns:
        A tuple containing the content for: readme_full_content, readme_short_content, plugins_content, semantics_content, appendix_content
    """

    # Add the content of src/dtagent.conf/readme.md to README.md
    readme_short_content = readme_full_content = _read_file(os.path.join(dtagent_conf_path, "readme.md"))
    plugins_content = ""
    semantics_content = ""
    appendix_content = ""

    # Read other markdown files
    dpo_content = _read_file("docs/DPO.md")
    usecases_content = _read_file("docs/USECASES.md")
    architecture_content = _read_file("docs/ARCHITECTURE.md")
    install_content = _read_file("docs/INSTALL.md")
    plugin_dev_content = _read_file("docs/PLUGIN_DEVELOPMENT.md")  # ADD THIS
    changelog_content = _read_file("docs/CHANGELOG.md")
    contributing_content = _read_file("docs/CONTRIBUTING.md")
    copyright_content = _read_file("docs/COPYRIGHT.md")

    # Generate appendices for all CSV files in src/assets/
    assets_path = "src/assets"
    appendix_toc = []
    if os.path.exists(assets_path):
        for asset_file_path in sorted(os.listdir(assets_path)):
            if asset_file_path.startswith("appx-") and asset_file_path.endswith("-header.md"):
                base_name = asset_file_path[: -len("-header.md")]
                appendix_content += _generate_appendix(os.path.join(assets_path, base_name))
                title, anchor = _extract_appendix_info(os.path.join(assets_path, asset_file_path))
                if title and anchor:
                    appendix_toc.append(f"- [{title}](README.md#{anchor})")

    if appendix_toc:
        readme_full_content += "\n".join(appendix_toc) + "\n"
        readme_short_content += "- [Appendix](docs/APPENDIX.md)\n"

    # Combine all contents into full content README for PDF generation
    readme_full_content += "\n"
    readme_full_content += _lower_headers_one_level(dpo_content) + "\n"
    readme_full_content += _lower_headers_one_level(usecases_content) + "\n"
    readme_full_content += _lower_headers_one_level(architecture_content) + "\n"

    plugins_content, plugins_toc = _generate_plugins_info(dtagent_plugins_path, dtagent_conf_path)
    readme_full_content += "## Plugins\n\n"
    readme_full_content += "\n".join(plugins_toc)
    readme_full_content += "\n\n"
    readme_full_content += _lower_headers_one_level(plugins_content)

    semantics_content, semantics_toc = _generate_semantics_section(dtagent_conf_path, dtagent_plugins_path)
    readme_full_content += "## Semantic Dictionary\n\n"
    readme_full_content += "\n".join(semantics_toc)
    readme_full_content += "\n\n"
    readme_full_content += _lower_headers_one_level(semantics_content)

    readme_full_content += _lower_headers_one_level(install_content) + "\n"
    readme_full_content += _lower_headers_one_level(changelog_content) + "\n"
    readme_full_content += _lower_headers_one_level(contributing_content)
    readme_full_content += _lower_headers_one_level(plugin_dev_content)

    readme_full_content += appendix_content

    readme_full_content += _lower_headers_one_level(copyright_content)
    # readme_full_content = re.sub(
    #     r"\]\(docs\/", "](https://github.com/dynatrace-oss/dynatrace-snowflake-observability-agent/tree/main/docs/", readme_full_content
    # )  # replace internal links to docs with absolute links to GitHub
    readme_full_content = re.sub(
        r"\]\(test\/", "](https://github.com/dynatrace-oss/dynatrace-snowflake-observability-agent/tree/main/test/", readme_full_content
    )  # replace internal links to test directory with absolute links to GitHub
    readme_full_content = re.sub(r"\b[A-Z_]+\.md#", "#", readme_full_content)  # removing references between .md files

    # Update links in PDF version to point to sections within the same document
    readme_full_content = re.sub(r"(docs/)?DPO\.md", _turn_header_into_link(dpo_content), readme_full_content)
    readme_full_content = re.sub(r"(docs/)?USECASES\.md", _turn_header_into_link(usecases_content), readme_full_content)
    readme_full_content = re.sub(r"(docs/)?ARCHITECTURE\.md", _turn_header_into_link(architecture_content), readme_full_content)
    readme_full_content = re.sub(r"(docs/)?INSTALL\.md", _turn_header_into_link(install_content), readme_full_content)
    readme_full_content = re.sub(r"(docs/)?PLUGIN_DEVELOPMENT\.md", _turn_header_into_link(plugin_dev_content), readme_full_content)
    readme_full_content = re.sub(r"(docs/)?CHANGELOG\.md", _turn_header_into_link(changelog_content), readme_full_content)
    readme_full_content = re.sub(r"(docs/)?CONTRIBUTING\.md", _turn_header_into_link(contributing_content), readme_full_content)
    readme_full_content = re.sub(r"(docs/)?README\.md", _turn_header_into_link(readme_full_content), readme_full_content)

    readme_full_content = re.sub(r"""(\]\(|src=")(assets[/].*\.jpg)""", r"\1docs/\2", readme_full_content)

    # Postprocess the short README.md content
    plugins_content = (
        "# Plugins\n\n"
        + "\n".join(plugins_toc)
        + plugins_content.replace("[Show semantics for this plugin](#", "[Show semantics for this plugin](SEMANTICS.md#").rstrip()
        + "\n"
    )
    semantics_content = (
        "# Semantic Dictionary\n\n"
        + "\n".join(semantics_toc)
        + semantics_content.replace("[Show plugin description](#", "[Show plugin description](PLUGINS.md#").rstrip()
        + "\n"
    )
    appendix_content = ("# Appendix\n\n" + "\n".join(appendix_toc) + "\n\n" + appendix_content.rstrip() + "\n").replace(
        "README.md#appendix", "#appendix"
    )

    return readme_full_content, readme_short_content, plugins_content, semantics_content, appendix_content


def main():
    """Runs readme generation and saves to .md file"""

    # Define the paths
    base_path = "src"
    dtagent_conf_path = os.path.join(base_path, "dtagent.conf")
    dtagent_plugins_path = os.path.join(base_path, "dtagent", "plugins")

    # Initialize the content of README.md
    readme_full_content, readme_short_content, plugins_content, semantics_content, appendix_content = generate_readme_content(
        dtagent_conf_path, dtagent_plugins_path
    )

    # Update headers for INSTALL and CONTRIBUTING

    # Write the markdown files
    with open("README.md", "w", encoding="utf-8") as file:
        file.write(readme_short_content)

    with open("docs/PLUGINS.md", "w", encoding="utf-8") as file:
        file.write(plugins_content)

    with open("docs/SEMANTICS.md", "w", encoding="utf-8") as file:
        file.write(semantics_content)

    with open("docs/APPENDIX.md", "w", encoding="utf-8") as file:
        file.write(appendix_content)

    with open("_readme_full.md", "w", encoding="utf-8") as file:
        file.write(readme_full_content)

    print("Documentation has been successfully refreshed.")


if __name__ == "__main__":
    main()
