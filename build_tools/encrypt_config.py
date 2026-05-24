"""
Run ONCE on your machine to generate config.dat from .env
Never ship this script to clients.
Usage: python build_tools/encrypt_config.py
"""

import os
import sys
import json
import hashlib
import base64
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SECRET_SALT = "PINNACLE_2024_SECRET_XYZ_CHANGE_THIS"

def get_encryption_key():
    raw = f"{SECRET_SALT}_DATAPROCESSOR_v1"
    key_bytes = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)

def encrypt_config():
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not anon_key:
        print("❌ ERROR: SUPABASE_URL or SUPABASE_ANON_KEY missing in .env")
        sys.exit(1)
    
    config = {
        "SUPABASE_URL": url,
        "SUPABASE_ANON_KEY": anon_key,
        "APP_VERSION": "1.0.0",
        "APP_NAME": "DataProcessor"
    }
    
    key = get_encryption_key()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(json.dumps(config).encode())
    
    os.makedirs("dist_output", exist_ok=True)
    config_path = os.path.join("dist_output", "config.dat")
    with open(config_path, "wb") as f:
        f.write(encrypted)
    
    print(f"✅ config.dat generated at: {config_path}")
    print("   Ship this file alongside your EXE")
    print("   NEVER ship .env to clients")

if __name__ == "__main__":
    encrypt_config()
