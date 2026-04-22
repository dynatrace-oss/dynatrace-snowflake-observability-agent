# DSOA Advanced Installation Guide

This document covers advanced installation scenarios. For the standard quick-start path, see [INSTALL.md](INSTALL.md).

## Table of Contents

- [Restricting Elevated Privileges](#restricting-elevated-privileges)
- [Custom Object Names](#custom-object-names)
- [Setting up a Snowflake Connection Profile](#setting-up-a-snowflake-connection-profile)
- [Multitenancy](#multitenancy)
- [Plugin Configuration](#plugin-configuration)
- [OpenTelemetry Configuration](#opentelemetry-configuration)
- [Common Configuration Mistakes](#common-configuration-mistakes)

---

## Restricting Elevated Privileges

By default, `--scope=all` requires `ACCOUNTADMIN`. These options let you minimize or eliminate
elevated privilege requirements after the initial setup.

### Option 1: Pre-Created Objects (Most Restrictive — No ACCOUNTADMIN Required)

Have your DBA pre-create all Snowflake objects. Configure DSOA to use those names.
Subsequent deployments require only `DTAGENT_OWNER`.

```bash
# DBA creates objects once (as ACCOUNTADMIN)
# Then configure custom names in conf/config-prod.yml and deploy without init/admin:
./scripts/deploy/deploy.sh --env=prod --scope=setup,plugins,config,agents,apikey --options=skip_confirm
```

See [Custom Object Names](#custom-object-names) for the configuration details.

### Option 2: Generate Init Script for Manual Review

Generate the initialization SQL, have an admin review and execute it, then deploy the rest yourself:

```bash
# Generate init script (no execution)
./scripts/deploy/deploy.sh --env=prod --scope=init --options=manual --output-file=init-script.sql

# DBA reviews and executes init-script.sql as ACCOUNTADMIN
# Then deploy remaining scopes:
./scripts/deploy/deploy.sh --env=prod --scope=setup,plugins,config,agents,apikey --options=skip_confirm
```

### Option 3: Deploy Without Admin Scope

```bash
# DBA runs init once
./scripts/deploy/deploy.sh --env=prod --scope=init --options=manual --output-file=init-script.sql
# Review and execute init-script.sql

# Deploy all components except admin scope
./scripts/deploy/deploy.sh --env=prod --scope=setup,plugins,config,agents --options=skip_confirm
```

Without `admin` scope, you must manually grant:

- `MONITOR` on warehouses to `DTAGENT_VIEWER` (required for `query_history` plugin)
- `MONITOR` on dynamic tables to `DTAGENT_VIEWER` (required for `dynamic_tables` plugin)
- Other plugin-specific privileges as documented in each plugin's `config.md`

### Option 4: Split Init + Admin + Regular Deployment

```bash
# Step 1: DBA runs init
./scripts/deploy/deploy.sh --env=prod --scope=init --options=manual --output-file=init.sql
# Execute init.sql as ACCOUNTADMIN

# Step 2: Admin runs admin scope (creates DTAGENT_ADMIN, sets up privilege grants)
./scripts/deploy/deploy.sh --env=prod --scope=admin

# Step 3: Regular user with DTAGENT_OWNER runs the rest
./scripts/deploy/deploy.sh --env=prod --scope=setup,plugins,config,agents,apikey --options=skip_confirm
```

### Step-by-Step: Using a Custom Initialization Script

This gives DBAs full control over object naming before DSOA touches anything.

1. Copy the init script:

   ```bash
   cp build/00_init.sql conf/custom-init.sql
   # Optional: append admin setup
   cat build/10_admin.sql >> conf/custom-init.sql
   ```

1. Add a header to `conf/custom-init.sql` documenting your custom names:

   ```sql
   --
   -- CUSTOM OBJECT NAMES:
   -- DB: DTAGENT_DB
   -- WAREHOUSE: DTAGENT_WH
   -- RESOURCE MONITOR: DTAGENT_RS (or "-" to skip)
   -- OWNER: DTAGENT_OWNER
   -- ADMIN: DTAGENT_ADMIN (or "-" to skip)
   -- VIEWER: DTAGENT_VIEWER
   -- API_INTEGRATION: DTAGENT_API_INTEGRATION
   --
   ```

1. Find-and-replace default names throughout the file:

   ```text
   DTAGENT_API_INTEGRATION → ACME_API_INTEGRATION
   DTAGENT_DB              → ACME_MONITORING_DB
   DTAGENT_WH              → ACME_MONITORING_WH
   DTAGENT_RS              → ACME_MONITORING_RS
   DTAGENT_OWNER           → ACME_MONITORING_OWNER
   DTAGENT_ADMIN           → ACME_MONITORING_ADMIN
   DTAGENT_VIEWER          → ACME_MONITORING_VIEWER
   ```

   > **Tip:** Replace in the order above — most specific names first — to avoid partial matches.

1. DBA reviews and executes the custom init script.

1. Create `conf/config-prod.yml` with matching names:

   ```yaml
   core:
     dynatrace_tenant_address: your-tenant.live.dynatrace.com
     deployment_environment: PRODUCTION

     snowflake:
       account_name: myorg-myaccount
       database:
         name: "ACME_MONITORING_DB"
       warehouse:
         name: "ACME_MONITORING_WH"
       resource_monitor:
         name: "ACME_MONITORING_RS"   # or "-" to skip
       roles:
         owner: "ACME_MONITORING_OWNER"
         admin: "-"                   # "-" if skipped
         viewer: "ACME_MONITORING_VIEWER"
       api_integration:
         name: "ACME_API_INTEGRATION"
   ```

1. Deploy without init or admin scopes:

   ```bash
    export DTAGENT_TOKEN="your-token"
   ./scripts/deploy/deploy.sh --env=prod --scope=setup,plugins,config,agents,apikey --options=skip_confirm
   ```

---

## Custom Object Names

By default, DSOA creates Snowflake objects with these names:

| Object | Default Name |
|---|---|
| Database | `DTAGENT_DB` |
| Warehouse | `DTAGENT_WH` |
| Resource Monitor | `DTAGENT_RS` |
| Owner Role | `DTAGENT_OWNER` |
| Admin Role | `DTAGENT_ADMIN` |
| Viewer Role | `DTAGENT_VIEWER` |
| API Integration | `DTAGENT_API_INTEGRATION` |

Configure custom names under `core.snowflake.*` in your config file. Set any optional object to `"-"` to skip creation.

### Required vs Optional Objects

**Required (cannot be skipped):** database, warehouse, owner role, viewer role, API integration.

**Optional (skip with `"-"`):**

- `snowflake.roles.admin` — if skipped, `DTAGENT_ADMIN` is not created; grant privileges manually
- `snowflake.resource_monitor.name` — if skipped, no resource monitor is created

### Example: Full Custom Names

```yaml
core:
  deployment_environment: PRODUCTION
  snowflake:
    database:
      name: DT_MONITORING_DB
    warehouse:
      name: DT_MONITORING_WH
    resource_monitor:
      name: DT_MONITORING_RS
    roles:
      owner: DT_MONITORING_OWNER
      admin: "-"             # Skip admin role — grant privileges manually
      viewer: DT_MONITORING_VIEWER
    api_integration:
      name: DT_MONITORING_API_INTEGRATION
```

### Naming Rules

Snowflake identifier constraints apply:

- Letters (A-Z, a-z), numbers, underscores, and dollar signs only
- Must start with a letter or underscore
- Maximum 255 characters
- Case-insensitive in Snowflake

### Supported Installation Scenarios

| Scenario | Config | Scopes |
|---|---|---|
| Standard full install | Default names | `all` |
| Skip optional objects | `admin: "-"`, `resource_monitor: "-"` | `init,setup,plugins,config,agents,apikey` |
| TAG-based multitenancy | `tag: TNA` | `all` |
| Custom names full | Custom names for all objects | `init,admin,setup,plugins,config,agents,apikey` |
| Pre-created objects | Custom names matching pre-created | `setup,plugins,config,agents,apikey` |
| Custom names + TAG | Custom names + `tag` for telemetry only | `init,admin,setup,plugins,config,agents,apikey` |

---

## Setting up a Snowflake Connection Profile

The Snowflake CLI connection name **must** follow this pattern:

```text
snow_agent_<deployment_environment_lowercase>
```

This is derived from `deployment_environment` **inside** your config file, not from the `$ENV` filename.

### Automatic Setup (Recommended)

```bash
./setup.sh $ENV
# Reads deployment_environment from conf/config-$ENV.yml
# Creates: snow_agent_<deployment_environment_lowercase>
```

### Manual Setup

```bash
# 1. Find your deployment_environment:
yq '.core.deployment_environment' conf/config-$ENV.yml
# Example output: PRODUCTION_US_EAST_1

# 2. Create connection (lowercase):
snow connection add \
  --connection-name snow_agent_production_us_east_1 \
  --account myorg-myaccount \
  --user john.doe@company.com \
  --authenticator externalbrowser
```

### Finding Your Snowflake Account Identifier

```sql
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS account_name;
```

Use `orgname-accountname` format (preferred). The legacy `account.region` format is still supported.

### Verifying Connections

```bash
snow connection list
# Expected: snow_agent_production, snow_agent_production_us_east_1, etc.

# Check if required connection exists:
EXPECTED=$(yq '.core.deployment_environment' conf/config-$ENV.yml | tr '[:upper:]' '[:lower:]' | sed 's/^/snow_agent_/')
snow connection list | grep -q "$EXPECTED" && echo "OK" || echo "MISSING: $EXPECTED"
```

---

## Multitenancy

Deploy multiple DSOA instances on the same Snowflake account to send telemetry to one or more
Dynatrace tenants. Each instance needs a unique `deployment_environment` and unique Snowflake
object names (via `tag` or custom names).

### Using TAG (Simpler)

TAG automatically suffixes all Snowflake object names:

```yaml
# conf/config-prod-tenant-a.yml
core:
  deployment_environment: PRODUCTION_TENANT_A
  tag: TNA
  dynatrace_tenant_address: tenant-a.live.dynatrace.com
```

```yaml
# conf/config-prod-tenant-b.yml
core:
  deployment_environment: PRODUCTION_TENANT_B
  tag: TNB
  dynatrace_tenant_address: tenant-b.live.dynatrace.com
```

```bash
./setup.sh prod-tenant-a && ./setup.sh prod-tenant-b
./scripts/deploy/deploy.sh --env=prod-tenant-a --options=skip_confirm
./scripts/deploy/deploy.sh --env=prod-tenant-b --options=skip_confirm
```

This creates: `DTAGENT_TNA_DB`, `DTAGENT_TNA_WH`, `DTAGENT_TNB_DB`, `DTAGENT_TNB_WH`, etc.

### Using Custom Names (More Control)

Specify each object name explicitly. Optionally add `tag` for telemetry tracking only
(it won't affect object names when any custom name is set).

```yaml
core:
  deployment_environment: PRODUCTION_TENANT_A
  tag: TNA          # Optional: adds deployment.environment.tag to telemetry
  snowflake:
    database:
      name: ACME_TENANT_A_DB
    warehouse:
      name: ACME_TENANT_A_WH
    roles:
      owner: ACME_TENANT_A_OWNER
      viewer: ACME_TENANT_A_VIEWER
    api_integration:
      name: ACME_TENANT_A_API
```

### TAG and Custom Names Interaction

| Scenario | Object naming | Telemetry |
|---|---|---|
| TAG only | `DTAGENT_<TAG>_DB` etc. | `deployment.environment.tag: "<TAG>"` |
| Custom names only | Your custom names | `deployment.environment` only |
| Both TAG + custom names | Custom names (TAG doesn't affect objects) | Both dimensions |

**Key principle:** When ANY custom name is provided, TAG is disabled for ALL object naming.

### Critical Rules for Multitenancy

- `deployment_environment` must be **unique** across all instances — otherwise telemetry is indistinguishable in Dynatrace
- `tag` must be **unique** across instances using tag-based naming — otherwise Snowflake object name conflicts occur
- Do not encode the tag into `deployment_environment` — they serve different purposes

---

## Plugin Configuration

### Global Plugin Options

| Key | Type | Default | Description |
|---|---|---|---|
| `plugins.disabled_by_default` | Boolean | `false` | Disable all plugins unless explicitly enabled |
| `plugins.deploy_disabled_plugins` | Boolean | `true` | Deploy SQL for disabled plugins (but don't schedule them) |

### Per-Plugin Options

| Key | Type | Default | Description |
|---|---|---|---|
| `is_disabled` | Boolean | `false` | Disable this plugin |
| `is_enabled` | Boolean | `false` | Enable this plugin (when `disabled_by_default: true`) |
| `lookback_hours` | Integer | varies | Max lookback window for first run / after reset |
| `schedule` | String | varies | Cron (`USING CRON */30 * * * * UTC`), interval (`30 MINUTES`), or task graph (`after TASK_NAME`) |
| `telemetry` | List | varies | Signal types to emit: `logs`, `metrics`, `spans`, `events`, `biz_events` |

See each plugin's `config.md` for plugin-specific options (filters, retention, limits, etc.).

### Enabling a Subset of Plugins

```yaml
plugins:
  disabled_by_default: true
  deploy_disabled_plugins: false    # Don't deploy SQL for disabled plugins
  query_history:
    is_enabled: true
  data_volume:
    is_enabled: true
```

---

## OpenTelemetry Configuration

Leave `otel: {}` for defaults. Advanced tuning:

| Key | Type | Description |
|---|---|---|
| `max_consecutive_api_fails` | Integer | Circuit breaker threshold |
| `logs.export_timeout_millis` | Integer | Export timeout (ms) |
| `logs.max_export_batch_size` | Integer | Batch size cap |
| `logs.is_disabled` | Boolean | Disable log export |
| `spans.export_timeout_millis` | Integer | Export timeout (ms) |
| `spans.max_export_batch_size` | Integer | Batch size cap |
| `spans.max_event_count` | Integer | Max events per span |
| `spans.max_attributes_per_event_count` | Integer | Max attributes per event |
| `spans.max_span_attributes` | Integer | Max attributes per span |
| `spans.is_disabled` | Boolean | Disable span export |
| `metrics.api_post_timeout` | Integer | POST timeout (s) |
| `metrics.max_retries` | Integer | Max retry attempts |
| `metrics.max_batch_size` | Integer | Batch size cap |
| `metrics.retry_delay_ms` | Integer | Retry delay (ms) |
| `metrics.is_disabled` | Boolean | Disable metrics export |
| `events.*` | various | Same pattern as `metrics.*` |
| `biz_events.*` | various | Same pattern as `metrics.*` |
| `davis_events.*` | various | Same pattern as `metrics.*` |

### Without a Dynatrace Platform Subscription (DPS)

BizEvents and OpenPipeline events require DPS. Disable them:

```yaml
otel:
  events:
    is_disabled: true
  biz_events:
    is_disabled: true
```

Logs, metrics, spans, and Davis Events work on all tenants.

---

## Common Configuration Mistakes

### Connection profile name mismatch

**Symptom:** `Connection 'snow_agent_xxx' not found`

The connection must be named `snow_agent_<deployment_environment_lowercase>` — based on the
value **inside** your config, not on the `$ENV` filename.

```bash
# Wrong: based on file name
snow connection add --connection-name snow_agent_prod

# Correct: based on deployment_environment value
yq '.core.deployment_environment' conf/config-prod.yml
# → PRODUCTION_US_EAST
snow connection add --connection-name snow_agent_production_us_east
```

### Using account locator instead of org-account format

**Symptom:** Random strings appear as service names in Dynatrace.

```yaml
# Avoid (legacy locator — cryptic):
account_name: abc12345.us-east-1

# Prefer (meaningful):
account_name: myorg-myaccount
```

### Reusing `deployment_environment` or `tag` across instances

Both must be unique per instance. Reusing `deployment_environment` makes telemetry indistinguishable.
Reusing `tag` causes Snowflake object naming conflicts.

### Connection name in wrong case

Snowflake CLI connection names are case-sensitive. Always use lowercase:

```bash
# Wrong:
snow connection add --connection-name snow_agent_PRODUCTION

# Correct:
snow connection add --connection-name snow_agent_production
```

### Dynatrace API token API URL (`.apps` vs `.live`)

The `dynatrace_tenant_address` must use `.live.dynatrace.com` for the API endpoint.
If you accidentally use `.apps.dynatrace.com`, the deploy script will auto-correct it
with a warning.
