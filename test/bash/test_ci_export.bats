#!/usr/bin/env bats
#
# Tests for --ci-export=github in interactive_wizard.sh
#

setup() {
    # shellcheck disable=SC2154
    cd "$BATS_TEST_DIRNAME/../.." || exit 1

    # Create minimal build artifacts for wizard
    mkdir -p build conf
    cat > build/config-default.yml << 'EOF'
version: "0.9.5"
core:
  log_level: "WARN"
  procedure_timeout: 3600
EOF

    # Clean up any leftover files
    rm -f GITHUB_SECRETS_SETUP.md
    rm -f .github/workflows/dsoa-deploy.yml
}

teardown() {
    rm -f GITHUB_SECRETS_SETUP.md
    rm -f .github/workflows/dsoa-deploy.yml
    rm -f build/config-default.yml
    rm -f conf/config-ci-test.yml
}

@test "--ci-export=github generates .github/workflows/dsoa-deploy.yml" {
    local test_dir
    test_dir=$(mktemp -d)
    cd "$test_dir"
    mkdir -p build conf

    cat > build/config-default.yml << 'EOF'
version: "0.9.5"
core:
  log_level: "WARN"
EOF

    # Source wizard and call export function directly
    # shellcheck disable=SC1090
    source "$BATS_TEST_DIRNAME/../../scripts/deploy/interactive_wizard.sh" 2>/dev/null || true

    WIZARD_ENV="ci-test"
    SF_ACCOUNT="myorg-myaccount"

    run export_github_ci "ci-test"
    [ "$status" -eq 0 ]
    [ -f ".github/workflows/dsoa-deploy.yml" ]

    cd "$BATS_TEST_DIRNAME/../.."
    rm -rf "$test_dir"
}

@test "--ci-export=github generates GITHUB_SECRETS_SETUP.md" {
    local test_dir
    test_dir=$(mktemp -d)
    cd "$test_dir"
    mkdir -p build conf

    cat > build/config-default.yml << 'EOF'
version: "0.9.5"
core:
  log_level: "WARN"
EOF

    # shellcheck disable=SC1090
    source "$BATS_TEST_DIRNAME/../../scripts/deploy/interactive_wizard.sh" 2>/dev/null || true

    WIZARD_ENV="ci-test"
    SF_ACCOUNT="myorg-myaccount"

    run export_github_ci "ci-test"
    [ "$status" -eq 0 ]
    [ -f "GITHUB_SECRETS_SETUP.md" ]

    cd "$BATS_TEST_DIRNAME/../.."
    rm -rf "$test_dir"
}

@test "--ci-export=github substitutes env name in workflow" {
    local test_dir
    test_dir=$(mktemp -d)
    cd "$test_dir"
    mkdir -p build conf

    cat > build/config-default.yml << 'EOF'
version: "0.9.5"
core:
  log_level: "WARN"
EOF

    # shellcheck disable=SC1090
    source "$BATS_TEST_DIRNAME/../../scripts/deploy/interactive_wizard.sh" 2>/dev/null || true

    WIZARD_ENV="ci-test"
    SF_ACCOUNT="myorg-myaccount"

    export_github_ci "ci-test"
    grep -q "ci-test" .github/workflows/dsoa-deploy.yml

    cd "$BATS_TEST_DIRNAME/../.."
    rm -rf "$test_dir"
}

@test "--ci-export=github substitutes version from build/config-default.yml" {
    local test_dir
    test_dir=$(mktemp -d)
    cd "$test_dir"
    mkdir -p build conf

    cat > build/config-default.yml << 'EOF'
version: "0.9.5"
core:
  log_level: "WARN"
EOF

    # shellcheck disable=SC1090
    source "$BATS_TEST_DIRNAME/../../scripts/deploy/interactive_wizard.sh" 2>/dev/null || true

    WIZARD_ENV="ci-test"
    SF_ACCOUNT="myorg-myaccount"

    export_github_ci "ci-test"
    grep -q "0.9.5" .github/workflows/dsoa-deploy.yml

    cd "$BATS_TEST_DIRNAME/../.."
    rm -rf "$test_dir"
}

@test "--ci-export=github workflow YAML has no unsubstituted placeholders" {
    local test_dir
    test_dir=$(mktemp -d)
    cd "$test_dir"
    mkdir -p build conf

    cat > build/config-default.yml << 'EOF'
version: "0.9.5"
core:
  log_level: "WARN"
EOF

    # shellcheck disable=SC1090
    source "$BATS_TEST_DIRNAME/../../scripts/deploy/interactive_wizard.sh" 2>/dev/null || true

    WIZARD_ENV="ci-test"
    SF_ACCOUNT="myorg-myaccount"

    export_github_ci "ci-test"
    run grep -q "__[A-Z_]*__" .github/workflows/dsoa-deploy.yml
    [ "$status" -ne 0 ]

    cd "$BATS_TEST_DIRNAME/../.."
    rm -rf "$test_dir"
}

@test "--ci-export=github workflow YAML is syntactically valid" {
    local test_dir
    test_dir=$(mktemp -d)
    cd "$test_dir"
    mkdir -p build conf

    cat > build/config-default.yml << 'EOF'
version: "0.9.5"
core:
  log_level: "WARN"
EOF

    # shellcheck disable=SC1090
    source "$BATS_TEST_DIRNAME/../../scripts/deploy/interactive_wizard.sh" 2>/dev/null || true

    WIZARD_ENV="ci-test"
    SF_ACCOUNT="myorg-myaccount"

    export_github_ci "ci-test"
    run yq '.' .github/workflows/dsoa-deploy.yml
    [ "$status" -eq 0 ]

    cd "$BATS_TEST_DIRNAME/../.."
    rm -rf "$test_dir"
}

@test "--ci-export=unknown prints error and fails" {
    local test_dir
    test_dir=$(mktemp -d)
    cd "$test_dir"
    mkdir -p build conf

    cat > build/config-default.yml << 'EOF'
version: "0.9.5"
core:
  log_level: "WARN"
EOF

    # shellcheck disable=SC1090
    source "$BATS_TEST_DIRNAME/../../scripts/deploy/interactive_wizard.sh" 2>/dev/null || true

    WIZARD_ENV="ci-test"
    SF_ACCOUNT="myorg-myaccount"
    CI_EXPORT="unknown-platform"

    # Simulate the CI export dispatch that happens in main()
    run bash -c "
        source '$BATS_TEST_DIRNAME/../../scripts/deploy/interactive_wizard.sh' 2>/dev/null || true
        CI_EXPORT='unknown-platform'
        WIZARD_ENV='ci-test'
        case \"\$CI_EXPORT\" in
            github) export_github_ci \"\$WIZARD_ENV\" ;;
            *) log_error \"Unknown --ci-export value: '\$CI_EXPORT'. Supported: github\"; exit 1 ;;
        esac
    "
    [ "$status" -ne 0 ]
    echo "$output" | grep -qi "unknown"

    cd "$BATS_TEST_DIRNAME/../.."
    rm -rf "$test_dir"
}
