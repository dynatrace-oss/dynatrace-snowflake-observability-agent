#!/bin/bash

JSON_FILE=$1

if [ -z "$JSON_FILE" ]; then
    echo "Usage: $0 <json_file>"
    exit 1
fi

CWD=$(dirname "$0")

# Call the convert script
"$CWD/../scripts/deploy/convert_config_to_yaml.sh" "$JSON_FILE"

# Compute output file (assuming single object; for arrays, this handles the first)
BASE_NAME=$(basename "$JSON_FILE" .json)
DIR=$(dirname "$JSON_FILE")
OUTPUT_FILE="$DIR/$BASE_NAME.yaml"

# Do the git mv trick
mv "$OUTPUT_FILE" "${OUTPUT_FILE}.bak"
git mv "$JSON_FILE" "$OUTPUT_FILE"
mv "${OUTPUT_FILE}.bak" "$OUTPUT_FILE"