"""
Complete secured build script using PyInstaller.
Usage: python build_tools/build_exe.py
Requirements: pip install pyinstaller
Approximate build time: 2-5 minutes.
"""

import os
import sys
import shutil
import subprocess

APP_NAME = "DataProcessor"
MAIN_FILE = "main.py"
VERSION = "1.0.0"
ICON_FILE = "app_icon_source_v2.png"
OUTPUT_DIR = "dist_output"
DIST_FOLDER = f"{OUTPUT_DIR}/{APP_NAME}_v{VERSION}"

ALL_MODULES = [
    "models", "worker", "ui", "undo",
    "auth_db", "session",
    "login_window", "password_reset_window", "admin_panel",
    "admin_extract_data",
    "sheet_manager", "sheet_tab_bar", "sheet_controller",
    "cloud_config", "cloud_worker", "cloud_dashboard",
    "cloud_hooks", "auto_save_manager"
]

def clean():
    print("🧹 Cleaning previous build...")
    for folder in [OUTPUT_DIR, "build", "__pycache__"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    for f in os.listdir("."):
        if f.endswith(".spec"):
            os.remove(f)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("   Done.")

def verify_env():
    print("🔍 Verifying .env before build...")
    from dotenv import load_dotenv
    load_dotenv()
    missing = []
    for key in ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY"]:
        if not os.getenv(key):
            missing.append(key)
    if missing:
        print(f"❌ Missing in .env: {missing}")
        sys.exit(1)
    print("   .env OK")

# Removed encrypt_config as it's no longer needed

def build_exe():
    print("🔨 Starting Nuitka compilation (this takes a while)...")
    
    cmd = [
        sys.executable, "-m", "nuitka",
        "--assume-yes-for-downloads",
        "--standalone",
        "--onefile",
        "--enable-plugin=pyqt6",
        "--windows-console-mode=disable",
        f"--output-dir={OUTPUT_DIR}",
    ]
    
    if os.path.exists(ICON_FILE):
        if sys.platform == "win32":
            cmd.append(f"--windows-icon-from-ico={ICON_FILE}")
        elif sys.platform == "darwin":
            cmd.append(f"--macos-app-icon={ICON_FILE}")
    
    # Include packages for Nuitka
    hidden_imports = [
        "pandas", "pyarrow", "bcrypt", "cryptography", "supabase", "keyring", "dotenv",
        "postgrest", "realtime", "storage3", "httpx", "pydantic",
        "supabase_auth", "supabase_functions", "yarl"
    ]
    for pkg in hidden_imports:
        cmd.append(f"--include-package={pkg}")
    
    cmd.append(MAIN_FILE)
    
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print("❌ Nuitka build failed. Check errors above.")
        sys.exit(1)
    
    print("✅ Executable compiled successfully.")

def package():
    print("📦 Creating distribution package...")
    
    os.makedirs(DIST_FOLDER, exist_ok=True)
    
    # Find the output executable (Nuitka names it depending on OS)
    exe_src = os.path.join(OUTPUT_DIR, f"{APP_NAME}.exe")
    if not os.path.exists(exe_src):
        # Fallback for Mac/Linux Nuitka outputs and Windows main.exe
        alt_src_bin = os.path.join(OUTPUT_DIR, "main.bin")
        alt_src_out = os.path.join(OUTPUT_DIR, "main")
        alt_src_exe = os.path.join(OUTPUT_DIR, "main.exe")
        if os.path.exists(alt_src_bin):
            exe_src = alt_src_bin
        elif os.path.exists(alt_src_out):
            exe_src = alt_src_out
        elif os.path.exists(alt_src_exe):
            exe_src = alt_src_exe
        else:
            print("❌ Executable not found in dist_output/")
            sys.exit(1)
            
    # Copy to dist folder and rename it properly
    final_exe_name = f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME
    shutil.copy(exe_src, os.path.join(DIST_FOLDER, final_exe_name))
    
    # Write README for client
    readme = f"""{APP_NAME} v{VERSION} — Setup Instructions
{'='*45}

REQUIREMENTS:
- Internet connection (required for login and cloud sync)

SETUP:
1. Double-click the {final_exe_name} executable to launch
2. Enter your User ID and Password provided by administrator
3. On first login you will be forced to set a new password

RULES:
- Do NOT share your credentials with anyone
- Your files are automatically saved to cloud every 30 seconds

Support: your@email.com
Version: {VERSION}
"""
    with open(os.path.join(DIST_FOLDER, "README.txt"), "w") as f:
        f.write(readme)
    
    # ZIP the folder
    zip_path = f"{OUTPUT_DIR}/{APP_NAME}_v{VERSION}"
    shutil.make_archive(zip_path, "zip", OUTPUT_DIR, f"{APP_NAME}_v{VERSION}")
    
    print(f"\n{'='*50}")
    print(f"✅ BUILD COMPLETE")
    print(f"{'='*50}")
    print(f"📁 Folder:  {DIST_FOLDER}/")
    print(f"📦 ZIP:     {zip_path}.zip")
    print(f"\nContents:")
    print(f"   ├── {final_exe_name}    ← send this to client")
    print(f"   └── README.txt        ← send this to client")
    print(f"\n⚠️  NEVER send these to client:")
    print(f"   ✗ .env")
    print(f"   ✗ any .py files")
    print(f"   ✗ auth.db")
    print(f"   ✗ build_tools/")
    print(f"   ✗ venv/")

def main():
    print("="*50)
    print(f"  {APP_NAME} — Secured Build Pipeline")
    print("="*50)
    clean()
    verify_env()
    build_exe()
    package()

if __name__ == "__main__":
    main()
