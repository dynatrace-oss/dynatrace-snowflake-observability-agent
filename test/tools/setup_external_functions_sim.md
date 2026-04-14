# External Functions Simulation Setup

Adds an AWS Lambda-backed Snowflake External Function to the Query Deep Dive simulation so that
dashboard tiles 15 and 16 (External Functions section) display real telemetry.

**Estimated time:** 20–30 minutes
**Estimated cost:** near-zero (Lambda free tier; XSMALL Snowflake warehouse)
**Prerequisites:** AWS account with permission to create Lambda functions, IAM roles, and API Gateway;
Snowflake `ACCOUNTADMIN` access on the test account.

---

## Overview

```text
SP_WORKLOAD_ROOT()
  └─ SELECT EF_ECHO(...)     ← Snowflake External Function
       └─ API Gateway (POST /echo)
            └─ Lambda (echo rows back)
```

Snowflake records `external_function_total_invocations`, `external_bytes_sent`, and
`external_bytes_received` in `QUERY_HISTORY` for any query that calls an external function.
The DSOA `query_history` plugin picks these up and emits them as telemetry, populating tiles 15–16.

---

## Part 1 — AWS: Create the Lambda function

### 1.1 Open Lambda in the AWS Console

1. Go to [https://console.aws.amazon.com/lambda](https://console.aws.amazon.com/lambda).
2. Make sure you are in the **us-east-1** region (top-right region selector) — this matches the
   Snowflake account `your_snowflake_test_account.us-east-1`.
3. Click **Create function**.

### 1.2 Configure the function

| Field               | Value                                               |
|---------------------|-----------------------------------------------------|
| Author from scratch | selected                                            |
| Function name       | `dsoa-ef-echo`                                      |
| Runtime             | Python 3.12                                         |
| Architecture        | x86\_64                                             |
| Execution role      | **Create a new role with basic Lambda permissions** |

Click **Create function**.

### 1.3 Paste the function code

In the **Code** tab, replace the contents of `lambda_function.py` with:

```python
# Copyright (c) 2025 Dynatrace Open Source — MIT License
# Snowflake External Function echo handler.
# Receives a Snowflake batch request and returns each row unchanged.
# Snowflake external function request format:
#   { "data": [ [row_number, col1, col2, ...], ... ] }
# Response format must mirror the same structure.
#
# Note: Snowflake signs requests with SigV4 via HTTP API Gateway (payload
# format v2.0). The body arrives base64-encoded AND gzip-compressed.
import base64
import gzip
import json


def lambda_handler(event, context):
    """Echo each input row back to Snowflake unchanged."""
    raw = event.get("body", "")
    if event.get("isBase64Encoded"):
        decoded = base64.b64decode(raw)
        # Snowflake gzip-compresses the body before base64-encoding it.
        if decoded[:2] == b"\x1f\x8b":
            decoded = gzip.decompress(decoded)
        raw = decoded.decode("utf-8")
    payload = json.loads(raw)

    rows = payload.get("data", [])
    response_rows = [[row[0], row[1]] for row in rows]

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"data": response_rows}),
    }
```

Click **Deploy**.

### 1.4 Test the function

Click **Test**, then **Create new test event**. Test with a plain JSON body first:

```json
{
  "body": "{\"data\": [[0, \"order-001\"], [1, \"order-002\"]]}",
  "isBase64Encoded": false
}
```

Click **Test**. The response body should be:

```json
{"data": [[0, "order-001"], [1, "order-002"]]}
```

Also test the base64 path (this is what Snowflake sends via SigV4):

```json
{
  "body": "eyJkYXRhIjogW1swLCAib3JkZXItMDAxIl0sIFsxLCAib3JkZXItMDAyIl1dfQ==",
  "isBase64Encoded": true
}
```

The base64 string above decodes to `{"data": [[0, "order-001"], [1, "order-002"]]}`.
The response body should be the same as above.

If both pass, move on.

---

## Part 2 — AWS: Create the API Gateway

### 2.1 Open API Gateway

1. Go to [https://console.aws.amazon.com/apigateway](https://console.aws.amazon.com/apigateway).
2. Click **Create API**.
3. Choose **HTTP API** (not REST API — HTTP API is simpler and cheaper).
4. Click **Build**.

### 2.2 Configure the API

**Step 1 — Integrations:**

| Field            | Value          |
|------------------|----------------|
| Integration type | Lambda         |
| AWS Region       | us-east-1      |
| Lambda function  | `dsoa-ef-echo` |

Click **Add integration**, then **Next**.

**Step 2 — Routes:**

| Field              | Value          |
|--------------------|----------------|
| Method             | POST           |
| Resource path      | `/echo`        |
| Integration target | `dsoa-ef-echo` |

Click **Next**.

**Step 3 — Stages:**

Leave the default stage name `$default` with auto-deploy enabled. Click **Next**.

**Step 4 — Review and Create:**

Click **Create**.

### 2.3 Note the invoke URL

After creation, go to your API → **Stages** → `$default`. Copy the **Invoke URL**, e.g.:

```text
https://abc12345.execute-api.us-east-1.amazonaws.com
```

The full endpoint for the external function will be:

```text
https://abc12345.execute-api.us-east-1.amazonaws.com/echo
```

> **Note:** When using `<INVOKE_URL>` as a placeholder in the SQL snippets below, substitute
> only the **hostname** portion (without the `https://` scheme), e.g.
> `abc12345.execute-api.us-east-1.amazonaws.com`.

Keep this URL — you will need it in Part 4.

### 2.4 Note the Lambda ARN

Go back to Lambda → `dsoa-ef-echo` → copy the **Function ARN** shown at the top, e.g.:

```text
arn:aws:lambda:us-east-1:123456789012:function:dsoa-ef-echo
```

---

## Part 3 — AWS: Create the IAM role for Snowflake

Snowflake authenticates to API Gateway using SigV4 — it assumes an IAM role you create and
grant it. This is a two-step bootstrap: create the role first with a placeholder trust policy,
then after the Snowflake API integration is created you update the trust policy with the real
Snowflake principal and external ID.

### 3.1 Create the IAM role (placeholder trust policy)

1. Go to [https://console.aws.amazon.com/iam](https://console.aws.amazon.com/iam).
2. Click **Roles** → **Create role**.
3. Choose **Custom trust policy** and paste the following placeholder (you will replace it in Step 4.3).
   Replace `<YOUR_ACCOUNT_ID>` with your own 12-digit AWS account ID (visible in the top-right corner of the console):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::<YOUR_ACCOUNT_ID>:root" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

1. Click **Next**. On the **Add permissions** page, click **Next** (no permissions needed —
   Snowflake only needs `sts:AssumeRole`, not resource access).
1. Name the role `dsoa-ef-snowflake-role`. Click **Create role**.
1. Open the new role and copy its **ARN**, e.g.:

```text
arn:aws:iam::123456789012:role/dsoa-ef-snowflake-role
```

### 3.2 Grant the role permission to invoke API Gateway

The role needs permission to execute the API Gateway stage. In the role's **Permissions** tab,
click **Add permissions** → **Create inline policy** → JSON tab, and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "execute-api:Invoke",
      "Resource": "arn:aws:execute-api:us-east-1:*:*/*"
    }
  ]
}
```

> **Least-privilege note:** The wildcard `Resource` above is intentional for this simulation guide
> because you may not yet know your API ID. For production use, replace it with the specific ARN
> of your API stage and route, e.g.:
> `arn:aws:execute-api:us-east-1:123456789012:<api-id>/$default/POST/echo`

Click **Next** → name it `dsoa-ef-api-invoke` → **Create policy**.

### 3.3 Verify API Gateway invokes Lambda

Before wiring up Snowflake, confirm the Lambda side works end-to-end:

```bash
curl -s -X POST \
  https://abc12345.execute-api.us-east-1.amazonaws.com/echo \
  -H "Content-Type: application/json" \
  -d '{"data": [[0, "test-row"]]}'
```

Expected response:

```json
{"data": [[0, "test-row"]]}
```

> **Security note:** Snowflake external functions do not support sending custom request headers
> from the `CREATE EXTERNAL FUNCTION` statement. Access control for this test endpoint is
> provided entirely by IAM (SigV4 signing via the assumed role). The endpoint cannot be invoked
> without valid AWS credentials for the role. No application-level secret headers are needed or
> possible.

---

## Part 4 — Snowflake: Create the API integration and external function

This is a **two-pass** process. You create the integration first, then read the Snowflake-generated
IAM principal and external ID from it, update the AWS trust policy, and only then create the
external function.

### 4.1 Create the API integration (requires ACCOUNTADMIN)

Replace `<ROLE_ARN>` with the ARN from Step 3.1 and `<INVOKE_URL>` with the value from Step 2.3.

```sql
USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE API INTEGRATION dsoa_test_api_integration
    API_PROVIDER         = aws_api_gateway
    API_AWS_ROLE_ARN     = '<ROLE_ARN>'
    API_ALLOWED_PREFIXES = ('https://<INVOKE_URL>/')
    ENABLED              = TRUE
    COMMENT              = 'DSOA test — echo external function';

-- Grant USAGE on the integration to the role that will create/use the external function.
-- Without this, CREATE EXTERNAL FUNCTION will fail with "Insufficient privileges to operate
-- on integration" even if the role owns the schema.
GRANT USAGE ON INTEGRATION dsoa_test_api_integration TO ROLE DTAGENT_QA_OWNER;
```

### 4.2 Read the Snowflake IAM principal and external ID

Snowflake generates a dedicated IAM user and external ID for this integration. You must
configure the AWS trust policy to allow exactly this principal.

```sql
DESC INTEGRATION dsoa_test_api_integration;
```

Look for these two rows in the result:

| property               | value                                           |
|------------------------|-------------------------------------------------|
| `API_AWS_IAM_USER_ARN` | `arn:aws:iam::<snowflake-account-id>:user/xxxx` |
| `API_AWS_EXTERNAL_ID`  | `<some-string>_SFCRole=...`                     |

Copy both values — you need them in the next step.

### 4.3 Update the IAM role trust policy

Go back to IAM → Roles → `dsoa-ef-snowflake-role` → **Trust relationships** tab →
**Edit trust policy**. Replace the entire policy with:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "<API_AWS_IAM_USER_ARN>"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "<API_AWS_EXTERNAL_ID>"
        }
      }
    }
  ]
}
```

Replace `<API_AWS_IAM_USER_ARN>` and `<API_AWS_EXTERNAL_ID>` with the exact values from Step 4.2.
Click **Update policy**.

### 4.4 Create the external function

Replace `<INVOKE_URL>` with the value from Step 2.3.

```sql
USE ROLE DTAGENT_QA_OWNER;
USE DATABASE DSOA_TEST_DB;
USE SCHEMA QUERY_HISTORY_TEST;

CREATE OR REPLACE EXTERNAL FUNCTION ef_echo(val VARCHAR)
    RETURNS VARIANT
    API_INTEGRATION    = dsoa_test_api_integration
    AS 'https://<INVOKE_URL>/echo';

-- Grant usage to the viewer role so DSOA can observe it in ACCOUNT_USAGE.
GRANT USAGE ON FUNCTION ef_echo(VARCHAR) TO ROLE DTAGENT_QA_VIEWER;
```

### 4.5 Smoke test

```sql
USE ROLE DTAGENT_QA_OWNER;
USE DATABASE DSOA_TEST_DB;
USE SCHEMA QUERY_HISTORY_TEST;
USE WAREHOUSE DSOA_TEST_WH;

SELECT ef_echo('hello-from-snowflake');
```

Expected result: a single row with value `"hello-from-snowflake"`.

If you see `Error assuming AWS_ROLE`, the trust policy has not been updated yet or the
`API_AWS_IAM_USER_ARN` / `API_AWS_EXTERNAL_ID` values were not copied exactly — re-check Step 4.3.

If you see `Error calling remote service`, the Lambda or API Gateway is not reachable —
re-run the `curl` test from Step 3.3.

---

## Part 5 — Snowflake: Update the workload stored procedure

Add a call to `ef_echo` inside `SP_WORKLOAD_ROOT` so the external function is invoked on every
task run (every 5 minutes), generating telemetry for dashboard tiles 15–16.

Run this in Snowsight or via `snow sql --connection snow_agent_test-qa --role DTAGENT_QA_OWNER --database DSOA_TEST_DB --warehouse DSOA_TEST_WH`:

```sql
USE ROLE DTAGENT_QA_OWNER;
USE DATABASE DSOA_TEST_DB;
USE SCHEMA QUERY_HISTORY_TEST;

CREATE OR REPLACE PROCEDURE DSOA_TEST_DB.QUERY_HISTORY_TEST.SP_WORKLOAD_ROOT()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    run_ts  VARCHAR DEFAULT TO_VARCHAR(CURRENT_TIMESTAMP(), 'YYYY-MM-DD HH24:MI:SS');
    v_dummy NUMBER;
BEGIN

    -- ── Query 1: Full-table GROUP BY + JOIN (bytes_scanned, partition_scan_ratio)
    SELECT COUNT(*) INTO :v_dummy FROM (
        SELECT
            c.segment,
            o.region,
            COUNT(o.order_id)               AS order_count,
            SUM(o.quantity * o.unit_price)  AS total_revenue,
            AVG(o.discount_pct)             AS avg_discount,
            MAX(o.order_date)               AS latest_order
        FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS  o
        JOIN DSOA_TEST_DB.QUERY_HISTORY_TEST.DIM_CUSTOMERS c ON c.customer_id = o.customer_id
        GROUP BY c.segment, o.region
        ORDER BY total_revenue DESC
    );

    -- ── Query 2: Cross-join — forces spill on XSMALL
    SELECT COUNT(*) INTO :v_dummy FROM (
        SELECT
            a.notes || b.notes AS combined_notes,
            a.quantity * b.unit_price AS cross_value
        FROM (SELECT * FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS LIMIT 50) a
        CROSS JOIN (SELECT * FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS LIMIT 50) b
        WHERE LENGTH(a.notes) > 10
    );

    -- ── Query 3: Repeated identical SELECT (result-cache)
    SELECT COUNT(*) INTO :v_dummy
    FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS;

    SELECT COUNT(*) INTO :v_dummy
    FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS;

    -- ── Query 4: DML refresh
    DELETE FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.STAGING_ORDERS;

    -- ── Query 5: External function call (tiles 15-16)
    --   Sends 20 order_id values to the AWS Lambda echo endpoint.
    --   Generates external_function_total_invocations = 1, non-zero bytes_sent/received.
    --   Wrapped in COUNT(*) so INTO :v_dummy receives exactly 1 row.
    SELECT COUNT(*) INTO :v_dummy FROM (
        SELECT ef_echo(order_id::VARCHAR)
        FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS
        LIMIT 20
    );

    -- ── Child proc call → parent_query_id relationship (tile 12)
    CALL DSOA_TEST_DB.QUERY_HISTORY_TEST.SP_WORKLOAD_CHILD(:run_ts);

    RETURN 'workload complete at ' || :run_ts;
END;
$$;
```

### 5.1 Run immediately to verify

```sql
USE WAREHOUSE DSOA_TEST_WH;
CALL DSOA_TEST_DB.QUERY_HISTORY_TEST.SP_WORKLOAD_ROOT();
```

It should return `workload complete at <timestamp>` without errors.

### 5.2 Confirm external function invocation was recorded

Wait ~2 minutes, then check `INFORMATION_SCHEMA` (no lag):

```sql
SELECT
    query_id,
    query_text,
    external_function_total_invocations,
    external_bytes_sent,
    external_bytes_received,
    start_time
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(
    USER_NAME    => CURRENT_USER(),
    RESULT_LIMIT => 20
))
WHERE external_function_total_invocations > 0
ORDER BY start_time DESC;
```

You should see one row with `external_function_total_invocations = 1` and non-zero byte counts.

After ~45 minutes the same row will appear in `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY`, where the
DSOA `query_history` plugin reads it and emits it as telemetry for tiles 15–16.

---

## Part 6 — Verify in Dynatrace

After the next DTAGENT run (~30 min schedule, or trigger manually):

```dql
fetch logs, from: now()-2h
| filter db.system == "snowflake"
| filter dsoa.run.plugin == "query_history"
| filter deployment.environment == "TEST-QA"
| filter toDouble(snowflake.external_functions.invocations) > 0
| fields db.user, snowflake.warehouse.name, snowflake.external_functions.invocations,
         snowflake.external_functions.data.sent, snowflake.external_functions.data.received
| sort timestamp desc
```

You should see rows from `DTAGENT_QA_OWNER` with non-zero invocation and byte counts.
Dashboard tiles 15 and 16 will then show data.

---

## Cleanup

When you no longer need the simulation:

```sql
-- Snowflake
USE ROLE DTAGENT_QA_OWNER;
DROP FUNCTION IF EXISTS DSOA_TEST_DB.QUERY_HISTORY_TEST.ef_echo(VARCHAR);
USE ROLE ACCOUNTADMIN;
DROP API INTEGRATION IF EXISTS dsoa_test_api_integration;
```

```bash
# AWS — via console or CLI
aws lambda delete-function --function-name dsoa-ef-echo --region us-east-1
# Delete the HTTP API in API Gateway console → your API → Actions → Delete
```

---

## Troubleshooting

| Symptom                                                                                | Likely cause                                                                                                   | Fix                                                                                                                      |
|----------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| `Insufficient privileges to operate on integration`                                    | `GRANT USAGE ON INTEGRATION` missing                                                                           | Run `GRANT USAGE ON INTEGRATION dsoa_test_api_integration TO ROLE DTAGENT_QA_OWNER;` as ACCOUNTADMIN (Step 4.1)          |
| `Error calling remote service` on `SELECT ef_echo(...)`                                | API Gateway URL wrong or Lambda not deployed                                                                   | Re-run `curl` test from Step 3.1; check `API_ALLOWED_PREFIXES`                                                           |
| `Integration not found`                                                                | API integration not created with ACCOUNTADMIN                                                                  | Run Step 4.1 as ACCOUNTADMIN                                                                                             |
| Tiles 15–16 still empty after 1 hour                                                   | ACCOUNT_USAGE lag or DTAGENT not run                                                                           | Check `INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER` for `external_function_total_invocations > 0`; trigger DTAGENT manually |
| `500 Internal Server Error` / `JSONDecodeError` or `UnicodeDecodeError` in Lambda logs | Snowflake gzip-compresses and base64-encodes the body when using SigV4; old code without gzip handling crashes | Redeploy Lambda with the updated `lambda_function.py` from Step 1.3                                                      |
| `Error assuming AWS_ROLE` on `SELECT ef_echo(...)`                                     | Trust policy not updated with Snowflake principal                                                              | Re-check Step 4.3: `API_AWS_IAM_USER_ARN` and `API_AWS_EXTERNAL_ID` must be copied exactly from `DESC INTEGRATION`       |
| `external_bytes_sent` is very small                                                    | Only 20 rows sent per run                                                                                      | Increase `LIMIT 20` in `SP_WORKLOAD_ROOT` Query 5 to 200                                                                 |
