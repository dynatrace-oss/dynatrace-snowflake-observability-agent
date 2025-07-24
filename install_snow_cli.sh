#!/bin/bash
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

# Step 1: Detect system architecture
ARCH=$(uname -m)
OS=$(uname -s)

if [ "$OS" == "Darwin" ]; then
    if [ "$ARCH" == "arm64" ]; then
        ARCH="darwin_arm64"
    else
        echo "Unsupported architecture for macOS: $ARCH"
        exit 1
    fi
elif [ "$OS" == "Linux" ]; then
    if [ "$ARCH" == "x86_64" ]; then
        ARCH="x86_64"
    elif [ "$ARCH" == "aarch64" ]; then
        ARCH="aarch64"
    else
        echo "Unsupported architecture for Linux: $ARCH"
        exit 1
    fi
else
    echo "Unsupported operating system: $OS"
    exit 1
fi

# Step 2: Check the newest version available
URL="https://sfc-repo.snowflakecomputing.com/snowflake-cli/linux_$ARCH/index.html"
if [ "$OS" == "Darwin" ]; then
    URL="https://sfc-repo.snowflakecomputing.com/snowflake-cli/$ARCH/index.html"
fi

VERSION=$(curl -s $URL | grep -o '<a href="[^"]*/index.html' | sed 's|<a href="||;s|/index.html||' | sort -V | tail -n 1)

# Step 3: Download the latest version
if [ "$OS" == "Darwin" ]; then
    DOWNLOAD_URL="https://sfc-repo.snowflakecomputing.com/snowflake-cli/$ARCH/$VERSION/snowflake-cli-$VERSION-darwin-arm64.pkg"
    FILE_NAME="snowflake-cli-$VERSION.$ARCH.pkg"
else
    DOWNLOAD_URL="https://sfc-repo.snowflakecomputing.com/snowflake-cli/linux_$ARCH/$VERSION/snowflake-cli-$VERSION.$ARCH.deb"
    FILE_NAME="snowflake-cli-$VERSION.$ARCH.deb"
fi

echo "Downloading Snowflake CLI installation package $DOWNLOAD_URL"

curl -f -L -o $FILE_NAME $DOWNLOAD_URL

# Step 4: Verify the downloaded file
FILE="snowflake-cli-$VERSION.$ARCH.pkg"
if [ "$OS" == "Linux" ]; then
    FILE="snowflake-cli-$VERSION.$ARCH.deb"
fi

if file $FILE | grep -q 'Debian binary package\|xar archive'; then
    echo "The file is a valid package."
else
    echo "The file is not a valid package. Please check the URL and try again."
    exit 1
fi

# Step 5: Install the downloaded package
if [ "$OS" == "Linux" ]; then
    sudo dpkg -i $FILE
elif [ "$OS" == "Darwin" ]; then
    sudo installer -pkg $FILE -target /
fi

