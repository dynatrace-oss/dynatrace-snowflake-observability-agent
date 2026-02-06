# How to Install

Dynatrace Snowflake Observability Agent (DSOA) comes in the form of a series of SQL scripts (accompanied with a few configuration files). You must deploy these scripts to Snowflake by executing them in the correct order.

This document assumes you are installing from the distribution package (`dynatrace_snowflake_observability_agent-*.zip`). If you are a
developer and want to build from source, please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) guide.

## Table of Contents

- [Table of Contents](#table-of-contents)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Deploying DSOA](#deploying-dynatrace-snowflake-observability-agent)
- [Setting up a profile](#setting-up-a-profile)
- [Setting up connection to Snowflake](#setting-up-connection-to-snowflake)
- [Common Configuration Mistakes](#common-configuration-mistakes)

## Prerequisites

Before deploying the agent, ensure the following tools are installed on your system.

### Windows Users

**Important:** On Windows, you must install Windows Subsystem for Linux (WSL) version 2.0 or higher. The deployment scripts must run through
WSL. See the [Install WSL guide](https://learn.microsoft.com/en-us/windows/wsl/install) for more details.

### All Users

**Required command-line tools:**

- **bash**: The deployment scripts are written in bash.
- **Snowflake CLI**: For connecting to and deploying objects in Snowflake.
- **jq**: For processing JSON files.
- **yq**: For processing YAML files.
- **gawk**: For text processing.

You can run the included `./setup.sh` script, which will attempt to install these dependencies for you.

Alternatively, you can install them manually:

#### Snowflake CLI

Install using `pipx` (recommended):

```bash
# If you do not have pipx installed, run:
# on Ubuntu/Debian
sudo apt install pipx
# on macOS
brew install pipx

# With pipx installed, run:
pipx install snowflake-cli-labs
```

Or on macOS with Homebrew:

```bash
brew tap snowflakedb/snowflake-cli
brew install snowflake-cli
```

#### jq and gawk

On **Ubuntu/Debian**:

```bash
sudo apt install jq yq gawk
```

On **macOS** (with Homebrew):

```bash
brew install jq yq gawk
```

## Quick Start

1. **Create configuration file** (choose a descriptive `$ENV` name for your file):

   ```bash
   cp conf/config-template.yml conf/config-$ENV.yml
   # Example: cp conf/config-template.yml conf/config-production.yml
   ```

2. **Edit configuration** - Set your `deployment_environment` and other parameters:

   ```yaml
   core:
     deployment_environment: PRODUCTION  # This identifies your instance in telemetry
     tag: ""                             # Optional: Use for multitenancy (suffixes Snowflake objects)
     snowflake:
       # Use organization-account format (recommended)
       account_name: "myorg-myaccount"
       host_name: "-"  # Will be auto-derived
       # ... other settings
   ```

3. **Set up Snowflake CLI connection** (based on your `deployment_environment`, not file name):

   ```bash
   # Automatic setup (recommended):
   ./setup.sh production

   # The script will create connection: snow_agent_production
   # (derived from deployment_environment, converted to lowercase)
   ```

4. **Deploy**:

   ```bash
   ./deploy.sh production
   ```

**Important to understand:**

- `production` in the commands above is the `$ENV` parameter - it only locates the file `config-production.yml`
- The actual Snowflake connection used is `snow_agent_<deployment_environment>` (from inside the config file)
- In this example, if `deployment_environment: PRODUCTION`, the connection name is `snow_agent_production` (lowercase)

**Alternative: Deployment with Custom Object Names:**

If you need to deploy with custom object names and without ACCOUNTADMIN privileges, see the [Step-by-Step: Using a Custom Initialization Script](#step-by-step-using-a-custom-initialization-script) guide in the "Restricting Elevated Privileges" section.

## Deploying Dynatrace Snowflake Observability Agent

### Understanding the Deployment Process

The deployment process uses your `$ENV` parameter only to locate the configuration file. Everything else is driven by values **inside** that configuration file.

**Step-by-step flow when you run `./deploy.sh $ENV`:**

1. **Configuration Loading**:
   - Loads file: `conf/config-$ENV.yml`
   - The `$ENV` parameter is only used here

2. **Value Extraction**:
   - Reads `core.deployment_environment` from inside the config
   - Reads `core.tag` from inside the config

3. **Connection Selection**:
   - Uses Snowflake CLI connection: `snow_agent_<deployment_environment_lowercase>`
   - This is NOT based on `$ENV`, but on `deployment_environment` value

4. **Object Creation**:
   - Creates Snowflake objects with naming: `DTAGENT_<tag>_*` (if tag provided)
   - Without tag: `DTAGENT_*`

5. **Configuration Storage**:
   - Stores `deployment_environment` in Snowflake tables
   - This value is used at runtime

6. **Runtime Identification**:
   - Agent reads `deployment_environment` from Snowflake tables
   - Sends all telemetry with dimension: `deployment.environment: "<deployment_environment>"`

**Visual Example:**

```bash
./deploy.sh prod-useast
```

```text
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Load config-prod-useast.yml                         │
│ (ENV parameter: "prod-useast" used only here)               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Extract values from config file:                    │
│   deployment_environment: "PRODUCTION_US_EAST_1"            │
│   tag: "USEAST"                                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Use Snowflake connection:                           │
│   snow_agent_production_us_east_1                           │
│   (from deployment_environment, lowercase)                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Create Snowflake objects:                           │
│   DTAGENT_USEAST_DB                                         │
│   DTAGENT_USEAST_WH                                         │
│   DTAGENT_USEAST_OWNER (role)                               │
│   (from tag)                                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 5: Store in DTAGENT_USEAST_DB.APP.DTAGENT_CONFIG:      │
│   deployment_environment: "PRODUCTION_US_EAST_1"            │
│   deployment_environment_tag: "USEAST"                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 6: Runtime - Send telemetry to Dynatrace:              │
│   deployment.environment: "PRODUCTION_US_EAST_1"            │
│   deployment.environment.tag: "USEAST"                      │
└─────────────────────────────────────────────────────────────┘
```

### Deployment Commands

To deploy Dynatrace Snowflake Observability Agent, run the `./deploy.sh` command:

```bash
./deploy.sh $ENV [--scope=SCOPE] [--from-version=VERSION] [--output-file=FILE] [--options=OPTIONS]
```

#### Required Parameters

- **`$ENV`** (required): Environment identifier that must match one of the previously created configuration files. The file must be named `config-$ENV.yml` in the `conf/` directory.

#### Optional Parameters

- **`--scope=SCOPE`** (optional, default: `all`): Specifies the deployment scope. Valid values:
  - `init` - Initialize database and basic structure - **Optional** (can be performed manually)
  - `admin` - Administrative operations (creates DTAGENT_ADMIN role, role grants, ownership transfers) - **Optional**
  - `setup` - Set up core schemas, tables, and procedures
  - `plugins` - Deploy plugin code and views
  - `config` - Update configuration table only
  - `agents` - Deploy agent procedures and tasks
  - `apikey` - Update Dynatrace Access Token only
  - `all` - Full deployment without upgrade step (default)
  - `teardown` - Uninstall Dynatrace Snowflake Observability Agent from your Snowflake account
  - `upgrade` - Upgrade from a previous version (requires `--from-version`)
  - `file_pattern` - Any other value will deploy only files matching that pattern

  **Note:** The `admin` scope is **optional**. If not installed, the `DTAGENT_ADMIN` role will not be created, and administrative operations (such as granting MONITOR privileges on warehouses) must be performed manually.

  **Multiple scopes** can be specified as a comma-separated list (e.g., `setup,plugins,config,agents,apikey`). This allows you to deploy only specific components in a single operation. Note that `all` and `teardown` cannot be combined with other scopes.

- **`--from-version=VERSION`** (required when `--scope=upgrade`): Specifies the version number you are upgrading from (e.g., `0.9.2`).

- **`--output-file=FILE`** (optional): Custom output file path for manual mode. If not specified, defaults to `dsoa-deploy-script-{ENV}-{TIMESTAMP}.sql`.

- **`--options=OPTIONS`** (optional): Comma-separated list of deployment options:
  - `manual` - Generate SQL script without executing it. You can review and execute it manually.
  - `service_user` - Use service user authentication (for CI/CD pipelines)
  - `skip_confirm` - Skip deployment confirmation prompt
  - `no_dep` - Skip sending deployment BizEvents to Dynatrace

#### Examples

```bash
# Full deployment to 'dev' environment
./deploy.sh dev

# Deploy only configuration changes
./deploy.sh prod --scope=config

# Deploy multiple scopes in one operation
./deploy.sh prod --scope=setup,plugins,config,agents

# Upgrade from version 0.9.2
./deploy.sh test --scope=upgrade --from-version=0.9.2

# Generate manual deployment script for review
./deploy.sh prod --options=manual --output-file=my-deployment.sql

# Deploy only plugins matching a pattern
./deploy.sh dev --scope=053_v_ac

# Deploy multiple patterns (using pipe separator)
./deploy.sh test --scope="053_v_ac|70"

# CI/CD deployment with service user (skip confirmation and BizEvents)
./deploy.sh prod --options=service_user,skip_confirm
```

### Understanding the Role Model and Deployment Flexibility

Dynatrace Snowflake Observability Agent uses a flexible role model to provide security and deployment options:

#### Role Hierarchy

- **`DTAGENT_OWNER`**: Owns all Dynatrace Snowflake Observability Agent artifacts (database, schemas, tables, procedures, tasks). This role creates and manages all objects within the `DTAGENT_DB` database.

- **`DTAGENT_ADMIN`** (Optional): Handles elevated administrative operations including role grants, ownership transfers, and privilege management. This role has `MANAGE GRANTS` privilege on the account to grant monitoring privileges on warehouses and dynamic tables to `DTAGENT_VIEWER`. **This role is only created when the `admin` scope is installed.**

- **`DTAGENT_VIEWER`**: Executes regular telemetry collection and processing operations. This role runs all agent tasks and queries telemetry data from Snowflake, then sends it to Dynatrace.

The role hierarchy is:

- Primary hierarchy: `ACCOUNTADMIN` → `DTAGENT_OWNER` → `DTAGENT_VIEWER`
- Admin branch (optional): `DTAGENT_OWNER` → `DTAGENT_ADMIN`

#### Deployment Scope Privileges

Different deployment scopes require different privilege levels:

| Scope      | Required Role   | Description                                                                         |
| ---------- | --------------- | ----------------------------------------------------------------------------------- |
| `init`     | `ACCOUNTADMIN`  | Creates roles, database, warehouse, and initial structure                           |
| `admin`    | `DTAGENT_ADMIN` | **Optional.** Performs administrative operations (role grants, ownership transfers) |
| `setup`    | `DTAGENT_OWNER` | Creates schemas, tables, procedures, and core objects                               |
| `plugins`  | `DTAGENT_OWNER` | Deploys plugin code, views, and procedures                                          |
| `config`   | `DTAGENT_OWNER` | Updates configuration table                                                         |
| `agents`   | `DTAGENT_OWNER` | Deploys agent tasks and schedules                                                   |
| `apikey`   | `DTAGENT_OWNER` | Updates Dynatrace API key secret                                                    |
| `upgrade`  | `DTAGENT_OWNER` | Runs upgrade scripts (may require `DTAGENT_ADMIN` for some version upgrades)        |
| `all`      | `ACCOUNTADMIN`  | Full deployment including init and admin scopes (creates DTAGENT_ADMIN)             |
| `teardown` | `ACCOUNTADMIN`  | Removes all Dynatrace Snowflake Observability Agent objects                         |

**Note:** The `admin` scope is optional. If you skip it, `DTAGENT_ADMIN` will not be created, and you must manually grant required privileges (e.g., MONITOR on warehouses).

#### Restricting Elevated Privileges

If you want to minimize the use of elevated privileges in your organization, you have several deployment options:

##### Option 1: Pre-Created Objects with Custom Names (Most Restrictive - No ACCOUNTADMIN Required)

Use [Custom Object Names](#custom-object-names) to reference objects that have been pre-created by your database administrators. This approach allows deployment without any elevated privileges:

```bash
# 1. DBA pre-creates all core objects as ACCOUNTADMIN (one-time setup)
#    - Database, warehouse, resource monitor, roles, API integration
# 2. Configure custom names in conf/config-prod.yml to match pre-created objects
# 3. Deploy without init or admin scopes (no ACCOUNTADMIN required)
./deploy.sh prod --scope=setup,plugins,config,agents,apikey
```

###### Benefits

- **One-time ACCOUNTADMIN access**: Only needed during initial setup
- **Clear documentation**: Header shows all custom names in one place
- **Consistent naming**: All objects use your organization's naming conventions
- **Privilege separation**: Regular deployments don't require elevated privileges
- **Reproducible**: Custom init script can be version-controlled and reviewed
- **Flexible**: Optionally include admin role setup to further reduce privilege requirements

See the [Custom Object Names](#custom-object-names) section for detailed configuration and use case examples.

###### Step-by-Step: Using a Custom Initialization Script

This approach provides a structured way to have a Snowflake administrator initialize core objects with custom names, which are then used for deployment without ACCOUNTADMIN rights.

1. Copy deployment scripts to a custom file
    - Copy the content of the initialization script to create your custom file:

      ```bash
      # Copy the init script content
      cp build/00_init.sql conf/custom-init.sql
      ```

    - If you want to include the admin role setup (to avoid using ACCOUNTADMIN during main deployment), also append the admin script:

      ```bash
      # Append admin script content
      cat build/10_admin.sql >> conf/custom-init.sql
      ```

1. Add a header at the top of `conf/custom-init.sql` documenting the custom names you'll use. This header serves as a reference for the replacements you'll make throughout the file:

    ```sql
    --
    -- CUSTOM OBJECT NAMES:
    -- DB: DTAGENT_DB
    -- WAREHOUSE: DTAGENT_WH
    -- RESOURCE MONITOR: DTAGENT_RS (optional - omit if setting to "-" in config)
    -- OWNER: DTAGENT_OWNER
    -- ADMIN: DTAGENT_ADMIN (optional - omit if setting to "-" in config)
    -- VIEWER: DTAGENT_VIEWER
    -- API_INTEGRATION: DTAGENT_API_INTEGRATION (required)
    --
    ```

    > **Note:** If you plan to skip optional objects (admin role or resource monitor), you can either:
    > - Keep their default names in the script and set them to `"-"` in your config (the deployment will filter them out), OR
    > - Manually remove their creation statements from your custom-init.sql file

1. Use your text editor's find-and-replace function to update all default names to your custom names throughout the entire file:

    ```text
    DTAGENT_API_INTEGRATION → DTAGENT_MY_API_INTEGRATION
    DTAGENT_DB → DTAGENT_MY_DB
    DTAGENT_WH → DTAGENT_MY_WAREHOUSE
    DTAGENT_RS → DTAGENT_MY_RESOURCE_MONITOR
    DTAGENT_OWNER → DTAGENT_MY_OWNER
    DTAGENT_ADMIN → DTAGENT_MY_ADMIN
    DTAGENT_VIEWER → DTAGENT_MY_VIEWER
    ```

    > **Tip:** Perform replacements in order, starting with the most specific names first to avoid partial matches. Do DTAGENT_API_INTEGRATION before DTAGENT_DB to avoid accidentally replacing the DB part of the integration name.

1. Have your Snowflake administrator review and execute the custom initialization script
1. Create a configuration file in `conf/config-custom-init.yml` that matches your custom object names:

    ```yaml
    core:
      dynatrace_tenant_address: your-tenant.live.dynatrace.com
      deployment_environment: CUSTOM-INIT

      snowflake:
        database:
          name: "DTAGENT_MY_DB"
        warehouse:
          name: "DTAGENT_MY_WAREHOUSE"
        resource_monitor:
          name: "DTAGENT_MY_RESOURCE_MONITOR"  # or "-" to skip
        roles:
          owner: "DTAGENT_MY_OWNER"
          admin: "DTAGENT_MY_ADMIN"  # or "-" to skip
          viewer: "DTAGENT_MY_VIEWER"
        api_integration:
          name: "DTAGENT_MY_API_INTEGRATION"
    ```

    **Example with optional objects disabled:**

    ```yaml
    core:
      dynatrace_tenant_address: your-tenant.live.dynatrace.com
      deployment_environment: CUSTOM-INIT-MINIMAL

      snowflake:
        database:
          name: "DTAGENT_MY_DB"
        warehouse:
          name: "DTAGENT_MY_WAREHOUSE"
        resource_monitor:
          name: "-"  # Skip resource monitor creation
        roles:
          owner: "DTAGENT_MY_OWNER"
          admin: "-"  # Skip admin role creation
          viewer: "DTAGENT_MY_VIEWER"
        api_integration:
          name: "DTAGENT_MY_API_INTEGRATION"
    ```

1. [Set up Snowflake CLI connection](#quick-start)
1. Deploy without Init/Admin scopes

    ```bash
    export HISTCONTROL=ignorespace
    export DTAGENT_TOKEN="your-dynatrace-token"

    # If you included admin setup (or do not want to install use the admin role) in your custom init script:
    ./deploy.sh custom-init --scope=setup,plugins,config,agents,apikey
    ```

##### Option 2: Using Generated Init Script with Manual Execution

Generate the initialization script using the `manual` option, then have an administrator execute it:

```bash
# Generate init script without executing
./deploy.sh $ENV --scope=init --options=manual --output-file=init-script.sql

# Have your Snowflake administrator review and execute
snow sql -c admin_connection -f init-script.sql
```

Then deploy the remaining scopes without ACCOUNTADMIN:

```bash
./deploy.sh $ENV --scope=setup,plugins,config,agents,apikey
```

This is simpler than creating a custom init script but uses default object names.

##### Option 3: Deploy With Init But Without Admin Scope

```bash
# Have an administrator run init scope once
./deploy.sh $ENV --scope=init --options=manual --output-file=init-script.sql
# Review init-script.sql and execute it as ACCOUNTADMIN

# Deploy all components except admin scope
./deploy.sh $ENV --scope=setup,plugins,config,agents
```

**Important:** Without the admin scope, you must manually grant required privileges:

- Grant `MONITOR` privilege on warehouses to `DTAGENT_VIEWER` for query_history plugin
- Grant `MONITOR` privilege on dynamic tables to `DTAGENT_VIEWER` for dynamic_tables plugin
- Other plugin-specific privileges as documented in each plugin's configuration

##### Option 4: Split Deployment by Scope (With Admin)

Have an administrator with `ACCOUNTADMIN` privileges run the `init` scope once to create the base roles and database:

```bash
./deploy.sh $ENV --scope=init --options=manual --output-file=init-script.sql
# Review init-script.sql and execute it as ACCOUNTADMIN
```

Then, run the admin scope to create `DTAGENT_ADMIN` and set up automated privilege grants:

```bash
./deploy.sh $ENV --scope=admin
```

Finally, have a user with `DTAGENT_OWNER` role run the remaining scopes:

```bash
# As a user granted DTAGENT_OWNER role
./deploy.sh $ENV --scope=setup,plugins,config,agents,apikey
```

##### Option 5: Separate Admin Operations (Alternative)

Similarly, you can separate the `admin` scope (which requires `DTAGENT_ADMIN` privileges for granting monitoring permissions) from other operations:

```bash
# Have an administrator run admin scope
./deploy.sh $ENV --scope=admin --options=manual --output-file=admin-script.sql
# Review and execute as DTAGENT_ADMIN or ACCOUNTADMIN

# Regular deployment without admin operations
./deploy.sh $ENV --scope=setup,plugins,config,agents
```

This approach allows organizations to maintain strict separation of duties while still deploying and maintaining Dynatrace Snowflake Observability Agent effectively.

### Dynatrace API Token Setup

You should store the Access Token for your Dynatrace tenant (to which you want to send telemetry from your environment) as the environment
variable `DTAGENT_TOKEN`. The token should have the following scopes enabled:

| Scope ID                    | Scope Name                   | API                          | Comment |
| --------------------------- | ---------------------------- | ---------------------------- | ------- |
| `logs.ingest`               | Ingest Logs                  | `/api/v2/otlp/v1/logs`       |         |
| `metrics.ingest`            | Ingest Metrics               | `/api/v2/metrics/ingest`     |         |
| `bizevents.ingest`          | Ingest BizEvents             | `/api/v2/bizevents/ingest`   |         |
| `openpipeline.events`       | OpenPipeline - Ingest Events | `/platform/ingest/v1/events` |         |
| `openTelemetryTrace.ingest` | Ingest OpenTelemetry Traces  | `/api/v2/otlp/v1/traces`     |         |
| `events.ingest`             | Ingest Events                | `/api/v2/events/ingest`      | <0.9.1  |

We **strongly** recommend to ensure your token is not recorded in shell script history; please find an example how to define `DTAGENT_TOKEN`
environment variable on Linux or WSL below:

```bash
export HISTCONTROL=ignorespace
# make sure to put the space before the next command to ensure that the TOKEN is not recorded in bash history
 export DTAGENT_TOKEN="dynatrace-token"
```

If you do not set the `DTAGENT_TOKEN` environment variable, or if it does not contain a valid token value:

- The Dynatrace Snowflake Observability Agent deployment process **WILL NOT** send self-monitoring BizEvents to your Dynatrace tenant to
  mark the start and finish of the deployment process.
- The deployment process _is not able_ to set `DTAGENT_API_KEY` when deploying the complete configuration (`./deploy.sh $config_name`)
  or when updating just the API key (`./deploy.sh $config_name apikey`). In these cases, **YOU WILL** be prompted to provide the correct
  `DTAGENT_TOKEN` value during deployment.
- The deployment process _will not be able_ to send BizEvents to your Dynatrace tenant to mark the start and finish of the deployment
  process.

No additional objects need to be provided for the deployment process on the Snowflake side. Dynatrace Snowflake Observability Agent will
build a database to store his information - `DTAGENT_DB` by default or `DTAGENT_{$core.tag}_DB` if tag is provided (see
[Multitenancy](#multitenancy)).

The complete log of deployment and the script executed during deployment is available as
`.logs/dsoa-deploy-log-$config_name-$current_date.sql`.

> **Troubleshooting:** If tasks are running in Snowflake but no data appears in Dynatrace, please refer to
> [Troubleshooting: No Data in Dynatrace](docs/debug/no-data-in-dt/readme.md) for a comprehensive debugging guide.

## Setting up a profile

Before you deploy Dynatrace Snowflake Observability Agent to Snowflake, you need to configure a profile with necessary information to
establish connection between single Snowflake account and single Dynatrace account. Dynatrace Snowflake Observability Agent enables to send
telemetry from multiple Snowflake accounts to one or multiple (see [Multitenancy](#multitenancy)) Dynatrace account. You will need to create
a profile configuration file for each Snowflake-Dynatrace pair.

### Creating profile configuration file for Snowflake-Dynatrace connection

You must create the deployment configuration file in the `conf/` directory. The file must follow `config-$config_name.yml` naming
convention and the content as presented in the `conf/config-template.yml` template. Make sure the `core` entries; you can skip the rest.
Optionally you can adjust plugin configurations.

#### Core Configuration Options

The following table describes all available `core` configuration options:

| Configuration Key                                | Type    | Required    | Default                   | Description                                                                                                                                                                                                                                                                                                                          |
| ------------------------------------------------ | ------- | ----------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `dynatrace_tenant_address`                       | String  | Yes         | -                         | The address of your Dynatrace tenant (e.g., `abc12345.live.dynatrace.com`)                                                                                                                                                                                                                                                           |
| `deployment_environment`                         | String  | Yes         | -                         | Unique identifier for the deployment environment                                                                                                                                                                                                                                                                                     |
| `log_level`                                      | String  | Yes         | `WARN`                    | Logging level. Valid values: `DEBUG`, `INFO`, `WARN`, `ERROR`                                                                                                                                                                                                                                                                        |
| `tag`                                            | String  | No          | `""`                      | Optional custom tag for Dynatrace Snowflake Observability Agent specific Snowflake objects. Used for multitenancy scenarios. **INFO:** if tag is a number put it in quotes, e.g., `tag: "093"`, to ensure it is interpreted as text.                                                                                                 |
| `procedure_timeout`                              | Integer | No          | 3600                      | Timeout in seconds for stored procedure execution. Default is 1 hour (3600 seconds)                                                                                                                                                                                                                                                  |
| **Snowflake Configuration**                      |         |             |                           |                                                                                                                                                                                                                                                                                                                                      |
| `snowflake.account_name`                         | String  | Recommended | (auto-detected)           | Your Snowflake account identifier in format `orgname-accountname` (e.g., `myorg-myaccount`). If not provided, will be auto-detected via SQL query at startup (adds ~100ms startup time). Legacy format `account.region` also supported. See [Account identifiers](https://docs.snowflake.com/en/user-guide/admin-account-identifier) |
| `snowflake.host_name`                            | String  | No          | (derived)                 | Your Snowflake host name (e.g., `myorg-myaccount.snowflakecomputing.com`). If not provided or set to "-", will be automatically derived from `account_name` or auto-detected                                                                                                                                                         |
| `snowflake.database.name`                        | String  | No          | `DTAGENT_DB`              | Custom name for the Dynatrace agent database. Empty or missing value uses default                                                                                                                                                                                                                                                    |
| `snowflake.database.data_retention_time_in_days` | Integer | No          | 1                         | Data retention time in days for permanent tables in the database. Does not affect transient tables which always have 0-day retention                                                                                                                                                                                                 |
| `snowflake.warehouse.name`                       | String  | No          | `DTAGENT_WH`              | Custom name for the Dynatrace agent warehouse. Empty or missing value uses default                                                                                                                                                                                                                                                   |
| `snowflake.resource_monitor.name`                | String  | No          | `DTAGENT_RS`              | Custom name for the resource monitor. Empty/missing uses default, `"-"` skips creation (**see note below**)                                                                                                                                                                                                                          |
| `snowflake.resource_monitor.credit_quota`        | Integer | Yes         | 5                         | Credit quota limit for Snowflake operations                                                                                                                                                                                                                                                                                          |
| `snowflake.roles.owner`                          | String  | No          | `DTAGENT_OWNER`           | Custom name for the owner role. Empty or missing value uses default                                                                                                                                                                                                                                                                  |
| `snowflake.roles.admin`                          | String  | No          | `DTAGENT_ADMIN`           | Custom name for the admin role. Empty/missing uses default, `"-"` skips creation (**see note below**)                                                                                                                                                                                                                                |
| `snowflake.roles.viewer`                         | String  | No          | `DTAGENT_VIEWER`          | Custom name for the viewer role. Empty or missing value uses default                                                                                                                                                                                                                                                                 |
| `snowflake.api_integration.name`                 | String  | No          | `DTAGENT_API_INTEGRATION` | Custom name for the external access integration. Empty or missing value uses default. **Note:** Unlike admin role and resource monitor, the API integration is required for agent operation                                                                                                                                          |

> **Note on Optional Objects**: When `snowflake.roles.admin` or `snowflake.resource_monitor.name` is set to `"-"`, the corresponding object will not be created during deployment. All SQL code related to these objects will be automatically excluded from the deployment script. If you set `snowflake.roles.admin` to `"-"`, you cannot use the `admin` deployment scope as it requires the admin role to exist.
>
> **Required Objects**: The following objects are always required and cannot be skipped: database, warehouse, owner role, viewer role, and API integration. These are essential for agent operation.

#### Custom Object Names

By default, Dynatrace Snowflake Observability Agent creates Snowflake objects with standard names (e.g., `DTAGENT_DB`, `DTAGENT_WH`, `DTAGENT_OWNER`, `DTAGENT_API_INTEGRATION`). You can customize these names using the configuration options described above. This feature is useful when:

- You need to comply with organizational naming conventions
- You want to avoid naming conflicts with existing objects
- You prefer more descriptive or context-specific names
- **You want to pre-create objects and deploy without elevated privileges** (see use case below)

##### Use Case: Deploying Without Admin Rights

Custom object names enable a deployment model where database administrators pre-create all necessary Snowflake objects, allowing the agent to be deployed without requiring `ACCOUNTADMIN` or elevated privileges:

1. **Pre-creation Phase** (performed by DBA with ACCOUNTADMIN):
   - Create custom-named database, warehouse, resource monitor, roles, and API integration
   - Grant necessary privileges to the owner role
   - Set up the required object structure

2. **Deployment Phase** (can be performed by regular user with owner role):
   - Configure custom names to match pre-created objects
   - Deploy using restricted scopes: `--scope=setup,plugins,config,apikey`
   - Skip `init` and `admin` scopes entirely

This approach is ideal for organizations with strict privilege separation policies where regular users should not have `ACCOUNTADMIN` access.

###### Example Configuration

```yaml
core:
  deployment_environment: prod
  snowflake:
    # Recommended: Use organization-account format
    account_name: myorg-myaccount
    host_name: "-"  # Will be derived as myorg-myaccount.snowflakecomputing.com

    # Alternative: Legacy locator format
    # account_name: myaccount.us-east-1
    # host_name: myaccount.us-east-1.snowflakecomputing.com
    database:
      name: DT_MONITORING_DB
    warehouse:
      name: DT_MONITORING_WH
    resource_monitor:
      name: DT_MONITORING_RS  # or "-" if pre-created separately
    roles:
      owner: DT_MONITORING_OWNER
      admin: "-"  # Skip admin role - privileges granted manually by DBA
      viewer: DT_MONITORING_VIEWER
    api_integration:
      name: DT_MONITORING_API_INTEGRATION
```

###### Deployment Command

```bash
# Deploy without init/admin scopes (no ACCOUNTADMIN required)
./deploy.sh prod --scope=setup,plugins,config,agents,apikey
```

##### Validation Rules

Custom names must follow Snowflake identifier rules:

- Can contain only letters (A-Z, a-z), numbers (0-9), underscores (_), and dollar signs ($)
- Must start with a letter or underscore (not a number)
- Cannot contain spaces or special characters
- Maximum length is 255 characters
- Names are case-insensitive in Snowflake

The deployment script will validate all custom names before proceeding. If validation fails, the deployment will stop with an error message.

##### Supported Installation Scenarios

The agent supports various installation paths depending on your organizational requirements and privilege constraints:

| Scenario                              | Required Objects          | Optional Objects                    | Configuration                               | Deployment Scopes                                          |
| ------------------------------------- | ------------------------- | ----------------------------------- | ------------------------------------------- | ---------------------------------------------------------- |
| **Standard Full Install**             | All defaults              | Admin role + Resource monitor       | Default names, no TAG                       | `all` or `init,admin,setup,plugins,config,agents,apikey`   |
| **Standard Without Optional**         | Defaults                  | Admin: `-`<br>Resource monitor: `-` | Set to `"-"` in config                      | `init,setup,plugins,config,agents,apikey` (skip `admin`)   |
| **TAG-based Multitenancy**            | Defaults with TAG suffix  | Admin + Resource monitor            | TAG only (e.g., `tag: TNA`)                 | `all` or `init,admin,setup,plugins,config,agents,apikey`   |
| **Custom Names Full**                 | Custom names for all      | Admin + Resource monitor            | Custom names in config                      | `init,admin,setup,plugins,config,agents,apikey`            |
| **Custom Names Without Optional**     | Custom names              | Admin: `-`<br>Resource monitor: `-` | Custom names + `"-"` for optional           | `init,setup,plugins,config,agents,apikey`                  |
| **Custom Names + TAG (Multitenancy)** | Custom names              | Admin + Resource monitor            | Custom names + TAG (TAG for telemetry only) | `init,admin,setup,plugins,config,agents,apikey`            |
| **Pre-Created Objects (Full)**        | DBA creates all           | Admin + Resource monitor            | Match pre-created names                     | `setup,plugins,config,agents,apikey` (skip `init`,`admin`) |
| **Pre-Created Objects (Minimal)**     | DBA creates required only | Skip both                           | Match required names, `"-"` for optional    | `setup,plugins,config,agents,apikey`                       |
| **Pre-Created + TAG**                 | DBA creates custom names  | Admin + Resource monitor            | Match pre-created names + TAG for telemetry | `setup,plugins,config,agents,apikey`                       |

**Required Objects (Cannot be skipped):**

- Database (`DTAGENT_DB` or custom)
- Warehouse (`DTAGENT_WH` or custom)
- Owner Role (`DTAGENT_OWNER` or custom)
- Viewer Role (`DTAGENT_VIEWER` or custom)
- API Integration (`DTAGENT_API_INTEGRATION` or custom)

**Optional Objects (Can be skipped with `"-"`):**

- Admin Role (`DTAGENT_ADMIN` or custom or `"-"`)
- Resource Monitor (`DTAGENT_RS` or custom or `"-"`)

When admin role is skipped (`"-"`), you must manually grant required privileges:

- `MONITOR` on warehouses (for `query_history` plugin)
- `MONITOR` on dynamic tables (for `dynamic_tables` plugin)
- Plugin-specific privileges as documented

##### TAG and Custom Names Interaction

The `tag` and custom object names can be used together or separately:

###### Scenario 1: TAG only (no custom names)

- Object naming: `DTAGENT_DB` → `DTAGENT_<TAG>_DB`
- Telemetry: Includes `deployment.environment.tag: "<TAG>"`
- Use case: Simple multitenancy with automatic object name suffixing

###### Scenario 2: Custom names only (no TAG)

- Object naming: Uses your custom names exactly as specified
- Telemetry: Only `deployment.environment` (no tag dimension)
- Use case: Single instance with organizational naming conventions

###### Scenario 3: Both TAG and custom names

- Object naming: Uses custom names where provided, defaults for others (TAG does NOT affect object names at all)
- Telemetry: Includes both `deployment.environment` and `deployment.environment.tag: "<TAG>"`
- Logger name: `DTAGENT_<TAG>_OTLP` (e.g., `DTAGENT_TENANT_A_OTLP`)
- Use case: Custom naming conventions + multitenancy tracking in telemetry

**Key principle:** When ANY custom name is provided, TAG is disabled for ALL object naming. TAG only affects:

1. Telemetry dimension: `deployment.environment.tag`
2. Logger name: `DTAGENT_<TAG>_OTLP`

**Example combining both:**

```yaml
core:
  deployment_environment: PRODUCTION_US_EAST
  tag: TENANT_A  # Only for telemetry tracking

  snowflake:
    database:
      name: "ACME_MONITORING_DB"  # Custom name used (not DTAGENT_TENANT_A_DB)
    warehouse:
      name: "ACME_MONITORING_WH"
    roles:
      owner: "ACME_MONITORING_OWNER"
      viewer: "ACME_MONITORING_VIEWER"
    api_integration:
      name: "ACME_MONITORING_API"
```

This creates:

- Database: `ACME_MONITORING_DB` (custom name)
- Warehouse: `ACME_MONITORING_WH` (custom name)
- Owner role: `ACME_MONITORING_OWNER` (custom name)
- Viewer role: `ACME_MONITORING_VIEWER` (custom name)
- API Integration: `ACME_MONITORING_API` (custom name)
- Admin role: `DTAGENT_ADMIN` (default - NOT `DTAGENT_TENANT_A_ADMIN`)
- Resource Monitor: `DTAGENT_RS` (default - NOT `DTAGENT_TENANT_A_RS`)
- Logger name: `DTAGENT_TENANT_A_OTLP`
- Telemetry: `deployment.environment: "PRODUCTION_US_EAST"`, `deployment.environment.tag: "TENANT_A"`

**Note:** Once any custom name is used, TAG no longer affects object naming for ANY object (even those without custom names).

#### Plugin Configuration Options

The `plugins` section allows you to configure plugin behavior globally and individually:

| Configuration Key                 | Type    | Default | Description                                                                                                                                        |
| --------------------------------- | ------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.disabled_by_default`     | Boolean | `false` | When set to `true`, all plugins are disabled by default unless explicitly enabled                                                                  |
| `plugins.deploy_disabled_plugins` | Boolean | `true`  | Deploy plugin code even if the plugin is disabled. When `true`, disabled plugins' SQL objects and procedures are deployed but not scheduled to run |

Each individual plugin can be configured with plugin-specific options. See the plugin documentation for available configuration options per plugin.

#### OpenTelemetry Configuration Options

The `otel` section allows you to configure OpenTelemetry behavior. By default, you can leave this section empty (`otel: {}`) to use default values. Advanced users can configure the following options:

| Configuration Key                      | Type           | Default | Description                                                                |
| -------------------------------------- | -------------- | ------- | -------------------------------------------------------------------------- |
| `max_consecutive_api_fails`            | Integer        | -       | Maximum number of consecutive API failures before circuit breaker triggers |
| `logs.export_timeout_millis`           | Integer        | -       | Export timeout for logs in milliseconds                                    |
| `logs.max_export_batch_size`           | Integer        | -       | Maximum batch size for log exports                                         |
| `logs.is_disabled`                     | Boolean        | `false` | Disable log telemetry export                                               |
| `spans.export_timeout_millis`          | Integer        | -       | Export timeout for spans in milliseconds                                   |
| `spans.max_export_batch_size`          | Integer        | -       | Maximum batch size for span exports                                        |
| `spans.max_event_count`                | Integer        | -       | Maximum number of events per span                                          |
| `spans.max_attributes_per_event_count` | Integer        | -       | Maximum number of attributes per event                                     |
| `spans.max_span_attributes`            | Integer        | -       | Maximum number of attributes per span                                      |
| `spans.is_disabled`                    | Boolean        | `false` | Disable span telemetry export                                              |
| `metrics.api_post_timeout`             | Integer        | -       | API POST timeout for metrics in seconds                                    |
| `metrics.max_retries`                  | Integer        | -       | Maximum retry attempts for metrics export                                  |
| `metrics.max_batch_size`               | Integer        | -       | Maximum batch size for metrics                                             |
| `metrics.retry_delay_ms`               | Integer        | -       | Delay between retries in milliseconds                                      |
| `metrics.is_disabled`                  | Boolean        | `false` | Disable metrics telemetry export                                           |
| `events.api_post_timeout`              | Integer        | -       | API POST timeout for events in seconds                                     |
| `events.max_retries`                   | Integer        | -       | Maximum retry attempts for events export                                   |
| `events.max_payload_bytes`             | Integer        | -       | Maximum payload size for events in bytes                                   |
| `events.max_event_count`               | Integer        | -       | Maximum number of events per batch                                         |
| `events.retry_delay_ms`                | Integer        | -       | Delay between retries in milliseconds                                      |
| `events.retry_on_status`               | Array[Integer] | -       | HTTP status codes that trigger retry                                       |
| `events.is_disabled`                   | Boolean        | `false` | Disable events telemetry export                                            |
| `davis_events.api_post_timeout`        | Integer        | -       | API POST timeout for Davis events in seconds                               |
| `davis_events.max_retries`             | Integer        | -       | Maximum retry attempts for Davis events export                             |
| `davis_events.retry_delay_ms`          | Integer        | -       | Delay between retries in milliseconds                                      |
| `davis_events.is_disabled`             | Boolean        | `false` | Disable Davis events telemetry export                                      |
| `biz_events.api_post_timeout`          | Integer        | -       | API POST timeout for business events in seconds                            |
| `biz_events.max_retries`               | Integer        | -       | Maximum retry attempts for business events export                          |
| `biz_events.max_payload_bytes`         | Integer        | -       | Maximum payload size for business events in bytes                          |
| `biz_events.max_event_count`           | Integer        | -       | Maximum number of business events per batch                                |
| `biz_events.retry_delay_ms`            | Integer        | -       | Delay between retries in milliseconds                                      |
| `biz_events.retry_on_status`           | Array[Integer] | -       | HTTP status codes that trigger retry                                       |
| `biz_events.is_disabled`               | Boolean        | `false` | Disable business events telemetry export                                   |

#### Plugin Scheduling

One of the configuration options for each Dynatrace Snowflake Observability Agent plugin is the `schedule`, which determines when the
Snowflake task responsible for executing this plugin should start. By default, the majority of tasks are scheduled to execute on the hour or
half hour to increase warehouse utilization and reduce costs. Dynatrace Snowflake Observability Agent allows you to configure the schedule
for each plugin separately using one of three formats:

- CRON format: `USING CRON */30 * * * * UTC`
- Interval format: `30 MINUTES`
- Task graph definition: `after DTAGENT_DB.APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS`

> **NOTE:** Due to Snowflake limitations, using task graph definition (`AFTER`) requires all tasks in one graph to be owned by the same
> role.

#### Multitenancy

If you want to deliver telemetry from one Snowflake account to multiple Dynatrace tenants, or require different configurations and schedules
for some plugins, you can deploy multiple Dynatrace Snowflake Observability Agent instances on the same Snowflake account.

**Requirements for each instance:**

1. **Unique `deployment_environment`** - Identifies the instance in Dynatrace telemetry
2. **Unique Snowflake object names** - Either via `tag` OR custom names to prevent conflicts
3. **Unique Snowflake CLI connection** - Named `snow_agent_<deployment_environment_lowercase>`

**Two approaches for object naming:**

Approach 1: Using TAG (simpler)

- `tag` automatically suffixes all Snowflake object names
- Example: `tag: TNA` creates `DTAGENT_TNA_DB`, `DTAGENT_TNA_WH`

Approach 2: Using custom names (more control)

- Specify custom names for each object
- Optionally include `tag` for telemetry tracking (doesn't affect object names)

**Important distinctions:**

- `deployment_environment` → Used for telemetry dimensions in Dynatrace (e.g., `PRODUCTION_TENANT_A`)
- `tag` → When used alone: suffixes Snowflake object names (e.g., `TNA` creates `DTAGENT_TNA_DB`)
- `tag` with custom names → Only appears in telemetry as `deployment.environment.tag`, does NOT modify object names
- `deployment_environment` and `tag` serve **different purposes** and should NOT be combined in the value

**Valid multitenancy configuration (TAG approach):**

```yaml
# File: conf/config-prod-tenant-a.yml
core:
  deployment_environment: PRODUCTION_TENANT_A  # Unique telemetry identifier
  tag: TNA                                      # Unique object suffix
  dynatrace_tenant_address: tenant-a.live.dynatrace.com
  # ... other config
```

```yaml
# File: conf/config-prod-tenant-b.yml
core:
  deployment_environment: PRODUCTION_TENANT_B  # Different from tenant A
  tag: TNB                                      # Different from tenant A
  dynatrace_tenant_address: tenant-b.live.dynatrace.com
  # ... other config
```

**Valid multitenancy configuration (custom names approach):**

```yaml
# File: conf/config-prod-tenant-a.yml
core:
  deployment_environment: PRODUCTION_TENANT_A
  tag: TNA  # Optional: for telemetry only
  dynatrace_tenant_address: tenant-a.live.dynatrace.com

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

```yaml
# File: conf/config-prod-tenant-b.yml
core:
  deployment_environment: PRODUCTION_TENANT_B
  tag: TNB  # Optional: for telemetry only
  dynatrace_tenant_address: tenant-b.live.dynatrace.com

  snowflake:
    database:
      name: ACME_TENANT_B_DB
    warehouse:
      name: ACME_TENANT_B_WH
    roles:
      owner: ACME_TENANT_B_OWNER
      viewer: ACME_TENANT_B_VIEWER
    api_integration:
      name: ACME_TENANT_B_API
```

**Deploy both instances:**

```bash
# Setup connections for both
./setup.sh prod-tenant-a  # Creates: snow_agent_production_tenant_a
./setup.sh prod-tenant-b  # Creates: snow_agent_production_tenant_b

# Deploy both
./deploy.sh prod-tenant-a  # Uses: snow_agent_production_tenant_a, creates: DTAGENT_TNA_*
./deploy.sh prod-tenant-b  # Uses: snow_agent_production_tenant_b, creates: DTAGENT_TNB_*
```

**Critical warnings:**

❌ **Never reuse `deployment_environment` across instances** - This causes:

- Indistinguishable telemetry in Dynatrace
- Confusion about which instance generated which data

❌ **Never reuse `tag` across instances** - This causes:

- Snowflake object naming conflicts
- Data corruption as instances overwrite each other's tables
- Deployment failures

❌ **Don't include tag in `deployment_environment`** - They serve different purposes:

```yaml
# ❌ Wrong:
deployment_environment: PRODUCTION_TNA  # Don't mix concerns
tag: TNA

# ✅ Correct:
deployment_environment: PRODUCTION_TENANT_A  # Logical environment name
tag: TNA                                      # Separate object suffix
```

You can specify the configuration for each instance in separate configuration files (as shown above) or use multi-configuration deployment described below.

## Setting up connection to Snowflake

You must configure Snowflake CLI connection profiles for deployment. The connection profile name **must** follow this pattern: `snow_agent_<deployment_environment_in_lowercase>`

**The connection profile name is derived from `deployment_environment` inside your config file, NOT from the `$ENV` parameter you use when running scripts.**

The user configured in the connection profile must be able to assume the `ACCOUNTADMIN` role on the target Snowflake account.

### Automatic Connection Setup (Recommended)

Running `./setup.sh $ENV` will:

1. Read `core.deployment_environment` from `conf/config-$ENV.yml`
2. Convert it to lowercase
3. Check if `snow_agent_<deployment_environment_lowercase>` exists
4. Prompt you to create it if it doesn't exist

```bash
# Example: For config-prod-useast.yml with deployment_environment: "PRODUCTION_US_EAST_1"
./setup.sh prod-useast

# Output:
# Checking connection profile for PRODUCTION_US_EAST_1...
# WARNING: No Dynatrace Snowflake Observability Agent connection is defined for the PRODUCTION_US_EAST_1 environment. Creating it now...
#
# This will create: snow_agent_production_us_east_1
```

### Manual Connection Setup

If you need to create the connection manually, first determine the correct name:

```bash
# Step 1: Find your deployment_environment value
yq -r '.core.deployment_environment' conf/config-$ENV.yml

# Example output: PRODUCTION_US_EAST_1

# Step 2: Convert to lowercase and add prefix
# Connection name: snow_agent_production_us_east_1

# Step 3: Create the connection
snow connection add --connection-name snow_agent_production_us_east_1
```

### Verifying Your Connections

To list currently configured connections:

```bash
snow connection list
```

You should see connection names like:

```text
snow_agent_production
snow_agent_production_us_east_1
snow_agent_test_tenant_001
```

### Connection Configuration Example

When creating a connection, use external browser authentication for SSO (recommended):

**Important:** The `Snowflake account name` prompt in the `snow connection add` command asks for your **account identifier**, which should match your `account_name` in the config file.

```bash
# Recommended format (orgname-accountname):
Snowflake account name: myorg-myaccount
Snowflake username: john.doe@company.com
Snowflake password [optional]:
Role for the connection [optional]:
Database for the connection [optional]:
Schema for the connection [optional]:
Connection host [optional]:
Connection port [optional]:
Snowflake region [optional]:
Authentication method [optional]: externalbrowser
Path to private key file [optional]:
```

**Complete command example** (for automated setups):

```bash
# For config with deployment_environment: "PRODUCTION_US_EAST_1"
# Using recommended orgname-accountname format
snow connection add \
  --connection-name snow_agent_production_us_east_1 \
  --account myorg-myaccount \
  --user john.doe@company.com \
  --authenticator externalbrowser
```

**Important:** The connection name must exactly match `snow_agent_` + your `deployment_environment` value in lowercase.

### Understanding Snowflake Account Identifiers

Snowflake supports two formats for account identifiers, which can cause confusion:

#### Recommended Format: Organization-Account Name (`orgname-accountname`)

**Example:** `myorg-myaccount`

This is the **preferred** modern format that Snowflake recommends using. It consists of:

- Your organization name (`myorg`)
- Your account name (`myaccount`)
- Connected with a hyphen

**Advantages:**

- Clear, human-readable account identification
- Works consistently across all Snowflake regions
- Provides a meaningful account name in telemetry (e.g., Dynatrace dimensions)

#### Legacy Format: Account Locator (`account.region`)

**Example:** `abc12345.us-east-1`

This is the **legacy** format that uses:

- A randomly-generated account locator (`abc12345`)
- The region identifier (`us-east-1`)

**Disadvantages:**

- Account locator is a random string that's hard to remember
- Less meaningful in monitoring and telemetry
- Considered legacy by Snowflake (though still supported)

#### Configuration Best Practices

**Recommended configuration (provides best performance):**

```yaml
core:
  snowflake:
    account_name: myorg-myaccount  # Clear, meaningful identifier
    host_name: "-"                 # Auto-derived: myorg-myaccount.snowflakecomputing.com
```

**Minimal configuration (auto-detects at startup with ~100ms overhead):**

```yaml
core:
  snowflake:
    account_name: "-"  # Will query Snowflake: CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME()
    host_name: "-"     # Will be derived from auto-detected account_name
```

**Why provide account_name?**

- ✅ **Faster startup**: Avoids SQL query during agent initialization
- ✅ **Explicit configuration**: Clear documentation of which account is being monitored
- ✅ **Offline validation**: Can validate config without connecting to Snowflake

**When to use auto-detection:**

- Running in multiple environments with different accounts
- Dynamic/automated deployments where account isn't known in advance
- Simplified configuration (accepts ~100ms startup overhead)

**Legacy configuration (still supported):**

```yaml
core:
  snowflake:
    account_name: abc12345.us-east-1                # Account locator format
    host_name: abc12345.us-east-1.snowflakecomputing.com  # Must match
```

#### How to Find Your Account Identifier

To find your Snowflake account identifier, run this query in Snowflake:

```sql
-- Returns organization and account names
SELECT
  CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() as account_identifier,
  CURRENT_ACCOUNT() as account_locator,
  CURRENT_REGION() as region;
```

Example output:

```text
ACCOUNT_IDENTIFIER: myorg-myaccount
ACCOUNT_LOCATOR: abc12345
REGION: AWS_US_EAST_1
```

Use `ACCOUNT_IDENTIFIER` for your config (recommended) or construct the legacy format as `ACCOUNT_LOCATOR.REGION`.

#### Host Name Derivation

When `host_name` is not provided or set to `"-"`, it will be automatically derived:

- For `orgname-accountname` format: `orgname-accountname.snowflakecomputing.com`
- For `account.region` format: `account.region.snowflakecomputing.com`

This eliminates the need to manually specify both values and reduces configuration errors.

## Common Configuration Mistakes

### Mistake 1: Using Account Locator Without Understanding

**Symptom:** Random strings appear as account names in Dynatrace telemetry.

**Cause:** Using legacy account locator format (`abc12345.us-east-1`) instead of the meaningful organization-account format (`myorg-myaccount`).

**Wrong:**

```yaml
snowflake:
  account_name: abc12345.us-east-1  # Random locator - hard to identify in Dynatrace
```

**In Dynatrace, you'll see:**

```text
service.name: abc12345.us-east-1  # What account is this?
```

**Correct:**

```yaml
snowflake:
  account_name: myorg-myaccount  # Clear, meaningful identifier
```

**In Dynatrace, you'll see:**

```text
service.name: myorg-myaccount  # Clearly identifiable!
```

### Mistake 2: Connection Profile Name Mismatch

**Symptom:** Deployment fails with "Connection 'snow_agent_xxx' not found" error.

**Cause:** The Snowflake CLI connection profile name doesn't match your `deployment_environment`.

**Example of the problem:**

```yaml
# File: config-prod.yml
core:
  deployment_environment: PRODUCTION_US_EAST
```

```bash
# Wrong connection created:
snow connection add --connection-name snow_agent_prod  # ❌ Based on file name!

# Deployment fails because it looks for:
# snow_agent_production_us_east  # ✓ Based on deployment_environment!
```

**Solution:**

```bash
# Find the correct deployment_environment:
yq -r '.core.deployment_environment' conf/config-prod.yml
# Output: PRODUCTION_US_EAST

# Create matching connection (lowercase):
snow connection add --connection-name snow_agent_production_us_east

# Or use automatic setup:
./setup.sh prod
```

### Mistake 3: Confusing ENV with deployment_environment

**Symptom:** Trying to create connections or objects based on the file name instead of config values.

**Wrong approach:**

```bash
# File: config-prod-useast.yml
# Thinking: "I need snow_agent_prod-useast"  # ❌ Wrong!

snow connection add --connection-name snow_agent_prod-useast  # ❌ Wrong!
```

**Correct approach:**

```bash
# File: config-prod-useast.yml (this is just for file organization)
# Check what's INSIDE the file:
yq -r '.core.deployment_environment' conf/config-prod-useast.yml
# Output: PRODUCTION_US_EAST_1

# Create connection based on deployment_environment:
snow connection add --connection-name snow_agent_production_us_east_1  # ✓ Correct!
```

**Remember:**

- File name (`ENV` parameter) = Your organizational choice
- `deployment_environment` = What actually matters for connections and deployment

### Mistake 4: Reusing Tags or Deployment Environments

**Symptom:** Deployment fails, or instances overwrite each other's data.

**Cause:** Two configuration files use the same `tag` or `deployment_environment`.

**Wrong:**

```yaml
# File: config-prod-mt001.yml
core:
  deployment_environment: PRODUCTION  # ❌ Same!
  tag: MT001

# File: config-prod-mt002.yml
core:
  deployment_environment: PRODUCTION  # ❌ Same!
  tag: MT002
```

**Result:** Both instances send telemetry with the same `deployment.environment` dimension, making them indistinguishable in Dynatrace.

**Correct:**

```yaml
# File: config-prod-mt001.yml
core:
  deployment_environment: PRODUCTION_TENANT_001  # ✓ Unique!
  tag: MT001                                      # ✓ Unique!

# File: config-prod-mt002.yml
core:
  deployment_environment: PRODUCTION_TENANT_002  # ✓ Different!
  tag: MT002                                      # ✓ Different!
```

### Mistake 5: Including Tag in deployment_environment

**Symptom:** Redundant or confusing naming that mixes concerns.

**Wrong:**

```yaml
core:
  deployment_environment: PRODUCTION_MT001  # ❌ Tag included in environment name
  tag: MT001                                 # Redundant
```

**Why it's wrong:**

- `deployment_environment` is for logical environment identification in telemetry
- `tag` is for telemetry tracking and (when used without custom names) Snowflake object name disambiguation
- Mixing them in the environment name creates confusion and redundancy

**Correct Option 1 (TAG-based naming):**

```yaml
core:
  deployment_environment: PRODUCTION_US_EAST  # ✓ Logical environment
  tag: MT001                                   # ✓ Separate - affects object names
```

**This creates:**

- Telemetry dimension: `deployment.environment: "PRODUCTION_US_EAST"`
- Additional dimension: `deployment.environment.tag: "MT001"`
- Snowflake objects: `DTAGENT_MT001_DB`, `DTAGENT_MT001_WH`

**Correct Option 2 (Custom names + TAG for telemetry only):**

```yaml
core:
  deployment_environment: PRODUCTION_US_EAST
  tag: MT001  # Only for telemetry tracking

  snowflake:
    database:
      name: ACME_MONITORING_DB  # Custom name used
    # ... other custom names
```

**This creates:**

- Telemetry dimension: `deployment.environment: "PRODUCTION_US_EAST"`
- Additional dimension: `deployment.environment.tag: "MT001"`
- Snowflake objects: `ACME_MONITORING_DB` (custom names, TAG doesn't affect them)

### Mistake 6: Not Using Lowercase for Connection Names

**Symptom:** Connection not found even though you created it.

**Cause:** Snowflake CLI connection names are case-sensitive.

**Wrong:**

```bash
# Your deployment_environment: PRODUCTION_US_EAST
snow connection add --connection-name snow_agent_PRODUCTION_US_EAST  # ❌ Uppercase!
```

**Correct:**

```bash
# Always convert to lowercase:
snow connection add --connection-name snow_agent_production_us_east  # ✓ Lowercase!
```

**Tip:** The deployment scripts automatically convert `deployment_environment` to lowercase when looking for connections:

```bash
CONNECTION_ENV="${DEPLOYMENT_ENV,,}"  # Bash syntax for lowercase conversion
```

### Quick Diagnostic Commands

If you're experiencing issues, use these commands to diagnose:

```bash
# 1. Check what deployment_environment is in your config:
yq -r '.core.deployment_environment' conf/config-$ENV.yml

# 2. Check what connection name should be (lowercase):
yq -r '.core.deployment_environment' conf/config-$ENV.yml | tr '[:upper:]' '[:lower:]' | sed 's/^/snow_agent_/'

# 3. List your current connections:
snow connection list

# 4. Check if the required connection exists:
EXPECTED_CONN=$(yq -r '.core.deployment_environment' conf/config-$ENV.yml | tr '[:upper:]' '[:lower:]' | sed 's/^/snow_agent_/')
snow connection list | grep -q "$EXPECTED_CONN" && echo "✓ Connection exists" || echo "✗ Connection missing"
```
