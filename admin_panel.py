"""
admin_panel.py — Admin-only user management dialog.

Shows all users in a QTableWidget; supports Add, Delete, and Refresh.
Passwords are never shown.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QInputDialog, QFrame,
)

import auth_db


class AdminPanel(QDialog):
    """
    Modal admin panel — only opened when the logged-in user has role 'admin'.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Admin Panel — User Management")
        self.setMinimumSize(640, 460)
        self.setModal(True)
        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setStyleSheet("background-color: #F5F7F8;")
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(14)

        # Header
        hdr = QHBoxLayout()
        icon = QLabel("👤")
        icon.setStyleSheet("font-size: 28px;")
        title = QLabel("User Management")
        title.setFont(QFont("Helvetica", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #212121;")
        hdr.addWidget(icon)
        hdr.addWidget(title)
        hdr.addStretch()
        main.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E0E0E0;")
        main.addWidget(sep)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["User ID", "Role", "First Login Pending"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #E0E0E0;
                background-color: white;
                gridline-color: #F5F5F5;
                border-radius: 6px;
            }
            QTableWidget::item:selected {
                background-color: #E3F2FD;
                color: #212121;
            }
            QHeaderView::section {
                background-color: #FAFAFA;
                border: 1px solid #E0E0E0;
                padding: 6px;
                font-weight: bold;
                color: #424242;
            }
        """)
        main.addWidget(self.table, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_add     = self._make_btn("➕ Add User",    "#4CAF50", "#388E3C")
        self.btn_delete  = self._make_btn("🗑️  Delete User", "#F44336", "#C62828")
        self.btn_refresh = self._make_btn("🔄 Refresh",     "#2196F3", "#1565C0")
        self.btn_close   = self._make_btn("✔ Close",        "#757575", "#424242")

        self.btn_add.clicked.connect(self._on_add)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_refresh.clicked.connect(self._refresh)
        self.btn_close.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_refresh)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_close)
        main.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        """Reload the user list from the database."""
        try:
            users = auth_db.list_users()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.table.setRowCount(0)   # clear first — no ghost rows
        for row_idx, user in enumerate(users):
            self.table.insertRow(row_idx)

            uid_item  = QTableWidgetItem(user["user_id"])
            role_item = QTableWidgetItem(user["role"].capitalize())
            fl_item   = QTableWidgetItem(
                "⏳ Pending" if user["is_first_login"] else "✔ Done"
            )
            fl_item.setForeground(
                Qt.GlobalColor.darkYellow if user["is_first_login"] else Qt.GlobalColor.darkGreen
            )
            for item in (uid_item, role_item, fl_item):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row_idx, 0, uid_item)
            self.table.setItem(row_idx, 1, role_item)
            self.table.setItem(row_idx, 2, fl_item)

    def _on_add(self) -> None:
        """4-step flow: User ID → temp password → confirm → create."""
        # Step 1: User ID
        user_id, ok1 = QInputDialog.getText(self, "Add User", "New User ID:")
        if not ok1 or not user_id.strip():
            return
        user_id = user_id.strip()

        # Step 2: Temporary password (masked)
        temp_pw, ok2 = QInputDialog.getText(
            self, "Add User",
            f"Set temporary password for '{user_id}':\n"
            "(User will be forced to reset on first login)",
            QLineEdit.EchoMode.Password,
        )
        if not ok2 or not temp_pw.strip():
            return
        temp_pw = temp_pw.strip()

        # Step 3: Confirm password (masked)
        confirm, ok3 = QInputDialog.getText(
            self, "Add User",
            "Confirm temporary password:",
            QLineEdit.EchoMode.Password,
        )
        if not ok3 or confirm != temp_pw:
            QMessageBox.warning(self, "Mismatch", "Passwords do not match. User not created.")
            return

        # Step 4: Create user (always role='user' from this panel)
        try:
            auth_db.create_user(user_id, temp_pw, role="user")
            QMessageBox.information(
                self, "User Created",
                f"User '{user_id}' created successfully.\n\n"
                f"Temporary password: {temp_pw}\n\n"
                "Share this with the user — they will be forced to reset it on first login.",
            )
            self._refresh()
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot Create User", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not create user: {exc}")

    def _on_delete(self) -> None:
        """Delete the selected user after confirmation."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a user row to delete.")
            return

        # Column 0 is User ID
        row = self.table.currentRow()
        uid_item = self.table.item(row, 0)
        if uid_item is None:
            return
        user_id = uid_item.text()

        if user_id == "admin":
            QMessageBox.warning(
                self, "Protected Account",
                "The 'admin' account cannot be deleted.",
            )
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete user '{user_id}'?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            auth_db.delete_user(user_id)
            self._refresh()
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot Delete", str(exc))
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_btn(text: str, bg: str, hover: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 16px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """)
        return btn
