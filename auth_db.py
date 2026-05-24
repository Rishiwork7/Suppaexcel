"""
auth_db.py — Local SQLite authentication database.

Pure Python / no Qt.  Uses bcrypt (rounds=12) for all password hashing.
Never logs or exposes plaintext or hashed passwords.
"""

from __future__ import annotations

import os
import platform
import sqlite3
import sys
from typing import Optional

import bcrypt


# ---------------------------------------------------------------------------
# Database path — next to EXE when frozen, next to __file__ otherwise
# ---------------------------------------------------------------------------

def _db_path() -> str:
    if getattr(sys, "frozen", False):          # PyInstaller bundle
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "auth.db")


import os
import bcrypt
from cloud_config import get_supabase_client

def _hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=12)).decode()

def _check_password(plaintext: str, hashed: str) -> bool:
    if not hashed.startswith("$2b$"):
        # Allow plaintext matching for admin-created temporary passwords
        return plaintext == hashed
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except Exception:
        return False

def init_db() -> None:
    # We no longer create local DBs.
    # The users must be created directly in the Supabase `user_profiles` table.
    pass

def verify_user(user_id: str, password: str) -> dict | None:
    try:
        client = get_supabase_client()
        res = client.table("user_profiles").select("*").eq("user_id", user_id).execute()
        if not res.data:
            return None
            
        user_row = res.data[0]
        hashed = user_row.get("hashed_password", "")
        role = user_row.get("role", "user")
        is_first_login = int(user_row.get("is_first_login", 0))
        
        if not _check_password(password, hashed):
            return None
            
        return {"user_id": user_id, "role": role, "is_first_login": is_first_login}
    except Exception as e:
        print(f"Verify user failed: {e}")
        return None

def reset_password(user_id: str, new_password: str) -> None:
    try:
        client = get_supabase_client()
        hashed = _hash_password(new_password)
        client.table("user_profiles").update({
            "hashed_password": hashed,
            "is_first_login": 0
        }).eq("user_id", user_id).execute()
    except Exception as e:
        raise RuntimeError(f"Reset password failed: {e}")

# The following methods are obsolete since Admin panel is removed, but kept to prevent import errors
def create_user(*args, **kwargs):
    pass

def list_users(*args, **kwargs):
    return []

def delete_user(*args, **kwargs):
    pass

