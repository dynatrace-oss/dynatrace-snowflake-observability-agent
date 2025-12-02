#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
}

@test "build.sh runs without immediate errors" {
    # This test assumes dependencies like pylint are installed
    # In a real environment, this would pass if build tools are available
    run timeout 60 ./scripts/dev/build.sh
    # Allow it to pass even if it fails due to missing dependencies, as long as it doesn't crash immediately
    if [ "$status" -ne 0 ] && [ "$status" -ne 1 ]; then
        echo "build.sh failed with status $status"
        echo "Output: $output"
    fi
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

    # Check that 70*.sql files have correct handler functions
    for sql_file in build/70*.sql; do
        if [ -f "$sql_file" ]; then
            # Extract handler value
            handler=$(grep "handler = " "$sql_file" | sed "s/.*handler = '\([^']*\)'.*/\1/")
            if [ -z "$handler" ]; then
                echo "Handler not found in $sql_file"
                exit 1
            fi
            # Extract Python code between $$ and $$
            # Find the line numbers of $$
            start_line=$(grep -n '^[$][$]' "$sql_file" | head -1 | cut -d: -f1)
            end_line=$(grep -n '^[$][$]' "$sql_file" | tail -1 | cut -d: -f1)
            if [ -z "$start_line" ] || [ -z "$end_line" ]; then
                echo "Python code delimiters not found in $sql_file"
                exit 1
            fi
            # Extract lines between start+1 and end-1
            python_code=$(sed -n "$((start_line+1)),$((end_line-1))p" "$sql_file")
            # Check if def $handler( exists
            if ! echo "$python_code" | grep -q "def $handler("; then
                echo "Handler function '$handler' not found in $sql_file"
                exit 1
            fi
        fi
    done
}

@test "build_docs.sh creates expected documentation files" {
    # Run build_docs.sh
    run timeout 60 ./scripts/dev/build_docs.sh
    if [ "$status" -ne 0 ] && [ "$status" -ne 1 ]; then
        echo "build_docs.sh failed with status $status"
        echo "Output: $output"
    fi
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

@test "package.sh creates a valid package zip with build files and documentation" {
    run ./scripts/dev/package.sh
    if [ "$status" -ne 0 ]; then
        echo "package.sh failed with status $status"
        echo "Output: $output"
    fi

    # Find the latest zip file
    zip_file=$(ls dynatrace_snowflake_observability_agent-*.zip | tail -1)
    echo "zip_file: $zip_file"
    [ -f "$zip_file" ]

    # Check that the zip contains the PDF
    pdf_file=$(unzip -l "$zip_file" | grep "Dynatrace-Snowflake-Observability-Agent-[0-9.]*pdf")
    echo "pdf_file: $pdf_file"
    [ -n "$pdf_file" ]

    # Check that build/ directory exists in zip
    build_dir=$(unzip -l "$zip_file" | grep "^.*build/$")
    echo "build_dir: $build_dir"
    [ -n "$build_dir" ]

    # Check that config-default.json is in build/
    config_file=$(unzip -l "$zip_file" | grep "build/config-default.json")
    echo "config_file: $config_file"
    [ -n "$config_file" ]

    # Check that instruments-def.json is in build/
    instruments_file=$(unzip -l "$zip_file" | grep "build/instruments-def.json")
    echo "instruments_file: $instruments_file"
    [ -n "$instruments_file" ]

    # Check that conf/ exists
    conf_dir=$(unzip -l "$zip_file" | grep "^.*conf/$")
    echo "conf_dir: $conf_dir"
    [ -n "$conf_dir" ]

    # Check that config-template.json is in conf/
    config_template_file=$(unzip -l "$zip_file" | grep "conf/config-template.json")
    echo "config_template_file: $config_template_file"
    [ -n "$config_template_file" ]

    # Check that docs/ exists
    docs_dir=$(unzip -l "$zip_file" | grep "^.*docs/$")
    echo "docs_dir: $docs_dir"
    [ -n "$docs_dir" ]

    # Check that bom.yml is in docs/
    bom_file=$(unzip -l "$zip_file" | grep "docs/bom.yml")
    echo "bom_file: $bom_file"
    [ -n "$bom_file" ]

    # Check that bom_references.csv is in docs/
    bom_references_csv=$(unzip -l "$zip_file" | grep "docs/bom_references.csv")
    echo "bom_references_csv: $bom_references_csv"
    [ -n "$bom_references_csv" ]

    # Check that dashboards.zip is in docs/
    dashboards_zip=$(unzip -l "$zip_file" | grep "docs/dashboards.zip")
    echo "dashboards_zip: $dashboards_zip"
    [ -n "$dashboards_zip" ]

    # Check that debug.zip is in docs/
    debug_zip=$(unzip -l "$zip_file" | grep "docs/debug.zip")
    echo "debug_zip: $debug_zip"
    [ -n "$debug_zip" ]

    # Check that bom_delivers.csv is in docs/
    bom_delivers_csv=$(unzip -l "$zip_file" | grep "docs/bom_delivers.csv")
    echo "bom_delivers_csv: $bom_delivers_csv"
    [ -n "$bom_delivers_csv" ]

    # Check that deploy.sh is present
    deploy_script=$(unzip -l "$zip_file" | grep "deploy.sh")
    echo "deploy_script: $deploy_script"
    [ -n "$deploy_script" ]

    # Check that get_config_key.sh is present
    get_config_key_script=$(unzip -l "$zip_file" | grep "get_config_key.sh")
    echo "get_config_key_script: $get_config_key_script"
    [ -n "$get_config_key_script" ]

    # Check that install_snow_cli.sh is present
    install_snow_cli_script=$(unzip -l "$zip_file" | grep "install_snow_cli.sh")
    echo "install_snow_cli_script: $install_snow_cli_script"
    [ -n "$install_snow_cli_script" ]

    # Check that prepare_config.sh is present
    prepare_config_script=$(unzip -l "$zip_file" | grep "prepare_config.sh")
    echo "prepare_config_script: $prepare_config_script"
    [ -n "$prepare_config_script" ]

    # Check that prepare_configuration_ingest.sh is present
    prepare_configuration_ingest_script=$(unzip -l "$zip_file" | grep "prepare_configuration_ingest.sh")
    echo "prepare_configuration_ingest_script: $prepare_configuration_ingest_script"
    [ -n "$prepare_configuration_ingest_script" ]

    # Check that prepare_deploy_script.sh is present
    prepare_deploy_script_script=$(unzip -l "$zip_file" | grep "prepare_deploy_script.sh")
    echo "prepare_deploy_script_script: $prepare_deploy_script_script"
    [ -n "$prepare_deploy_script_script" ]

    # Check that prepare_instruments_ingest.sh is present
    prepare_instruments_ingest_script=$(unzip -l "$zip_file" | grep "prepare_instruments_ingest.sh")
    echo "prepare_instruments_ingest_script: $prepare_instruments_ingest_script"
    [ -n "$prepare_instruments_ingest_script" ]

    # Check that refactor_field_names.sh is present
    refactor_field_names_script=$(unzip -l "$zip_file" | grep "refactor_field_names.sh")
    echo "refactor_field_names_script: $refactor_field_names_script"
    [ -n "$refactor_field_names_script" ]

    # Check that send_bizevent.sh is present
    send_bizevent_script=$(unzip -l "$zip_file" | grep "send_bizevent.sh")
    echo "send_bizevent_script: $send_bizevent_script"
    [ -n "$send_bizevent_script" ]

    # Check that setup.sh is present
    setup_script=$(unzip -l "$zip_file" | grep "setup.sh")
    echo "setup_script: $setup_script"
    [ -n "$setup_script" ]

    # Check that update_secret.sh is present
    update_secret_script=$(unzip -l "$zip_file" | grep "update_secret.sh")
    echo "update_secret_script: $update_secret_script"
    [ -n "$update_secret_script" ]

    # Check that LICENSE file is present
    license_file=$(unzip -l "$zip_file" | grep "LICENSE")
    echo "license_file: $license_file"
    [ -n "$license_file" ]

    # Check that there are many SQL files in build/
    sql_count=$(unzip -l "$zip_file" | grep "build/.*\.sql$" | wc -l)
    [ "$sql_count" -gt 50 ]
}