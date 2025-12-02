"""Instruments are a set of defined payload properties which allow for setting e.g. metric dimensions."""

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

from typing import Any, Dict, Optional

##endregion COMPILE_REMOVE


##region ------------------------ INSTRUMENTS INIT ----------------------------------------
class Semantics:
    """Gathers defined payload properties from CONFIG.V_INSTRUMENTS"""

    def __init__(self):
        self._metric_semantics = {
            ##INSERT build/_metric_semantics.txt
        }

    def _gen_metric_definition_line(self, metric_name: str, metric_details: Dict[str, str]) -> str:
        """Generates a single doc line that will be sent along with actual data to Dynatrace Metrics API v2

        Args:
            metric_name (str): name of the metric
            metric_details (Dict[str, str]): details (displayName, unit) for that metric

        Returns:
            str: single doc line for given metric
        """

        def __gen_metric_details(metric_details: Dict[str, str], metric_name: str) -> str:
            """Helper function that packs together displayName and other metadata about each metric
            according to the Dynatrace Metrics v2 API specs
            """
            from dtagent.util import _esc  # COMPILE_REMOVE

            return ",".join(
                [
                    f'dt.meta.{k}="{_esc(v)}"'
                    for k, v in {
                        "displayName": " ".join(metric_name.split(".")[-1:]).replace("_", " ").title(),
                        **metric_details,
                    }.items()
                    if k[:2] != "__"  # skip internal names
                ]
            )

        return f"#{metric_name} gauge {__gen_metric_details(metric_details, metric_name)}"

    def get_metric_definition(self, metric_name: str, local_metrics_def: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
        """Returns set of instruments for metric of given name,
        with optional local semantic dictionary which might be provided at runtime.
        """
        result = self._metric_semantics.get(metric_name, None)

        if result is None:
            # we could use (local_metrics_def or {}) but I think this will be faster, on top of calling this only when really needed
            if local_metrics_def is not None and metric_name in local_metrics_def:
                result = self._gen_metric_definition_line(metric_name, local_metrics_def[metric_name])

                self._metric_semantics[metric_name] = result  # caching results for the time being
            else:
                result = ""

        return result


##endregion
