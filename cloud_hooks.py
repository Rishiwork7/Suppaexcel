import builtins
from PyQt6.QtWidgets import QMessageBox
from auto_save_manager import AutoSaveManager
from cloud_worker import CloudUploadWorker

class CloudHooks:
    def __init__(self, app):
        self.app = app
        
        if not getattr(builtins, "CLOUD_AVAILABLE", False):
            return
            
        self.auto_save = AutoSaveManager(app.sheet_manager, app.model, getattr(app, 'sheet_controller', None), interval_seconds=30)
        
        sheets = getattr(builtins, "CLOUD_SHEETS", None)
        if sheets is not None:
            # User opened existing file
            app.sheet_manager.sheets.clear()
            for s in sheets:
                app.sheet_manager.add_sheet(s['name'])
                app.sheet_manager.set_sheet_data(
                    app.sheet_manager.sheet_count() - 1,
                    s['df'],
                    s['mask']
                )
                
            sheet_names = [s['name'] for s in app.sheet_manager.sheets]
            app.sheet_tab_bar.refresh(sheet_names, active_index=0)
            
            first_sheet = app.sheet_manager.sheets[0]
            app.model.load_dataframe(first_sheet['df'], first_sheet['mask'])
            
            file_id = builtins.CLOUD_FILE_ID
            storage_path = builtins.CLOUD_STORAGE_PATH
            if file_id and storage_path:
                self.auto_save.start(file_id, storage_path)
                # Immediate save so data is persisted right away
                self.auto_save.force_save()
                
        # Connect export action
        self.app.window.action_export.triggered.connect(self._on_export)
        
        # We need to hook into the worker finish from app, but app uses a worker object.
        # Wait, the app.worker has a finished signal. Let's just wrap it.
        # But wait, btn_upload opens file dialog, then app starts a worker.
        # We can hook into the worker finished. However, app creates the worker dynamically.
        # So it's easier to connect to app._on_worker_finished or app._on_file_loaded.
        # Let's see if DataProcessorApp has a known signal.
        # The prompt says: "Connect app.window.btn_upload finished signal: after first local file load,
        # if CLOUD_FILE_ID is None, auto-upload to cloud via CloudUploadWorker"
        # Since btn_upload doesn't have a finished signal, the user might mean `app._on_worker_finished` or similar.
        # Or I can just overwrite app.window.btn_upload.clicked, but that violates rules.
        # I can just monkey-patch the app's _on_worker_finished safely.
        
        original_finished = self.app._on_file_loaded
        def wrapped_finished(*args, **kwargs):
            original_finished(*args, **kwargs)
            self._check_first_upload()
            # If already linked to a cloud file, save immediately
            if getattr(builtins, "CLOUD_FILE_ID", None) and getattr(builtins, "CLOUD_STORAGE_PATH", None):
                self.auto_save.force_save()
        
        self.app._on_file_loaded = wrapped_finished

    def _on_export(self):
        self.auto_save.force_save()
        
    def _check_first_upload(self):
        if not getattr(builtins, "CLOUD_AVAILABLE", False):
            return
            
        file_id = getattr(builtins, "CLOUD_FILE_ID", None)
        if file_id is None:
            idx = self.app.sheet_tab_bar._active_index
            if idx >= 0 and idx < self.app.sheet_manager.sheet_count():
                file_name = self.app.sheet_manager.get_sheet(idx).get('name', 'untitled.csv')
            else:
                file_name = "untitled.csv"
                
            self.app.sheet_controller.sync_current_sheet_data()
            self.upload_worker = CloudUploadWorker(self.app.model.df, self.app.model.duplicate_mask, file_name, self.app.sheet_manager)
            self.upload_worker.finished.connect(self._on_first_upload_done)
            self.upload_worker.error.connect(self._on_upload_error)
            self.upload_worker.start()
            
    def _on_first_upload_done(self, file_id, storage_path):
        builtins.CLOUD_FILE_ID = file_id
        builtins.CLOUD_STORAGE_PATH = storage_path
        self.auto_save.start(file_id, storage_path)
        # First upload succeeded — ensure immediate persistence
        self.auto_save.force_save()
        
    def _on_upload_error(self, err):
        QMessageBox.critical(self.app.window, "Cloud Upload Error", f"Upload failed:\n{err}")
