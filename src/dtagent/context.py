"""Context const and context related functions."""

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

##endregion COMPILE_REMOVE

from typing import Dict, Optional

CONTEXT_NAME = "dsoa.run.context"
RUN_ID_NAME = "dsoa.run.id"


def get_context_by_name(context_name: str, run_id: Optional[str] = None) -> Dict[str, str]:
    """Generates the complete context dictionary based on the given name and optional run ID"""
    import uuid

    return {
        CONTEXT_NAME: context_name,
        RUN_ID_NAME: run_id or str(uuid.uuid4().hex),
    }
