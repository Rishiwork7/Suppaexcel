"""
User Interface components for the Data Processing Application.

Builds the main window with a clean menu bar, status label, and data grid.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableView, QFileDialog, QMessageBox, QProgressBar,
    QAbstractItemView, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence, QAction, QIcon


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
                border-radius: 4px;
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
    Main application window with sleek menu bar and data grid.
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

        # === MENU BAR (Sleek, Excel-like) ===
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)
        menu_bar.setStyleSheet("""
            QMenuBar { background-color: #F5F7F8; border-bottom: 1px solid #E0E0E0; }
            QMenuBar::item { padding: 6px 12px; font-size: 12px; }
            QMenuBar::item:selected { background: #E3F2FD; border-radius: 4px; }
            QMenu { background: white; border: 1px solid #E0E0E0; }
            QMenu::item { padding: 6px 16px; font-size: 12px; }
            QMenu::item:selected { background: #E3F2FD; }
        """)

        # Actions
        self.action_home = QAction("Open Cloud Files...", self)
        self.action_logout = QAction("Logout", self)
        self.action_upload = QAction("Upload File...", self)
        self.action_merge = QAction("Merge Files...", self)
        self.action_export = QAction("Export...", self)

        self.action_remove_duplicates = QAction("Remove Duplicates", self)
        self.action_remove_and_download = QAction("Remove & Download Duplicates", self)

        self.action_add_row = QAction("Add Row", self)
        self.action_add_col = QAction("Add Column", self)
        self.action_del_row = QAction("Delete Row", self)
        self.action_del_col = QAction("Delete Column", self)
        self.action_rename_col = QAction("Rename Column", self)
        self.action_format = QAction("Format Cells...", self)

        # Menus
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(self.action_upload)
        file_menu.addAction(self.action_merge)
        file_menu.addSeparator()
        file_menu.addAction(self.action_export)

        home_menu = menu_bar.addMenu("Home")
        home_menu.addAction(self.action_home)
        home_menu.addSeparator()
        home_menu.addAction(self.action_remove_duplicates)
        home_menu.addAction(self.action_remove_and_download)

        insert_menu = menu_bar.addMenu("Insert")
        insert_menu.addAction(self.action_add_row)
        insert_menu.addAction(self.action_add_col)

        edit_menu = menu_bar.addMenu("Edit")
        edit_menu.addAction(self.action_rename_col)
        edit_menu.addAction(self.action_del_row)
        edit_menu.addAction(self.action_del_col)

        format_menu = menu_bar.addMenu("Format")
        format_menu.addAction(self.action_format)

        account_menu = menu_bar.addMenu("Account")
        account_menu.addAction(self.action_logout)

        # Disable data-dependent actions initially
        for act in [
            self.action_remove_duplicates, self.action_remove_and_download, self.action_export,
            self.action_add_row, self.action_add_col, self.action_rename_col,
            self.action_format, self.action_del_row, self.action_del_col
        ]:
            act.setEnabled(False)

        # Slim top row: search only
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search data...")
        self.search_bar.setFixedWidth(220)
        self.search_bar.setMinimumHeight(30)
        self.search_bar.setStyleSheet("""
            QLineEdit {
                padding: 4px 10px; border: 1px solid #DDD; border-radius: 14px;
                background-color: white; font-size: 11px;
            }
            QLineEdit:focus { border: 1px solid #2196F3; }
        """)
        top_row.addStretch()
        top_row.addWidget(self.search_bar)
        main_layout.addLayout(top_row)

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

        # Selection counter — bottom-right pill, hidden until something is selected
        self.selection_label = QLabel()
        self.selection_label.setVisible(False)
        self.selection_label.setStyleSheet("""
            QLabel {
                color: #1565C0;
                background-color: #E3F2FD;
                border: 1px solid #90CAF9;
                border-radius: 10px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
        """)

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.selection_label)
        status_layout.addSpacing(8)
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
