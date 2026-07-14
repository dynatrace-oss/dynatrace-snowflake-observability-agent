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
#                                          [--schema <path>] [--generate-docs] [--sd-repo <dir>]
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
#   --schema <path>     Path to semconv.schema.json (default: scripts/tools/semconv.schema.json).
#                       Accepts absolute paths or paths relative to the repository root.
#   --generate-docs     After YAML export, write SD metadata (OWNERS, definitions, doc/
#                       model and field stubs) into the SD repo and run the SD generator
#                       (--md-only) to fill the stubs with rendered attribute tables and
#                       DQL examples. Results stay in the SD repo checkout ready to commit
#                       to PR #1903 — nothing is copied back to docs/semantic-dictionary/.
#                       Requires Docker and the full SD repo checkout at .context/semantic-dictionary/.
#                       Use --sd-repo to point to a different SD repo location.
#   --sd-repo <dir>     Path to the full SD repo checkout containing generator/generate.sh.
#                       Only used when --generate-docs is passed.
#                       Default: .context/semantic-dictionary relative to the project root.
#   --help              Show this help message

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
EXPORT_SCRIPT="${PROJECT_ROOT}/src/build/export_semantics.py"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
OUTPUT_DIR="${PROJECT_ROOT}/build/_semdict/source"
SCHEMA_PATH="${PROJECT_ROOT}/scripts/tools/semconv.schema.json"
SD_REPO="${PROJECT_ROOT}/.context/semantic-dictionary"
CUSTOM_OUTPUT_DIR=false
FORCE_CLEAN=false
GENERATE_DOCS=false
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
        --schema)
            if [[ "$2" == /* ]]; then
                SCHEMA_PATH="$2"
            else
                SCHEMA_PATH="${PROJECT_ROOT}/$2"
            fi
            shift 2
            ;;
        --generate-docs)
            GENERATE_DOCS=true
            shift
            ;;
        --sd-repo)
            if [[ "$2" == /* ]]; then
                SD_REPO="$2"
            else
                SD_REPO="${PROJECT_ROOT}/$2"
            fi
            shift 2
            ;;
        --help|-h)
            grep "^#" "${BASH_SOURCE[0]}" | grep -v "^#!" | sed 's/^# *//' | head -35
            exit 0
            ;;
        *)
            log_error "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Doc generation: export into SD repo, run generator, copy doc/ output back
# ---------------------------------------------------------------------------
generate_docs() {
    log_info "--generate-docs: validating SD repo at ${SD_REPO}"
    if [[ ! -d "${SD_REPO}/generator" ]]; then
        log_error "--generate-docs requires a full SD repo checkout with generator/ at: ${SD_REPO}"
        log_error "Clone the semantic-dictionary repo there or pass --sd-repo <path>."
        return 1
    fi
    if ! command -v docker &>/dev/null; then
        log_error "--generate-docs requires Docker to be available on PATH"
        return 1
    fi

    # Step 1: export YAML + SD metadata (OWNERS, definitions, doc stubs) into the SD repo
    log_info "--generate-docs: exporting YAML + SD metadata into SD repo at ${SD_REPO}"
    cd "${PROJECT_ROOT}"
    if ! PYTHONPATH="${PROJECT_ROOT}/src" "${VENV_PYTHON}" "${EXPORT_SCRIPT}" \
        --output "${SD_REPO}/source" \
        --schema "${SCHEMA_PATH}" \
        --sd-metadata \
        "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"; then
        log_error "--generate-docs: export into SD repo failed"
        return 1
    fi

    # Step 2: resolve generator image version and SD version from SD repo metadata
    local generator_version sd_version
    generator_version=$(grep "^version=" "${SD_REPO}/generator/generator-version.properties" | cut -d= -f2)
    sd_version=$(grep "^version=" "${SD_REPO}/version.properties" | cut -d= -f2)
    if [[ -z "${generator_version}" || -z "${sd_version}" ]]; then
        log_error "--generate-docs: could not read generator/SD version from ${SD_REPO}"
        return 1
    fi
    local generator_image="registry.lab.dynatrace.org/deus/otel-build-tool:${generator_version}"
    log_info "--generate-docs: SD version=${sd_version}  generator image=${generator_image}"

    # Step 3: pull the generator image
    log_info "--generate-docs: pulling generator image ${generator_image}"
    if ! docker pull "${generator_image}"; then
        log_error "--generate-docs: docker pull failed for ${generator_image}"
        return 1
    fi

    # Step 4: run the generator in --md-only mode (non-interactive; avoids -it tty requirement)
    log_info "--generate-docs: running SD generator markdown mode (non-interactive)"
    if ! docker run --rm \
        -v "${SD_REPO}/source:/source" \
        -v "${SD_REPO}/doc:/doc" \
        "${generator_image}" \
        --version "${sd_version}" \
        --missing-property-mode warning \
        --yaml-root /source \
        markdown \
        --markdown-root /doc; then
        log_error "--generate-docs: SD generator container failed"
        return 1
    fi

    # Step 5: restore non-DSOA doc files that the generator may have touched.
    # The SD generator regenerates ALL doc/ Markdown files, not just DSOA-owned ones.
    # We must restore everything outside DSOA ownership to avoid polluting the PR.
    # DSOA-owned doc paths:
    #   doc/model/snowflake/**       — per-plugin model stubs
    #   doc/fields/snowflake_*.md   — Snowflake signal field groups
    #   doc/fields/anomaly.md       — anomaly signal fields
    #   doc/fields/dsoa_*.md        — DSOA-specific field groups
    #   doc/fields/observed_timestamp.md
    log_info "--generate-docs: restoring non-DSOA doc files touched by the generator"
    cd "${SD_REPO}"
    # Collect all doc/ changes, then revert anything that isn't DSOA-owned
    git diff HEAD --name-only -- doc/ | while IFS= read -r f; do
        # Keep DSOA-owned paths; revert everything else
        if [[ "${f}" == doc/model/snowflake/* ]] || \
           [[ "${f}" == doc/fields/snowflake_*.md ]] || \
           [[ "${f}" == doc/fields/anomaly.md ]] || \
           [[ "${f}" == doc/fields/dsoa_*.md ]] || \
           [[ "${f}" == doc/fields/observed_timestamp.md ]]; then
            : # keep
        else
            git checkout HEAD -- "${f}" 2>/dev/null || true
        fi
    done
    cd "${PROJECT_ROOT}"

    log_success "--generate-docs: SD repo at ${SD_REPO} is ready."
    log_info "  doc/model/snowflake/ and doc/fields/ stubs generated — commit to SD PR #1903"
    return 0
}

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

    # Optional doc generation step
    if [[ "${GENERATE_DOCS}" == "true" ]]; then
        if ! generate_docs; then
            return 1
        fi
    fi

    return 0
}

main "$@"

