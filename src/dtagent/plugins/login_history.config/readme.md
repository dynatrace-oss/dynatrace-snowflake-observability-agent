Provides detail about logins history as well as sessions history in form of logs.
The log entries include information on:

- users id who is regarded by the log,
- potential error codes,
- type of Snowflake connection,
- timestamp of logging in,
- environment the client used during the session,
- timestamp of the start of the session,
- timestamp of the end of the session,
- reason of ending the session, and
- version used by the client.

Failed-login alerts are no longer sent as events by this plugin; alerting is provided by the Data Observability app.
