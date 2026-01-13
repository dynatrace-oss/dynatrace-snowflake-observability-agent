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
./deploy.sh $config_name $file_prefix
```

The `$config_name` parameter is required and must match one of the previously created configuration files.

The `$file_prefix` parameter is optional and can take multiple values:

- If left empty, all SQL scripts will be executed at once.
- If set to `config`, the configuration table will be updated using the config file specified by the `$config_name` parameter.
- If set to `apikey`, the Dynatrace Access Token (API Key) will be stored in Snowflake and made available only to the Dynatrace Snowflake
  Observability Agent stored procedure.
- If set to `manual`, a complete SQL script with all commands necessary to deploy and set up Dynatrace Snowflake Observability Agent will be
  produced; use the Snowflake Web UI to execute it.
- If set to `teardown`, Dynatrace Snowflake Observability Agent will be uninstalled from your Snowflake account.
- If set to any other value, only the files with base names starting with that `$file_prefix` will be executed as part of the deployment
  procedure.

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
`.logs/dsoa-deploy-$config_name-$current_date.log`.

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

| Configuration Key          | Type    | Required | Default | Description                                                                                                                 |
| -------------------------- | ------- | -------- | ------- | --------------------------------------------------------------------------------------------------------------------------- |
| `dynatrace_tenant_address` | String  | Yes      | -       | The address of your Dynatrace tenant (e.g., `abc12345.live.dynatrace.com`)                                                  |
| `deployment_environment`   | String  | Yes      | -       | Unique identifier for the deployment environment                                                                            |
| `snowflake_account_name`   | String  | Yes      | -       | Your Snowflake account name                                                                                                 |
| `snowflake_host_name`      | String  | Yes      | -       | Your Snowflake host name                                                                                                    |
| `snowflake_credit_quota`   | Integer | Yes      | 5       | Credit quota limit for Snowflake operations                                                                                 |
| `log_level`                | String  | Yes      | `WARN`  | Logging level. Valid values: `DEBUG`, `INFO`, `WARN`, `ERROR`                                                               |
| `tag`                      | String  | No       | `""`    | Optional custom tag for Dynatrace Snowflake Observability Agent specific Snowflake objects. Used for multitenancy scenarios |
| `procedure_timeout`        | Integer | No       | 3600    | Timeout in seconds for stored procedure execution. Default is 1 hour (3600 seconds)                                         |

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
