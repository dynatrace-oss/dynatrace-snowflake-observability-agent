#!/usr/bin/env bash
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

# this is an internal script for packaging Dynatrace Snowflake Observability Agent for distribution
# Args:
# * PARAM   [OPTIONAL] - can be either
#              = full          - which will keep full deploy package for internal usage with service user
#              =               - which will remove :DEV tags from deploy.sh
#

PARAM=$1

# Resetting the package directory
rm -Rf package/*

# building Dynatrace Snowflake Observability Agent and documentation
./build_docs.sh

# copying Dynatrace Snowflake Observability Agent compiled code
mkdir -v -p package/build
cp -v build/*.sql package/build/
cp -v build/instruments-def.json build/config-default.json package/build/

mkdir -v package/conf
cp -v conf/config-template.json package/conf/

cp -v setup.sh prepare_config.sh update_secret.sh install_snow_cli.sh send_bizevent.sh package/
cp -v prepare_instruments_ingest.sh prepare_configuration_ingest.sh prepare_deploy_script.sh get_config_key.sh package/
cp -v refactor_field_names.sh src/assets/fields-refactoring.csv src/assets/dsoa-fields-refactoring.csv package/

# preparing the deploy.sh script
if [ "$PARAM" == "full" ]; then
  sed -E -e "s/[.]\/src/.\/py/g" deploy.sh \
    >package/deploy.sh
else
  awk 'BEGIN { print_out=1; }
      /^[#][%]DEV[:].*/ { print_out=0; }
      { if (print_out==1) print $0; }
      /^[#][%][:]DEV.*/ { print_out=1; }' \
    deploy.sh |
    sed -E -e "s/[.]\/src/.\/py/g" \
      >package/deploy.sh
fi
echo "package/deploy.sh prepared"

chmod u+x package/*.sh

# packaging documentation

VERSION=$(grep 'VERSION =' build/_version.py | awk -F'"' '{print $2}')

# copying documentation
cp -v INSTALL.md "Dynatrace-Snowflake-Observability-Agent-$VERSION.pdf" CHANGELOG.md Dynatrace-Snowflake-Observability-Agent-install.pdf package/

# copying license file if exists
# it will only be available in packages created for customers entering private preview
# LICENSE.md file is created from the LICENSE.template.md where customer specific information is filled in
cp -v LICENSE.md package/

# copying the documentation
mkdir -v -p package/docs
for dir in docs/*/; do
  [ -d "$dir" ] || continue
  archive_name="package/docs/$(basename "$dir").zip"
  (cd "$dir" && zip -r -1 "../../$archive_name" . -x ".*")
done

# copying the Bill of Materials (BOM) files
cp -v build/bom* package/docs

# building a distribution zip
BUILD=$(grep 'BUILD =' build/_version.py | awk '{print $3}')

cd package
zip -r -1 "../dynatrace_snowflake_observability_agent-$VERSION.$BUILD.zip" * -x .gitkeep
cd ..

echo -e "\n-\n-\nDynatrace Snowflake Observability Agent package version $VERSION.$BUILD prepared\n-\n-\n"
