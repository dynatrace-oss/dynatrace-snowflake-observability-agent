# Dependency Maintenance — Snowflake SDK Audit and Version Update

- **Scope**: Full audit of all four Snowflake SDK packages in `requirements.txt` against latest stable PyPI releases.
- **Findings**:
  - `snowflake==1.12.0` — already at latest stable; no change.
  - `snowflake-core==1.12.0` — already at latest stable; no change.
  - `snowflake-connector-python>=4.4.0` — already at latest stable; no change.
  - `snowflake-snowpark-python>=1.48.1` — **updated to `>=1.49.0`** (released 2026-04-13). No breaking API changes
    affecting DSOA usage patterns (`Session`, `DataFrame`, `write_pandas`, cursor operations).
- **Python version constraint**: Constraint remains `<3.14`. Initial analysis incorrectly attributed the upper bound
  to `snowflake-snowpark-python==1.49.0` (which declares `<3.15`), but the binding constraint is `snowflake==1.12.0`
  which declares `requires_python: <3.14,>=3.10`. `snowflake-core==1.12.0` has no Python upper bound. Python 3.14
  support will require a new `snowflake` package release from Snowflake. Comment corrected accordingly.
- **Protobuf constraint unchanged**: `snowflake-snowpark-python==1.49.0` still caps at `protobuf<6.34`, consistent
  with the existing `>=6.33.5,<6.34` security pin (CVE-2026-0994). Updated inline comment to reference `>=1.49.0`.
- **Compatibility verified**: `pip install -r requirements.txt` clean; `pip check` no broken deps; SDK import smoke
  test passed; 99 core tests passed (3 skipped); pylint 10.00/10.
- **Files changed**: `requirements.txt`
