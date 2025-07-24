#!/usr/bin/env bash
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

if [ "$1" == 'y' ]; then
    PICKLE_CONF='--pickle_conf -y'
else 
    PICKLE_CONF=''
fi

iter_dir() {
    for file in test/$1/test_*.py; do
        echo $file
        pytest -s -v $file > .logs/dtagent-$(basename $file)-$(date '+%Y%m%d-%H%M%S').log
        if [ $? -ne 0 ]; then
            exit 1
        fi
    done
}

iter_dir core $PICKLE_CONF
iter_dir otel ''