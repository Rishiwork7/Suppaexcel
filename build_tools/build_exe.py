"""
Complete secured build script using Nuitka.
Usage: python build_tools/build_exe.py
Requirements: pip install nuitka ordered-set zstandard
Approximate build time: 10-15 minutes first run.
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

def encrypt_config():
    print("🔐 Generating encrypted config.dat...")
    result = subprocess.run(
        [sys.executable, "build_tools/encrypt_config.py"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("❌ encrypt_config.py failed:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
    print("   config.dat generated.")

def build_exe():
    print("🔨 Starting Nuitka compilation (this takes 10-15 min)...")
    
    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--windows-disable-console",
        f"--output-filename={APP_NAME}.exe",
        f"--output-dir={OUTPUT_DIR}",
        "--enable-plugin=pyqt6",
        "--python-flag=no_docstrings",
        "--python-flag=no_asserts",
        "--remove-output",
    ]
    
    # Include all modules
    for mod in ALL_MODULES:
        cmd.append(f"--include-module={mod}")
    
    # Include icon if exists
    if os.path.exists(ICON_FILE):
        cmd.append(f"--include-data-files={ICON_FILE}={ICON_FILE}")
        cmd.append(f"--windows-icon-from-ico={ICON_FILE}")
    
    # Include pandas, pyarrow data files
    cmd += [
        "--include-package=pandas",
        "--include-package=pyarrow",
        "--include-package=bcrypt",
        "--include-package=cryptography",
        "--include-package=supabase",
        "--include-package=keyring",
        "--include-package=dotenv",
    ]
    
    cmd.append(MAIN_FILE)
    
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print("❌ Nuitka build failed. Check errors above.")
        sys.exit(1)
    
    print("✅ EXE compiled successfully.")

def package():
    print("📦 Creating distribution package...")
    
    os.makedirs(DIST_FOLDER, exist_ok=True)
    
    # Copy EXE
    exe_src = os.path.join(OUTPUT_DIR, f"{APP_NAME}.exe")
    if not os.path.exists(exe_src):
        print("❌ EXE not found in dist_output/")
        sys.exit(1)
    shutil.copy(exe_src, DIST_FOLDER)
    
    # Copy config.dat
    config_src = os.path.join(OUTPUT_DIR, "config.dat")
    if not os.path.exists(config_src):
        print("❌ config.dat not found.")
        sys.exit(1)
    shutil.copy(config_src, DIST_FOLDER)
    
    # Write README for client
    readme = f"""{APP_NAME} v{VERSION} — Setup Instructions
{'='*45}

REQUIREMENTS:
- Windows 10 or higher (64-bit)
- Internet connection (required for login and cloud sync)

SETUP:
1. Keep {APP_NAME}.exe and config.dat in the SAME folder
   (Do NOT move config.dat elsewhere)
2. Double-click {APP_NAME}.exe to launch
3. Enter your User ID and Password provided by administrator
4. On first login you will be forced to set a new password

RULES:
- Do NOT delete config.dat — app will not start without it
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
    print(f"   ├── {APP_NAME}.exe    ← send this to client")
    print(f"   ├── config.dat        ← send this to client")
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
    encrypt_config()
    build_exe()
    package()

if __name__ == "__main__":
    main()
