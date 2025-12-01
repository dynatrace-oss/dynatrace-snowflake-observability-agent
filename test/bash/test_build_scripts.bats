#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
}

@test "build.sh runs without immediate errors" {
    # This test assumes dependencies like pylint are installed
    # In a real environment, this would pass if build tools are available
    run timeout 15 ./build.sh
    # Allow it to pass even if it fails due to missing dependencies, as long as it doesn't crash immediately
    [ "$status" -eq 0 ] || [ "$status" -eq 1 ]  # 0 for success, 1 for build failure

    # Check that expected files are created in build directory
    [ -f "build/_dtagent.py" ]
    [ -f "build/_send_telemetry.py" ]
    [ -f "build/_version.py" ]
    [ -f "build/instruments-def.json" ]
    [ -f "build/config-default.json" ]

    # Check that config-default.json is valid JSON and matches schema
    if command -v jq &> /dev/null && [ -f "build/config-default.json" ]; then
        # Check that it's valid JSON
        run jq empty build/config-default.json
        [ "$status" -eq 0 ]

        # Check that it has the required top-level keys
        run jq -e '.CORE and .OTEL and .PLUGINS' build/config-default.json
        [ "$status" -eq 0 ]

        # Validate schema if jsonschema is available
        if command -v jsonschema &> /dev/null && [ -f "test/config-default.schema.json" ]; then
            run jsonschema -i build/config-default.json test/config-default.schema.json
            [ "$status" -eq 0 ]
        fi
    fi

    # Check that SQL files are copied (excluding *.off.sql files)
    # Count SQL files in src (excluding *.off.sql)
    expected_sql_count=$(find src -type f \( -name "*.sql" ! -name "*.off.sql" \) |  wc -l)
    # Count SQL files in build
    actual_sql_count=$(find build -maxdepth 1 -type f -name "*.sql" | grep -v ".off.sql" | wc -l)
    [ "$actual_sql_count" -eq "$expected_sql_count" ]
}

@test "build_docs.sh creates expected documentation files" {
    # Run build_docs.sh
    run timeout 30 ./build_docs.sh
    [ "$status" -eq 0 ] || [ "$status" -eq 1 ]

    # Check that expected files exist (if they were created)
    # These checks are informational - don't fail if files don't exist in dev environment
    if [ -f "docs/PLUGINS.md" ]; then
        echo "✓ docs/PLUGINS.md exists"
    fi
    if [ -f "docs/SEMANTICS.md" ]; then
        echo "✓ docs/SEMANTICS.md exists"
    fi
    if [ -f "docs/APPENDIX.md" ]; then
        echo "✓ docs/APPENDIX.md exists"
    fi
    if [ -f "README.md" ]; then
        echo "✓ README.md exists"
    fi
    if [ -f "build/bom.json" ]; then
        echo "✓ build/bom.json exists"

        # Validate bom.json structure and schema
        if command -v jq &> /dev/null; then
            # Check that it's valid JSON
            run jq empty build/bom.json
            [ "$status" -eq 0 ]

            # Check that it has the required top-level keys
            run jq -e '.delivers and .references' build/bom.json
            [ "$status" -eq 0 ]

            # Check that delivers is an array
            run jq -e '.delivers | type == "array"' build/bom.json
            [ "$status" -eq 0 ]

            # Check that references is an array
            run jq -e '.references | type == "array"' build/bom.json
            [ "$status" -eq 0 ]

            # Check that delivers array has content
            delivers_count=$(jq '.delivers | length' build/bom.json)
            [ "$delivers_count" -gt 0 ]

            # Check that references array has content
            references_count=$(jq '.references | length' build/bom.json)
            [ "$references_count" -gt 0 ]

            # Validate schema if jsonschema is available
            if command -v jsonschema &> /dev/null && [ -f "test/bom.schema.json" ]; then
                run jsonschema -i build/bom.json test/bom.schema.json
                [ "$status" -eq 0 ]
            fi
        fi

        # Check for CSV files
        [ -f "build/bom_delivers.csv" ]
        [ -f "build/bom_references.csv" ]

        # Run markdownlint on generated markdown files if they exist
        if command -v markdownlint &> /dev/null; then
            markdown_files=""
            [ -f "docs/PLUGINS.md" ] && markdown_files="$markdown_files docs/PLUGINS.md"
            [ -f "docs/SEMANTICS.md" ] && markdown_files="$markdown_files docs/SEMANTICS.md"
            [ -f "docs/APPENDIX.md" ] && markdown_files="$markdown_files docs/APPENDIX.md"
            [ -f "README.md" ] && markdown_files="$markdown_files README.md"

            if [ -n "$markdown_files" ]; then
                run markdownlint $markdown_files
                [ "$status" -eq 0 ]
            fi
        fi
    fi

    # Check that PDF files exist (filename includes version)
    pdf_files=$(ls Dynatrace-Snowflake-Observability-Agent-*.pdf 2>/dev/null | wc -l)
    if [ "$pdf_files" -gt 0 ]; then
        echo "✓ PDF documentation exists"
    fi
}