import os
import sys

os.environ["SUPABASE_URL"] = "https://euloqmxisohlkioesztb.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "sb_secret_UpgkfiK3AEaeCQFM8sNIYA_au1EEcke"

from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

email = "admin@app.local"
password = "Admin@1234"

try:
    # Try to create user
    res = client.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True
    })
    print(f"✅ Auth User {email} created successfully!")
except Exception as e:
    if "already been registered" in str(e):
        print(f"User {email} already exists. Updating password...")
        # Get user
        users_res = client.auth.admin.list_users()
        for u in users_res:
            if u.email == email:
                client.auth.admin.update_user_by_id(u.id, {"password": password})
                print("✅ Password updated.")
                break
    else:
        print(f"❌ Error: {e}")
