"""Context const and context related functions."""

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

##endregion COMPILE_REMOVE

from typing import Dict, Optional

CONTEXT_NAME = "dsoa.run.context"
RUN_ID_NAME = "dsoa.run.id"
RUN_RESULTS_NAME = "dsoa.run.results"


def get_context_name_and_run_id(context_name: str, run_id: Optional[str] = None) -> Dict[str, str]:
    """Generates the complete context dictionary based on the given name and optional run ID"""
    import uuid

    return {
        CONTEXT_NAME: context_name,
        RUN_ID_NAME: run_id or str(uuid.uuid4().hex),
    }


def get_context_name(context_name: Optional[str] = None) -> Dict[str, str]:
    """Generates the context dictionary based on the given context name if provided, otherwise returns empty dict"""
    return {CONTEXT_NAME: context_name} if context_name else {}
