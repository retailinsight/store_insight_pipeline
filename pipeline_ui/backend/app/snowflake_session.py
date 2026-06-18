"""
Snowflake session factory for the Pipeline Experiments backend.

Mirrors the pattern in ``api2/app/snowflake_session.py`` — reads connection
parameters from environment variables (or a ``.env`` file).
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_der_private_key,
    load_pem_private_key,
)
from dotenv import load_dotenv
from snowflake.snowpark import Session

load_dotenv(override=True)

_session: Session | None = None


def _is_alive(session: Session) -> bool:
    try:
        session.sql("SELECT 1").collect()
        return True
    except Exception as exc:
        print(f"[snowflake_session] Cached session is dead: {exc}")
        return False


def get_session() -> Session:
    """Return a cached Snowpark session, creating one if needed."""
    global _session
    if _session is not None and not _is_alive(_session):
        try:
            _session.close()
        except Exception:
            pass
        _session = None
    if _session is None:
        _session = _create_session()
    return _session


def _load_private_key_bytes() -> bytes | None:
    passphrase_str = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    passphrase = passphrase_str.encode() if passphrase_str else None

    key_b64 = os.getenv("SNOWFLAKE_PRIVATE_KEY_B64")
    key_pem = os.getenv("SNOWFLAKE_PRIVATE_KEY")
    key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")

    if key_b64:
        key_data = base64.b64decode(key_b64.strip())
    elif key_pem:
        key_data = key_pem.replace("\\n", "\n").encode()
    elif key_path:
        with open(key_path, "rb") as f:
            key_data = f.read()
    else:
        return None

    try:
        private_key = load_pem_private_key(key_data, password=passphrase, backend=default_backend())
    except ValueError:
        private_key = load_der_private_key(key_data, password=passphrase, backend=default_backend())

    return private_key.private_bytes(
        encoding=Encoding.DER,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )


def _create_session() -> Session:
    params = {
        "account":   _require("SNOWFLAKE_ACCOUNT"),
        "user":      _require("SNOWFLAKE_USER"),
        "role":      os.getenv("SNOWFLAKE_ROLE",      "ACL_SNOWFLAKE_RI_EOE_PRD_DP_USER"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_LEARNING_WH"),
        "database":  os.getenv("SNOWFLAKE_DATABASE",  "SNOWFLAKE_LEARNING_DB"),
        "schema":    os.getenv("SNOWFLAKE_SCHEMA",    "STORE_INSIGHT"),
    }

    private_key_bytes = _load_private_key_bytes()
    if private_key_bytes:
        params["private_key"] = private_key_bytes
    elif os.getenv("SNOWFLAKE_PASSWORD"):
        params["password"] = os.getenv("SNOWFLAKE_PASSWORD")
    else:
        params["authenticator"] = "externalbrowser"

    return Session.builder.configs(params).create()


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise OSError(f"Required environment variable '{key}' is not set.")
    return value
