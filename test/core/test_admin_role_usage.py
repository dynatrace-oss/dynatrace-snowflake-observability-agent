"""Test to ensure role usage and deployment scope restrictions are properly enforced."""

import re
from pathlib import Path
import pytest


def should_skip_sql_file(sql_file: Path) -> bool:
    """Check if SQL file should be skipped during analysis."""
    return (
        "test" in sql_file.parts
        or "build" in sql_file.parts
        or "upgrade" in sql_file.parts
        or "init" in sql_file.parts
        or not sql_file.is_file()
    )


def find_sql_files(root_dir: str) -> dict[str, list[Path]]:
    """Find all SQL files categorized by type."""
    sql_files = {"admin": [], "non_admin": []}

    root = Path(root_dir)

    # Find all SQL files
    for sql_file in root.rglob("*.sql"):
        # Skip test files and build artifacts
        if should_skip_sql_file(sql_file):
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


class TestDeploymentScopes:
    """Test suite for deployment scope configuration and restrictions."""

    def test_all_scope_includes_admin_scripts(self):
        """Test that 'all' scope in prepare_deploy_script.sh includes admin scripts (10_admin.sql).
        This ensures complete deployment includes administrative setup.
        """
        deploy_script = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "prepare_deploy_script.sh"

        assert deploy_script.exists(), "prepare_deploy_script.sh not found"

        content = deploy_script.read_text()

        # Find the 'all' scope case
        all_scope_pattern = r'all\)\s*SQL_FILES="([^"]+)"'
        match = re.search(all_scope_pattern, content, re.MULTILINE)

        assert match, "Could not find 'all' scope definition in prepare_deploy_script.sh"

        sql_files = match.group(1)

        # Check that 10_admin.sql is included
        assert "10_admin.sql" in sql_files, f"'all' scope must include 10_admin.sql. Found: {sql_files}"

        # Also verify the expected files are present
        expected_files = ["00_init.sql", "10_admin.sql", "20_setup.sql", "40_config.sql", "70_agents.sql"]
        for expected_file in expected_files:
            assert expected_file in sql_files, f"'all' scope missing expected file: {expected_file}. Found: {sql_files}"

    def test_accountadmin_only_in_init_upgrade_scopes(self):
        """Test that ACCOUNTADMIN role is only used in init and upgrade scopes.
        This ensures proper privilege separation at deployment level.
        """
        build_dir = Path(__file__).parent.parent.parent / "build"

        if not build_dir.exists():
            pytest.skip("build directory not found. Run build.sh first.")

        # Files that should NOT contain ACCOUNTADMIN
        restricted_files = {
            "admin": build_dir / "10_admin.sql",
            "setup": build_dir / "20_setup.sql",
            "config": build_dir / "40_config.sql",
            "agents": build_dir / "70_agents.sql",
        }

        # Check plugins separately
        plugins_dir = build_dir / "30_plugins"
        if plugins_dir.exists():
            for plugin_file in plugins_dir.glob("*.sql"):
                restricted_files[f"plugins/{plugin_file.name}"] = plugin_file

        violations_by_file = {}

        for scope, file_path in restricted_files.items():
            if not file_path.exists():
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    # Skip comments
                    if line.strip().startswith("--"):
                        continue

                    # Check for ACCOUNTADMIN usage
                    if re.search(r"\bACCOUNTADMIN\b", line, re.IGNORECASE):
                        if scope not in violations_by_file:
                            violations_by_file[scope] = []
                        violations_by_file[scope].append((line_num, line.strip()))

        if violations_by_file:
            error_msg = "Found ACCOUNTADMIN usage outside init/upgrade scopes:\n\n"
            for scope, violations in violations_by_file.items():
                error_msg += f"{scope} scope:\n"
                for line_num, line in violations:
                    error_msg += f"  Line {line_num}: {line}\n"
                error_msg += "\n"
            error_msg += "ACCOUNTADMIN should only be used in:\n"
            error_msg += "  - init scope (00_init.sql)\n"
            error_msg += "  - upgrade scope (09_upgrade/*.sql)\n"
            error_msg += "  - teardown operations (handled separately)\n"

            pytest.fail(error_msg)

    def test_dtagent_admin_only_in_admin_upgrade_scopes(self):
        """Test that DTAGENT_ADMIN role is only used in admin and upgrade scopes.
        This ensures proper privilege separation at deployment level.
        """
        build_dir = Path(__file__).parent.parent.parent / "build"

        if not build_dir.exists():
            pytest.skip("build directory not found. Run build.sh first.")

        # Files that should NOT contain DTAGENT_ADMIN (except in comments or grants TO DTAGENT_ADMIN)
        restricted_files = {
            "init": build_dir / "00_init.sql",
            "setup": build_dir / "20_setup.sql",
            "config": build_dir / "40_config.sql",
            "agents": build_dir / "70_agents.sql",
        }

        # Check plugins separately
        plugins_dir = build_dir / "30_plugins"
        if plugins_dir.exists():
            for plugin_file in plugins_dir.glob("*.sql"):
                restricted_files[f"plugins/{plugin_file.name}"] = plugin_file

        violations_by_file = {}

        for scope, file_path in restricted_files.items():
            if not file_path.exists():
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    # Skip comments
                    if line.strip().startswith("--"):
                        continue

                    # Skip lines that grant TO DTAGENT_ADMIN (these are allowed everywhere)
                    if re.search(r"\bTO\s+ROLE\s+DTAGENT_ADMIN\b", line, re.IGNORECASE):
                        continue

                    # Check for USE ROLE DTAGENT_ADMIN (not allowed outside admin/upgrade scope)
                    if re.search(r"\bUSE\s+ROLE\s+DTAGENT_ADMIN\b", line, re.IGNORECASE):
                        if scope not in violations_by_file:
                            violations_by_file[scope] = []
                        violations_by_file[scope].append((line_num, line.strip()))

        if violations_by_file:
            error_msg = "Found DTAGENT_ADMIN role usage (USE ROLE) outside admin/upgrade scopes:\n\n"
            for scope, violations in violations_by_file.items():
                error_msg += f"{scope} scope:\n"
                for line_num, line in violations:
                    error_msg += f"  Line {line_num}: {line}\n"
                error_msg += "\n"
            error_msg += "DTAGENT_ADMIN (USE ROLE) should only be used in:\n"
            error_msg += "  - admin scope (10_admin.sql)\n"
            error_msg += "  - upgrade scope (09_upgrade/*.sql)\n"
            error_msg += "\nNote: Grants TO ROLE DTAGENT_ADMIN are allowed in any scope.\n"

            pytest.fail(error_msg)

    def test_no_hardcoded_roles_in_shell_scripts(self):
        """Test that shell scripts don't contain hardcoded ACCOUNTADMIN or DTAGENT_ADMIN references.
        Scripts should use variables or configuration, not hardcoded role names.
        Exception: teardown SQL generation is allowed to use these roles.
        """
        scripts_dir = Path(__file__).parent.parent.parent / "scripts" / "deploy"

        if not scripts_dir.exists():
            pytest.skip("scripts/deploy directory not found.")

        violations_by_file = {}

        for script_file in scripts_dir.glob("*.sh"):
            in_teardown_section = False
            in_heredoc = False

            with open(script_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    # Check if we're entering teardown section
                    if "== 'teardown'" in line:
                        in_teardown_section = True
                        continue

                    # Check if we're exiting teardown section (next if statement)
                    if in_teardown_section and line.strip().startswith("if ["):
                        in_teardown_section = False
                        in_heredoc = False

                    # Track heredoc blocks
                    if "<<EOF" in line:
                        in_heredoc = True
                        continue
                    if in_heredoc and line.strip() == "EOF":
                        in_heredoc = False
                        continue

                    # Skip comments
                    if line.strip().startswith("#"):
                        continue

                    # Skip lines in teardown SQL generation blocks
                    if in_teardown_section and in_heredoc:
                        continue

                    # Check for hardcoded ACCOUNTADMIN (except in documentation/help text)
                    if re.search(r"\bACCOUNTADMIN\b", line, re.IGNORECASE):
                        # Allow in case statements, conditionals, or documentation
                        if not any(pattern in line for pattern in ["case ", "if [", "==", "#", "echo", "'"]):
                            if script_file.name not in violations_by_file:
                                violations_by_file[script_file.name] = []
                            violations_by_file[script_file.name].append((line_num, "ACCOUNTADMIN", line.strip()))

                    # Check for hardcoded DTAGENT_ADMIN
                    if re.search(r"\bDTAGENT_ADMIN\b", line):
                        # Allow in case statements, conditionals, or documentation
                        if not any(pattern in line for pattern in ["case ", "if [", "==", "#", "echo", "'"]):
                            if script_file.name not in violations_by_file:
                                violations_by_file[script_file.name] = []
                            violations_by_file[script_file.name].append((line_num, "DTAGENT_ADMIN", line.strip()))

        if violations_by_file:
            error_msg = "Found hardcoded role references in shell scripts:\n\n"
            for file_name, violations in violations_by_file.items():
                error_msg += f"{file_name}:\n"
                for line_num, role, line in violations:
                    error_msg += f"  Line {line_num} ({role}): {line}\n"
                error_msg += "\n"
            error_msg += "Shell scripts should not contain hardcoded role names outside teardown blocks.\n"
            error_msg += "These are handled in SQL files during deployment.\n"

            pytest.fail(error_msg)


class TestAccountAdminRoleUsage:
    """Test suite for ACCOUNTADMIN role usage restrictions."""

    @pytest.fixture(scope="class")
    def build_sql_files(self):
        """Get built SQL files from package/build directory."""
        build_dir = Path(__file__).parent.parent.parent / "package" / "build"

        if not build_dir.exists():
            pytest.skip("package/build directory not found. This is expected in dev environment.")

        return {
            "init": build_dir / "00_init.sql",
            "admin": build_dir / "10_admin.sql",
            "setup": build_dir / "20_setup.sql",
            "plugins": list((build_dir / "30_plugins").glob("*.sql")) if (build_dir / "30_plugins").exists() else [],
            "config": build_dir / "40_config.sql",
            "agents": build_dir / "70_agents.sql",
            "upgrade": list((build_dir / "09_upgrade").glob("*.sql")) if (build_dir / "09_upgrade").exists() else [],
        }

    def check_accountadmin_usage(self, file_path: Path) -> list[tuple[int, str]]:
        """Check for ACCOUNTADMIN role usage in any form."""
        violations = []

        if not file_path.exists() or not file_path.is_file():
            return violations

        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                # Skip comments
                if line.strip().startswith("--") or line.strip().startswith("#"):
                    continue

                # Check for ACCOUNTADMIN usage (case-insensitive)
                if re.search(r"\bACCOUNTADMIN\b", line, re.IGNORECASE):
                    violations.append((line_num, line.strip()))

        return violations

    def test_accountadmin_only_in_init_and_upgrade(self, build_sql_files):
        """Test that ACCOUNTADMIN role is used only in init (00_init.sql) and upgrade scripts.
        This ensures proper privilege separation and security boundaries.
        """
        violations_by_file = {}

        # Check files that should NOT contain ACCOUNTADMIN
        restricted_files = {
            "admin": build_sql_files["admin"],
            "setup": build_sql_files["setup"],
            "plugins": build_sql_files["plugins"],
            "config": build_sql_files["config"],
            "agents": build_sql_files["agents"],
        }

        for scope, file_path_list in restricted_files.items():
            for file_path in file_path_list if isinstance(file_path_list, list) else [file_path_list]:
                if file_path.exists():
                    violations = self.check_accountadmin_usage(file_path)
                    if violations:
                        violations_by_file[f"{scope} ({file_path})"] = violations

        if violations_by_file:
            error_msg = "Found ACCOUNTADMIN usage in non-init/upgrade files:\n\n"
            for file_path, violations in violations_by_file.items():
                error_msg += f"{file_path}:\n"
                for line_num, line in violations:
                    error_msg += f"  Line {line_num}: {line}\n"
                error_msg += "\n"
            error_msg += "\nACCOUNTADMIN should only be used in:\n"
            error_msg += "  - 00_init.sql (initialization)\n"
            error_msg += "  - 09_upgrade/*.sql (upgrade scripts)\n"

            pytest.fail(error_msg)

    def test_accountadmin_exists_in_init(self, build_sql_files):
        """Test that ACCOUNTADMIN is actually used in init script.
        This verifies that initial setup uses proper admin privileges.
        """
        init_file = build_sql_files["init"]

        if not init_file.exists():
            pytest.skip("00_init.sql not found in package/build")

        violations = self.check_accountadmin_usage(init_file)

        assert len(violations) > 0, (
            "00_init.sql should contain ACCOUNTADMIN usage for initial setup. " "If this is intentional, update the test."
        )

    def test_accountadmin_in_source_files(self):
        """Test that ACCOUNTADMIN in source files is only in init and upgrade directories."""
        src_dir = Path(__file__).parent.parent.parent / "src"
        violations_by_file = {}

        # Find all SQL files in src
        for sql_file in src_dir.rglob("*.sql"):
            if should_skip_sql_file(sql_file):
                continue
            violations = self.check_accountadmin_usage(sql_file)
            if violations:
                violations_by_file[str(sql_file.relative_to(src_dir))] = violations

        if violations_by_file:
            error_msg = "Found ACCOUNTADMIN usage in source files outside init/upgrade:\n\n"
            for file_path, violations in violations_by_file.items():
                error_msg += f"{file_path}:\n"
                for line_num, line in violations:
                    error_msg += f"  Line {line_num}: {line}\n"
                error_msg += "\n"
            error_msg += "\nACCOUNTADMIN should only be used in:\n"
            error_msg += "  - src/**/init/*.sql (initialization scripts)\n"
            error_msg += "  - src/**/upgrade/*.sql (upgrade scripts)\n"

            pytest.fail(error_msg)
