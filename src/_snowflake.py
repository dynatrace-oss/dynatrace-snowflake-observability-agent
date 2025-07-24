"""Managing snowflake secrets"""

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
