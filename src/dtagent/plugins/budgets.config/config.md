| Parameter          | Type   | Default                        | Description                                                                                    |
| ------------------ | ------ | ------------------------------ | ---------------------------------------------------------------------------------------------- |
| `quota`            | int    | `10`                           | Credit quota for the agent's own `DTAGENT_BUDGET`.                                             |
| `schedule`         | string | `USING CRON 30 0 * * * UTC`    | Cron schedule for the budgets collection task.                                                 |
| `monitored_budgets`| list   | `[]`                           | Fully-qualified custom budget names to monitor, e.g. `["MY_DB.MY_SCHEMA.MY_BUDGET"]`.          |
| `schedule_grants`  | string | `USING CRON 30 */12 * * * UTC` | Cron schedule for `TASK_DTAGENT_BUDGETS_GRANTS` (admin scope only).                            |

### Enabling the Budgets plugin

1. Set `IS_ENABLED` to `true` in your configuration file.
1. For **account budget only** (no custom budgets): no additional grants needed — `SNOWFLAKE.BUDGET_VIEWER` is already granted.
1. For **custom budgets**: configure `monitored_budgets` and run `P_GRANT_BUDGET_MONITORING()` (admin scope required), or grant
   privileges manually (see below).

### Granting access to custom budgets manually

For each custom budget `<DB>.<SCHEMA>.<BUDGET_NAME>`, grant the following to `DTAGENT_VIEWER`:

```sql
grant usage on database <DB> to role DTAGENT_VIEWER;
grant usage on schema <DB>.<SCHEMA> to role DTAGENT_VIEWER;
grant snowflake.core.budget role <DB>.<SCHEMA>.<BUDGET_NAME>!VIEWER to role DTAGENT_VIEWER;
grant database role SNOWFLAKE.USAGE_VIEWER to role DTAGENT_VIEWER;
```
