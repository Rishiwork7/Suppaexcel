"""
SheetController — wires SheetTabBar signals to SheetManager operations
and keeps the VirtualDataModel in sync with the active sheet.

This is the only file that imports from all three layers.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from PyQt6.QtWidgets import QMessageBox

from sheet_manager import SheetManager
from sheet_tab_bar import SheetTabBar

logger = logging.getLogger(__name__)


class SheetController:
    """
    Connects SheetTabBar UI events to SheetManager state changes, then
    reflects those changes in the VirtualDataModel.

    Parameters
    ----------
    sheet_manager : SheetManager
    tab_bar       : SheetTabBar
    model         : VirtualDataModel  (typed as object to avoid circular
                                       imports; duck-typed at runtime)
    """

    def __init__(
        self,
        sheet_manager: SheetManager,
        tab_bar: SheetTabBar,
        model: object,
    ) -> None:
        self._manager: SheetManager = sheet_manager
        self._tab_bar: SheetTabBar = tab_bar
        self._model = model
        self.current_index: int = 0

        # Wire signals
        tab_bar.sheet_selected.connect(self._on_sheet_selected)
        tab_bar.sheet_added.connect(self._on_sheet_added)
        tab_bar.sheet_removed.connect(self._on_sheet_removed)
        tab_bar.sheet_renamed.connect(self._on_sheet_renamed)

        # Draw initial state
        self._refresh_tab_bar()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_sheet_selected(self, index: int) -> None:
        """User clicked a tab — save current sheet then load the new one."""
        if index == self.current_index:
            return  # already on this sheet

        try:
            self._save_current_to_manager()
            self.current_index = index
            self._load_active_sheet()
            self._refresh_tab_bar()
        except Exception as exc:
            logger.error("SheetController._on_sheet_selected error: %s", exc)

    def _on_sheet_added(self) -> None:
        """User clicked '+' — create a new empty sheet and switch to it."""
        try:
            self._save_current_to_manager()
            new_index = self._manager.add_sheet()
            self.current_index = new_index
            self._load_active_sheet()
            self._refresh_tab_bar()
        except Exception as exc:
            logger.error("SheetController._on_sheet_added error: %s", exc)

    def _on_sheet_removed(self, index: int) -> None:
        """User chose Delete from the context menu."""
        if self._manager.sheet_count() <= 1:
            QMessageBox.warning(
                None,
                "Cannot Delete Sheet",
                "Cannot delete the only sheet.\nA workbook must have at least one sheet.",
            )
            return

        try:
            self._manager.remove_sheet(index)

            # Clamp current_index to valid range after removal
            max_valid = self._manager.sheet_count() - 1
            self.current_index = min(self.current_index, max_valid)
            if self.current_index > index:
                self.current_index -= 1  # adjust for removed sheet before current
            elif self.current_index == index:
                # We deleted the active sheet — land on same position (now a different sheet)
                self.current_index = min(index, max_valid)

            self._load_active_sheet()
            self._refresh_tab_bar()
        except Exception as exc:
            logger.error("SheetController._on_sheet_removed error: %s", exc)

    def _on_sheet_renamed(self, index: int, new_name: str) -> None:
        """User confirmed a rename — update manager and refresh bar."""
        try:
            self._manager.rename_sheet(index, new_name)
            self._refresh_tab_bar()
        except Exception as exc:
            logger.error("SheetController._on_sheet_renamed error: %s", exc)

    # ------------------------------------------------------------------
    # Public utility
    # ------------------------------------------------------------------

    def sync_current_sheet_data(self) -> None:
        """
        Save the model's current state back into SheetManager.

        Call this before export / dedup so the active sheet's data is always
        persisted in SheetManager (not only on tab-switch).
        """
        try:
            self._save_current_to_manager()
        except Exception as exc:
            logger.error("SheetController.sync_current_sheet_data error: %s", exc)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _save_current_to_manager(self) -> None:
        """Persist the model's current df + mask into the current sheet slot."""
        try:
            df   = getattr(self._model, "df", None)
            mask = getattr(self._model, "duplicate_mask", None)
            self._manager.set_sheet_data(self.current_index, df, mask)
        except Exception as exc:
            logger.error("SheetController._save_current_to_manager error: %s", exc)

    def _load_active_sheet(self) -> None:
        """Load the active sheet's df + mask into the model."""
        try:
            sheet = self._manager.get_sheet(self.current_index)
            df    = sheet.get("df")
            mask  = sheet.get("mask")

            if df is not None:
                self._model.load_dataframe(df, mask)
            else:
                # Empty sheet — clear model
                if callable(getattr(self._model, "clear", None)):
                    self._model.clear()
                else:
                    # Fallback: load an empty frame
                    self._model.load_dataframe(
                        pd.DataFrame(),
                        pd.Series(dtype=bool),
                    )
        except Exception as exc:
            logger.error("SheetController._load_active_sheet error: %s", exc)

    def _refresh_tab_bar(self) -> None:
        """Re-render all tabs to reflect current SheetManager state."""
        try:
            self._tab_bar.refresh(
                self._manager.sheet_names(),
                self.current_index,
            )
        except Exception as exc:
            logger.error("SheetController._refresh_tab_bar error: %s", exc)
