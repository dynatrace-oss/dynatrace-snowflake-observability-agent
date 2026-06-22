#!/usr/bin/env bash
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
# Orchestrates semantic dictionary YAML export for DSOA.
# Calls export_semantics.py, validates output, and reports summary.
#
# Usage:
#   ./scripts/dev/build_semantic_export.sh [--output-dir <dir>] [--clean] [--verbose]
#
# Options:
#   --output-dir <dir>  Output directory (default: build/_semdict/source).
#                       When a custom directory is supplied the output directory is
#                       NOT wiped before export — only DSOA-owned files are overwritten.
#                       Use --clean to force a wipe even for custom dirs.
#   --clean             Force-clean the output directory before export, even when
#                       --output-dir points to an external location (e.g. SD repo).
#                       Always enabled for the default build/_semdict/source location.
#   --verbose           Enable verbose (DEBUG) logging
#   --help              Show this help message

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
EXPORT_SCRIPT="${PROJECT_ROOT}/src/build/export_semantics.py"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
OUTPUT_DIR="${PROJECT_ROOT}/build/_semdict/source"
SCHEMA_PATH="${PROJECT_ROOT}/_otel-build-tool/semantic-conventions/semconv.schema.json"
CUSTOM_OUTPUT_DIR=false
FORCE_CLEAN=false
EXTRA_ARGS=()

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log_info()    { echo "[INFO] $*" >&2; }
log_warn()    { echo "[WARN] $*" >&2; }
log_error()   { echo "[ERROR] $*" >&2; }
log_success() { echo "[✓] $*" >&2; }

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="$2"
            CUSTOM_OUTPUT_DIR=true
            shift 2
            ;;
        --clean)
            FORCE_CLEAN=true
            shift
            ;;
        --verbose)
            EXTRA_ARGS+=("--verbose")
            shift
            ;;
        --help|-h)
            grep "^#" "${BASH_SOURCE[0]}" | grep -v "^#!" | sed 's/^# *//' | head -25
            exit 0
            ;;
        *)
            log_error "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
main() {
    log_info "Starting semantic dictionary export..."

    if [[ ! -f "${VENV_PYTHON}" ]]; then
        log_error "Python venv not found at ${VENV_PYTHON}"
        log_error "Run: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
        return 1
    fi

    if [[ ! -f "${EXPORT_SCRIPT}" ]]; then
        log_error "Export script not found at ${EXPORT_SCRIPT}"
        return 1
    fi

    # Clean output directory only when safe:
    #   - Always clean the default build/_semdict/source (never a shared working tree).
    #   - Never clean a custom --output-dir (e.g. SD repo) unless --clean is explicitly passed,
    #     to avoid wiping non-DSOA files in an external repository.
    if [[ "${CUSTOM_OUTPUT_DIR}" == "false" ]] || [[ "${FORCE_CLEAN}" == "true" ]]; then
        log_info "Cleaning output directory: ${OUTPUT_DIR}"
        rm -rf "${OUTPUT_DIR}"
    fi
    mkdir -p "${OUTPUT_DIR}"

    # Run export
    log_info "Running export_semantics.py..."
    cd "${PROJECT_ROOT}"
    if ! PYTHONPATH="${PROJECT_ROOT}/src" "${VENV_PYTHON}" "${EXPORT_SCRIPT}" \
        --output "${OUTPUT_DIR}" \
        --schema "${SCHEMA_PATH}" \
        "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"; then
        log_error "Export script failed"
        return 1
    fi

    log_success "Semantic dictionary export complete"
    log_info "Output: ${OUTPUT_DIR}"
    return 0
}

main "$@"
