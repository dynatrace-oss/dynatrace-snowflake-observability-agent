#!/usr/bin/env python3
#
# Copyright (c) 2026 Dynatrace Open Source
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
"""Removes docstrings from Python source files using AST transformation.

This is used during the build process to reduce the size of deployed code.
"""

import sys
import ast


class DocstringRemover(ast.NodeTransformer):
    """AST transformer that removes docstrings from functions, classes, and modules."""

    def visit_FunctionDef(self, node):
        """Remove docstring from function definition."""
        self.generic_visit(node)
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
        return node

    def visit_AsyncFunctionDef(self, node):
        """Remove docstring from async function definition."""
        self.generic_visit(node)
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
        return node

    def visit_ClassDef(self, node):
        """Remove docstring from class definition."""
        self.generic_visit(node)
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
        return node

    def visit_Module(self, node):
        """Remove docstring from module."""
        self.generic_visit(node)
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body = node.body[1:]
        return node


def remove_docstrings(file_path: str) -> None:
    """Remove docstrings from a Python file in-place.

    Preserves #%PLUGIN: markers that are used to identify plugin sections.

    Args:
        file_path: Path to the Python file to process
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split content by plugin markers
    lines = content.split("\n")
    sections = []
    current_section = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#%PLUGIN:") or stripped.startswith("#%:PLUGIN:"):
            # Save current section if it has content
            if current_section:
                sections.append(("code", "\n".join(current_section)))
                current_section = []
            # Save marker
            sections.append(("marker", line))
        else:
            current_section.append(line)

    # Don't forget the last section
    if current_section:
        sections.append(("code", "\n".join(current_section)))

    # Process each code section
    result_parts = []
    for section_type, section_content in sections:
        if section_type == "marker":
            result_parts.append(section_content)
        else:
            # Process code section
            try:
                tree = ast.parse(section_content)
                remover = DocstringRemover()
                new_tree = remover.visit(tree)
                processed = ast.unparse(new_tree)
                result_parts.append(processed)
            except SyntaxError:
                # If section can't be parsed (e.g., incomplete code), keep as-is
                result_parts.append(section_content)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(result_parts))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <python_file>", file=sys.stderr)
        sys.exit(1)

    remove_docstrings(sys.argv[1])
