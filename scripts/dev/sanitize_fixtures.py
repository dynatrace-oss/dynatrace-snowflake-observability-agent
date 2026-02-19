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
"""PII sanitization script for NDJSON fixture files and golden result files.

Applies deterministic find-and-replace of known PII values (real usernames,
IPs, tenant URLs, database names) with synthetic test values, using the
shared deny-list at ``test/test_data/_deny_patterns.json``.

Operates on plain text so changes are fully reviewable.

Usage::

    # Sanitize all fixture and golden result files (in-place)
    python scripts/dev/sanitize_fixtures.py

    # Preview changes without writing (dry run)
    python scripts/dev/sanitize_fixtures.py --dry-run

    # Report only — show which files would change, no replacements
    python scripts/dev/sanitize_fixtures.py --report
"""

import argparse
import json
import os
import re
import sys


DENY_PATTERNS_PATH = "test/test_data/_deny_patterns.json"

# Directories / glob patterns to sanitize
TARGET_DIRS = [
    "test/test_data",
    "test/test_results",
]

# File extensions to process (case-insensitive)
TARGET_EXTENSIONS = {".ndjson", ".json", ".txt"}


def load_deny_patterns(path: str) -> list:
    """Load PII patterns from the shared deny-list JSON file.

    Args:
        path: Path to the deny-list JSON file.

    Returns:
        List of compiled (pattern, replacement) tuples.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    compiled = []
    for entry in data["patterns"]:
        regex = re.compile(entry["pattern"])
        compiled.append((regex, entry["replacement"], entry["id"]))
    return compiled


def sanitize_text(text: str, patterns: list) -> tuple:
    """Apply all PII patterns to *text* and return (modified_text, change_count).

    Args:
        text: Input text to sanitize.
        patterns: List of (compiled_regex, replacement, pattern_id) tuples.

    Returns:
        Tuple of (sanitized_text, total_replacements_made).
    """
    total = 0
    for regex, replacement, _ in patterns:
        new_text, n = regex.subn(replacement, text)
        text = new_text
        total += n
    return text, total


def find_target_files(dirs: list) -> list:
    """Walk *dirs* and collect all files matching TARGET_EXTENSIONS.

    The deny-list file (``_deny_patterns.json``) is excluded from sanitization
    since it intentionally contains the PII patterns as regex strings.

    Args:
        dirs: List of directory paths to search.

    Returns:
        Sorted list of matching file paths.
    """
    # Resolve the absolute path of the deny-list so we can exclude it
    deny_list_abs = os.path.abspath(DENY_PATTERNS_PATH)

    found = []
    for root_dir in dirs:
        if not os.path.isdir(root_dir):
            continue
        for dirpath, _, filenames in os.walk(root_dir):
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in TARGET_EXTENSIONS:
                    continue
                full_path = os.path.join(dirpath, fname)
                if os.path.abspath(full_path) == deny_list_abs:
                    continue  # Never sanitize the deny-list itself
                found.append(full_path)
    return sorted(found)


def sanitize_files(
    target_files: list,
    patterns: list,
    dry_run: bool = False,
    report_only: bool = False,
) -> dict:
    """Sanitize all *target_files* using *patterns*.

    Args:
        target_files: List of file paths to process.
        patterns: Compiled PII patterns.
        dry_run: If True, compute changes but do not write.
        report_only: If True, only report which files have PII matches.

    Returns:
        Dict mapping file path to number of replacements made.
    """
    results = {}

    for fpath in target_files:
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                original = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"  [SKIP] {fpath}: {exc}")
            continue

        sanitized, total = sanitize_text(original, patterns)

        if total == 0:
            continue

        results[fpath] = total

        if report_only:
            print(f"  [HIT]  {fpath}: {total} replacement(s)")
        elif dry_run:
            print(f"  [DRY]  {fpath}: {total} replacement(s) would be made")
        else:
            with open(fpath, "w", encoding="utf-8") as fh:
                fh.write(sanitized)
            print(f"  [OK]   {fpath}: {total} replacement(s) applied")

    return results


def main():
    """Entry point for the sanitization script."""
    parser = argparse.ArgumentParser(description="Sanitize PII from NDJSON fixtures and golden result files.")
    parser.add_argument("--deny-patterns", default=DENY_PATTERNS_PATH, help="Path to _deny_patterns.json")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files")
    parser.add_argument("--report", action="store_true", help="Report matching files without showing replacements")
    args = parser.parse_args()

    if not os.path.exists(args.deny_patterns):
        print(f"ERROR: Deny-patterns file not found: {args.deny_patterns}")
        sys.exit(1)

    patterns = load_deny_patterns(args.deny_patterns)
    print(f"Loaded {len(patterns)} PII pattern(s) from {args.deny_patterns}")
    print()

    target_files = find_target_files(TARGET_DIRS)
    print(f"Found {len(target_files)} file(s) to scan in {TARGET_DIRS}")
    print()

    results = sanitize_files(target_files, patterns, dry_run=args.dry_run, report_only=args.report)

    if not results:
        print("No PII found in any file.")
    else:
        total_files = len(results)
        total_replacements = sum(results.values())
        mode = "would be made" if (args.dry_run or args.report) else "applied"
        print(f"\n{total_files} file(s) with {total_replacements} total replacement(s) {mode}.")

    if args.dry_run or args.report:
        sys.exit(0 if not results else 0)

    sys.exit(0)


if __name__ == "__main__":
    main()
