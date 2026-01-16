#!/bin/bash
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
csv_file="$1"
code_directory="$2"

# Set sed in-place flag based on OS
if [ $(uname -s) = 'Darwin' ]; then
    SED_INPLACE="sed -i ''"
else
    SED_INPLACE="sed -i"
fi

while IFS=';' read -r old_id new_id
do
    # Trim any leading/trailing whitespace and remove carriage returns
    old_id=$(echo "$old_id" | tr -d '\r' | xargs)
    new_id=$(echo "$new_id" | tr -d '\r' | xargs)

    # Check if old_id and new_id are different
    if [ "$old_id" != "$new_id" ]; then
        # echo "Replacing [s/$old_id/$new_id/g] at [$code_directory]"
        egrep -rlw --include=\*.{py,sql,json,jsonc,sh,md,txt,dql,yml} --exclude-dir="./.*"  "$old_id" "$code_directory" | while read -r file; do
            echo "$SED_INPLACE -E -e \"s/$old_id/$new_id/g\" \"$file\""
            $SED_INPLACE -E -e "s/$old_id/$new_id/g" "$file"
        done
    # else
    #     echo "Skipping replacement for [$old_id] as it is the same as [$new_id]"
    fi
done < "$csv_file"

echo "Identifiers updated successfully!"
