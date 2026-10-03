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


def _write_env_file(updates: dict):
    """Update or insert key=value pairs in .env file cleanly."""
    lines = []
    existing_keys = set()
    if ENV_PATH.exists():
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if "=" in stripped and not stripped.startswith("#"):
                        k, _ = stripped.split("=", 1)
                        k = k.strip()
                        if k in updates:
                            lines.append(f"{k}={updates[k]}\n")
                            existing_keys.add(k)
                            continue
                    lines.append(line)
        except Exception:
            pass

    for k, v in updates.items():
        if k not in existing_keys:
            lines.append(f"{k}={v}\n")

    try:
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        print(f"[Credentials] Error writing .env: {e}")


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
    """Store a secret securely across Windows Credential Manager and local .env file."""
    # 1. Set in active process environment immediately
    os.environ[key] = secret

    # 2. Write to local .env fallback
    _write_env_file({key: secret})

    # 3. Store in Windows Credential Manager
    if keyring:
        try:
            keyring.set_password(SERVICE_NAME, key, secret)
            return True
        except Exception as e:
            print(f"[Credentials] Keyring write notice: {e}")
            return True  # Saved to .env and os.environ

    return True


def delete_secret(key: str) -> bool:
    """Remove a secret from Windows Credential Manager, os.environ, and .env."""
    os.environ.pop(key, None)
    if ENV_PATH.exists():
        try:
            env_vars = _read_env_file()
            if key in env_vars:
                del env_vars[key]
                lines = [f"{k}={v}\n" for k, v in env_vars.items()]
                with open(ENV_PATH, "w", encoding="utf-8") as f:
                    f.writelines(lines)
        except Exception:
            pass

    if keyring:
        try:
            keyring.delete_password(SERVICE_NAME, key)
            return True
        except Exception:
            pass
    return True


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
    },
    "Depositphotos": {
        "protocol": "ftp",
        "host": "ftp.depositphotos.com",
        "port": 21,
        "default_user": "AngelusH",
        "remote_dir": "/",
        "cred_key": "DEPOSITPHOTOS_PASSWORD",
        "notes": "Standard FTP (ftp.depositphotos.com, port 21, passive mode)"
    },
    "Alamy": {
        "protocol": "ftp",
        "host": "upload.alamy.com",
        "port": 21,
        "default_user": "AngelusH",
        "remote_dir": "Stock",
        "cred_key": "ALAMY_PASSWORD",
        "notes": "Standard FTP (upload.alamy.com:21). Upload images to 'Stock' directory. Alamy auto-ingests IPTC/XMP from JPEG."
    }
}
