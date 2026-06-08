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
"""Unit tests for QueryHistoryPlugin._obfuscate_query_text."""

from unittest.mock import MagicMock

import pytest

from dtagent.plugins.query_history import QueryHistoryPlugin


def _make_plugin(mode: str) -> QueryHistoryPlugin:
    """Construct a minimal QueryHistoryPlugin instance with a mocked configuration.

    Args:
        mode (str): Value to return for the 'obfuscation_mode' config key.

    Returns:
        QueryHistoryPlugin: Plugin instance ready for obfuscation tests.
    """
    plugin = QueryHistoryPlugin.__new__(QueryHistoryPlugin)
    plugin._plugin_name = "query_history"
    config_mock = MagicMock()
    config_mock.get.return_value = mode
    plugin._configuration = config_mock
    return plugin


class TestObfuscateModeOff:
    """Mode 'off' — text returned unchanged."""

    def test_plain_query_unchanged(self):
        """Plain query text is returned as-is."""
        plugin = _make_plugin("off")
        text = "SELECT * FROM users WHERE id = 42"
        assert plugin._obfuscate_query_text(text) == text

    def test_query_with_credentials_unchanged(self):
        """Query with credentials is returned unchanged in off mode."""
        plugin = _make_plugin("off")
        text = "COPY INTO s3://bucket FROM t CREDENTIALS=(AWS_KEY_ID='AKIAIOSFODNN7' AWS_SECRET_KEY='secret')"
        assert plugin._obfuscate_query_text(text) == text

    def test_empty_string_unchanged(self):
        """Empty string is returned unchanged."""
        plugin = _make_plugin("off")
        assert plugin._obfuscate_query_text("") == ""


class TestObfuscateModeFull:
    """Mode 'full' — entire text replaced with '[OBFUSCATED]'."""

    def test_query_replaced(self):
        """Any query text is replaced with [OBFUSCATED]."""
        plugin = _make_plugin("full")
        assert plugin._obfuscate_query_text("SELECT secret FROM t") == "[OBFUSCATED]"

    def test_error_message_replaced(self):
        """Error message containing query text is fully replaced."""
        plugin = _make_plugin("full")
        text = "SQL compilation error: syntax error at position 7 unexpected 'FROM'. SELECT FROM users WHERE password = 'secret'"
        assert plugin._obfuscate_query_text(text) == "[OBFUSCATED]"

    def test_empty_string_replaced(self):
        """Empty string also becomes [OBFUSCATED] in full mode."""
        plugin = _make_plugin("full")
        assert plugin._obfuscate_query_text("") == "[OBFUSCATED]"


class TestObfuscateModeLiterals:
    """Mode 'literals' — string and numeric literals replaced with '?'."""

    def test_string_literal_replaced(self):
        """Single-quoted string literals are replaced with '?'."""
        plugin = _make_plugin("literals")
        result = plugin._obfuscate_query_text("SELECT * FROM t WHERE name = 'John'")
        assert "'John'" not in result
        assert "'?'" in result

    def test_numeric_literal_replaced(self):
        """Standalone numeric literals are replaced with '?'."""
        plugin = _make_plugin("literals")
        result = plugin._obfuscate_query_text("SELECT * FROM t WHERE age > 30")
        assert "30" not in result
        assert "?" in result

    def test_sql_structure_preserved(self):
        """SQL keywords and column names are not replaced."""
        plugin = _make_plugin("literals")
        result = plugin._obfuscate_query_text("SELECT id, name FROM users WHERE active = 1")
        assert "SELECT" in result
        assert "FROM" in result
        assert "WHERE" in result
        assert "users" in result

    def test_copy_credentials_replaced(self):
        """Credential string literals in COPY INTO are obfuscated."""
        plugin = _make_plugin("literals")
        text = "COPY INTO t FROM s3://bucket CREDENTIALS=(AWS_KEY_ID='AKIAIOSFODNN7' AWS_SECRET_KEY='wJalrXUtnFEMI')"
        result = plugin._obfuscate_query_text(text)
        assert "AKIAIOSFODNN7" not in result
        assert "wJalrXUtnFEMI" not in result
        assert "COPY INTO" in result
        assert "CREDENTIALS" in result

    def test_multiple_string_literals_replaced(self):
        """Multiple string literals in one query are all replaced."""
        plugin = _make_plugin("literals")
        result = plugin._obfuscate_query_text("INSERT INTO t VALUES ('Alice', 'secret123', 'admin')")
        assert "Alice" not in result
        assert "secret123" not in result
        assert "admin" not in result
        assert result.count("'?'") == 3

    def test_error_message_literals_replaced(self):
        """Literals embedded in an error message are replaced."""
        plugin = _make_plugin("literals")
        text = "Syntax error near 'DROP TABLE users WHERE id = 99'"
        result = plugin._obfuscate_query_text(text)
        assert "DROP TABLE users WHERE id = 99" not in result
        assert "?" in result

    def test_empty_string_literal_replaced(self):
        """Empty string literal '' is replaced with '?'."""
        plugin = _make_plugin("literals")
        result = plugin._obfuscate_query_text("SELECT * FROM t WHERE x = ''")
        assert "''" not in result
        assert "'?'" in result


class TestObfuscateModeUnknown:
    """Unknown / invalid mode — safe fallback returns text unchanged."""

    @pytest.mark.parametrize("mode", ["FULL", "Literals", "redact", "1", " ", "none"])
    def test_unknown_mode_returns_raw(self, mode: str):
        """Any unrecognised mode value falls back to returning the original text."""
        plugin = _make_plugin(mode)
        text = "SELECT * FROM t WHERE password = 'secret'"
        assert plugin._obfuscate_query_text(text) == text
