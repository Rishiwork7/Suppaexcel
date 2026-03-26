"""
User Interface components for the Data Processing Application.

Builds the main window with a colorful toolbar, status label, and data grid.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QTableView, QFileDialog, QMessageBox, QProgressBar,
    QAbstractItemView, QFrame, QLineEdit, QMenu
)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal, QTimer, QPropertyAnimation, QPoint
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QAction, QIcon


class UndoPopup(QFrame):
    """
    Floating popup for instant Undo action.
    """
    undo_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 50)
        self.setStyleSheet("""
            QFrame {
                background-color: #333;
                border-radius: 8px;
            }
            QLabel {
                color: white;
                font-size: 12px;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border_radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        
        self.label = QLabel("Duplicates removed.")
        layout.addWidget(self.label)
        
        layout.addStretch()
        
        self.btn_undo = QPushButton("UNDO")
        self.btn_undo.clicked.connect(self.undo_requested.emit)
        layout.addWidget(self.btn_undo)
        
        self.hide()

    def show_message(self, message: str):
        self.label.setText(message)
        self.show()
        self.raise_()
        
        # Position at bottom center
        if self.parent():
            p_rect = self.parent().rect()
            self.move(
                (p_rect.width() - self.width()) // 2,
                p_rect.height() - self.height() - 40
            )


class MainWindow(QMainWindow):
    """
    Main application window with colorful toolbar and data grid.
    """
    undo_triggered = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("High-Performance Data Processor")
        self.setGeometry(100, 100, 1200, 750)
        self.setWindowIcon(QIcon("app_icon_source_v2.png"))

        # Setup platform-standard Undo shortcut (Cmd+Z on Mac, Ctrl+Z on Windows/Linux)
        self.shortcut_undo = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.shortcut_undo.activated.connect(self.undo_triggered.emit)
        
        # Initialize Undo Popup
        self.undo_popup = UndoPopup(self)
        
        # Initialize central widget
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #F5F7F8;")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # === COLORFUL TOOLBAR ===
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(10)
        
        def create_btn(text, color, hover_color):
            btn = QPushButton(text)
            btn.setMinimumHeight(40)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color}; color: white; border: none; 
                    border-radius: 6px; padding: 5px 15px; font-weight: bold; font-size: 11px;
                }}
                QPushButton:hover {{ background-color: {hover_color}; }}
                QPushButton:disabled {{ background-color: #cccccc; color: #666666; }}
            """)
            return btn

        self.btn_upload = create_btn("📂 Upload File", "#2196F3", "#1976D2")
        self.btn_merge = create_btn("🔗 Merge Files", "#009688", "#00796B")
        self.btn_deduplicate = create_btn("🧹 Remove Duplicates", "#e91e63", "#c2185b")
        self.btn_export = create_btn("💾 Export Data", "#FF9800", "#F57C00")
        
        self.dedup_menu = QMenu(self)
        self.action_remove_duplicates = QAction("🧹 Remove Duplicates", self)
        self.action_remove_and_download = QAction("📥 Remove & Download Duplicates", self)
        self.dedup_menu.addAction(self.action_remove_duplicates)
        self.dedup_menu.addAction(self.action_remove_and_download)
        self.btn_deduplicate.setMenu(self.dedup_menu)
        
        # Edit actions
        self.btn_add_row = create_btn("+ Row", "#4CAF50", "#388E3C")
        self.btn_add_col = create_btn("+ Column", "#9C27B0", "#7B1FA2")
        self.btn_rename_col = create_btn("✏️ Rename", "#FF5722", "#E64A19")
        self.btn_format = create_btn("🎨 Format", "#00BCD4", "#0097A7")
        self.btn_del_row = create_btn("🗑️ Row", "#757575", "#616161")
        self.btn_del_col = create_btn("🗑️ Col", "#757575", "#616161")
        
        # Disable all except upload initially
        for btn in [self.btn_deduplicate, self.btn_export, self.btn_add_row, 
                    self.btn_add_col, self.btn_rename_col, self.btn_format,
                    self.btn_del_row, self.btn_del_col]:
            btn.setEnabled(False)
            
        toolbar_layout.addWidget(self.btn_upload)
        toolbar_layout.addWidget(self.btn_merge)
        toolbar_layout.addWidget(self.btn_deduplicate)
        toolbar_layout.addWidget(self.btn_add_row)
        toolbar_layout.addWidget(self.btn_del_row)
        toolbar_layout.addSpacing(5)
        toolbar_layout.addWidget(self.btn_add_col)
        toolbar_layout.addWidget(self.btn_del_col)
        toolbar_layout.addWidget(self.btn_rename_col)
        toolbar_layout.addWidget(self.btn_format)
        
        # Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search data...")
        self.search_bar.setFixedWidth(200)
        self.search_bar.setMinimumHeight(35)
        self.search_bar.setStyleSheet("""
            QLineEdit {
                padding: 5px 10px; border: 1px solid #DDD; border-radius: 17px;
                background-color: white; font-size: 11px;
            }
            QLineEdit:focus { border: 1px solid #2196F3; }
        """)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.search_bar)
        
        toolbar_layout.addWidget(self.btn_export)
        
        main_layout.addLayout(toolbar_layout)

        # === FORMULA BAR ===
        formula_container = QFrame()
        formula_container.setFixedHeight(35)
        formula_container.setStyleSheet("background-color: white; border: 1px solid #DDD; border-radius: 4px;")
        formula_layout = QHBoxLayout(formula_container)
        formula_layout.setContentsMargins(10, 0, 10, 0)
        
        fx_label = QLabel("fx")
        fx_label.setStyleSheet("color: #666; font-style: italic; font-weight: bold; font-size: 14px;")
        formula_layout.addWidget(fx_label)
        
        self.formula_bar = QLineEdit()
        self.formula_bar.setStyleSheet("border: none; font-size: 13px; background: transparent;")
        self.formula_bar.setPlaceholderText("Select a cell to edit content...")
        formula_layout.addWidget(self.formula_bar)
        
        main_layout.addWidget(formula_container)
        
        # === DATA GRID ===
        self.table_view = QTableView()
        self.table_view.setStyleSheet("""
            QTableView {
                border: 1px solid #DDD;
                background-color: white;
                gridline-color: #F0F0F0;
            }
            QTableView::item:selected {
                background-color: #E3F2FD;
                color: black;
            }
            QHeaderView::section {
                background-color: #FAFAFA;
                padding: 6px;
                border: 1px solid #DDD;
                font-weight: bold;
                color: #333;
            }
        """)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.installEventFilter(self)

        # Header selection logic
        self.table_view.horizontalHeader().sectionClicked.connect(self._select_column)
        self.table_view.verticalHeader().sectionClicked.connect(self._select_row)
        self.table_view.installEventFilter(self)
        
        main_layout.addWidget(self.table_view, 1)
        
        # === STATUS BAR ===
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready. No data loaded.")
        self.status_label.setStyleSheet("color: #555; font-size: 11px;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #CCC; border-radius: 6px; text-align: center; }
            QProgressBar::chunk { background-color: #4CAF50; border-radius: 5px; }
        """)
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress_bar)
        main_layout.addLayout(status_layout)

    def set_status(self, message: str):
        self.status_label.setText(message)
    
    def show_loading(self, visible: bool = True):
        self.progress_bar.setVisible(visible)
        if not visible:
            self.progress_bar.setValue(0)
            
    def _select_row(self, row_idx: int):
        self.table_view.selectRow(row_idx)

    def _select_column(self, col_idx: int):
        self.table_view.selectColumn(col_idx)

    def eventFilter(self, source, event):
        if source is self.table_view:
            if event.type() == QEvent.Type.MouseButtonPress:
                if not self.table_view.indexAt(event.pos()).isValid():
                    self.table_view.clearSelection()
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                index = self.table_view.indexAt(event.pos())
                if index.isValid():
                    # "first cell" double click selects full row/col
                    if index.column() == 0:
                        self.table_view.selectRow(index.row())
                        return True
                    if index.row() == 0:
                        self.table_view.selectColumn(index.column())
                        return True
                        
        return super().eventFilter(source, event)

    def show_error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def show_info(self, title: str, message: str):
        QMessageBox.information(self, title, message)

    def get_open_file(self) -> str:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Data File", "", 
            "Supported Files (*.csv *.xlsx *.txt);;CSV Files (*.csv);;Excel Files (*.xlsx);;Text Files (*.txt);;All Files (*)"
        )
        return file_path

    def get_open_files(self) -> list[str]:
        """Support multiple file selection with clear instructions."""
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Select Multiple Files (Hold Cmd/Shift to select many)")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilter("Supported Files (*.csv *.xlsx *.txt);;CSV Files (*.csv);;Excel Files (*.xlsx);;Text Files (*.txt);;All Files (*)")
        
        if dialog.exec():
            return dialog.selectedFiles()
        return []
    
    def get_save_file(self) -> str:
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Data", "cleaned_data.csv", 
            "CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)"
        )
        return file_path
