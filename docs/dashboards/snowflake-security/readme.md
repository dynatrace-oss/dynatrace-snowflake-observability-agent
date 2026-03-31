# Dashboard: Snowflake Security

This dashboard provides insights into the security aspects of your Snowflake accounts. It includes visualizations and metrics that help you monitor user authentication, login issues, administrative activity, and security compliance based on Snowflake's Trust Center.

## Consolidating Trust Center Findings for Enhanced Security Management

- Centralizes findings from Snowflake's internal Trust Center, which consolidates security-related tests and queries to provide a comprehensive overview of vulnerabilities and compliance issues.
- Enables efficient comparison of findings across multiple accounts to identify those with the most pressing security problems, a process that would otherwise require manual logins to each account.
- Allows security teams to prioritize and address critical security concerns efficiently, improving risk management and ensuring compliance with industry standards.
![Trust Center monitoring](./img/01-trust-center.png)

## Query History of Users with Excessive Privileges

- Monitors the query history of users with excessive privileges (e.g., admin roles) to safeguard sensitive data and detect potential misuse.
- Analyzes query patterns and helps identify unusual or unauthorized access to sensitive information, ensuring that powerful accounts are used responsibly.
- This proactive oversight helps maintain data integrity, prevent insider threats, and enforce strict access controls.
![Admin activity monitoring](./img/02-admin-activity.png)

## Monitoring Failed Login Attempts for Early Threat Detection

- Tracks failed login attempts to identify potential brute force attacks and unauthorized access attempts, enabling the Incident Detection and Response (IDR) team to take immediate action.
- By analyzing patterns of failed logins, it helps detect ongoing attacks and allows for a swift response to prevent security breaches.
- Provides a detailed log of login incidents for further investigation and forensic analysis.
![Problems with login to Snowflake](./img/03-login-problems.png)

## Enforcing Secure Authentication Methods

- Identifies which users need to be migrated to stronger authentication methods like Multi-Factor Authentication (MFA) or Single Sign-On (SSO), as Snowflake will soon discontinue support for logins using only a username and password.
- For service accounts, it helps ensure they are configured with secure, non-password methods such as Key-Pair Authentication, Programmatic Access Tokens (PAT), External OAuth, or Workload Identity Federation (WIF).
- Tracks authentication methods used by both human and service users to monitor the transition to more secure practices.
![Login Analysis](./img/04-logins-by-auth-type.png)

## Privilege Escalation Detection

- Identifies users with broad role grants showing the complete list of roles and who granted them.
- Surfaces users with extensive privilege grants including the privilege type, target objects, and granting roles.
- Detects role revocations to track when roles are removed from users, which may indicate security policy changes or incident response.
- Enables security teams to detect privilege escalation patterns and enforce least-privilege principles.

All data is sourced from the `users` plugin (`dsoa.run.context == "users"`) via `fetch logs`, with each subset distinguished by attribute presence (e.g., `isNotNull(snowflake.user.roles.all)` for all-roles data).

![Privilege escalation detection](./img/05-privilege-escalation.png)

## User Identity & Access

- Provides an at-a-glance view of account health: active vs disabled vs locked accounts as a bar chart.
- Shows MFA enrollment status as a pie chart to identify users without multi-factor authentication.
- Displays RSA key usage distribution to track adoption of key-pair authentication.
- Breaks down user type distribution (e.g., `PERSON`, `SERVICE`, `LEGACY_SERVICE`) to understand the account landscape.
- Lists password-only accounts (no MFA, no RSA, no PAT) that represent the highest authentication risk.

![User identity and access](./img/06-user-identity-access.png)
