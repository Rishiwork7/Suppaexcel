import os
import sys
import argparse

os.environ["SUPABASE_URL"] = "https://euloqmxisohlkioesztb.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "sb_secret_UpgkfiK3AEaeCQFM8sNIYA_au1EEcke"

from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

def generate_user(username, password, role="user"):
    email = f"{username}@app.local"
    try:
        # Create user in Auth
        res = client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True
        })
        print(f"✅ Auth User {email} created successfully!")
    except Exception as e:
        if "already been registered" in str(e):
            print(f"User {email} already exists. Updating password...")
            users_res = client.auth.admin.list_users()
            for u in users_res:
                if u.email == email:
                    client.auth.admin.update_user_by_id(u.id, {"password": password})
                    print("✅ Password updated.")
                    break
        else:
            print(f"❌ Error creating auth user: {e}")
            return

    # Create profile
    try:
        import bcrypt
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        
        client.table("user_profiles").upsert({
            "user_id": username,
            "hashed_password": hashed,
            "role": role,
            "is_first_login": 1
        }).execute()
        print(f"✅ User profile for {username} created/updated successfully!")
    except Exception as e:
        print(f"❌ Error creating user profile: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("username", help="Username (without @app.local)")
    parser.add_argument("password", help="Password")
    parser.add_argument("--role", default="user", help="Role (admin or user)")
    args = parser.parse_args()
    
    generate_user(args.username, args.password, args.role)
