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

"""Test suite to verify copyright headers in source files.

This test ensures all SQL files in the src/ directory contain the required
MIT License copyright header with proper formatting.

To run this test:
    pytest test/core/test_copyrights.py

The test will fail if any SQL files are missing or have an incorrect copyright header.
"""

import os
import re
from pathlib import Path


class TestCopyrights:
    """Test that all source files contain proper copyright headers."""

    # Expected copyright header pattern for SQL files (as regex)
    # Allows years 2025 or later, and 2+ trailing comment lines
    SQL_COPYRIGHT_PATTERN = r"""(?:--
)+-- Copyright \(c\) (202[5-9]|20[3-9][0-9]) Dynatrace Open Source
--
-- Permission is hereby granted, free of charge, to any person obtaining a copy
-- of this software and associated documentation files \(the "Software"\), to deal
-- in the Software without restriction, including without limitation the rights
-- to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
-- copies of the Software, and to permit persons to whom the Software is
-- furnished to do so, subject to the following conditions:
--
-- The above copyright notice and this permission notice shall be included in all
-- copies or substantial portions of the Software\.
--
-- THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
-- IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
-- FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT\. IN NO EVENT SHALL THE
-- AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
-- LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
-- OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
-- SOFTWARE\.
--
--(?:
--)*"""

    def _get_sql_files(self, directory: str) -> list:
        """Recursively find all SQL files in the specified directory.

        Args:
            directory (str): Root directory to search

        Returns:
            list: List of Path objects for all SQL files found
        """
        sql_files = []
        src_path = Path(directory)

        if not src_path.exists():
            return sql_files

        for sql_file in src_path.rglob("*.sql"):
            # Skip __pycache__ and build artifacts, and ensure it's actually a file not a directory
            if "__pycache__" not in str(sql_file) and "build" not in str(sql_file) and sql_file.is_file():
                sql_files.append(sql_file)

        return sorted(sql_files)

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text for comparison.

        Strips trailing whitespace from each line but preserves line structure.

        Args:
            text (str): Text to normalize

        Returns:
            str: Normalized text
        """
        lines = text.split("\n")
        normalized_lines = [line.rstrip() for line in lines]
        return "\n".join(normalized_lines)

    def _check_copyright_header(self, file_path: Path, expected_pattern: str) -> tuple:
        """Check if file contains the expected copyright header.

        Args:
            file_path (Path): Path to the file to check
            expected_pattern (str): Expected copyright header regex pattern

        Returns:
            tuple: (bool, str) - (has_copyright, error_message)
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Normalize line endings and whitespace for comparison
            content_normalized = self._normalize_whitespace(content.replace("\r\n", "\n"))

            # Use regex to match the copyright pattern (with MULTILINE flag for multi-line patterns)
            if re.search(expected_pattern, content_normalized, re.MULTILINE):
                return True, None
            else:
                return False, "Missing or incorrect copyright header"

        except (OSError, UnicodeDecodeError) as e:
            return False, f"Error reading {file_path}: {str(e)}"

    def test_sql_files_have_copyright_header(self):
        """Test that all SQL files in src/ directory contain the copyright header."""
        # Get the project root directory (assuming test is in test/core/)
        test_dir = Path(__file__).parent
        project_root = test_dir.parent.parent
        src_dir = project_root / "src"

        # Find all SQL files
        sql_files = self._get_sql_files(str(src_dir))

        # Assert we found at least one SQL file
        assert len(sql_files) > 0, f"No SQL files found in {src_dir}"

        # Check each file for copyright header
        missing_copyright = []
        for sql_file in sql_files:
            has_copyright, problem = self._check_copyright_header(sql_file, self.SQL_COPYRIGHT_PATTERN)

            if not has_copyright:
                missing_copyright.append(str(sql_file.relative_to(project_root)) + ": " + problem)

        # Assert all files have copyright headers
        if missing_copyright:
            error_message = (
                f"\n\nThe following {len(missing_copyright)} SQL file(s) are missing "
                f"the required copyright header:\n  - " + "\n  - ".join(missing_copyright)
            )
            assert False, error_message
