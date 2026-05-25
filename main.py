"""
High-Performance Data Processing Desktop Application.

A PyQt6-based application for handling massive datasets (up to 10M rows)
with virtual scrolling, multithreading, and background data processing.
"""

import sys
import os

# Set environment variables previously in .env
os.environ["SUPABASE_URL"] = "https://euloqmxisohlkioesztb.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV1bG9xbXhpc29obGtpb2VzenRiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkzMjM3NjYsImV4cCI6MjA5NDg5OTc2Nn0.9LHuNcLkf_W7M-0hamyumanMwF6Bf3ofVh6EiE8THHo"

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox
from PyQt6.QtCore import Qt, QTimer
import pandas as pd

from ui import MainWindow
from models import VirtualDataModel
from worker import FileLoadWorker, DeduplicateWorker, ExportWorker, SearchWorker, MergeWorker
from undo import (
    UndoStack, EditCellCommand, AddRowCommand, 
    AddColCommand, RenameColCommand, DeduplicateCommand,
    DeleteRowCommand, DeleteColCommand
)


class DataProcessorApp:
    """
    Main application controller (Simplified & Colorful).
    """
    
    def __init__(self):
        """Initialize the application."""
        self.window = MainWindow()
        self.model = VirtualDataModel()
        self.undo_stack = UndoStack(limit=15)
        
        # Set the virtual model on the table view
        self.window.table_view.setModel(self.model)
        
        # State tracking
        self.current_worker = None
        self.pending_dedup_command = None
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        
        # Local deduplication state for popup only
        self.last_dedup_command = None
        
        # Connect UI signals to slots
        self._connect_signals()
        
        self.window.show()

        # ── Multi-Sheet Support (injected; no existing code modified) ────────
        from sheet_manager import SheetManager
        from sheet_tab_bar import SheetTabBar
        from sheet_controller import SheetController

        self.sheet_manager = SheetManager()
        self.sheet_tab_bar = SheetTabBar(self.window)

        # Insert tab bar between table_view (index 2) and status bar (index 3).
        # layout order in MainWindow: toolbar=0, formula=1, table=2, status=3
        central = self.window.centralWidget()
        layout  = central.layout()
        insert_at = min(3, layout.count())  # guard: never exceed current count
        layout.insertWidget(insert_at, self.sheet_tab_bar)

        self.sheet_controller = SheetController(
            self.sheet_manager,
            self.sheet_tab_bar,
            self.model,
        )
        # ── End Multi-Sheet Support ──────────────────────────────────────────

    def _connect_signals(self):
        """Connect UI button signals to their handler methods."""
        self.window.action_home.triggered.connect(self.on_home_clicked)
        self.window.action_logout.triggered.connect(self.on_logout_clicked)
        self.window.action_upload.triggered.connect(self.on_upload_clicked)
        self.window.action_merge.triggered.connect(self.on_merge_clicked)
        self.window.action_add_row.triggered.connect(self.on_add_row_clicked)
        self.window.action_add_col.triggered.connect(self.on_add_col_clicked)
        self.window.action_rename_col.triggered.connect(self.on_rename_col_clicked)
        self.window.action_format.triggered.connect(self.on_format_clicked)
        self.window.action_export.triggered.connect(self.on_export_clicked)
        
        # Remove Duplicates menu actions
        self.window.action_remove_duplicates.triggered.connect(self.on_deduplicate_clicked)
        self.window.action_remove_and_download.triggered.connect(self.on_remove_and_download_clicked)
        
        self.window.action_del_row.triggered.connect(self.on_del_row_clicked)
        self.window.action_del_col.triggered.connect(self.on_del_col_clicked)
        
        # Formula bar sync
        self.window.formula_bar.editingFinished.connect(self.on_formula_bar_edited)

        # Undo shortcut
        self.window.undo_triggered.connect(self.on_undo)

        # Search bar
        self.window.search_bar.textChanged.connect(self.on_search_text_changed)

        # Undo popup
        self.window.undo_popup.undo_requested.connect(self.on_undo_via_popup)
        self.popup_timer = QTimer()
        self.popup_timer.setSingleShot(True)
        self.popup_timer.timeout.connect(self.window.undo_popup.hide)

    def on_undo_via_popup(self):
        if self.last_dedup_command:
            self.last_dedup_command.undo()
            self.last_dedup_command = None
            self.window.set_status("⟲ Deduplication Undone.")
        self.window.undo_popup.hide()

    def on_search_text_changed(self):
        """Trigger search with debounce."""
        self.search_timer.start(300)

    def perform_search(self):
        """Execute search in background."""
        query = self.window.search_bar.text().strip()
        if self.model.get_full_dataframe() is None: return
        
        if not query:
            self.model.clear_filter()
            self.window.set_status("Search cleared.")
            return

        self.window.set_status(f"🔍 Searching for '{query}'...")
        
        # Fix 3: Use cancel flag instead of terminate() — terminate() is unsafe on Windows
        # and can corrupt pandas internal state mid-operation
        if isinstance(self.current_worker, SearchWorker) and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.wait(500)

        self.current_worker = SearchWorker(self.model.get_full_dataframe(), self.model._full_mask, query)
        self.current_worker.finished.connect(self._on_search_finished)
        self.current_worker.start()

    def _on_search_finished(self, filtered_df, filtered_mask):
        self.model.set_view(filtered_df, filtered_mask)
        self.window.set_status(f"✓ Found {len(filtered_df):,} matches.")

    def on_undo(self):
        """Handle Ctrl+Z undo action."""
        command = self.undo_stack.undo()
        if command:
            self.window.set_status(f"⟲ Undone: {type(command).__name__}")
        else:
            self.window.set_status("Nothing to undo.")

    def on_upload_clicked(self):
        """Handle Upload File button click."""
        file_path = self.window.get_open_file()
        if not file_path: return
        
        self._set_ui_enabled(False)
        self.window.set_status("Loading file...")
        self.window.show_loading(True)
        
        self.current_worker = FileLoadWorker(file_path)
        self.current_worker.finished.connect(self._on_file_loaded)
        self.current_worker.error.connect(self._on_load_error)
        self.current_worker.start()

    def on_home_clicked(self):
        """Open Cloud Dashboard and switch to selected file or new blank file."""
        import builtins
        if not getattr(builtins, "CLOUD_AVAILABLE", False):
            self.window.show_info("Cloud", "Cloud is not available.")
            return

        from cloud_dashboard import CloudDashboard

        dashboard = CloudDashboard(self.window)
        dashboard.exec()

        # Stop autosave for previous cloud file (if any)
        if getattr(self, "cloud_hooks", None) and getattr(self.cloud_hooks, "auto_save", None):
            self.cloud_hooks.auto_save.stop()

        builtins.CLOUD_FILE_ID = dashboard.chosen_file_id
        builtins.CLOUD_STORAGE_PATH = dashboard.chosen_storage_path
        builtins.CLOUD_SHEETS = dashboard.chosen_sheets

        if dashboard.chosen_sheets:
            self.sheet_manager._sheets.clear()
            for s in dashboard.chosen_sheets:
                self.sheet_manager.add_sheet(s['name'])
                self.sheet_manager.set_sheet_data(
                    self.sheet_manager.sheet_count() - 1,
                    s['df'],
                    s['mask']
                )

            self.sheet_controller.current_index = 0
            self.sheet_tab_bar.refresh(self.sheet_manager.sheet_names(), active_index=0)

            first_sheet = self.sheet_manager.get_sheet(0)
            self.model.load_dataframe(first_sheet['df'], first_sheet['mask'])

            if builtins.CLOUD_FILE_ID and builtins.CLOUD_STORAGE_PATH and getattr(self, "cloud_hooks", None):
                self.cloud_hooks.auto_save.start(builtins.CLOUD_FILE_ID, builtins.CLOUD_STORAGE_PATH)
        else:
            # New file: reset to a blank sheet
            self.sheet_manager._sheets.clear()
            self.sheet_manager.add_sheet("Sheet1")
            self.sheet_controller.current_index = 0
            self.sheet_tab_bar.refresh(self.sheet_manager.sheet_names(), active_index=0)
            self.model.load_dataframe(pd.DataFrame(), pd.Series(dtype=bool))
            self.window.set_status("New file created.")

    def on_logout_clicked(self):
        """Log out current user and show login dialog again."""
        reply = QMessageBox.question(
            self.window,
            "Logout",
            "Do you want to log out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Stop autosave if running
        if getattr(self, "cloud_hooks", None) and getattr(self.cloud_hooks, "auto_save", None):
            self.cloud_hooks.auto_save.stop()

        from session import clear_session
        clear_session()

        # Hide main window while re-authenticating
        self.window.hide()

        from login_window import LoginWindow
        login = LoginWindow()
        login.exec()

        if not login.logged_in_user:
            QApplication.quit()
            return

        import builtins
        builtins.CURRENT_USER = login.logged_in_user

        # Return to Cloud Dashboard for new session
        from cloud_dashboard import CloudDashboard
        dashboard = CloudDashboard(self.window)
        dashboard.exec()

        builtins.CLOUD_FILE_ID = dashboard.chosen_file_id
        builtins.CLOUD_STORAGE_PATH = dashboard.chosen_storage_path
        builtins.CLOUD_SHEETS = dashboard.chosen_sheets

        # Restore UI and load data based on dashboard choice
        self.window.show()
        self.on_home_clicked()

    def _on_file_loaded(self, df: pd.DataFrame, duplicate_mask: pd.Series):
        """Slot called when file loading completes."""
        self.model.load_dataframe(df, duplicate_mask)
        
        # Fix 6: Disconnect previous signal connection before reconnecting
        # to prevent the handler firing N times after N file loads
        sel_model = self.window.table_view.selectionModel()
        if sel_model:
            try:
                sel_model.currentChanged.disconnect(self._on_selection_changed)
            except TypeError:
                pass  # was not connected yet — safe to ignore
            sel_model.currentChanged.connect(self._on_selection_changed)

            try:
                sel_model.selectionChanged.disconnect(self._on_selection_count_changed)
            except TypeError:
                pass
            sel_model.selectionChanged.connect(self._on_selection_count_changed)
        
        dup_count = duplicate_mask.sum()
        row_count, col_count = len(df), len(df.columns)
        self.window.set_status(f"✓ Loaded: {row_count:,} rows, {col_count} columns | Found {dup_count:,} duplicates")
        
        # Performance optimization: resizing is too slow for 1M+ rows
        if row_count < 20000:
            self.window.table_view.resizeColumnsToContents()
        else:
            # Set a good default width for large datasets or just let the user resize
            for i in range(col_count):
                self.window.table_view.setColumnWidth(i, 150)
            self.window.set_status(f"✓ Loaded {row_count:,} rows. (Columns fixed-width for performance)")
        
        self._set_ui_enabled(True)
        self.window.show_loading(False)

    def _on_load_error(self, error_msg: str):
        self.window.show_error("Load Error", error_msg)
        # Fix 2: Only re-enable upload/merge — data-dependent buttons stay disabled
        self.window.action_upload.setEnabled(True)
        self.window.action_merge.setEnabled(True)
        self.window.show_loading(False)

    def on_merge_clicked(self):
        """Handle Merge Files button click."""
        file_paths = self.window.get_open_files()
        if not file_paths: return
        
        self._set_ui_enabled(False)
        self.window.set_status(f"Starting merge of {len(file_paths)} files...")
        self.window.show_loading(True)
        
        self.current_worker = MergeWorker(file_paths)
        self.current_worker.finished.connect(self._on_file_loaded) # Reuse _on_file_loaded
        self.current_worker.error.connect(self._on_merge_error)
        self.current_worker.progress.connect(self.window.set_status)
        self.current_worker.start()

    def _on_merge_error(self, error_msg: str):
        self.window.show_error("Merge Error", error_msg)
        # Fix 2: Only re-enable upload/merge — data-dependent buttons stay disabled
        self.window.action_upload.setEnabled(True)
        self.window.action_merge.setEnabled(True)
        self.window.show_loading(False)

    def on_remove_and_download_clicked(self):
        """Combined action: export duplicates then remove them."""
        df = self.model.get_dataframe()
        mask = self.model.duplicate_mask
        if df is None or mask is None or not mask.any():
            self.window.show_info("Info", "No duplicates found.")
            return

        file_path = self.window.get_save_file()
        if not file_path: return
        
        self._set_ui_enabled(False)
        self.window.set_status("Exporting duplicates before removal...")
        self.window.show_loading(True)
        
        dup_df = df[mask]
        self.current_worker = ExportWorker(dup_df, file_path)
        # Chain the removal on success
        self.current_worker.finished.connect(self._on_export_finished_then_remove)
        self.current_worker.error.connect(self._on_export_error)
        self.current_worker.start()

    def _on_export_finished_then_remove(self):
        """Export done, now start deduplication."""
        self.window.set_status("Export successful. Removing duplicates...")
        full_df = self.model.get_full_dataframe()
        
        # Clear search when deduplicating
        self.window.search_bar.clear()
        self.model.clear_filter()
        
        # Capture for Undo (matches on_deduplicate_clicked)
        old_mask = self.model._full_mask.copy() if self.model._full_mask is not None else None
        self.pending_dedup_command = DeduplicateCommand(
            self.model, self.model._full_df.copy(), old_mask
        )
        
        self.current_worker = DeduplicateWorker(full_df)
        self.current_worker.finished.connect(self._on_deduplicate_finished)
        self.current_worker.error.connect(self._on_deduplicate_error)
        self.current_worker.start()

    def on_deduplicate_clicked(self):
        """Handle Remove Duplicates button click."""
        full_df = self.model.get_full_dataframe()
        if full_df is None: return
        
        self._set_ui_enabled(False)
        self.window.set_status("Removing duplicates (Full Dataset)...")
        self.window.show_loading(True)
        
        # Clear search when deduplicating to ensure consistent state
        self.window.search_bar.clear()
        self.model.clear_filter()
        
        # Capture current state for Undo
        old_mask = self.model._full_mask.copy() if self.model._full_mask is not None else None
        self.pending_dedup_command = DeduplicateCommand(
            self.model, self.model._full_df.copy(), old_mask
        )
        
        self.current_worker = DeduplicateWorker(full_df)
        self.current_worker.finished.connect(self._on_deduplicate_finished)
        self.current_worker.error.connect(self._on_deduplicate_error)
        self.current_worker.start()

    def _on_deduplicate_finished(self, df: pd.DataFrame, removed_count: int, duplicate_mask: pd.Series):
        if self.pending_dedup_command:
            self.pending_dedup_command.capture_new(df, duplicate_mask)
            # Store locally for popup, do NOT push to global undo_stack
            self.last_dedup_command = self.pending_dedup_command
            self.pending_dedup_command = None

        self.model.load_dataframe(df, duplicate_mask)
        row_count = len(df)
        self.window.set_status(f"✓ Removed {removed_count:,} duplicates. Remaining: {row_count:,} rows")
        
        # Performance optimization for deduplication too
        if row_count < 20000:
            self.window.table_view.resizeColumnsToContents()
            
        # Show Undo popup for 5 seconds
        self.window.undo_popup.show_message(f"Removed {removed_count:,} duplicates.")
        self.popup_timer.start(5000)
        
        self._set_ui_enabled(True)
        self.window.show_loading(False)

    def _on_deduplicate_error(self, error_msg: str):
        self.window.show_error("Deduplication Error", error_msg)
        self._set_ui_enabled(True)
        self.window.show_loading(False)

    def on_export_clicked(self, only_duplicates=False):
        """Handle Export button click with choice to filter duplicates."""
        df = self.model.get_dataframe()
        if df is None: return
        
        if only_duplicates:
            mask = self.model.duplicate_mask
            if mask is not None:
                df = df[mask]
                if df.empty:
                    self.window.show_info("Export Info", "No duplicates found to export.")
                    return
            else:
                self.window.show_info("Export Info", "No duplicate analysis available.")
                return

        file_path = self.window.get_save_file()
        if not file_path: return
        
        self._set_ui_enabled(False)
        self.window.set_status(f"Exporting {'duplicates' if only_duplicates else 'data'}...")
        self.window.show_loading(True)
        
        self.current_worker = ExportWorker(df, file_path)
        self.current_worker.finished.connect(self._on_export_finished)
        self.current_worker.error.connect(self._on_export_error)
        self.current_worker.start()

    def _on_export_finished(self):
        self.window.set_status("✓ Export successful!")
        self._set_ui_enabled(True)
        self.window.show_loading(False)

    def _on_export_error(self, error_msg: str):
        self.window.show_error("Export Error", error_msg)
        self._set_ui_enabled(True)
        self.window.show_loading(False)

    def on_del_row_clicked(self):
        """Delete rows containing any selected cells with Undo support."""
        selection = self.window.table_view.selectionModel().selectedIndexes()
        if not selection:
            self.window.show_error("Selection Error", "Please select cell(s) in the row(s) to delete.")
            return
        
        # Get unique, sorted row indices (backward) to maintain order during removal
        indices = sorted(list(set(idx.row() for idx in selection)), reverse=True)
        for row_idx in indices:
            row_data = self.model.df.iloc[row_idx].copy()
            mask_val = self.model.duplicate_mask.iloc[row_idx] if self.model.duplicate_mask is not None else False
            self.undo_stack.push(DeleteRowCommand(self.model, row_idx, row_data, mask_val))
            self.model.remove_row(row_idx)
        
        self.window.set_status(f"✓ Deleted {len(indices)} rows.")

    def on_del_col_clicked(self):
        """Delete columns containing any selected cells with Undo support."""
        selection = self.window.table_view.selectionModel().selectedIndexes()
        if not selection:
            self.window.show_error("Selection Error", "Please select cell(s) in the column(s) to delete.")
            return
            
        # Get unique, sorted column indices (backward) to maintain order
        indices = sorted(list(set(idx.column() for idx in selection)), reverse=True)
        for col_idx in indices:
            col_name = self.model.df.columns[col_idx]
            col_data = self.model.df.iloc[:, col_idx].copy()
            self.undo_stack.push(DeleteColCommand(self.model, col_idx, col_name, col_data))
            self.model.remove_column(col_idx)
            
        self.window.set_status(f"✓ Deleted {len(indices)} columns.")

    def on_add_row_clicked(self):
        row_idx = self.model.rowCount()
        self.model.add_row()
        self.undo_stack.push(AddRowCommand(self.model, row_idx))
        self.window.set_status(f"✓ New row added.")

    def on_add_col_clicked(self):
        name, ok = QInputDialog.getText(self.window, "Add Column", "Enter column name:")
        if ok and name:
            col_idx = self.model.columnCount()
            self.model.add_column(name)
            self.undo_stack.push(AddColCommand(self.model, col_idx, name))
            self.window.set_status(f"✓ Column '{name}' added.")

    def on_rename_col_clicked(self):
        selection = self.window.table_view.selectionModel().selectedIndexes()
        if not selection:
            self.window.show_error("Selection Error", "Please select a cell in the column to rename.")
            return
        col_idx = selection[0].column()
        old_name = self.model.df.columns[col_idx]
        new_name, ok = QInputDialog.getText(self.window, "Rename Column", f"New name for '{old_name}':")
        if ok and new_name:
            self.undo_stack.push(RenameColCommand(self.model, col_idx, old_name, new_name))
            self.model.rename_column(col_idx, new_name)

    def on_format_clicked(self):
        selection = self.window.table_view.selectionModel().selectedIndexes()
        if not selection: return
        options = ["Bold", "Red Text", "Align Center", "Light Blue BG"]
        choice, ok = QInputDialog.getItem(self.window, "Formatting", "Choose format:", options, 0, False)
        if ok and choice:
            for index in selection:
                row, col = index.row(), index.column()
                fmt = self.model.formatting.get((row, col), {}).copy()
                if choice == "Bold": fmt["bold"] = True
                elif choice == "Red Text": fmt["color"] = "#F44336"
                elif choice == "Align Center": fmt["alignment"] = Qt.AlignmentFlag.AlignCenter
                elif choice == "Light Blue BG": fmt["bg_color"] = "#E3F2FD"
                self.model.set_cell_format(row, col, fmt)

    def _on_selection_changed(self, current, previous):
        """Update formula bar when table selection changes."""
        if current.isValid():
            value_obj = self.model.data(current, Qt.ItemDataRole.EditRole)
            # data() with EditRole returns a QVariant-like object or direct value in our custom model
            # Let's ensure we handle what VirtualDataModel returns
            self.window.formula_bar.setText(str(value_obj))
        else:
            self.window.formula_bar.clear()

    def _on_selection_count_changed(self, selected, deselected):
        """Update the bottom-right selection pill with the count of selected rows."""
        sel_model = self.window.table_view.selectionModel()
        if sel_model is None:
            self.window.selection_label.setVisible(False)
            return

        indexes = sel_model.selectedIndexes()
        if not indexes:
            self.window.selection_label.setVisible(False)
            return

        row_count = len({idx.row() for idx in indexes})
        col_count = len({idx.column() for idx in indexes})

        if row_count == 1 and col_count == 1:
            text = "1 cell selected"
        elif row_count == 1:
            text = f"1 row · {col_count} cols selected"
        else:
            text = f"{row_count:,} rows selected"

        self.window.selection_label.setText(text)
        self.window.selection_label.setVisible(True)

    def on_formula_bar_edited(self):
        """Update selected cell when formula bar is edited."""
        selection = self.window.table_view.selectionModel().currentIndex()
        if selection.isValid():
            row, col = selection.row(), selection.column()
            old_val = self.model.df.iloc[row, col]
            new_text = self.window.formula_bar.text()
            
            # Record undo
            self.undo_stack.push(EditCellCommand(self.model, row, col, old_val, new_text))
            self.model.setData(selection, new_text, Qt.ItemDataRole.EditRole)

    def _set_ui_enabled(self, enabled: bool):
        """Helper to enable/disable UI buttons."""
        self.window.action_upload.setEnabled(enabled)
        self.window.action_merge.setEnabled(enabled)
        self.window.action_remove_duplicates.setEnabled(enabled)
        self.window.action_remove_and_download.setEnabled(enabled)
        self.window.action_export.setEnabled(enabled)
        self.window.action_add_row.setEnabled(enabled)
        self.window.action_add_col.setEnabled(enabled)
        self.window.action_rename_col.setEnabled(enabled)
        self.window.action_format.setEnabled(enabled)
        self.window.action_del_row.setEnabled(enabled)
        self.window.action_del_col.setEnabled(enabled)


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    data_app = DataProcessorApp()
    return app, data_app


if __name__ == "__main__":
    import sys as _sys
    import signal as _signal
    from PyQt6.QtWidgets import QApplication as _QApplication

    # Restore default SIGINT so Ctrl+C immediately kills the app
    # (Qt's event loop blocks Python's KeyboardInterrupt by default)
    _signal.signal(_signal.SIGINT, _signal.SIG_DFL)

    from auth_db import init_db as _init_db
    from session import load_session as _load_session
    from login_window import LoginWindow as _LoginWindow

    _app = _QApplication(_sys.argv)
    _app.setStyle("Fusion")

    # Ensure DB + default admin exist (idempotent)
    _init_db()

    _logged_in_user = None

    # ── Try to resume an existing valid session ─────────────────────
    _existing = _load_session()
    if _existing:
        _logged_in_user = _existing
    else:
        _login_win = _LoginWindow()
        _login_win.exec()
        _logged_in_user = _login_win.logged_in_user

    if not _logged_in_user:
        _sys.exit(0)

    # ── Expose current user globally so the app can read it ─────────
    import builtins as _builtins
    _builtins.CURRENT_USER = _logged_in_user  # type: ignore[attr-defined]

    # Admin panel has been removed as user management is now entirely handled via Supabase Cloud

    from cloud_config import get_supabase_client
    from cloud_dashboard import CloudDashboard

    # Verify Supabase connection is reachable (MANDATORY)
    try:
        get_supabase_client()  # will raise if .env missing
    except RuntimeError as e:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Internet Connection Required", 
            "This application requires an active internet connection to run.\n\nPlease check your network and try again.")
        _sys.exit(1)

    dashboard = CloudDashboard()
    dashboard.exec()
    
    import builtins
    builtins.CLOUD_FILE_ID = dashboard.chosen_file_id
    builtins.CLOUD_STORAGE_PATH = dashboard.chosen_storage_path
    builtins.CLOUD_SHEETS = dashboard.chosen_sheets
    builtins.CLOUD_AVAILABLE = True

    _qt_app, _data_app = main()
    from cloud_hooks import CloudHooks
    _data_app.cloud_hooks = CloudHooks(_data_app)
    _sys.exit(_qt_app.exec())