This plugin reports the state of resource monitors and analyzes the conditions of warehouses. All necessary information found by the plugin is delivered through metrics and logs. Additionally, events are sent when changes in the state of a resource monitor or warehouse are detected.

By default, it executes every 30 minutes and resumes the analysis from where it left off. Before collecting the data, the state of all resource monitors is refreshed.

This plugin:

* logs the current state of each resource monitor and warehouse,
* logs an error if an account-level monitor setup is missing,
* logs a warning if a warehouse is not monitored at all, and
* sends events on all new activities of monitors and warehouses.
