"""
session.py — OS-keyring session management with Fernet fallback.

Pure Python / no Qt.
Session token = JSON {user_id, role, timestamp} stored under the key "session"
in the OS credential store via keyring.  If keyring is unavailable (e.g. a
headless server), a Fernet-encrypted file .session_cache is used instead.
Sessions expire after SESSION_TIMEOUT_HOURS hours.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
import uuid
from typing import Optional

APP_NAME: str = "DataProcessorApp"
SESSION_KEY: str = "session"
SESSION_TIMEOUT_HOURS: float = 8.0

# ---------------------------------------------------------------------------
# Fallback path — same directory as auth.db
# ---------------------------------------------------------------------------

def _base_dir() -> str:
    if getattr(sys, "frozen", False) or '__compiled__' in globals():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


FALLBACK_PATH: str = os.path.join(_base_dir(), ".session_cache")


# ---------------------------------------------------------------------------
# Machine-specific Fernet key (for fallback)
# ---------------------------------------------------------------------------

def _fernet_key() -> bytes:
    """Derive a stable 32-byte key from machine identifiers."""
    from cryptography.fernet import Fernet
    import base64

    raw = f"{uuid.getnode()}|{platform.node()}"
    digest = hashlib.sha256(raw.encode()).digest()   # 32 bytes
    return base64.urlsafe_b64encode(digest)          # Fernet needs URL-safe b64


def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(_fernet_key())


# ---------------------------------------------------------------------------
# Low-level read / write — keyring with Fernet fallback
# ---------------------------------------------------------------------------

def _write_token(token: str) -> None:
    """Persist *token* string to keyring or fallback file."""
    try:
        import keyring
        keyring.set_password(APP_NAME, SESSION_KEY, token)
        return
    except Exception:
        pass  # keyring unavailable — fall through to file fallback

    # Fernet-encrypted file fallback
    try:
        encrypted = _fernet().encrypt(token.encode())
        with open(FALLBACK_PATH, "wb") as fh:
            fh.write(encrypted)
        if platform.system() != "Windows":
            try:
                os.chmod(FALLBACK_PATH, 0o600)
            except OSError:
                pass
    except Exception:
        pass  # best-effort


def _read_token() -> Optional[str]:
    """Return stored token string or None."""
    # Try keyring first
    try:
        import keyring
        token = keyring.get_password(APP_NAME, SESSION_KEY)
        if token:
            return token
    except Exception:
        pass

    # Try fallback file
    try:
        if os.path.exists(FALLBACK_PATH):
            with open(FALLBACK_PATH, "rb") as fh:
                encrypted = fh.read()
            return _fernet().decrypt(encrypted).decode()
    except Exception:
        pass

    return None


def _delete_token() -> None:
    """Remove stored token from keyring and/or fallback file."""
    try:
        import keyring
        keyring.delete_password(APP_NAME, SESSION_KEY)
    except Exception:
        pass

    try:
        if os.path.exists(FALLBACK_PATH):
            os.remove(FALLBACK_PATH)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_session(user_id: str, role: str) -> None:
    """Persist a new session for *user_id* with *role*."""
    payload = {"user_id": user_id, "role": role, "timestamp": time.time()}
    _write_token(json.dumps(payload))


def load_session() -> Optional[dict]:
    """
    Return ``{user_id, role, timestamp}`` if a valid, non-expired session
    exists, else return None.
    """
    token = _read_token()
    if not token:
        return None
    try:
        payload = json.loads(token)
    except (json.JSONDecodeError, ValueError):
        _delete_token()
        return None

    # Validate required fields
    if not all(k in payload for k in ("user_id", "role", "timestamp")):
        _delete_token()
        return None

    # Check expiry
    age_hours = (time.time() - float(payload["timestamp"])) / 3600.0
    if age_hours >= SESSION_TIMEOUT_HOURS:
        _delete_token()
        return None

    return payload


def clear_session() -> None:
    """Invalidate the stored session."""
    _delete_token()
