#!/bin/bash

csv_file="$1"
code_directory="$2"

while IFS=';' read -r old_id new_id
do
    # Trim any leading/trailing whitespace and remove carriage returns
    old_id=$(echo "$old_id" | tr -d '\r' | xargs)
    new_id=$(echo "$new_id" | tr -d '\r' | xargs)
    
    # Check if old_id and new_id are different
    if [ "$old_id" != "$new_id" ]; then
        # echo "Replacing [s/$old_id/$new_id/g] at [$code_directory]"
        egrep -rlw --include=\*.{py,sql,json,jsonc,sh,md,txt,dql,yml} --exclude-dir="./.*"  "$old_id" "$code_directory" | while read -r file; do
            echo "sed -i '' -E -e \"s/$old_id/$new_id/g\" \"$file\""
            sed -i "" -E -e "s/$old_id/$new_id/g" "$file"
        done
    # else
    #     echo "Skipping replacement for [$old_id] as it is the same as [$new_id]"
    fi
done < "$csv_file"

echo "Identifiers updated successfully!"
