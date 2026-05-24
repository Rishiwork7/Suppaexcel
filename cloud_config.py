import os
import sys
import json
import hashlib
import base64
import logging
from cryptography.fernet import Fernet
from supabase import create_client, Client

logger = logging.getLogger(__name__)
_client_cache = {}

SECRET_SALT = "PINNACLE_2024_SECRET_XYZ_CHANGE_THIS"

def _get_encryption_key():
    raw = f"{SECRET_SALT}_DATAPROCESSOR_v1"
    key_bytes = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)

def _get_config_path():
    if getattr(sys, 'frozen', False) or '__compiled__' in globals():
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.dat")

def _load_config() -> dict:
    config_path = _get_config_path()
    
    if not os.path.exists(config_path):
        # Development fallback
        from dotenv import load_dotenv
        load_dotenv()
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise RuntimeError(
                "Missing config. Run: python build_tools/encrypt_config.py"
            )
        logger.info("Config loaded from .env")
        return {"SUPABASE_URL": url, "SUPABASE_ANON_KEY": key}
    
    try:
        with open(config_path, "rb") as f:
            encrypted = f.read()
        fernet = Fernet(_get_encryption_key())
        decrypted = fernet.decrypt(encrypted)
        config = json.loads(decrypted.decode())
        logger.info("Config loaded from config.dat")
        return config
    except Exception:
        raise RuntimeError(
            "Config file is corrupted. Please contact support."
        )

def get_supabase_client(use_service_key: bool = False) -> Client:
    cache_key = "service" if use_service_key else "anon"
    
    if cache_key in _client_cache:
        return _client_cache[cache_key]
    
    config = _load_config()
    
    if use_service_key:
        from dotenv import load_dotenv
        load_dotenv()
        svc_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not svc_key:
            raise RuntimeError(
                "Service key not available. "
                "This operation requires admin access."
            )
        client = create_client(config["SUPABASE_URL"], svc_key)
    else:
        client = create_client(
            config["SUPABASE_URL"],
            config["SUPABASE_ANON_KEY"]
        )
    
    _client_cache[cache_key] = client
    return client
