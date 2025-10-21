"""Defines resource creation and IS_OTEL_BELOW_21 const."""

##region ------------------------------ IMPORTS  -----------------------------------------
#
#
# Copyright (c) 2025 Dynatrace Open Source
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
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
        str(_payload)[:100],
    )


IS_OTEL_BELOW_1_21 = otel_version.__version__ < "1.21.0"

USER_AGENT = f"dsoa/{'.'.join(VERSION.split('.')[:3])}"
##endregion
