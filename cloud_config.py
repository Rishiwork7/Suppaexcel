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

def get_supabase_client(use_service_key: bool = False) -> Client:
    cache_key = "service" if use_service_key else "anon"
    
    if cache_key in _client_cache:
        return _client_cache[cache_key]
    
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise RuntimeError("Missing SUPABASE_URL in environment. Hardcode it in main.py.")
        
    if use_service_key:
        svc_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not svc_key:
            raise RuntimeError("Missing SUPABASE_SERVICE_KEY in environment.")
        client = create_client(url, svc_key)
    else:
        anon_key = os.environ.get("SUPABASE_ANON_KEY")
        if not anon_key:
            raise RuntimeError("Missing SUPABASE_ANON_KEY in environment.")
        client = create_client(url, anon_key)
    
    _client_cache[cache_key] = client
    return client
