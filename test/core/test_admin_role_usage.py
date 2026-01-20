"""Test to ensure DTAGENT_ADMIN role usage is restricted to admin files only."""

import os
import re
from pathlib import Path
import pytest


def find_sql_files(root_dir: str) -> dict[str, list[Path]]:
    """Find all SQL files categorized by type."""
    sql_files = {"admin": [], "non_admin": []}

    root = Path(root_dir)

    # Find all SQL files
    for sql_file in root.rglob("*.sql"):
        # Skip test files and build artifacts
        if (
            "test" in sql_file.parts
            or "build" in sql_file.parts
            or "upgrade" in sql_file.parts
            or "init" in sql_file.parts
            or not sql_file.is_file()
        ):
            continue

        # Check if file is in admin directory
        if "admin" in sql_file.parts:
            sql_files["admin"].append(sql_file)
        else:
            sql_files["non_admin"].append(sql_file)

    return sql_files


def check_admin_role_usage(file_path: Path) -> list[tuple[int, str]]:
    """Check for DTAGENT_ADMIN role usage or ownership grants to it."""
    violations = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            # Skip comments
            if line.strip().startswith("--"):
                continue

            # Check for USE ROLE DTAGENT_ADMIN
            if re.search(r"\bUSE\s+ROLE\s+DTAGENT_ADMIN\b", line, re.IGNORECASE):
                violations.append((line_num, line.strip()))

            # Check for GRANT OWNERSHIP ... TO ROLE DTAGENT_ADMIN
            if re.search(r"\bGRANT\s+OWNERSHIP\b.*\bTO\s+ROLE\s+DTAGENT_ADMIN\b", line, re.IGNORECASE):
                violations.append((line_num, line.strip()))

    return violations


class TestAdminRoleUsage:
    """Test suite for admin role usage restrictions."""

    @pytest.fixture(scope="class")
    def sql_files(self):
        """Get categorized SQL files."""
        root_dir = Path(__file__).parent.parent.parent / "src"
        return find_sql_files(str(root_dir))

    def test_admin_role_not_in_non_admin_files(self, sql_files):
        """Test that DTAGENT_ADMIN role is not used outside admin files.
        This ensures proper separation of admin operations.
        """
        violations_by_file = {}

        for file_path in sql_files["non_admin"]:
            violations = check_admin_role_usage(file_path)
            if violations:
                violations_by_file[str(file_path)] = violations

        if violations_by_file:
            error_msg = "Found DTAGENT_ADMIN role usage in non-admin files:\n\n"
            for file_path, violations in violations_by_file.items():
                error_msg += f"{file_path}:\n"
                for line_num, line in violations:
                    error_msg += f"  Line {line_num}: {line}\n"
                error_msg += "\n"

            pytest.fail(error_msg)

    def test_admin_files_exist(self, sql_files):
        """Test that admin SQL files exist."""
        assert len(sql_files["admin"]) > 0, "No admin SQL files found in src/dtagent.sql/admin or plugin admin directories"

    def test_build_creates_admin_sql(self):
        """Test that build process creates 10_admin.sql."""
        admin_sql = Path(__file__).parent.parent.parent / "build" / "10_admin.sql"

        # Run build if file doesn't exist
        if not admin_sql.exists():
            pytest.skip("build/10_admin.sql not found. Run build.sh first.")

        assert admin_sql.is_file(), "build/10_admin.sql should exist after build"
        assert admin_sql.stat().st_size > 0, "build/10_admin.sql should not be empty"
