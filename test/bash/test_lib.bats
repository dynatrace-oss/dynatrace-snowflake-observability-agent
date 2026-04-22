#!/usr/bin/env bats

# Tests for scripts/deploy/lib.sh shared library

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Source the library
    # shellcheck source=scripts/deploy/lib.sh
    source scripts/deploy/lib.sh
}

##region Logging Tests

@test "log_info outputs to stderr" {
    run log_info "test message"
    [ "$status" -eq 0 ]
    [[ "$output" == *"[INFO] test message"* ]]
}

@test "log_ok outputs success marker" {
    run log_ok "success"
    [ "$status" -eq 0 ]
    [[ "$output" == *"✓ success"* ]]
}

@test "log_warn outputs warning marker" {
    run log_warn "warning"
    [ "$status" -eq 0 ]
    [[ "$output" == *"⚠ WARNING: warning"* ]]
}

@test "log_error outputs error marker" {
    run log_error "error"
    [ "$status" -eq 0 ]
    [[ "$output" == *"✗ ERROR: error"* ]]
}

##endregion

##region Validator Tests

@test "validate_dt_tenant accepts valid .live.dynatrace.com" {
    run validate_dt_tenant "abc123.live.dynatrace.com"
    [ "$status" -eq 0 ]
    [ "$output" = "abc123.live.dynatrace.com" ]
}

@test "validate_dt_tenant auto-corrects .apps. to .live." {
    run validate_dt_tenant "abc123.apps.dynatrace.com"
    [ "$status" -eq 0 ]
    [ "$output" = "abc123.live.dynatrace.com" ]
}

@test "validate_dt_tenant rejects invalid format" {
    run validate_dt_tenant "invalid-tenant"
    [ "$status" -eq 1 ]
}

@test "validate_sf_account accepts org-account format" {
    run validate_sf_account "myorg-myaccount"
    [ "$status" -eq 0 ]
}

@test "validate_sf_account accepts locator.region format" {
    run validate_sf_account "abc12345.us-east-1"
    [ "$status" -eq 0 ]
}

@test "validate_sf_account rejects invalid format" {
    run validate_sf_account "invalid"
    [ "$status" -eq 1 ]
}

@test "validate_nonempty accepts non-empty string" {
    run validate_nonempty "value"
    [ "$status" -eq 0 ]
}

@test "validate_nonempty rejects empty string" {
    run validate_nonempty ""
    [ "$status" -eq 1 ]
}

@test "validate_alphanumeric accepts alphanumeric" {
    run validate_alphanumeric "abc123_def"
    [ "$status" -eq 0 ]
}

@test "validate_alphanumeric rejects special chars" {
    run validate_alphanumeric "abc-123"
    [ "$status" -eq 1 ]
}

@test "validate_alphanumeric accepts empty string" {
    run validate_alphanumeric ""
    [ "$status" -eq 0 ]
}

##endregion

##region Config Helper Tests

@test "read_config_key returns value from YAML" {
    local temp_file=$(mktemp)
    cat > "$temp_file" << 'EOF'
core:
  dynatrace_tenant_address: "test.live.dynatrace.com"
  deployment_environment: "test-env"
EOF

    run read_config_key "$temp_file" "core.dynatrace_tenant_address"
    [ "$status" -eq 0 ]
    [[ "$output" == *"test.live.dynatrace.com"* ]]

    rm -f "$temp_file"
}

@test "read_config_key returns error for missing file" {
    run read_config_key "/nonexistent/file.yml" "core.key"
    [ "$status" -eq 1 ]
}

@test "write_config_key creates new YAML file" {
    local temp_file=$(mktemp)
    rm -f "$temp_file"

    write_config_key "$temp_file" "core.test_key" "test_value"
    [ -f "$temp_file" ]

    # Verify content
    run read_config_key "$temp_file" "core.test_key"
    [[ "$output" == *"test_value"* ]]

    rm -f "$temp_file"
}

@test "write_config_key updates existing YAML" {
    local temp_file=$(mktemp)
    cat > "$temp_file" << 'EOF'
core:
  existing_key: "old_value"
EOF

    write_config_key "$temp_file" "core.new_key" "new_value"

    # Verify both keys exist
    run read_config_key "$temp_file" "core.existing_key"
    [[ "$output" == *"old_value"* ]]

    run read_config_key "$temp_file" "core.new_key"
    [[ "$output" == *"new_value"* ]]

    rm -f "$temp_file"
}

##endregion
