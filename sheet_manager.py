"""
SheetManager — Pure Python/Pandas multi-sheet state manager.

Manages an ordered list of sheet dicts, each holding a name, a DataFrame,
and a duplicate mask.  No Qt imports — this file must stay framework-free.
"""

from __future__ import annotations

from typing import Optional
import pandas as pd


class SheetManager:
    """
    Maintains an ordered list of sheets.

    Each sheet is a dict:
        {
            "name": str,
            "df":   pd.DataFrame | None,
            "mask": pd.Series | None,
        }

    Invariant: there is always at least one sheet.
    """

    def __init__(self) -> None:
        self._sheets: list[dict] = [
            {"name": "Sheet1", "df": None, "mask": None}
        ]

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def sheet_count(self) -> int:
        """Return the total number of sheets."""
        return len(self._sheets)

    def sheet_names(self) -> list[str]:
        """Return a list of all sheet names in order."""
        return [s["name"] for s in self._sheets]

    @property
    def sheets(self) -> list[dict]:
        """Backward-compatible access to internal sheets list."""
        return self._sheets

    def get_sheet(self, index: int) -> dict:
        """
        Return the sheet dict at *index*.

        Returns an empty sentinel dict if *index* is out of range so callers
        never have to guard against IndexError.
        """
        if index < 0 or index >= len(self._sheets):
            return {"name": "", "df": None, "mask": None}
        return self._sheets[index]

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_sheet(self, name: Optional[str] = None) -> int:
        """
        Append a new empty sheet.

        If *name* is None or empty the sheet is auto-named "Sheet<N>" where
        N is the smallest integer that produces a unique name.

        Returns the index of the newly added sheet.
        """
        if not name:
            existing = set(self.sheet_names())
            n = len(self._sheets) + 1
            while f"Sheet{n}" in existing:
                n += 1
            name = f"Sheet{n}"

        self._sheets.append({"name": str(name), "df": None, "mask": None})
        return len(self._sheets) - 1

    def remove_sheet(self, index: int) -> None:
        """
        Remove the sheet at *index*.

        - No-op if *index* is out of range.
        - No-op if removing would leave zero sheets (minimum 1 enforced).
        """
        if index < 0 or index >= len(self._sheets):
            return  # out of range — safe no-op
        if len(self._sheets) <= 1:
            return  # would violate invariant — silent no-op
        self._sheets.pop(index)

    def rename_sheet(self, index: int, new_name: str) -> bool:
        """
        Rename the sheet at *index* to *new_name*.

        Returns True on success, False if the index is invalid or the name
        is empty / not a string.
        """
        if index < 0 or index >= len(self._sheets):
            return False
        if not isinstance(new_name, str) or not new_name.strip():
            return False
        self._sheets[index]["name"] = new_name.strip()
        return True

    def set_sheet_data(
        self,
        index: int,
        df: Optional[pd.DataFrame],
        mask: Optional[pd.Series],
    ) -> None:
        """
        Store *df* and *mask* into the sheet at *index*.

        No-op if *index* is out of range.
        """
        if index < 0 or index >= len(self._sheets):
            return
        self._sheets[index]["df"] = df
        self._sheets[index]["mask"] = mask
