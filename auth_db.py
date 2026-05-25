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
    if getattr(sys, "frozen", False) or '__compiled__' in globals():          # PyInstaller or Nuitka bundle
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "auth.db")


import os
import bcrypt
from cloud_config import get_supabase_client

def init_db() -> None:
    pass

def verify_user(user_id: str, password: str) -> dict | None:
    try:
        client = get_supabase_client()
        email = f"{user_id}@app.local"
        
        # 1. Sign in using Supabase Native Auth
        auth_res = client.auth.sign_in_with_password({
            "email": email, 
            "password": password
        })
        if not auth_res.user:
            return None
            
        # 2. Fetch profile metadata (role, is_first_login) using the authenticated session
        res = client.table("user_profiles").select("*").eq("user_id", user_id).execute()
        
        if res.data:
            user_row = res.data[0]
            role = user_row.get("role", "user")
            is_first_login = int(user_row.get("is_first_login", 0))
        else:
            role = "user"
            is_first_login = 0
            
        return {
            "user_id": user_id, 
            "role": role, 
            "is_first_login": is_first_login,
            "session_token": auth_res.session.access_token if auth_res.session else None,
            "auth_uid": auth_res.user.id
        }
    except Exception as e:
        import traceback
        try:
            with open("login_error_debug.txt", "w") as f:
                f.write(traceback.format_exc())
        except:
            pass
        print(f"Verify user failed: {e}")
        return None

def reset_password(user_id: str, new_password: str) -> None:
    try:
        client = get_supabase_client()
        
        # Update password in Supabase Auth (requires active user session, which we have from verify_user)
        client.auth.update_user({"password": new_password})
        
        # Update first login flag in profiles
        client.table("user_profiles").update({
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

