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

