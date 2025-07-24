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
#
# This script is used to build target documentation into README.md file

./build.sh

VERSION=$(grep 'VERSION =' build/_version.py | awk -F'"' '{print $2}')
BUILD=$(grep 'BUILD =' build/_version.py | sed -E -e 's/^.*[=] ([0-9]+)\s*/\1/')
CURRENT_DATE=$(date +%Y-%m-%d)

PYTHONPATH="$PYTHONPATH:./src" python -m build.compile_bom
PYTHONPATH="$PYTHONPATH:./src" python -m build.update_docs

# we keep CONTRIBUTING in PDF grep -v "CONTRIBUTING.md" README.md |\
sed -E "s/# Dynatrace Snowflake Observability Agent$/# Dynatrace Snowflake Observability Agent (v$VERSION)\n<a id='dynatrace-snowflake-observability-agent'><\/a>/" README.md >README.tmp.md
echo "" >>README.tmp.md
echo "**Dynatrace Snowflake Observability Agent** Version: $VERSION.$BUILD ($CURRENT_DATE)" >>README.tmp.md

pandoc README.tmp.md \
    -o "Dynatrace-Snowflake-Observability-Agent-$VERSION.pdf" \
    -f markdown \
    -t pdf \
    --pdf-engine=weasyprint \
    --css=src/assets/readme.css \
    --metadata title=" "

rm README.tmp.md

pandoc INSTALL.md \
    -o Dynatrace-Snowflake-Observability-Agent-install.pdf \
    -f markdown \
    -t pdf \
    --pdf-engine=weasyprint \
    --css=src/assets/index.css \
    --metadata title=" "

echo "Dynatrace-Snowflake-Observability-Agent-$VERSION.pdf and Dynatrace-Snowflake-Observability-Agent-install.pdf files successfully created"
