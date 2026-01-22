# How to Install

Dynatrace Snowflake Observability Agent comes in the form of a series of SQL scripts (accompanied with a few configuration files), which
need to be deployed at Snowflake by executing them in the correct order.

This document assumes you are installing from the distribution package (`dynatrace_snowflake_observability_agent-*.zip`). If you are a
developer and want to build from source, please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) guide.

## Prerequisites

Before you can deploy the agent, you need to ensure the following tools are installed on your system.

### Windows Users

On Windows, it is necessary to install Windows Subsystem for Linux (WSL) version 2.0 or higher. The deployment scripts must be run through
WSL. See [Install WSL guide](https://learn.microsoft.com/en-us/windows/wsl/install) for more details.

### All Users

You will need the following command-line tools:

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

## Deploying Dynatrace Snowflake Observability Agent

The default option to install Dynatrace Snowflake Observability Agent is from the distribution package. To deploy Dynatrace Snowflake
Observability Agent, run the `./deploy.sh` command:

```bash
./deploy.sh $ENV [--scope=SCOPE] [--from-version=VERSION] [--output-file=FILE] [--options=OPTIONS]
```

### Required Parameters

- **`$ENV`** (required): Environment identifier that must match one of the previously created configuration files. The file must be named `config-$ENV.yml` in the `conf/` directory.

### Optional Parameters

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

### Examples

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

##### Option 1: Manual Initialization Without Init or Admin Scopes (Most Restrictive)

Manually create the required roles and database structure, then skip both `init` and `admin` scopes entirely:

```bash
# Manually create roles and database as ACCOUNTADMIN:
# CREATE ROLE DTAGENT_OWNER;
# CREATE ROLE DTAGENT_VIEWER;
# GRANT ROLE DTAGENT_VIEWER TO ROLE DTAGENT_OWNER;
# CREATE DATABASE DTAGENT_DB;
# ...

# Deploy without init or admin scopes
./deploy.sh $ENV --scope=setup,plugins,config,agents
```

**Important:** Without init and admin scopes, you must manually create all required objects and grant privileges.

##### Option 2: Deploy With Init But Without Admin Scope

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

##### Option 3: Split Deployment by Scope (With Admin)

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
./deploy.sh $ENV --scope=setup
./deploy.sh $ENV --scope=plugins
./deploy.sh $ENV --scope=config
./deploy.sh $ENV --scope=agents
```

##### Option 4: Separate Admin Operations (Alternative)

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

| Scope ID                    | Scope Name                   | Comment |
| --------------------------- | ---------------------------- | ------- |
| `logs.ingest`               | Ingest Logs                  |         |
| `metrics.ingest`            | Ingest Metrics               |         |
| `bizevents.ingest`          | Ingest BizEvents             |         |
| `openpipeline.events`       | OpenPipeline - Ingest Events |         |
| `openTelemetryTrace.ingest` | Ingest OpenTelemetry Traces  |         |
| `events.ingest`             | Ingest Events                | <0.9.1  |

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

| Configuration Key                                | Type    | Required | Default          | Description                                                                                                                          |
| ------------------------------------------------ | ------- | -------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `dynatrace_tenant_address`                       | String  | Yes      | -                | The address of your Dynatrace tenant (e.g., `abc12345.live.dynatrace.com`)                                                           |
| `deployment_environment`                         | String  | Yes      | -                | Unique identifier for the deployment environment                                                                                     |
| `log_level`                                      | String  | Yes      | `WARN`           | Logging level. Valid values: `DEBUG`, `INFO`, `WARN`, `ERROR`                                                                        |
| `tag`                                            | String  | No       | `""`             | Optional custom tag for Dynatrace Snowflake Observability Agent specific Snowflake objects. Used for multitenancy scenarios          |
| `procedure_timeout`                              | Integer | No       | 3600             | Timeout in seconds for stored procedure execution. Default is 1 hour (3600 seconds)                                                  |
| **Snowflake Configuration**                      |         |          |                  |                                                                                                                                      |
| `snowflake.account_name`                         | String  | Yes      | -                | Your Snowflake account name                                                                                                          |
| `snowflake.host_name`                            | String  | Yes      | -                | Your Snowflake host name                                                                                                             |
| `snowflake.database.name`                        | String  | No       | `DTAGENT_DB`     | Custom name for the Dynatrace agent database. Empty or missing value uses default                                                    |
| `snowflake.database.data_retention_time_in_days` | Integer | No       | 1                | Data retention time in days for permanent tables in the database. Does not affect transient tables which always have 0-day retention |
| `snowflake.warehouse.name`                       | String  | No       | `DTAGENT_WH`     | Custom name for the Dynatrace agent warehouse. Empty or missing value uses default                                                   |
| `snowflake.resource_monitor.name`                | String  | No       | `DTAGENT_RS`     | Custom name for the resource monitor. Empty/missing uses default, `"-"` skips creation (**see note below**)                          |
| `snowflake.resource_monitor.credit_quota`        | Integer | Yes      | 5                | Credit quota limit for Snowflake operations                                                                                          |
| `snowflake.roles.owner`                          | String  | No       | `DTAGENT_OWNER`  | Custom name for the owner role. Empty or missing value uses default                                                                  |
| `snowflake.roles.admin`                          | String  | No       | `DTAGENT_ADMIN`  | Custom name for the admin role. Empty/missing uses default, `"-"` skips creation (**see note below**)                                |
| `snowflake.roles.viewer`                         | String  | No       | `DTAGENT_VIEWER` | Custom name for the viewer role. Empty or missing value uses default                                                                 |

> **Note on Optional Objects**: When `snowflake.roles.admin` or `snowflake.resource_monitor.name` is set to `"-"`, the corresponding object will not be created during deployment. All SQL code related to these objects will be automatically excluded from the deployment script. If you set `snowflake.roles.admin` to `"-"`, you cannot use the `admin` deployment scope as it requires the admin role to exist.

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
for some plugins, you can achieve this by creating configuration with multiple deployment environment (Dynatrace Snowflake Observability
Agent instances) definitions. Specify a different `core.deployment_environment` parameter for each instance. We **strongly** recommend also
defining a unique `core.tag` for each additional Dynatrace Snowflake Observability Agent instance running on the same Snowflake account.

Example:

```yaml
- core:
  deployment_environment: test-mt001
  tag: mt001
```

You can specify the configuration for each instance in a separate configuration file or use the multi-configuration deployment described
above.

### Setting up connection to Snowflake

You must add a connection definition to Snowflake using the following command. The connection name must follow this pattern:
`snow_agent_$config_name`. Only the required fields are necessary, as external authentication is used by default. These connection profiles
are used **ONLY** during the deployment process.

To deploy Dynatrace Snowflake Observability Agent properly, the specified user must be able to assume the `ACCOUNTADMIN` role on the target
Snowflake account.

**HINT:** Running `./setup.sh $config_name` or `./deploy.sh $config_name` will prompt you to create Snowflake connection profiles named
`snow_agent_$ENV`, where `ENV` matches each `core.deployment_environment` in your configuration. If these profiles do not exist, you will be
prompted to create them.

**WARNING:** If you wish to use a different connection name or pattern, you must modify the `./deploy.sh` script and update the
`--connection` parameter in the `snow sql` call.

```bash
snow connection add --connection-name snow_agent_$ENV
```

To list your currently defined connections run:

```bash
snow connection list
```

Here is an example of how to fill in the form to configure connection based on external browser authentication, which is a recommended way
for users authenticating with external SSO:

```bash
Snowflake account name: ${YOUR_SNOWFLAKE_ACCOUNT_NAME.REGION_NAME}
Snowflake username: ${YOUR_USERNAME}
Snowflake password [optional]:
Role for the connection [optional]:
Warehouse for the connection [optional]:
Database for the connection [optional]:
Schema for the connection [optional]:
Connection host [optional]:
Connection port [optional]:
Snowflake region [optional]:
Authentication method [optional]: externalbrowser
Path to private key file [optional]:
```

You can also run this command to fill in the required and recommended parts:

```bash
snow connection add --connection-name snow_agent_$config_name \
                    --account ${YOUR_SNOWFLAKE_ACCOUNT_NAME.REGION_NAME} \
                    --user ${YOUR_USERNAME} \
                    --authenticator externalbrowser
```

If you have any issues setting up the connection check [the SnowCli documentation](https://docs.snowflake.com/en/user-guide/snowsql).
