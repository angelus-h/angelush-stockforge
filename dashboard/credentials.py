"""
credentials.py
Secure credential storage for StockForge using Windows Credential Manager (keyring)
with automatic fallback to .env and environment variables.
"""

import os
from pathlib import Path

try:
    import keyring
except ImportError:
    keyring = None

SERVICE_NAME = "StockForge"
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"


def _read_env_file():
    """Simple parser for .env file key=value pairs."""
    env_vars = {}
    if ENV_PATH.exists():
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip().strip("'\"")
        except Exception:
            pass
    return env_vars


def get_secret(key: str, default: str = "") -> str:
    """
    Retrieve a password/secret using secure hierarchy:
    1. Windows Credential Manager (keyring)
    2. os.environ
    3. .env file
    """
    # 1. Try Windows Credential Manager
    if keyring:
        try:
            val = keyring.get_password(SERVICE_NAME, key)
            if val:
                return val
        except Exception:
            pass

    # 2. Try os.environ
    if key in os.environ and os.environ[key]:
        return os.environ[key]

    # 3. Try .env file
    env_vars = _read_env_file()
    if key in env_vars and env_vars[key]:
        return env_vars[key]

    return default


def set_secret(key: str, secret: str) -> bool:
    """Store a secret securely in Windows Credential Manager."""
    if not keyring:
        return False
    try:
        keyring.set_password(SERVICE_NAME, key, secret)
        return True
    except Exception as e:
        print(f"[Credentials] Error setting password in keyring: {e}")
        return False


def delete_secret(key: str) -> bool:
    """Remove a secret from Windows Credential Manager."""
    if not keyring:
        return False
    try:
        keyring.delete_password(SERVICE_NAME, key)
        return True
    except Exception:
        return False


# Standard Agency Presets with default parameters
AGENCY_PRESETS = {
    "Adobe Stock": {
        "protocol": "sftp",
        "host": "sftp.contributor.adobestock.com",
        "port": 22,
        "default_user": "208758992",
        "remote_dir": "/",
        "cred_key": "ADOBE_STOCK_PASSWORD",
        "notes": "SFTP with password authentication"
    },
    "Vecteezy": {
        "protocol": "sftp",
        "host": "content-ftp.eezy.com",
        "port": 22,
        "default_user": "miklosgreczi424081",
        "remote_dir": "/",
        "cred_key": "VECTEEZY_PASSWORD",
        "auto_upload_csv": True,
        "notes": "SFTP upload (media + vecteezy.csv)"
    },
    "Shutterstock": {
        "protocol": "ftps",
        "host": "ftps.shutterstock.com",
        "port": 21,
        "default_user": "AngelusH",
        "remote_dir": "/",
        "cred_key": "SHUTTERSTOCK_PASSWORD",
        "notes": "Explicit FTPS (TLS)"
    },
    "Pond5": {
        "protocol": "ftp",
        "host": "ftp.pond5.com",
        "port": 21,
        "default_user": "AngelusH",
        "remote_dir": "/",
        "cred_key": "POND5_PASSWORD",
        "notes": "Standard FTP"
    },
    "Dreamstime": {
        "protocol": "ftp",
        "host": "upload.dreamstime.com",
        "port": 21,
        "default_user": "61235210",
        "remote_dir": "/",
        "cred_key": "DREAMSTIME_PASSWORD",
        "passive": True,
        "notes": "FTP / FTPS (passive mode)"
    }
}
