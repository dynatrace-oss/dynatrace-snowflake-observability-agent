This plugin enables tracking the volume of data (in bytes and rows) stored in Snowflake through reported metrics.
Additionally, it sends events when there are changes in table structure (DDL) or content.

The following information is reported:

- table type,
- timestamp of the last data update and the time elapsed since then,
- timestamp of the last DDL and the time elapsed since then,
- number of bytes in the table, and
- number of rows in the table.
