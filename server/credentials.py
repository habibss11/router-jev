"""Credential storage independent of the installed plugin's version/cache."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


def key_file():
    override = os.environ.get("CODEX_DECISION_ROUTER_KEY_FILE")
    return Path(override).expanduser() if override else Path.home() / ".config/codex-decision-router/credentials.json"


def valid_key(value):
    return isinstance(value, str) and 8 <= len(value) <= 1024 and not any(c.isspace() for c in value)


def load_key():
    """Return (key, source, safe_error); never include credential content in errors."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return (key, "environment", None) if valid_key(key) else (None, "environment", "invalid_api_key_format")
    try:
        with key_file().open("rb") as source:
            data = source.read(8193)
        if len(data) > 8192:
            return None, "file", "credential_file_too_large"
        value = json.loads(data)
        key = value.get("OPENROUTER_API_KEY", "") if isinstance(value, dict) else None
        if key == "":
            return None, "file", "missing_openrouter_api_key"
        if not valid_key(key):
            return None, "file", "invalid_credential_file"
        return key, "file", None
    except FileNotFoundError:
        return None, "file", "missing_openrouter_api_key"
    except (OSError, ValueError, UnicodeError):
        return None, "file", "credential_file_unreadable_or_invalid"


def credential_status():
    key, source, error = load_key()
    return {"api_key_configured": bool(key), "api_key_source": source,
            "credential_file": str(key_file()), "credential_error": error}


def save_key(key, *, initialize_only=False):
    path = key_file()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if initialize_only:
        # O_EXCL preserves an existing credential without reading it.
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return path
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            target.write('{"OPENROUTER_API_KEY": ""}\n')
        return path
    if not valid_key(key):
        raise ValueError("invalid_api_key_format")
    fd, temporary = tempfile.mkstemp(prefix=".credentials-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump({"OPENROUTER_API_KEY": key}, target)
            target.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path
