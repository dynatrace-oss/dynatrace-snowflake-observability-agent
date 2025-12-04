# CI CD for Dynatrace Snowflake Observability Agent

Dynatrace Snowflake Observability Agent consists of a series of SQL scripts (accompanied by a few configuration files) that need to be
deployed to Snowflake by executing them in the correct order. In the context of manual deployment, this means either using a distribution
package or installing Dynatrace Snowflake Observability Agent from the source.

Part of the deployment process involves running scripts on the Snowflake database. Dynatrace Snowflake Observability Agent relies on the
Snowflake CLI utility, which can both create connections to the Snowflake instance and execute SQL scripts using those connections.

For the purpose of CI/CD operations, we need to enhance this process to avoid creating connection profiles and instead use a service user.
At the same time, we need to eliminate all interactive parts of the deployment to provide a fully automated experience.

## Preparation of the deployment artifact

As we are using a fully automated type of deployment and presumably deploying to more than one Snowflake instance, we need to prepare the
package for deployment in a specific way. This is done by executing the command to compile the source code:

```bash
./build.sh
```

and to prepare package

```bash
./package.sh full
```

The full argument ensures that the script used for deploying (./deploy.sh) will support deployment using a service user and non-interactive
mode. Once ./deploy.sh full is run, a new zip file containing all necessary code will be created, and it can be uploaded to the artifactory.

### Configuring Snowflake service user

For deploying the code, we are going to use a service user, which needs to be created in the target Snowflake instance. This user MUST have
the ACCOUNTADMIN role assigned directly. During deployment, credentials and host information are read from the following environment
variables, which need to be set:

```bash
SNOWFLAKE_USER_NAME=
SNOWFLAKE_PRIVATE_KEY_FILE=
SNOWFLAKE_ACC_NAME=
SNOWFLAKE_HOST_NAME=
```

### Configuring Dynatrace connection

Dynatrace Snowflake Observability Agent exports data to configured Dynatrace tenants. In this part, we configure the connection to Dynatrace
based on a combination of configuration files and environment variables. We create a new file following the `config-$environment.yaml` naming
convention, with content as presented in the conf/config-template.yaml template. We also need to set environment variables to specify the
connection to the Dynatrace tenant. The following variables need to be set:

```bash
ENVIRONMENT=
DTAGENT_TOKEN=
```

## Deploying the code

To the deploy code we execute:

```bash
 ./deploy.sh ${ENVIRONMENT} "" service_user skip_confirm
```

This specifies that the code will be deployed to $ENVIRONMENT using service user mode (reading connection data from the environment
variables) and not asking for any confirmation during the deployment. We also need to refresh the Dynatrace token used to connect to the
tenant. For that, we execute the following:

```bash
./deploy.sh ${ENVIRONMENT} apikey service_user skip_confirm
```
