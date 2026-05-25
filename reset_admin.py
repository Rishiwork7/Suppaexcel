import os
import bcrypt
from supabase import create_client

os.environ["SUPABASE_URL"] = "https://euloqmxisohlkioesztb.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "sb_secret_UpgkfiK3AEaeCQFM8sNIYA_au1EEcke"

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]

client = create_client(url, key)

admin_password = "Admin@1234"
hashed = bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

client.table("user_profiles").upsert({
    "user_id": "admin",
    "hashed_password": hashed,
    "role": "admin",
    "is_first_login": 1
}).execute()

print("✅ Admin password reset to Admin@1234 successfully.")
