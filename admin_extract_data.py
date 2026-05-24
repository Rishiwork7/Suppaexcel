import os
import zipfile
import io
import json
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

def extract_all_user_data(download_dir="./extracted_cloud_data"):
    """
    Downloads and extracts all user data from Supabase Cloud.
    Requires SUPABASE_SERVICE_KEY in .env to bypass Row Level Security.
    """
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        print("❌ Error: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
        print("Please add your Service Role Key to .env to extract all users' data.")
        return
        
    supabase = create_client(url, key)
    
    print("Fetching metadata for all users...")
    response = supabase.table("user_files").select("*").execute()
    files = response.data
    
    if not files:
        print("No files found in cloud.")
        return
        
    os.makedirs(download_dir, exist_ok=True)
    print(f"Found {len(files)} files. Starting extraction...\n")
    
    for f in files:
        user_id = f["user_id"]
        storage_path = f["storage_path"]
        file_name = f["file_name"]
        
        print(f"📥 Downloading '{file_name}' for user: {user_id}")
        
        try:
            # Download zip from storage
            res = supabase.storage.from_("user-files").download(storage_path)
            
            user_dir = os.path.join(download_dir, user_id)
            os.makedirs(user_dir, exist_ok=True)
            
            # Extract and convert back to CSV
            with zipfile.ZipFile(io.BytesIO(res), 'r') as zf:
                meta = json.loads(zf.read("sheet_meta.json"))
                for sheet in meta:
                    parquet_bytes = zf.read(f"sheet_{sheet['index']}.parquet")
                    df = pd.read_parquet(io.BytesIO(parquet_bytes))
                    
                    # Save as CSV for easy reading
                    out_name = f"{file_name.replace('.csv','')}_{sheet['name']}.csv"
                    out_path = os.path.join(user_dir, out_name)
                    df.to_csv(out_path, index=False)
                    print(f"  ✅ Saved: {out_path}")
        except Exception as e:
            print(f"  ❌ Failed to extract {file_name}: {e}")
            
    print("\n🎉 Extraction Complete! All data is saved in:", download_dir)

if __name__ == "__main__":
    extract_all_user_data()
