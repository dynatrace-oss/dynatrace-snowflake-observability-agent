"""Defines resource creation and IS_OTEL_BELOW_21 const."""

##region ------------------------------ IMPORTS  -----------------------------------------
#
#
# These materials contain confidential information and
# trade secrets of Dynatrace LLC.  You shall
# maintain the materials as confidential and shall not
# disclose its contents to any third party except as may
# be required by law or regulation.  Use, disclosure,
# or reproduction is prohibited without the prior express
# written permission of Dynatrace LLC.
#
# All Compuware products listed within the materials are
# trademarks of Dynatrace LLC.  All other company
# or product names are trademarks of their respective owners.
#
# Copyright (c) 2024 Dynatrace LLC.  All rights reserved.
#
#

import requests
from opentelemetry.sdk.resources import Resource
from opentelemetry import version as otel_version
from dtagent.config import Configuration
from dtagent.version import VERSION

##endregion COMPILE_REMOVE


##region ------------------------ OTEL INIT ----------------------------------------
def _gen_resource(config: Configuration) -> Resource:
    """Generates configuration's resource.attributes field"""

    return Resource.create(attributes=config.get("resource.attributes"))


def _log_warning(response: requests.Response, _payload, source: str = "data") -> None:
    """Logs warning of problems while sending to DT"""

    from dtagent import LOG  # COMPILE_REMOVE

    LOG.warning(
        "Problem sending %s to Dynatrace; error code: %s, reason: %s, response: %s, payload: %r",
        source,
        response.status_code,
        response.reason,
        response.text,
        _payload,
    )


IS_OTEL_BELOW_1_21 = otel_version.__version__ < "1.21.0"

USER_AGENT = f"dsoa/{'.'.join(VERSION.split('.')[:3])}"
##endregion
