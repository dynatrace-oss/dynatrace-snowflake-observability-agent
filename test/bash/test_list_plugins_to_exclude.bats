#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    TEST_CONFIG_FILE=$(mktemp)
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
}

teardown() {
    rm -f "$TEST_CONFIG_FILE"
    unset BUILD_CONFIG_FILE
}

@test "list_plugins_to_exclude.sh lists explicitly disabled plugins" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.disabled_by_default",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.test_plugin.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.active_plugin.is_disabled",
    "TYPE": "bool",
    "VALUE": false
  }
]
EOF

    run ./package/list_plugins_to_exclude.sh
    [ "$status" -eq 0 ]
    [[ "$output" =~ "test_plugin" ]]
    ! [[ "$output" =~ "active_plugin" ]]
}

@test "list_plugins_to_exclude.sh lists plugins not enabled when disabled_by_default is true" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.disabled_by_default",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.enabled_plugin.is_enabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.not_enabled_plugin.is_disabled",
    "TYPE": "bool",
    "VALUE": false
  }
]
EOF

    run ./package/list_plugins_to_exclude.sh
    [ "$status" -eq 0 ]

    # not_enabled_plugin should be excluded (not explicitly enabled when disabled_by_default=true)
    [[ "$output" =~ (^|[[:space:]])not_enabled_plugin([[:space:]]|$) ]]
    # enabled_plugin should NOT be excluded (explicitly enabled)
    ! [[ "$output" =~ (^|[[:space:]])enabled_plugin([[:space:]]|$) ]]
}

@test "list_plugins_to_exclude.sh returns empty when deploy_disabled_plugins is true" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.test_plugin.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF

    run ./package/list_plugins_to_exclude.sh
    [ "$status" -eq 0 ]
    # Should not exclude any plugins when deploy_disabled_plugins=true
    [ -z "$output" ]
}

@test "list_plugins_to_exclude.sh handles multiple disabled plugins" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.disabled_by_default",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.plugin_one.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.plugin_two.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.plugin_three.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF

    run ./package/list_plugins_to_exclude.sh
    [ "$status" -eq 0 ]
    [[ "$output" =~ "plugin_one" ]]
    [[ "$output" =~ "plugin_two" ]]
    [[ "$output" =~ "plugin_three" ]]
}

@test "list_plugins_to_exclude.sh handles disabled_by_default with explicit enables and disables" {
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.disabled_by_default",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.enabled_one.is_enabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.enabled_two.is_enabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.explicitly_disabled.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  },
  {
    "PATH": "plugins.not_configured.is_disabled",
    "TYPE": "bool",
    "VALUE": false
  }
]
EOF

    run ./package/list_plugins_to_exclude.sh
    [ "$status" -eq 0 ]
    # explicitly_disabled should be excluded (explicitly disabled)
    [[ "$output" =~ (^|[[:space:]])explicitly_disabled([[:space:]]|$) ]]
    # not_configured should be excluded (not explicitly enabled when disabled_by_default=true)
    [[ "$output" =~ (^|[[:space:]])not_configured([[:space:]]|$) ]]
    # enabled_one and enabled_two should NOT be excluded (explicitly enabled)
    ! [[ "$output" =~ (^|[[:space:]])enabled_one([[:space:]]|$) ]]
    ! [[ "$output" =~ (^|[[:space:]])enabled_two([[:space:]]|$) ]]
}
