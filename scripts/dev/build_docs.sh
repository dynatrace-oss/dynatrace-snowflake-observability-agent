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
#
# This script is used to build target documentation into README.md file

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

./scripts/dev/build.sh

VERSION=$(grep 'VERSION =' build/_version.py | awk -F'"' '{print $2}')
BUILD=$(grep 'BUILD =' build/_version.py | sed -E -e 's/^.*[=] ([0-9]+)\s*/\1/')
CURRENT_DATE=$(date +%Y-%m-%d)

rm _readme_full.md 2>/dev/null
rm build/bom.yml 2>/dev/null

PYTHONPATH="$PYTHONPATH:./src" python -m build.compile_bom
PYTHONPATH="$PYTHONPATH:./src" python -m build.update_docs

if [ ! -f _readme_full.md ] || [ ! -f build/bom.yml ]; then
    echo "Error: Expected documentation files were not found" >&2
    exit 10
fi

sed -E "s/# Dynatrace Snowflake Observability Agent$/# Dynatrace Snowflake Observability Agent (v$VERSION)\n<a id='dynatrace-snowflake-observability-agent'><\/a>/" _readme_full.md > _readme_full.tmp.md
echo "" >>_readme_full.tmp.md
echo "**Dynatrace Snowflake Observability Agent** Version: $VERSION.$BUILD ($CURRENT_DATE)" >>_readme_full.tmp.md

pandoc _readme_full.tmp.md \
    -o "Dynatrace-Snowflake-Observability-Agent-$VERSION.pdf" \
    -f markdown \
    -t pdf \
    --pdf-engine=weasyprint \
    --css=src/assets/readme.css \
    --metadata title=" "

rm _readme_full.*

if command -v prettier >/dev/null 2>&1; then
    prettier --write docs/PLUGINS.md
    prettier --write docs/SEMANTICS.md
    prettier --write docs/APPENDIX.md
else
    echo "prettier not found, skipping formatting"
fi

echo "Dynatrace-Snowflake-Observability-Agent-$VERSION.pdf file successfully created"
