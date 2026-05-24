"""
Run ONCE to set admin password in Supabase.
Usage: python build_tools/setup_admin.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from dotenv import load_dotenv
from supabase import create_client

def setup_admin():
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not service_key:
        print("❌ ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
        sys.exit(1)
    
    client = create_client(url, service_key)
    
    admin_password = "Admin@1234"
    hashed = bcrypt.hashpw(
        admin_password.encode("utf-8"),
        bcrypt.gensalt(rounds=12)
    ).decode("utf-8")
    
    client.table("user_profiles").upsert({
        "user_id": "admin",
        "hashed_password": hashed,
        "role": "admin",
        "is_first_login": 1
    }).execute()
    
    print("✅ Admin user set in Supabase")
    print("   user_id:  admin")
    print("   password: Admin@1234")
    print("   ⚠️  Change this after first login!")

if __name__ == "__main__":
    setup_admin()
