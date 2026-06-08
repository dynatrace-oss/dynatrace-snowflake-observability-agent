This plugin enables tracking shares, both inbound and outbound, present in a Snowflake account, or a subset of those subject to configuration. Apart from reporting basic information on each share, as delivered from `SHOW SHARES`, this plugin also:

- logs lists tables that were shared with the current account (inbound share),
- logs objects shared from this account (outbound share),
- sends events when a share is created,
- sends events when an object is granted to a share, and
- sends events when a table is shared, updated, or modified (DDL).

By default, shares are monitored every 60 minutes. It is possible to exclude certain shares (or parts of them) from tracking detailed information.

When the `admin` scope is installed, `DTAGENT_VIEWER` is automatically granted `IMPORTED PRIVILEGES` on inbound shared databases as needed. Without admin scope, this grant must be applied manually — see `config.md` for the required SQL and details.
