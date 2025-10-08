Focuses on providing a broad overview of the users in the system. The data is downloaded from `USERS`, `LOGIN_HISTORY`, and `GRANTS_TO_USERS` views. By default, sends all e-mails hashed (to send them in cleartext, switch `PLUGINS.USERS.IS_HASHED` to `false`). It is possible to create a table with emails-to-hash map which can be accessed at `STATUS.EMAIL_HASH_MAP` by setting `PLUGINS.USERS.RETAIN_EMAIL_HASH_MAP` to `true`. The core functionality of the plugin is to report all active users and those that have been removed since last run, with one log line per user. This information is provided by default, regardless of other enabled modes.
Role monitoring includes three possible modes:

* `DIRECT_ROLES` - users with comma-separated list of roles directly granted to the user, with roles that have been removed since last run;
* `ALL_ROLES` - users with comma-separated list of all roles granted to the user;
* `ALL_PRIVILEGES` - users with all privileges granted per user.

Role monitoring mode can be defined at `PLUGINS.USERS.ROLES_MONITORING_MODE` configuration option. More detailed monitoring modes will impact performance, caution is recommended with more advanced modes.

It is possible to choose more than one mode at a time, which will result in multiple analyses being performed.

The plugin reports on:

* date of last successful login of a user,
* user's default and directly granted roles, and
* user account details.
