"""Managing snowflake secrets"""

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
from typing import Optional
import os

SECRETS = {}


def read_secret(
    secret_name: str,
    from_field: Optional[str] = None,
    from_file: Optional[str] = None,
    env_name: Optional[str] = None,
) -> None:
    """Reads secrets from specified json file or environment variable."""
    if env_name:
        SECRETS[secret_name] = os.environ.get(env_name, None)

    if not SECRETS[secret_name] and from_file and from_field:
        try:
            with open(from_file, "r", encoding="utf-8") as f:
                import json

                config = json.loads(f.read())
                SECRETS[secret_name] = config.get(from_field, None)
        except FileNotFoundError as e:
            import logging

            current_working_directory = os.getcwd()
            logging.error("%s\n CWD:%s", e.strerror, current_working_directory)


def get_generic_secret_string(label: str) -> str:
    """Retrieves specified secret from loaded const"""
    return SECRETS.get(label, label)
