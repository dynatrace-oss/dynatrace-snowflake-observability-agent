"""Unit tests for src/build/update_docs.py."""

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

from build.update_docs import _generate_markdown_table, _get_clean_description

##region Unit tests — _get_clean_description


class TestGetCleanDescription:
    """Verify _get_clean_description formats field descriptions for Markdown table cells."""

    def test_plain_description_no_enum(self):
        """Description without __enum is returned unchanged (aside from newline/dash handling)."""
        details = {"__description": "A simple field."}
        assert _get_clean_description(details) == "A simple field."

    def test_newlines_replaced_with_spaces(self):
        """Newlines in the base description become spaces."""
        details = {"__description": "Line one.\nLine two."}
        assert _get_clean_description(details) == "Line one. Line two."

    def test_dashes_replaced_with_br_dash(self):
        """Dashes in the base description are prefixed with <br> for list-like rendering."""
        details = {"__description": "Values:\n- one\n- two"}
        assert _get_clean_description(details) == "Values: <br>- one <br>- two"

    def test_missing_description_defaults_to_empty(self):
        """Missing __description defaults to an empty base string."""
        assert _get_clean_description({}) == ""

    def test_enum_with_members_and_brief(self):
        """Enum members with a brief render as `value` — brief, with trailing periods stripped."""
        details = {
            "__description": "The size.",
            "__enum": {"members": [{"value": "SMALL", "brief": "A small size."}]},
        }
        result = _get_clean_description(details)
        assert result == "The size. <br> Possible values: <ul><li> `SMALL` — A small size</ul>"

    def test_enum_member_without_brief(self):
        """Enum members without a brief render as just `value`."""
        details = {
            "__description": "The size.",
            "__enum": {"members": [{"value": "SMALL"}]},
        }
        result = _get_clean_description(details)
        assert result == "The size. <br> Possible values: <ul><li> `SMALL`</ul>"

    def test_enum_multiple_members_joined(self):
        """Multiple enum members are comma-joined within the <ul>."""
        details = {
            "__description": "The size.",
            "__enum": {"members": [{"value": "SMALL", "brief": "Small."}, {"value": "LARGE"}]},
        }
        result = _get_clean_description(details)
        assert result == "The size. <br> Possible values: <ul><li> `SMALL` — Small, <li> `LARGE`</ul>"

    def test_enum_empty_members_list_falls_back_to_base(self):
        """Empty members list yields just the base description, no enum block."""
        details = {"__description": "The size.", "__enum": {"members": []}}
        assert _get_clean_description(details) == "The size."

    def test_enum_missing_returns_base(self):
        """A falsy __enum value is treated as no enum at all."""
        details = {"__description": "The size.", "__enum": None}
        assert _get_clean_description(details) == "The size."

    def test_enum_not_a_dict_returns_base(self):
        """A non-dict __enum value is treated as no enum at all."""
        details = {"__description": "The size.", "__enum": "not-a-dict"}
        assert _get_clean_description(details) == "The size."

    def test_allow_custom_values_true_appends_note(self):
        """allow_custom_values: true appends the 'additional values' sentence."""
        details = {
            "__description": "The size.",
            "__enum": {"allow_custom_values": True, "members": [{"value": "SMALL"}]},
        }
        result = _get_clean_description(details)
        assert result.endswith("</ul> Additional values may be present.")

    def test_allow_custom_values_false_omits_note(self):
        """allow_custom_values: false does not append the 'additional values' sentence."""
        details = {
            "__description": "The size.",
            "__enum": {"allow_custom_values": False, "members": [{"value": "SMALL"}]},
        }
        result = _get_clean_description(details)
        assert result.endswith("</ul>")
        assert "Additional values" not in result

    def test_empty_base_description_no_extra_leading_space(self):
        """Empty base description does not add a spurious leading space before the enum block."""
        details = {"__enum": {"members": [{"value": "SMALL"}]}}
        result = _get_clean_description(details)
        assert result == "<br> Possible values: <ul><li> `SMALL`</ul>"


##endregion

##region Unit tests — _generate_markdown_table


class TestGenerateMarkdownTable:
    """Verify _generate_markdown_table produces well-formed, aligned Markdown tables."""

    def test_normal_multi_row_table(self):
        """Header, separator, and data rows are generated for a simple table."""
        table = _generate_markdown_table(["Name", "Value"], [["a", "1"], ["bb", "22"]])
        lines = table.split("\n")
        assert lines[0] == "| Name | Value |"
        assert lines[1] == "| ---- | ----- |"
        assert lines[2] == "| a    | 1     |"
        assert lines[3] == "| bb   | 22    |"

    def test_trailing_blank_line(self):
        """Table string ends with a trailing blank line."""
        table = _generate_markdown_table(["Name"], [["a"]])
        assert table.endswith("\n\n")

    def test_column_width_from_header(self):
        """Column width is at least as wide as the header when data is shorter."""
        table = _generate_markdown_table(["LongHeader"], [["x"]])
        lines = table.split("\n")
        assert lines[0] == "| LongHeader |"
        assert lines[2] == "| x          |"

    def test_column_width_from_data(self):
        """Column width expands to fit the widest data cell."""
        table = _generate_markdown_table(["ID"], [["short"], ["a_much_longer_value"]])
        lines = table.split("\n")
        width = len("a_much_longer_value")
        assert lines[0] == "| ID" + " " * (width - len("ID")) + " |"

    def test_pipe_character_escaped_in_cells(self):
        """Pipe characters in cell values are escaped so they don't break table structure."""
        table = _generate_markdown_table(["Value"], [["a|b"]])
        data_line = table.split("\n")[2]
        assert "a\\|b" in data_line
        # only the two cell-boundary pipes are unescaped; the content pipe is backslash-escaped
        assert data_line.replace("\\|", "").count("|") == 2

    def test_empty_rows_data(self):
        """An empty rows_data list still produces a header and separator, with no data rows."""
        table = _generate_markdown_table(["Name", "Value"], [])
        lines = table.split("\n")
        assert lines[0] == "| Name | Value |"
        assert lines[1] == "| ---- | ----- |"
        assert lines[2] == ""
        assert lines[3] == ""


##endregion
