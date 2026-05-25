import builtins
import io
import json
import zipfile
import re
import uuid
import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal

from cloud_config import get_supabase_client


def _serialize_sheet(df: pd.DataFrame | None) -> tuple[bytes, str]:
    """
    Serialize a sheet to bytes.
    Prefers Parquet (pyarrow) but falls back to CSV if pyarrow is unavailable.
    Returns (bytes, format).
    """
    if df is None:
        df = pd.DataFrame()
    try:
        import pyarrow  # noqa: F401
        df_buffer = io.BytesIO()
        df.to_parquet(df_buffer, index=False, engine='pyarrow')
        return df_buffer.getvalue(), "parquet"
    except Exception:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        return csv_bytes, "csv"

class CloudUploadWorker(QThread):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame, mask: pd.Series, file_name: str, sheet_manager):
        super().__init__()
        self.df = df
        self.mask = mask
        self.file_name = file_name
        self.sheet_manager = sheet_manager

    def run(self):
        try:
            user_id = builtins.CURRENT_USER.get("auth_uid")
            if not user_id:
                raise ValueError("Session is invalid. Please log out and log in again.")
            safe_file_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '', self.file_name.split('/')[-1].split('\\')[-1])
            if not safe_file_name:
                safe_file_name = "untitled.csv"
            
            file_id = str(uuid.uuid4())
            
            zip_buffer = io.BytesIO()
            sheet_meta = []
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for idx, sheet in enumerate(self.sheet_manager._sheets):
                    payload, fmt = _serialize_sheet(sheet['df'])
                    ext = "parquet" if fmt == "parquet" else "csv"
                    zf.writestr(f"sheet_{idx}.{ext}", payload)
                    
                    sheet_meta.append({
                        "index": idx,
                        "name": sheet['name'],
                        "row_count": len(sheet['df']),
                        "col_count": len(sheet['df'].columns),
                        "format": fmt,
                    })
                
                zf.writestr("sheet_meta.json", json.dumps(sheet_meta))
                
            zip_bytes = zip_buffer.getvalue()
            
            if len(zip_bytes) > 500 * 1024 * 1024:
                self.error.emit("File too large for cloud sync (max 500MB)")
                return
                
            storage_path = f"{user_id}/{file_id}/{safe_file_name}.zip"
            client = get_supabase_client()
            session_token = builtins.CURRENT_USER.get("session_token")
            if session_token:
                client.auth.set_session(session_token, builtins.CURRENT_USER.get("refresh_token") or "dummy")
            
            self.progress.emit("Uploading to cloud...")
            res = client.storage.from_("user-files").upload(
                storage_path, zip_bytes, {"content-type": "application/zip"}
            )
            
            # total rows and cols from the first sheet
            first_sheet_rows = sheet_meta[0]["row_count"] if sheet_meta else 0
            first_sheet_cols = sheet_meta[0]["col_count"] if sheet_meta else 0
            
            # Insert into user_files
            client.table("user_files").insert({
                "id": file_id,
                "user_id": user_id,
                "file_name": safe_file_name,
                "sheet_count": len(sheet_meta),
                "row_count": first_sheet_rows,
                "col_count": first_sheet_cols,
                "storage_path": storage_path,
            }).execute()
            
            self.finished.emit(file_id, storage_path)
            
        except Exception as e:
            self.error.emit(str(e))

class CloudDownloadWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, storage_path: str):
        super().__init__()
        self.storage_path = storage_path

    def run(self):
        try:
            client = get_supabase_client()
            session_token = builtins.CURRENT_USER.get("session_token")
            if session_token:
                client.auth.set_session(session_token, builtins.CURRENT_USER.get("refresh_token") or "dummy")
            user_id = builtins.CURRENT_USER.get("auth_uid")
            if not user_id:
                raise ValueError("Session is invalid. Please log out and log in again.")
            
            self.progress.emit("Downloading from cloud...")
            res = client.storage.from_("user-files").download(self.storage_path)
            
            zip_buffer = io.BytesIO(res)
            
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                meta_bytes = zf.read("sheet_meta.json")
                sheet_meta = json.loads(meta_bytes.decode('utf-8'))
                
                sheets_data = []
                for meta in sheet_meta:
                    try:
                        fmt = meta.get("format", "parquet")
                        if fmt == "csv":
                            csv_bytes = zf.read(f"sheet_{meta['index']}.csv")
                            df = pd.read_csv(io.BytesIO(csv_bytes))
                        else:
                            parquet_bytes = zf.read(f"sheet_{meta['index']}.parquet")
                            df_buffer = io.BytesIO(parquet_bytes)
                            df = pd.read_parquet(df_buffer, engine='pyarrow')
                        mask = df.duplicated(keep=False)
                        sheets_data.append({
                            "name": meta['name'],
                            "df": df,
                            "mask": mask
                        })
                    except Exception as sheet_e:
                        print(f"Error parsing sheet {meta['name']}: {sheet_e}")
                        continue
                        
                self.finished.emit({"sheets": sheets_data})
        except Exception as e:
            self.error.emit(str(e))

class CloudAutoSaveWorker(QThread):
    saved = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, file_id: str, storage_path: str, sheet_manager, model):
        super().__init__()
        self.file_id = file_id
        self.storage_path = storage_path
        self.sheet_manager = sheet_manager
        self.model = model

    def run(self):
        try:
            zip_buffer = io.BytesIO()
            sheet_meta = []
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for idx, sheet in enumerate(self.sheet_manager._sheets):
                    payload, fmt = _serialize_sheet(sheet['df'])
                    ext = "parquet" if fmt == "parquet" else "csv"
                    zf.writestr(f"sheet_{idx}.{ext}", payload)
                    
                    sheet_meta.append({
                        "index": idx,
                        "name": sheet['name'],
                        "row_count": len(sheet['df']),
                        "col_count": len(sheet['df'].columns),
                        "format": fmt,
                    })
                
                zf.writestr("sheet_meta.json", json.dumps(sheet_meta))
                
            zip_bytes = zip_buffer.getvalue()
            
            client = get_supabase_client()
            session_token = builtins.CURRENT_USER.get("session_token")
            if session_token:
                client.auth.set_session(session_token, builtins.CURRENT_USER.get("refresh_token") or "dummy")
            user_id = builtins.CURRENT_USER.get("auth_uid")
            if not user_id:
                raise ValueError("Session is invalid. Please log out and log in again.")
            
            client.storage.from_("user-files").upload(
                self.storage_path, zip_bytes, {"content-type": "application/zip", "upsert": "true"}
            )
            
            first_sheet_rows = sheet_meta[0]["row_count"] if sheet_meta else 0
            first_sheet_cols = sheet_meta[0]["col_count"] if sheet_meta else 0
            
            client.table("user_files").update({
                "sheet_count": len(sheet_meta),
                "row_count": first_sheet_rows,
                "col_count": first_sheet_cols,
                "updated_at": "now()"
            }).eq("id", self.file_id).eq("user_id", user_id).execute()
            
            self.saved.emit(self.storage_path)
        except Exception as e:
            self.error.emit(str(e))

class CloudListFilesWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            client = get_supabase_client()
            session_token = builtins.CURRENT_USER.get("session_token")
            if session_token:
                client.auth.set_session(session_token, builtins.CURRENT_USER.get("refresh_token") or "dummy")
            user_id = builtins.CURRENT_USER.get("auth_uid")
            if not user_id:
                raise ValueError("Session is invalid. Please log out and log in again.")
            
            res = client.table("user_files").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
            self.finished.emit(res.data)
        except Exception as e:
            self.error.emit(str(e))

class CloudDeleteFileWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, file_id: str, storage_path: str):
        super().__init__()
        self.file_id = file_id
        self.storage_path = storage_path

    def run(self):
        try:
            client = get_supabase_client()
            session_token = builtins.CURRENT_USER.get("session_token")
            if session_token:
                client.auth.set_session(session_token, builtins.CURRENT_USER.get("refresh_token") or "dummy")
            user_id = builtins.CURRENT_USER.get("auth_uid")
            if not user_id:
                raise ValueError("Session is invalid. Please log out and log in again.")
            
            client.storage.from_("user-files").remove([self.storage_path])
            client.table("user_files").delete().eq("id", self.file_id).eq("user_id", user_id).execute()
            
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
