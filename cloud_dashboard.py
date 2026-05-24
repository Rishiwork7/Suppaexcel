import builtins
from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QProgressBar
)

from cloud_worker import CloudListFilesWorker, CloudDownloadWorker, CloudDeleteFileWorker

class CloudDashboard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chosen_file_id = None
        self.chosen_storage_path = None
        self.chosen_sheets = None
        self._is_downloading = False
        
        self.setWindowTitle("Cloud Files")
        self.setMinimumSize(700, 500)
        self.setStyleSheet("background-color: #F5F7F8;")
        
        self._build_ui()
        self._load_files()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(14)
        
        # Header
        hdr = QHBoxLayout()
        title = QLabel(f"Welcome, {builtins.CURRENT_USER['user_id']}! Your Cloud Files:")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #212121;")
        hdr.addWidget(title)
        hdr.addStretch()
        
        self.btn_new = self._make_btn("📄 New File", "#4CAF50", "#388E3C")
        self.btn_refresh = self._make_btn("🔄 Refresh", "#2196F3", "#1565C0")
        self.btn_delete = self._make_btn("🗑️ Delete", "#F44336", "#C62828")
        
        self.btn_new.clicked.connect(self._on_new_file)
        self.btn_refresh.clicked.connect(self._load_files)
        self.btn_delete.clicked.connect(self._on_delete)
        
        hdr.addWidget(self.btn_new)
        hdr.addWidget(self.btn_refresh)
        hdr.addWidget(self.btn_delete)
        main.addLayout(hdr)
        
        self.no_files_label = QLabel("No files yet")
        self.no_files_label.setStyleSheet("color: #757575; font-size: 14px;")
        self.no_files_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_files_label.setVisible(False)
        main.addWidget(self.no_files_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["File Name", "Sheets", "Rows", "Last Modified"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_open)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #E0E0E0;
                background-color: white;
                border-radius: 6px;
            }
            QTableWidget::item:selected {
                background-color: #E3F2FD;
                color: #212121;
            }
            QHeaderView::section {
                background-color: #FAFAFA;
                padding: 6px;
                font-weight: bold;
            }
        """)
        main.addWidget(self.table)
        
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.progress.setRange(0, 0) # indeterminate
        main.addWidget(self.progress)
        
        # Bottom Open Button
        btm = QHBoxLayout()
        btm.addStretch()
        self.btn_open = self._make_btn("📂 Open Selected", "#2196F3", "#1565C0")
        self.btn_open.setFixedHeight(40)
        self.btn_open.clicked.connect(self._on_open)
        btm.addWidget(self.btn_open)
        main.addLayout(btm)
        
    def _make_btn(self, text, bg, hover):
        btn = QPushButton(text)
        btn.setFixedHeight(34)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: white; border: none; border-radius: 6px; padding: 4px 16px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:disabled {{ background-color: #BDBDBD; }}
        """)
        return btn

    def _set_ui_enabled(self, enabled):
        self.table.setEnabled(enabled)
        self.btn_new.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled)
        self.btn_delete.setEnabled(enabled)
        self.btn_open.setEnabled(enabled)
        self.progress.setVisible(not enabled)

    def _load_files(self):
        self._set_ui_enabled(False)
        self.worker = CloudListFilesWorker()
        self.worker.finished.connect(self._on_files_loaded)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_files_loaded(self, files):
        self._set_ui_enabled(True)
        self.files = files
        
        if not files:
            self.table.setVisible(False)
            self.no_files_label.setVisible(True)
            return
            
        self.table.setVisible(True)
        self.no_files_label.setVisible(False)
        self.table.setRowCount(0)
        
        for row_idx, f in enumerate(files):
            self.table.insertRow(row_idx)
            
            try:
                dt = datetime.fromisoformat(f["updated_at"].replace('Z', '+00:00'))
                dt_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                dt_str = f["updated_at"]
                
            self.table.setItem(row_idx, 0, QTableWidgetItem(f["file_name"]))
            
            sheets_item = QTableWidgetItem(str(f["sheet_count"]))
            sheets_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 1, sheets_item)
            
            rows_item = QTableWidgetItem(str(f["row_count"]))
            rows_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 2, rows_item)
            
            self.table.setItem(row_idx, 3, QTableWidgetItem(dt_str))

    def _on_new_file(self):
        self.chosen_file_id = None
        self.chosen_storage_path = None
        self.chosen_sheets = None
        self.accept()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
            
        file_data = self.files[row]
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete {file_data['file_name']} from cloud?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._set_ui_enabled(False)
            self.del_worker = CloudDeleteFileWorker(file_data["id"], file_data["storage_path"])
            self.del_worker.finished.connect(self._load_files)
            self.del_worker.error.connect(self._on_error)
            self.del_worker.start()

    def _on_open(self):
        if self._is_downloading:
            return
            
        row = self.table.currentRow()
        if row < 0:
            return
            
        self._is_downloading = True
        self._set_ui_enabled(False)
        self.file_data = self.files[row]
        
        self.dl_worker = CloudDownloadWorker(self.file_data["storage_path"])
        self.dl_worker.finished.connect(self._on_downloaded)
        self.dl_worker.error.connect(self._on_error)
        self.dl_worker.start()

    def _on_downloaded(self, data):
        self._is_downloading = False
        self._set_ui_enabled(True)
        self.chosen_file_id = self.file_data["id"]
        self.chosen_storage_path = self.file_data["storage_path"]
        self.chosen_sheets = data["sheets"]
        self.accept()

    def _on_error(self, err):
        self._is_downloading = False
        self._set_ui_enabled(True)
        QMessageBox.critical(self, "Cloud Error", f"Operation failed:\n{err}")
