"""
password_reset_window.py — Mandatory first-login password reset dialog.

Cannot be closed without setting a valid password.
All validation is shown inline — no popups.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame,
)

import auth_db
import session as sess

# Password policy
_MIN_LEN      = 8
_SPECIAL_CHARS = "!@#$%^&*"


class PasswordResetWindow(QDialog):
    """
    Blocking modal dialog forcing the user to set a new, strong password.

    ``self.success`` is True only if the password was successfully saved.

    Parameters
    ----------
    user_id : str
    role    : str
    """

    def __init__(self, user_id: str, role: str, parent=None) -> None:
        super().__init__(parent)
        self._user_id = user_id
        self._role    = role
        self.success  = False

        self.setWindowTitle("Set New Password")
        self.setFixedSize(420, 540)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setModal(True)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setStyleSheet("background-color: #F5F7F8;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #E0E0E0;
            }
        """)
        card.setFixedWidth(360)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 36, 36, 36)
        cl.setSpacing(14)

        logo = QLabel("🔑")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size: 40px; border: none;")
        cl.addWidget(logo)

        title = QLabel("Set Your Password")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Helvetica", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #212121; border: none;")
        cl.addWidget(title)

        note = QLabel(
            f"Welcome, <b>{self._user_id}</b>!<br>"
            "Please set a new password before continuing."
        )
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)
        note.setStyleSheet("color: #616161; font-size: 12px; border: none;")
        cl.addWidget(note)

        # Policy hint
        policy = QLabel(
            "• At least 8 characters\n"
            "• One uppercase letter\n"
            "• One digit\n"
            "• One special character: !@#$%^&*"
        )
        policy.setStyleSheet(
            "color: #757575; font-size: 11px; "
            "background-color: #F3F4F6; border-radius: 6px; "
            "padding: 8px 12px; border: none;"
        )
        cl.addWidget(policy)

        # New password
        lbl_new = QLabel("New Password")
        lbl_new.setStyleSheet("color: #424242; font-size: 12px; font-weight: bold; border: none;")
        cl.addWidget(lbl_new)

        self.input_new = QLineEdit()
        self.input_new.setPlaceholderText("New password")
        self.input_new.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_new.setFixedHeight(40)
        self.input_new.setStyleSheet(self._input_style())
        cl.addWidget(self.input_new)

        # Confirm password
        lbl_conf = QLabel("Confirm Password")
        lbl_conf.setStyleSheet("color: #424242; font-size: 12px; font-weight: bold; border: none;")
        cl.addWidget(lbl_conf)

        self.input_confirm = QLineEdit()
        self.input_confirm.setPlaceholderText("Confirm new password")
        self.input_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_confirm.setFixedHeight(40)
        self.input_confirm.setStyleSheet(self._input_style())
        self.input_confirm.returnPressed.connect(self._on_set_password)
        cl.addWidget(self.input_confirm)

        # Inline error
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet(
            "color: #D32F2F; font-size: 11px; border: none; min-height: 28px;"
        )
        self.error_label.setVisible(False)
        cl.addWidget(self.error_label)

        # Set password button
        self.btn_set = QPushButton("Set Password")
        self.btn_set.setFixedHeight(44)
        self.btn_set.setStyleSheet(self._btn_style())
        self.btn_set.clicked.connect(self._on_set_password)
        cl.addWidget(self.btn_set)

        # Centre card
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(card)
        h.addStretch()

        outer.addStretch()
        outer.addLayout(h)
        outer.addStretch()

    # ------------------------------------------------------------------
    # Slot
    # ------------------------------------------------------------------

    def _on_set_password(self) -> None:
        new_pw   = self.input_new.text()
        conf_pw  = self.input_confirm.text()

        # Validation
        error = self._validate(new_pw, conf_pw)
        if error:
            self._show_error(error)
            return

        try:
            auth_db.reset_password(self._user_id, new_pw)
            # Session saving is now handled by the login window after success
            pass
            self.success = True
            self.accept()
        except RuntimeError as exc:
            self._show_error(f"Failed to save password: {exc}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(pw: str, confirm: str) -> str | None:
        """Return an error message or None if valid."""
        if len(pw) < _MIN_LEN:
            return f"Password must be at least {_MIN_LEN} characters."
        if not re.search(r"[A-Z]", pw):
            return "Password must contain at least one uppercase letter."
        if not re.search(r"\d", pw):
            return "Password must contain at least one digit."
        if not any(c in _SPECIAL_CHARS for c in pw):
            return f"Password must contain at least one special character: {_SPECIAL_CHARS}"
        if pw != confirm:
            return "Passwords do not match."
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_error(self, msg: str) -> None:
        self.error_label.setText(msg)
        self.error_label.setVisible(True)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Cannot be dismissed — password reset is mandatory."""
        event.ignore()

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    @staticmethod
    def _input_style() -> str:
        return """
            QLineEdit {
                border: 1px solid #BDBDBD;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                background-color: #FAFAFA;
                color: #212121;
            }
            QLineEdit:focus {
                border: 2px solid #2196F3;
                background-color: white;
            }
        """

    @staticmethod
    def _btn_style() -> str:
        return """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #388E3C; }
            QPushButton:disabled { background-color: #BDBDBD; color: #757575; }
        """
