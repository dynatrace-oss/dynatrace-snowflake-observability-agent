--
--
-- Copyright (c) 2025 Dynatrace Open Source
--
-- Permission is hereby granted, free of charge, to any person obtaining a copy
-- of this software and associated documentation files (the "Software"), to deal
-- in the Software without restriction, including without limitation the rights
-- to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
-- copies of the Software, and to permit persons to whom the Software is
-- furnished to do so, subject to the following conditions:
--
-- The above copyright notice and this permission notice shall be included in all
-- copies or substantial portions of the Software.
--
-- THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
-- IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
-- FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
-- AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
-- LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
-- OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
-- SOFTWARE.
--
--
--
-- Sends a bizevent confirming that the deployment reached Snowflake and that
-- APP.SEND_TELEMETRY() can reach the configured Dynatrace tenant from inside
-- Snowflake (token, network rule, tenant URL) — verifying the runtime path,
-- not just that the deploy script itself finished executing.
-- This must remain the last statement executed for the "all" and "upgrade"
-- deployment scopes; see scripts/deploy/prepare_deploy_script.sh.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

-- Wrapped in its own exception handler so a Dynatrace-side failure (bad token, blocked
-- network rule, tenant unreachable) is reported but never fails this deploy script —
-- the deploy itself already succeeded by the time this, its last statement, runs.
execute immediate $$
begin
    call DTAGENT_DB.APP.SEND_TELEMETRY(
        OBJECT_CONSTRUCT(
            'event.type', 'dsoa.installation',
            'message', 'DSOA installation completed successfully',
            'dsoa.deployment.parameter', '__DSOA_DEPLOY_SCOPE__'
        ),
        OBJECT_CONSTRUCT(
            'context', 'installation_verification',
            'auto_mode', false,
            'logs', false,
            'biz_events', true
        )
    );
    return 'Installation bizevent sent';
exception
    when other then
        return 'Installation bizevent failed (deployment itself succeeded): ' || sqlerrm;
end;
$$;
