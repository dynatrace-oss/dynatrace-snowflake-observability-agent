This plugin enables tracking table storage metrics in Snowflake through reported metrics.

The following information is reported:

- active bytes (data currently stored in the table),
- time travel bytes (data maintained for Time Travel),
- failsafe bytes (data maintained for Failsafe),
- retained for clone bytes (data retained for cloning),
- number of rows in the table, and
- clustering key definition (if any).

The plugin supports include/exclude filtering to target specific tables and can be configured with minimum table size and maximum table count constraints.
