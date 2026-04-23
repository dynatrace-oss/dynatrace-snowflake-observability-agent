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

# DSOA deployment image — contains all runtime tools and build artifacts.
#
# NOTE: The build/ directory must exist before running docker build.
#       Run ./scripts/dev/build.sh first.
#
# Usage:
#   Interactive:     docker run -it -v ./conf:/app/conf -e DTAGENT_TOKEN=... dsoa-deploy:local --env=prod
#   Non-interactive: docker run -v ./conf:/app/conf \
#                      -e DTAGENT_TOKEN=... \
#                      -e SNOWFLAKE_ACCOUNT=... \
#                      -e SNOWFLAKE_USER=... \
#                      -e SNOWFLAKE_PRIVATE_KEY_RAW=... \
#                      dsoa-deploy:local --env=prod --defaults --options=skip_confirm

FROM python:3.11-slim

# Install system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        bash \
        curl \
        jq \
        gawk \
    && rm -rf /var/lib/apt/lists/*

# Install yq and Snowflake CLI
RUN pip install --no-cache-dir yq snowflake-cli-labs

WORKDIR /app

# Copy DSOA deployment artifacts
COPY build/ ./build/
COPY scripts/deploy/ ./scripts/deploy/
COPY conf/config-template.yml ./conf/config-template.yml
COPY src/assets/ ./src/assets/

# Make scripts executable
RUN chmod +x scripts/deploy/*.sh

ENTRYPOINT ["./scripts/deploy/deploy.sh"]
