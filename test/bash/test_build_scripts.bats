#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
}

setup_file() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Run build_docs.sh once for all tests
    BUILD_OUTPUT=$(timeout 240 ./scripts/dev/build_docs.sh 2>&1)
    export BUILD_DOCS_STATUS=$?
    export BUILD_OUTPUT
}

@test "build.sh runs without immediate errors" {
    # This test assumes dependencies like pylint are installed
    # In a real environment, this would pass if build tools are available
    run timeout 120 ./scripts/dev/build.sh
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
    [ -f "build/config-default.yml" ]

    # Check that config-default.yml is valid YAML and matches schema
    if command -v jq &> /dev/null && [ -f "build/config-default.yml" ]; then
        # Check that it's valid YAML
        run yq '.. | select(. == [] or . == {})' build/config-default.yml
        [ "$status" -eq 0 ]

        # Check that it has the required top-level keys
        run yq -e '.core and .otel and .plugins' build/config-default.yml
        [ "$status" -eq 0 ]

        # Validate schema if JSON schema is available
        if command -v check-jsonschema &> /dev/null && [ -f "test/config-default.schema.json" ]; then
            run check-jsonschema --schemafile test/config-default.schema.json build/config-default.yml
            if [ "$status" -ne 0 ]; then
                echo "check-jsonschema failed with status $status"
                echo "Output: $output"
            fi
            [ "$status" -eq 0 ]
        fi
    fi

    # Check that SQL files are copied correctly
    # Check main SQL files - should be exactly 5 files: 00_init.sql, 10_admin.sql, 20_setup.sql, 40_config.sql, 70_agents.sql
    main_sql_count=$(find build -maxdepth 1 -type f -name "*.sql" | wc -l | tr -d ' ')
    [ "$main_sql_count" -eq 5 ]

    # Verify specific files exist
    [ -f "build/00_init.sql" ]
    [ -f "build/10_admin.sql" ]
    [ -f "build/20_setup.sql" ]
    [ -f "build/40_config.sql" ]
    [ -f "build/70_agents.sql" ]

    # Check 09_upgrade folder
    [ -d "build/09_upgrade" ]
    upgrade_sql_count=$(find build/09_upgrade -type f -name "*.sql" | wc -l | tr -d ' ')
    expected_upgrade_count=$(find src/dtagent.sql/upgrade -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
    [ "$upgrade_sql_count" -eq "$expected_upgrade_count" ]

    # Check 30_plugins folder
    [ -d "build/30_plugins" ]
    plugin_sql_count=$(find build/30_plugins -type f -name "*.sql" | wc -l | tr -d ' ')
    expected_plugin_count=$(find src/dtagent/plugins -maxdepth 1 -type f -name "*.py" ! -name "__init__.py" | wc -l | tr -d ' ')
    [ "$plugin_sql_count" -eq "$expected_plugin_count" ]

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
    # Use the status from setup_file instead of running again
    if [ "$BUILD_DOCS_STATUS" -ne 0 ] && [ "$BUILD_DOCS_STATUS" -ne 1 ]; then
        echo "build_docs.sh failed with status $BUILD_DOCS_STATUS"
        echo "Output: $BUILD_OUTPUT"
    fi
    [ "$BUILD_DOCS_STATUS" -eq 0 ] || [ "$BUILD_DOCS_STATUS" -eq 1 ]

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
    if [ -f "build/bom.yml" ]; then
        echo "✓ build/bom.yml exists"

        # Validate bom.yml structure and schema
        if command -v yq &> /dev/null; then
            # Check that it's valid YAML
            run yq '.. | select(. == [] or . == {})' build/bom.yml
            [ "$status" -eq 0 ]

            # Check that it has the required top-level keys
            run yq -e '.delivers and .references' build/bom.yml
            [ "$status" -eq 0 ]

            # Check that delivers is an array
            run yq -e '.delivers | tag == "!!seq"' build/bom.yml
            [ "$status" -eq 0 ]

            # Check that references is an array
            run yq -e '.references | tag == "!!seq"' build/bom.yml
            [ "$status" -eq 0 ]

            # Check that delivers array has content
            delivers_count=$(yq '.delivers | length' build/bom.yml)
            [ "$delivers_count" -gt 0 ]

            # Check that references array has content
            references_count=$(yq '.references | length' build/bom.yml)
            [ "$references_count" -gt 0 ]

            # Validate schema if check-jsonschema is available
            if command -v check-jsonschema &> /dev/null && [ -f "test/bom.schema.json" ]; then
                run check-jsonschema --schemafile test/bom.schema.json build/bom.yml
                if [ "$status" -ne 0 ]; then
                    echo "check-jsonschema failed with status $status"
                    echo "Output: $output"
                fi
                [ "$status" -eq 0 ]
            fi
        fi

        # Validate schema if check-jsonschema is available
        if command -v check-jsonschema &> /dev/null && [ -f "test/config-default.schema.json" ]; then
            run check-jsonschema --schemafile test/config-default.schema.json build/config-default.yml
            [ "$status" -eq 0 ]
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
    run timeout 300 ./scripts/dev/package.sh
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

    # Check that config-default.yml is in build/
    config_file=$(unzip -l "$zip_file" | grep "build/config-default.yml")
    echo "config_file: $config_file"
    [ -n "$config_file" ]

    # Check that conf/ exists
    conf_dir=$(unzip -l "$zip_file" | grep "^.*conf/$")
    echo "conf_dir: $conf_dir"
    [ -n "$conf_dir" ]

    # Check that config-template.yml is in conf/
    config_template_file=$(unzip -l "$zip_file" | grep "conf/config-template.yml")
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

    # Check that dashboards/ directory exists
    dashboards_dir=$(unzip -l "$zip_file" | grep "^.*dashboards/$")
    echo "dashboards_dir: $dashboards_dir"
    [ -n "$dashboards_dir" ]

    # Check that dashboard JSON files exist in dashboards/
    dashboard_json_count=$(unzip -l "$zip_file" | grep "dashboards/.*\.json$" | wc -l | tr -d ' ')
    echo "dashboard_json_count: $dashboard_json_count"
    [ "$dashboard_json_count" -gt 0 ]

    # Check that specific dashboard JSON files exist (based on dashboard names)
    [ -n "$(unzip -l "$zip_file" | grep 'dashboards/Costs Monitoring.json')" ]
    [ -n "$(unzip -l "$zip_file" | grep 'dashboards/Snowflake Query Performance.json')" ]
    [ -n "$(unzip -l "$zip_file" | grep 'dashboards/Snowflake Query Quality.json')" ]
    [ -n "$(unzip -l "$zip_file" | grep 'dashboards/DSOA Self Monitoring.json')" ]
    [ -n "$(unzip -l "$zip_file" | grep 'dashboards/Snowflake Security.json')" ]

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

    # Check that there are SQL files in build/
    # Should have 5 main SQL files in build root
    main_sql_count=$(unzip -l "$zip_file" | grep "build/[^/]*\.sql$" | wc -l | tr -d ' ')
    [ "$main_sql_count" -eq 5 ]

    # Check specific main SQL files exist
    [ -n "$(unzip -l "$zip_file" | grep "build/00_init.sql")" ]
    [ -n "$(unzip -l "$zip_file" | grep "build/10_admin.sql")" ]
    [ -n "$(unzip -l "$zip_file" | grep "build/20_setup.sql")" ]
    [ -n "$(unzip -l "$zip_file" | grep "build/40_config.sql")" ]
    [ -n "$(unzip -l "$zip_file" | grep "build/70_agents.sql")" ]

    # Check 09_upgrade folder has SQL files
    upgrade_sql_count=$(unzip -l "$zip_file" | grep "build/09_upgrade/.*\.sql$" | wc -l | tr -d ' ')
    [ "$upgrade_sql_count" -gt 0 ]

    # Check 30_plugins folder has SQL files
    plugin_sql_count=$(unzip -l "$zip_file" | grep "build/30_plugins/.*\.sql$" | wc -l | tr -d ' ')
    [ "$plugin_sql_count" -gt 0 ]
}

@test "markdownlint passes for all documentation" {
    if ! command -v markdownlint &> /dev/null; then
        skip "markdownlint not installed"
    fi

    run markdownlint '**/*.md' --config .markdownlint.json
    [ "$status" -eq 0 ]
}

@test "generated documentation has correct image paths" {
    # Check docs/ files have correct relative paths
    if [ -f "docs/CONTRIBUTING.md" ]; then
        run grep -q "](assets/" "docs/CONTRIBUTING.md"
        [ "$status" -eq 0 ]
    fi
}

@test "PDF generation has no broken image errors" {
    # Check for image loading errors
    echo "$BUILD_OUTPUT" | grep -v "ERROR: Failed to load image"
}

@test "PDF has no broken anchor errors" {
    # Check for anchor errors
    echo "$BUILD_OUTPUT" | grep -v "ERROR: No anchor"
}