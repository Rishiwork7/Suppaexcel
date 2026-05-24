"""
SheetTabBar — Qt widget that renders Excel-style sheet tabs at the bottom
of the main window.

This file has NO direct reference to SheetManager or DataProcessorApp.
It communicates entirely through the four pyqtSignals defined below.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QScrollArea,
    QMenu, QInputDialog, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor


# ---------------------------------------------------------------------------
# SheetTabBar
# ---------------------------------------------------------------------------

class SheetTabBar(QWidget):
    """
    Horizontal tab bar rendered below the data grid (like Excel sheet tabs).

    Signals
    -------
    sheet_selected(int)       — user clicked a tab
    sheet_added()             — user clicked the "+" button
    sheet_removed(int)        — user chose Delete from the context menu
    sheet_renamed(int, str)   — user confirmed a rename via QInputDialog
    """

    sheet_selected = pyqtSignal(int)
    sheet_added    = pyqtSignal()
    sheet_removed  = pyqtSignal(int)
    sheet_renamed  = pyqtSignal(int, str)

    # Colour tokens — intentionally kept as class attributes so they are
    # easy to tweak without hunting through stylesheet strings.
    _ACTIVE_BG    = "#2196F3"
    _ACTIVE_FG    = "#FFFFFF"
    _INACTIVE_BG  = "#ECEFF1"
    _INACTIVE_FG  = "#546E7A"
    _HOVER_BG     = "#BBDEFB"
    _BORDER_COLOR = "#CFD8DC"
    _BAR_BG       = "#F5F7F8"
    _ADD_BG       = "#E8F5E9"
    _ADD_HOVER    = "#C8E6C9"
    _ADD_FG       = "#2E7D32"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active_index: int = 0
        self._sheet_names: list[str] = []

        self._build_ui()

    # ------------------------------------------------------------------
    # Private — UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Lay out the fixed chrome (scroll area + add button)."""
        self.setFixedHeight(34)
        self.setStyleSheet(f"background-color: {self._BAR_BG};")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 0)
        outer.setSpacing(0)

        # Thin top border that visually separates bar from table
        self.setStyleSheet(
            f"background-color: {self._BAR_BG};"
            f"border-top: 1px solid {self._BORDER_COLOR};"
        )

        # Scrollable area for the tab buttons
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(32)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._tab_container = QWidget()
        self._tab_container.setStyleSheet("background: transparent;")
        self._tab_layout = QHBoxLayout(self._tab_container)
        self._tab_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_layout.setSpacing(2)
        self._tab_layout.addStretch()

        self._scroll.setWidget(self._tab_container)

        # "+" add-sheet button
        self._btn_add = QPushButton("+")
        self._btn_add.setFixedSize(28, 28)
        self._btn_add.setToolTip("Add new sheet")
        self._btn_add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_add.setStyleSheet(self._add_btn_style())
        self._btn_add.clicked.connect(self.sheet_added.emit)

        outer.addWidget(self._scroll, 1)
        outer.addSpacing(4)
        outer.addWidget(self._btn_add)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self, sheet_names: list[str], active_index: int) -> None:
        """
        Rebuild the tab buttons to match *sheet_names*.

        Safe to call with an empty list (guard returns early).
        """
        if not sheet_names:
            return

        self._sheet_names = list(sheet_names)
        self._active_index = active_index

        # Clear existing buttons (leave the stretch at the end)
        while self._tab_layout.count() > 1:
            item = self._tab_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for idx, name in enumerate(sheet_names):
            btn = self._make_tab_button(idx, name, idx == active_index)
            # Insert before the trailing stretch
            self._tab_layout.insertWidget(idx, btn)

        # Scroll active tab into view
        self._scroll_to_active(active_index)

    # ------------------------------------------------------------------
    # Private — tab button helpers
    # ------------------------------------------------------------------

    def _make_tab_button(self, index: int, name: str, active: bool) -> QPushButton:
        """Create and return a single styled tab button."""
        btn = QPushButton(name)
        btn.setFixedHeight(28)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn.setMinimumWidth(max(60, len(name) * 8 + 24))
        btn.setMaximumWidth(200)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(self._tab_style(active))

        # Left-click → select sheet
        btn.clicked.connect(lambda _checked, i=index: self.sheet_selected.emit(i))

        # Right-click → context menu
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(
            lambda _pos, i=index, b=btn: self._show_context_menu(i, b)
        )

        return btn

    def _show_context_menu(self, index: int, source_btn: QPushButton) -> None:
        """Show Rename / Delete menu for the tab at *index*."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #CFD8DC;
                border-radius: 4px;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 20px;
                font-size: 12px;
                color: #333;
            }
            QMenu::item:selected {
                background-color: #E3F2FD;
                color: #1565C0;
            }
        """)

        act_rename = menu.addAction("✏️  Rename")
        menu.addSeparator()
        act_delete = menu.addAction("🗑️  Delete")

        chosen = menu.exec(QCursor.pos())

        if chosen == act_rename:
            self._do_rename(index)
        elif chosen == act_delete:
            self.sheet_removed.emit(index)

    def _do_rename(self, index: int) -> None:
        """Open a QInputDialog to get a new name for the sheet at *index*."""
        current_name = (
            self._sheet_names[index]
            if 0 <= index < len(self._sheet_names)
            else ""
        )
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Sheet",
            "New sheet name:",
            text=current_name,
        )
        if ok and new_name.strip():
            self.sheet_renamed.emit(index, new_name.strip())

    def _scroll_to_active(self, index: int) -> None:
        """Scroll the tab bar so the active tab is visible."""
        try:
            item = self._tab_layout.itemAt(index)
            if item and item.widget():
                widget = item.widget()
                self._scroll.ensureWidgetVisible(widget)
        except Exception:
            pass  # non-critical — just a visual aid

    # ------------------------------------------------------------------
    # Private — stylesheet builders
    # ------------------------------------------------------------------

    def _tab_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background-color: {self._ACTIVE_BG};
                    color: {self._ACTIVE_FG};
                    border: none;
                    border-radius: 4px 4px 0 0;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #1976D2;
                }}
            """
        return f"""
            QPushButton {{
                background-color: {self._INACTIVE_BG};
                color: {self._INACTIVE_FG};
                border: 1px solid {self._BORDER_COLOR};
                border-bottom: none;
                border-radius: 4px 4px 0 0;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: normal;
            }}
            QPushButton:hover {{
                background-color: {self._HOVER_BG};
                color: #1565C0;
            }}
        """

    def _add_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {self._ADD_BG};
                color: {self._ADD_FG};
                border: 1px solid #A5D6A7;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self._ADD_HOVER};
            }}
        """
