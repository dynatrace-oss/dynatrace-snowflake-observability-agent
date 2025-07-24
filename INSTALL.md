# How to Install

Dynatrace Snowflake Observability Agent comes in the form of a series of SQL scripts (accompanied with a few configuration files), which need to be deployed at Snowflake by executing them in the correct order.

## Deploying Dynatrace Snowflake Observability Agent

The default option to install Dynatrace Snowflake Observability Agent is from the distribution package.
Should you require to install Dynatrace Snowflake Observability Agent from the sources, please check the [Installing Dynatrace Snowflake Observability Agent from sources](#installing-dynatrace-snowflake-observability-agent-from-sources) section before continuing here.
To deploy Dynatrace Snowflake Observability Agent, run the `./deploy.sh` command:

```bash
./deploy.sh $config_name $file_prefix
```

The `$config_name` parameter is required and must match one of the previously created configuration files.

The `$file_prefix` parameter is optional and can take multiple values:

* If left empty, all SQL scripts will be executed at once.
* If set to `config`, the configuration table will be updated using the config file specified by the `$config_name` parameter.
* If set to `apikey`, the Dynatrace Access Token (API Key) will be stored in Snowflake and made available only to the Dynatrace Snowflake Observability Agent stored procedure.
* If set to `manual`, a complete SQL script with all commands necessary to deploy and set up Dynatrace Snowflake Observability Agent will be produced; use the Snowflake Web UI to execute it.
* If set to `teardown`, Dynatrace Snowflake Observability Agent will be uninstalled from your Snowflake account.
* If set to any other value, only the files with base names starting with that `$file_prefix` will be executed as part of the deployment procedure.

You should store the Access Token for your Dynatrace tenant (to which you want to send telemetry from your environment) as the environment variable `DTAGENT_TOKEN`. The token should have the following scopes enabled:

* `logs.ingest`
* `metrics.ingest`
* `events.ingest`
* `bizevents.ingest`
* `openTelemetryTrace.ingest`

We **strongly** recommend to ensure your token is not recorded in shell script history; please find an example how to define `DTAGENT_TOKEN` environment variable on Linux or WSL below:

```bash
export HISTCONTROL=ignorespace
# make sure to put the space before the next command to ensure that the TOKEN is not recorded in bash history
 export DTAGENT_TOKEN="dynatrace-token"
```

If you do not set the `DTAGENT_TOKEN` environment variable, or if it does not contain a valid token value:

* The Dynatrace Snowflake Observability Agent deployment process **WILL NOT** send self-monitoring BizEvents to your Dynatrace tenant to mark the start and finish of the deployment process.
* The deployment process *will not be able* to set `DTAGENT_API_KEY` when deploying the complete configuration (`./deploy.sh $config_name`) or when updating just the API key (`./deploy.sh $config_name apikey`). In these cases, **YOU WILL** be prompted to provide the correct `DTAGENT_TOKEN` value during deployment.

No additional objects need to be provided for the deployment process on the Snowflake side. Dynatrace Snowflake Observability Agent will build a database to store his information - `DTAGENT_DB` by default or `DTAGENT_{TAG}_DB` if tag is provided (see [Multitenancy](#multitenancy)).

The complete log of deployment and the script executed during deployment is available as `.logs/dtagent-deploy-$config_name-$current_date.log`.

## Setting up a profile

Before you deploy Dynatrace Snowflake Observability Agent to Snowflake, you need to configure a profile with necessary information to establish connection between single Snowflake account and single Dynatrace account.
Dynatrace Snowflake Observability Agent enables to send telemetry from multiple Snowflake accounts to one or multiple (see [Multitenancy](#multitenancy)) Dynatrace account.
You will need to create a profile configuration file for each Snowflake-Dynatrace pair.

### Creating profile configuration file for Snowflake-Dynatrace connection

You must create the deployment configuration file in the `conf/` directory.
The file must follow `config-$config_name.json` naming convention and the content as presented in the `conf/config-template.json` template.
Make sure the `CORE` entries; you can skip the rest.
Optionally you can adjust plugin configurations.

One of the configuration options for each Dynatrace Snowflake Observability Agent plugin is the `SCHEDULE`, which determines when the Snowflake task responsible for executing this plugin should start.
By default, the majority of tasks are scheduled to execute on the hour or half hour to increase warehouse utilization and reduce costs.
Dynatrace Snowflake Observability Agent allows you to configure the schedule for each plugin separately using one of three formats:

* CRON format: `USING CRON */30 * * * * UTC`
* Interval format: `30 MINUTES`
* Task graph definition: `after DTAGENT_DB.APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS`

> **NOTE:** Due to Snowflake limitations, using task graph definition (`AFTER`) requires all tasks in one graph to be owned by the same role.

#### Multi-configuration deployment

The configuration file is a JSON array containing multiple configuration definitions — one for each environment. This enables you to deploy to several environments, potentially with similar settings, in a single operation.

**HINT:** When specifying multiple configurations, the first configuration in the array serves as the base. All subsequent configurations inherit settings from the first, so you only need to specify the differences for each additional environment. This helps reduce duplication of common configuration values.

```jsonc
[
    {
        "CORE": {
            "DEPLOYMENT_ENVIRONMENT": "ENV1",
            /// ...
        },
        "OTEL": {
            /// ...
        },
        "PLUGINS": {
            /// ...
        }
    },
    {
        "CORE": {
            "DEPLOYMENT_ENVIRONMENT": "ENV2"
        }
    }
]
```

#### Multitenancy

If you want to deliver telemetry from one Snowflake account to multiple Dynatrace tenants, or require different configurations and schedules for some plugins, you can achieve this by creating configuration with multiple deployment environment (Dynatrace Snowflake Observability Agent instances) definitions. Specify a different `CORE.DEPLOYMENT_ENVIRONMENT` parameter for each instance. We **strongly** recommend also defining a unique `CORE.TAG` for each additional Dynatrace Snowflake Observability Agent instance running on the same Snowflake account.

Example:

```jsonc
[
    {
        //...
        "CORE": {
            //...
            "DEPLOYMENT_ENVIRONMENT": "TEST-MT001",
            //...
            "TAG": "MT001"
        },
        //...
    }
]
```

You can specify the configuration for each instance in a separate configuration file or use the multi-configuration deployment described above.

#### IMPORTANT

* Running `./deploy.sh $config_name` expects a `conf/config-$config_name.json` file with at least one configuration defined.
* If you have multiple `CORE.DEPLOYMENT_ENVIRONMENT` values specified in a single configuration file, you will need a [matching `snow connection` profile for each one](#setting-up-connection-to-snowflake).
* If you plan to deploy configurations that send telemetry to different Dynatrace tenants, **DO NOT** define the `DTAGENT_TOKEN` environment variable in advance; you will be prompted to provide it separately for each configuration as needed.

### Setting up connection to Snowflake

You must add a connection definition to Snowflake using the following command. The connection name must follow this pattern: `snow_agent_$config_name`. Only the required fields are necessary, as external authentication is used by default. These connection profiles are used **ONLY** during the deployment process.

To deploy Dynatrace Snowflake Observability Agent properly, the specified user must be able to assume the `ACCOUNTADMIN` role on the target Snowflake account.

**HINT:** Running `./setup.sh $config_name` or `./deploy.sh $config_name` will prompt you to create Snowflake connection profiles named `snow_agent_$ENV`, where `ENV` matches each `CORE.DEPLOYMENT_ENVIRONMENT` in your configuration. If these profiles do not exist, you will be prompted to create them.

**WARNING:** If you wish to use a different connection name or pattern, you must modify the `./deploy.sh` script and update the `--connection` parameter in the `snow sql` call.

```bash
snow connection add --connection-name snow_agent_$ENV
```

To list your currently defined connections run:

```bash
snow connection list
```

Here is an example of how to fill in the form to configure connection based on external browser authentication, which is a recommended way for users authenticating with external SSO:

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
snow connection add --connection-name snow_agent_$config_name --account ${YOUR_SNOWFLAKE_ACCOUNT_NAME.REGION_NAME} --user ${YOUR_USERNAME} --authenticator externalbrowser
```

If you have any issues setting up the connection check [the SnowCli documentation](https://docs.snowflake.com/en/user-guide/snowsql).

## Prerequisites

### Windows Subsystem for Linux

On Windows it is necessary to install Windows Subsystem for Linux before proceeding with the following steps. Dynatrace Snowflake Observability Agent must be executed through WSL to guarantee proper functioning: WSL version 2.0 or higher is recommended (see [Install WSL guide)](https://learn.microsoft.com/en-us/windows/wsl/install):

### MacOS

You will need `brew` installed and up to date (XCode) Command Line Tools.

To install `brew` go to [Brew installation](https://docs.brew.sh/Installation)
To update Command Line Tools you need to run

```bash
xcode-select --install
```

or go to Software Update in System Settings

## Installing Dynatrace Snowflake Observability Agent from sources

For the development purposes you can install Dynatrace Snowflake Observability Agent from sources.

### Getting local copy of Dynatrace Snowflake Observability Agent

To get the source code of Dynatrace Snowflake Observability Agent you will need `git` installed.
Run the following command:

```bash
git clone https://github.com/dynatrace-oss/dynatrace-snowflake-observability-agent.git
```

Otherwise you should receive a package with Dynatrace Snowflake Observability Agent named `dynatrace_snowflake_observability_agent-$version.zip` which you should unpack.

### Installing necessary software

You can simply run `./setup.sh` to install all necessary software on your MacOS or Ubuntu.

#### Creating virtual environment

Once you have Python (only versions 3.9 through 3.11 are supported) installed, it is a good practice to operate with Python code within a virtual environment (see [Virtual Environment Guide](https://docs.python.org/3/library/venv.html)). To create and active one run:

```bash
python -m venv .venv
source .venv/bin/activate
```

#### Installing required packages

Packages necessary to run the program should be installed using following commands.

We need [Snowflake CLI](https://github.com/snowflakedb/snowflake-cli) installed either via pipx

```bash
# if You do not have pipx installed, run
sudo apt install pipx
# with pipx installed, run
pipx install snowflake-cli-labs
```

or Homebrew (macOS only):

```bash
brew tap snowflakedb/snowflake-cli
brew install snowflake-cli
snow --help
```

Once this is done install the remaining Python packages:

```bash
pip install -r requirements.txt
```

Finally, you need to install few more development tools:

* [jq](https://github.com/jqlang/jq)

In Windows WSL / Ubuntu linux run:

```bash
sudo apt install jq
```

On macOS run:

```bash
brew install jq
```

* gawk

In Windows WSL / Ubuntu linux run:

```bash
sudo apt install gawk
```

On macOS run:

```bash
brew install gawk
```
