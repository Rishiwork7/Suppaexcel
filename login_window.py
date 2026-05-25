"""
login_window.py — Modal login dialog (cannot be closed or bypassed).

Implements:
  - 5-attempt lockout with 5-minute countdown timer
  - Inline error messages (no popups)
  - First-login redirect to PasswordResetWindow
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSpacerItem, QSizePolicy,
)

import auth_db
import session as sess
from password_reset_window import PasswordResetWindow


MAX_ATTEMPTS: int = 5
LOCKOUT_SECONDS: int = 5 * 60   # 5 minutes


class LoginWindow(QDialog):
    """
    Blocking modal login dialog.

    After a successful login ``self.logged_in_user`` is set to
    ``{user_id, role}`` and the dialog is accepted.
    It is None on failure or if the user never authenticated.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.logged_in_user: dict | None = None

        self._attempts: int = 0
        self._locked_until: float = 0.0     # epoch seconds; 0 = not locked
        self._countdown_remaining: int = 0

        self.setWindowTitle("Data Processor — Login")
        self.setFixedSize(420, 520)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setModal(True)

        self._build_ui()

        # Countdown timer — fires every second while locked
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick_lockout)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("background-color: #F5F7F8;")

        # ── Card ────────────────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #E0E0E0;
            }
        """)
        card.setFixedWidth(360)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 36)
        card_layout.setSpacing(16)

        # Logo / title
        logo = QLabel("🔐")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size: 40px; border: none;")
        card_layout.addWidget(logo)

        title = QLabel("Sign In")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Helvetica", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #212121; border: none;")
        card_layout.addWidget(title)

        subtitle = QLabel("Enter your credentials to continue")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #757575; font-size: 12px; border: none;")
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(8)

        # User ID
        lbl_uid = QLabel("User ID")
        lbl_uid.setStyleSheet("color: #424242; font-size: 12px; font-weight: bold; border: none;")
        card_layout.addWidget(lbl_uid)

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Enter your user ID")
        self.input_user.setFixedHeight(40)
        self.input_user.setStyleSheet(self._input_style())
        card_layout.addWidget(self.input_user)

        # Password
        lbl_pw = QLabel("Password")
        lbl_pw.setStyleSheet("color: #424242; font-size: 12px; font-weight: bold; border: none;")
        card_layout.addWidget(lbl_pw)

        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("Enter your password")
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_password.setFixedHeight(40)
        self.input_password.setStyleSheet(self._input_style())
        self.input_password.returnPressed.connect(self._on_login)
        card_layout.addWidget(self.input_password)

        # Inline error / status label
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet(
            "color: #D32F2F; font-size: 11px; border: none; min-height: 32px;"
        )
        self.error_label.setVisible(False)
        card_layout.addWidget(self.error_label)

        # Countdown label (shown during lockout)
        self.countdown_label = QLabel()
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet(
            "color: #E65100; font-size: 11px; font-weight: bold; border: none;"
        )
        self.countdown_label.setVisible(False)
        card_layout.addWidget(self.countdown_label)

        # Login button
        self.btn_login = QPushButton("Sign In")
        self.btn_login.setFixedHeight(44)
        self.btn_login.setStyleSheet(self._btn_style("#2196F3", "#1976D2"))
        self.btn_login.clicked.connect(self._on_login)
        card_layout.addWidget(self.btn_login)

        # Centre the card
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(card)
        h.addStretch()

        outer.addStretch()
        outer.addLayout(h)
        outer.addStretch()

    # ------------------------------------------------------------------
    # Slot — login button
    # ------------------------------------------------------------------

    def _on_login(self) -> None:
        import time

        # Still locked?
        if self._locked_until and time.time() < self._locked_until:
            return

        user_id  = self.input_user.text().strip()
        password = self.input_password.text()

        if not user_id or not password:
            self._show_error("Please enter both User ID and Password.")
            return

        try:
            result = auth_db.verify_user(user_id, password)
        except RuntimeError as exc:
            self._show_error(f"Database error: {exc}")
            return

        if result is None:
            self._attempts += 1
            remaining = MAX_ATTEMPTS - self._attempts
            if remaining <= 0:
                self._engage_lockout()
            else:
                self._show_error(
                    f"Invalid credentials.\n{remaining} attempt{'s' if remaining != 1 else ''} remaining."
                )
            return

        # ── Credentials accepted ────────────────────────────────────
        self._attempts = 0
        self._clear_error()

        if result["is_first_login"] == 1:
            # Force password reset before granting access
            self._do_first_login_reset(result)
            return

        sess.save_session(result["user_id"], result["role"], result.get("auth_uid"))
        self.logged_in_user = result
        self.accept()

    # ------------------------------------------------------------------
    # First-login flow
    # ------------------------------------------------------------------

    def _do_first_login_reset(self, result: dict) -> None:
        """Hide self, show PasswordResetWindow, then either accept or re-show."""
        self.hide()
        reset_win = PasswordResetWindow(result["user_id"], result["role"], parent=None)
        reset_win.exec()

        if reset_win.success:
            sess.save_session(result["user_id"], result["role"], result.get("auth_uid"))
            self.logged_in_user = result
            self.accept()
        else:
            # Reset was not completed — show login again
            self.show()
            self._show_error("Password reset was not completed. Please log in again.")

    # ------------------------------------------------------------------
    # Lockout
    # ------------------------------------------------------------------

    def _engage_lockout(self) -> None:
        import time
        self._locked_until = time.time() + LOCKOUT_SECONDS
        self._countdown_remaining = LOCKOUT_SECONDS
        self.btn_login.setEnabled(False)
        self.input_user.setEnabled(False)
        self.input_password.setEnabled(False)
        self._show_error("Too many failed attempts.")
        self._tick_lockout()          # update label immediately
        self._timer.start()

    def _tick_lockout(self) -> None:
        import time
        remaining = int(self._locked_until - time.time())
        if remaining <= 0:
            self._timer.stop()
            self._locked_until = 0.0
            self._attempts = 0
            self.btn_login.setEnabled(True)
            self.input_user.setEnabled(True)
            self.input_password.setEnabled(True)
            self.countdown_label.setVisible(False)
            self._clear_error()
            return

        mins, secs = divmod(remaining, 60)
        self.countdown_label.setText(
            f"⏱  Account locked — try again in {mins:02d}:{secs:02d}"
        )
        self.countdown_label.setVisible(True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_error(self, msg: str) -> None:
        self.error_label.setText(msg)
        self.error_label.setVisible(True)

    def _clear_error(self) -> None:
        self.error_label.setVisible(False)
        self.error_label.clear()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Prevent the dialog from being closed — login is mandatory."""
        event.ignore()

    # ------------------------------------------------------------------
    # Style helpers
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
    def _btn_style(bg: str, hover: str) -> str:
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:disabled {{
                background-color: #BDBDBD;
                color: #757575;
            }}
        """
