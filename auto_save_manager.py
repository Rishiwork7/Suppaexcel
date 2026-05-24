from PyQt6.QtCore import QTimer
from datetime import datetime
from cloud_worker import CloudAutoSaveWorker

class AutoSaveManager:
    def __init__(self, sheet_manager, model, sheet_controller, interval_seconds=30):
        self.sheet_manager = sheet_manager
        self.model = model
        self.sheet_controller = sheet_controller
        self.interval_seconds = interval_seconds
        self.file_id = None
        self.storage_path = None
        
        self.timer = None
        self.worker = None
        self._last_saved_at = None

    def set_file(self, file_id: str, storage_path: str):
        self.file_id = file_id
        self.storage_path = storage_path

    def start(self, file_id: str, storage_path: str):
        self.set_file(file_id, storage_path)
        if self.timer:
            self.timer.stop()
            self.timer.deleteLater()
            
        self.timer = QTimer(parent=None)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(self.interval_seconds * 1000)

    def stop(self):
        if self.timer:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None

    def force_save(self):
        if not self.file_id or not self.storage_path:
            return
            
        if self.worker and self.worker.isRunning():
            return
            
        if self.sheet_controller:
            self.sheet_controller.sync_current_sheet_data()
            
        self.worker = CloudAutoSaveWorker(self.file_id, self.storage_path, self.sheet_manager, self.model)
        self.worker.saved.connect(self._on_saved)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_tick(self):
        self.force_save()

    def _on_saved(self, path):
        self._last_saved_at = datetime.now()

    def _on_error(self, err):
        # Silent failure for auto-save
        print(f"Auto-save error: {err}")

    @property
    def last_saved_at(self):
        return self._last_saved_at
