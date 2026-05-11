# Bug Fixes: Dependency Security Upgrades — Dependabot CVE Remediation

- **Scope**: 7 open Dependabot alerts in `requirements.txt`, covering 5 packages.
- **Root cause for pyOpenSSL block**: `snowflake-connector-python<4.4.0` had an upper bound of `pyOpenSSL<26.0.0`,
  preventing the CVE fix. `snowflake-connector-python==4.4.0` (released 2026-03) removed that upper bound and itself
  bumped its minimum `cryptography` requirement to `>=46.0.5`.
- **Changes**:
  - `snowflake-connector-python>=4.4.0` (was `>=4.3.0`): lifts pyOpenSSL upper bound; resolves alerts #9 + #10.
  - `snowflake-snowpark-python>=1.48.1` (was `>=1.45.0`): picks up latest Snowpark SDK improvements.
  - `cryptography>=46.0.6` (was `>=46.0.5`): fixes SECT-curve subgroup attack (alert #3) and incomplete DNS
    name constraint enforcement (alert #13).
  - `requests>=2.33.0` (new pin): fixes insecure temp-file reuse in `extract_zipped_paths()` (alert #12).
  - `pyOpenSSL>=26.0.0` (new pin, replaces BLOCKED comment): fixes DTLS cookie callback buffer overflow (alert
    #10, HIGH) and TLS connection bypass via unhandled callback (alert #9, LOW).
  - `Pygments>=2.20.0` (new pin): fixes ReDoS via inefficient GUID-matching regex (alert #14, LOW). Pygments
    is a transitive dependency via `pytest` and `rich`.
  - Retained existing `urllib3>=2.6.3` and `wheel>=0.46.2` pins (no new alerts; still protective).
- **Protobuf alert #4**: advisory range is `>=6.30.0rc1,<=6.33.4` (6.x series only). Our pin `>=5.29.6,<6.0.0`
  means we are on the patched 5.x series and not affected. Alert can be dismissed as "not applicable" on GitHub.
- **Files changed**: `requirements.txt`
