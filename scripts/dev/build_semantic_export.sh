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
# Calls semantic_exporter/__init__.py, validates output, and reports summary.
#
# Usage:
#   ./scripts/dev/build_semantic_export.sh [--output-dir <dir>] [--clean] [--verbose]
#                                          [--schema <path>] [--generate-docs] [--sd-repo <dir>]
#                                          [--no-display-name] [--check]
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
#                       Only used when --generate-docs or --check is passed.
#                       Default: .context/semantic-dictionary relative to the project root.
#   --no-display-name   Suppress the display_name property on all emitted attribute and
#                       enum member nodes. Passed through to semantic_exporter/__init__.py.
#   --check             After export into the SD repo, run the SD generator's sanity checks
#                       (F001–F043, incl. F025 "unused domain-specific groups") against the
#                       SD repo source/ and doc/, scoped via --files-to-check to only the
#                       DSOA-owned source files (so the thousands of pre-existing findings
#                       from other vendor namespaces are excluded). Implies the same
#                       SD-metadata export as --generate-docs. Requires Docker and a full SD
#                       repo checkout. Use --sd-repo to point to a different location.
#                       --check is read-only with respect to doc/: the SD-metadata export it
#                       runs internally writes blank doc/ stubs (required for the sanity
#                       checker to have something to validate), but the SD repo's doc/ tree
#                       is snapshotted beforehand and restored to its prior state afterward —
#                       so running --check after --generate-docs never discards previously
#                       rendered documentation content.
#   --help              Show this help message

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
EXPORT_SCRIPT="${PROJECT_ROOT}/src/build/semantic_exporter/__init__.py"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
OUTPUT_DIR="${PROJECT_ROOT}/build/_semdict/source"
SCHEMA_PATH="${PROJECT_ROOT}/scripts/tools/semconv.schema.json"
SD_REPO="${PROJECT_ROOT}/.context/semantic-dictionary"
CUSTOM_OUTPUT_DIR=false
FORCE_CLEAN=false
GENERATE_DOCS=false
RUN_CHECKS=false
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
        --no-display-name)
            EXTRA_ARGS+=("--no-display-name")
            shift
            ;;
        --check)
            RUN_CHECKS=true
            shift
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
    pushd "${PROJECT_ROOT}" > /dev/null
    if ! PYTHONPATH="${PROJECT_ROOT}/src" "${VENV_PYTHON}" "${EXPORT_SCRIPT}" \
        --output "${SD_REPO}/source" \
        --schema "${SCHEMA_PATH}" \
        --sd-metadata \
        "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"; then
        popd > /dev/null
        log_error "--generate-docs: export into SD repo failed"
        return 1
    fi
    popd > /dev/null

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
    pushd "${SD_REPO}" > /dev/null
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
    popd > /dev/null

    log_success "--generate-docs: SD repo at ${SD_REPO} is ready."
    log_info "  doc/model/snowflake/ and doc/fields/ stubs generated — commit to SD PR #1903"
    return 0
}

# ---------------------------------------------------------------------------
# Sanity checks: export into SD repo, run the generator's sanity-check mode
# and report findings (F001–F035, incl. F025 unused domain-specific groups).
# ---------------------------------------------------------------------------
run_sanity_checks() {
    log_info "--check: validating SD repo at ${SD_REPO}"
    if [[ ! -d "${SD_REPO}/generator" ]]; then
        log_error "--check requires a full SD repo checkout with generator/ at: ${SD_REPO}"
        log_error "Clone the semantic-dictionary repo there or pass --sd-repo <path>."
        return 1
    fi
    if ! command -v docker &>/dev/null; then
        log_error "--check requires Docker to be available on PATH"
        return 1
    fi

    # --check is a read-only diagnostic: it must never leave the SD repo's doc/ tree in a
    # worse state than it found it. Step 1 below re-runs semantic_exporter/__init__.py --sd-metadata,
    # which writes blank doc/ stubs (bare <!-- semconv id --><!-- end_semconv --> markers) —
    # this is required so the sanity checker has something to validate, but it silently wipes
    # out any previously-rendered content (attribute tables, DQL examples) written by a prior
    # --generate-docs run. Snapshot doc/ now and restore it unconditionally on return (whether
    # --check succeeds, fails, or exits early) so callers never have to notice this happened.
    local doc_backup
    doc_backup="$(mktemp -d)/doc"
    if [[ -d "${SD_REPO}/doc" ]]; then
        cp -R "${SD_REPO}/doc" "${doc_backup}"
    fi
    # Use an inline trap command (not a named function called via trap) so the RETURN
    # trap runs in the same call frame and reliably sees this function's local variables
    # under `set -u` — a separately-defined function invoked via `trap fn RETURN` executes
    # in its own frame and can hit "unbound variable" on locals declared in the caller.
    # The trap body clears itself (`trap - RETURN`) as its last action — a RETURN trap is
    # NOT auto-unregistered after firing once; left in place it re-fires on every
    # subsequent function return for the rest of the script (hitting the same
    # "unbound variable" error once doc_backup is out of scope) unless explicitly cleared.
    trap 'if [[ -d "${doc_backup}" ]]; then rm -rf "${SD_REPO}/doc"; cp -R "${doc_backup}" "${SD_REPO}/doc"; rm -rf "$(dirname "${doc_backup}")"; fi; trap - RETURN' RETURN

    # Step 1: export YAML + SD metadata (OWNERS, definitions, doc stubs) into the SD repo.
    # The sanity checks compare source/ YAML against doc/ Markdown, so the metadata and
    # doc stubs must be present — this mirrors the --generate-docs export step. (doc/ is
    # restored to its pre-check state on return; see comment above.)
    log_info "--check: exporting YAML + SD metadata into SD repo at ${SD_REPO}"
    pushd "${PROJECT_ROOT}" > /dev/null
    if ! PYTHONPATH="${PROJECT_ROOT}/src" "${VENV_PYTHON}" "${EXPORT_SCRIPT}" \
        --output "${SD_REPO}/source" \
        --schema "${SCHEMA_PATH}" \
        --sd-metadata \
        "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"; then
        popd > /dev/null
        log_error "--check: export into SD repo failed"
        return 1
    fi
    popd > /dev/null


    # Step 2: resolve generator image version and SD version from SD repo metadata
    local generator_version sd_version
    generator_version=$(grep "^version=" "${SD_REPO}/generator/generator-version.properties" | cut -d= -f2)
    sd_version=$(grep "^version=" "${SD_REPO}/version.properties" | cut -d= -f2)
    if [[ -z "${generator_version}" || -z "${sd_version}" ]]; then
        log_error "--check: could not read generator/SD version from ${SD_REPO}"
        return 1
    fi
    local generator_image="registry.lab.dynatrace.org/deus/otel-build-tool:${generator_version}"
    log_info "--check: SD version=${sd_version}  generator image=${generator_image}"

    # Step 3: pull the generator image
    log_info "--check: pulling generator image ${generator_image}"
    if ! docker pull "${generator_image}"; then
        log_error "--check: docker pull failed for ${generator_image}"
        return 1
    fi

    # Step 4: locate the required inputs for sanity-check mode.
    # OWNERS and the global field categories file are written by the --sd-metadata export.
    local owners_rel="OWNERS"
    local categories_rel="definitions/mapping/global_field_categories.json"
    if [[ ! -f "${SD_REPO}/${owners_rel}" ]]; then
        log_error "--check: missing ${owners_rel} in SD repo (expected from --sd-metadata export)"
        return 1
    fi
    if [[ ! -f "${SD_REPO}/${categories_rel}" ]]; then
        log_error "--check: missing ${categories_rel} in SD repo (expected from --sd-metadata export)"
        return 1
    fi

    # Step 5: collect the DSOA-owned source files so the sanity checks only report on the
    # files this export produces — not the thousands of pre-existing findings across every
    # other vendor namespace in the SD repo. The generator's --files-to-check expects the
    # container-internal /source/... paths (the SD repo source/ is mounted at /source).
    # The globs mirror SD_OWNED_GROUP_PREFIXES in semantic_exporter/field_emitters.py.
    local dsoa_files=()
    local f
    while IFS= read -r f; do
        dsoa_files+=("/${f}")
    done < <(cd "${SD_REPO}" && find source \( \
            -path "source/fields/signal_fields/snowflake.yaml" \
            -o -path "source/fields/signal_fields/anomaly.yaml" \
            -o -path "source/fields/signal_fields/dsoa*.yaml" \
            -o -path "source/fields/signal_fields/observed_timestamp.yaml" \
            -o -path "source/fields/resource_fields/dsoa.yaml" \
            -o -path "source/fields/resource_fields/snowflake_resource.yaml" \
            -o -path "source/model/snowflake/*.yaml" \
            -o -path "source/model/snowflake/logs/*.yaml" \
            -o -path "source/model/snowflake/spans/*.yaml" \
            -o -path "source/model/snowflake/events/*.yaml" \
            -o -path "source/model/snowflake/**/*.yaml" \
            -o -path "source/metrics/snowflake_*.yaml" \
            -o -path "source/metrics/interfaces_dsoa.yaml" \
            -o -path "source/metrics/interfaces_snowflake.yaml" \
            -o -path "source/fields/signal_fields/authentication.yaml" \
            -o -path "source/fields/signal_fields/client.yaml" \
            -o -path "source/fields/signal_fields/db.yaml" \
            -o -path "source/fields/signal_fields/event.yaml" \
        \) -name "*.yaml" | sort)

    if [[ "${#dsoa_files[@]}" -eq 0 ]]; then
        log_error "--check: no DSOA source files found under ${SD_REPO}/source — did the export run?"
        return 1
    fi
    log_info "--check: scoping sanity checks to ${#dsoa_files[@]} DSOA-owned source file(s)"

    # Step 6: run the generator in sanity_check mode (non-interactive), scoped to DSOA files.
    # --md-check makes it report status without rewriting Markdown files.
    # The generator exits 0 even when it reports findings (it is a report, not a gate),
    # so parse the "Total: N issues found" line to decide the return code.
    log_info "--check: running SD generator sanity checks (F001–F043), DSOA-scoped"
    local check_output check_rc=0
    check_output=$(docker run --rm \
        -v "${SD_REPO}/source:/source" \
        -v "${SD_REPO}/doc:/doc" \
        -v "${SD_REPO}/${owners_rel}:/owners/OWNERS:ro" \
        -v "${SD_REPO}/${categories_rel}:/categories/global_field_categories.json:ro" \
        "${generator_image}" \
        --version "${sd_version}" \
        --missing-property-mode warning \
        --yaml-root /source \
        sanity_check \
        --markdown-root /doc \
        --md-check \
        --owners-file-path /owners/OWNERS \
        --global-field-categories-path /categories/global_field_categories.json \
        --files-to-check "${dsoa_files[@]}" 2>&1) || check_rc=$?

    echo "${check_output}"

    if [[ "${check_rc}" -ne 0 ]]; then
        log_error "--check: SD generator sanity-check run failed (exit code ${check_rc})."
        return "${check_rc}"
    fi

    # Parse the reported total (findings are now DSOA-scoped, so any total > 0 is ours).
    local total_issues
    total_issues=$(echo "${check_output}" | grep -oE "Total: [0-9]+ issues found" | grep -oE "[0-9]+" | tail -1)
    total_issues="${total_issues:-0}"

    if [[ "${total_issues}" -gt 0 ]]; then
        log_warn "--check: ${total_issues} DSOA-scoped sanity finding(s) — see the summary above."
        log_warn "  Note: some findings (e.g. F027/F030 OWNERS coverage) may be pre-existing"
        log_warn "  SD-repo issues that also touch DSOA files. Review each before acting."
        return 1
    fi

    log_success "--check: no DSOA-scoped sanity findings — all DSOA groups are documented."
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
    log_info "Running semantic_exporter/__init__.py..."
    pushd "${PROJECT_ROOT}" > /dev/null
    if ! PYTHONPATH="${PROJECT_ROOT}/src" "${VENV_PYTHON}" "${EXPORT_SCRIPT}" \
        --output "${OUTPUT_DIR}" \
        --schema "${SCHEMA_PATH}" \
        "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"; then
        popd > /dev/null
        log_error "Export script failed"
        return 1
    fi
    popd > /dev/null

    log_success "Semantic dictionary export complete"
    log_info "Output: ${OUTPUT_DIR}"

    # Optional doc generation step
    if [[ "${GENERATE_DOCS}" == "true" ]]; then
        if ! generate_docs; then
            return 1
        fi
    fi

    # Optional sanity-check step
    if [[ "${RUN_CHECKS}" == "true" ]]; then
        if ! run_sanity_checks; then
            return 1
        fi
    fi

    return 0
}

main "$@"

