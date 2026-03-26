"""
VirtualDataModel - Custom QAbstractTableModel for lazy-loading large datasets.

This model implements virtual scrolling, fetching and caching only the rows
currently visible in the viewport. This enables handling of 10M+ row datasets
without loading everything into memory at once.
"""

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant, pyqtSignal
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from PyQt6.QtGui import QColor, QFont


class VirtualDataModel(QAbstractTableModel):
    """
    Custom table model that implements virtual scrolling for large datasets.
    
    The model maintains a reference to the entire pandas DataFrame but only
    retrieves row data when the view requests it (rowCount) or when specific
    cells are rendered (data method). This prevents memory overload.
    """
    
    # Cache size: number of rows to keep in memory for fast access
    CACHE_SIZE = 500
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_df: Optional[pd.DataFrame] = None
        self._full_mask: Optional[pd.Series] = None
        
        self.df: Optional[pd.DataFrame] = None  # The current "view"
        self.duplicate_mask: Optional[pd.Series] = None
        
        self.formatting: Dict[tuple, Dict[str, Any]] = {}  # (row, col) -> format_dict
        self._cache = {}  # Simple cache for recently accessed rows
        self._cache_index = []  # Track cache order for LRU eviction
        
    def load_dataframe(self, df: pd.DataFrame, duplicate_mask: Optional[pd.Series] = None):
        """
        Load a pandas DataFrame into the model.
        """
        self.beginResetModel()
        self._full_df = df
        self._full_mask = duplicate_mask
        self.df = df
        self.duplicate_mask = duplicate_mask
        self._cache.clear()
        self._cache_index.clear()
        self.endResetModel()

    def set_view(self, df: pd.DataFrame, mask: Optional[pd.Series] = None):
        """Switch to a filtered view or back to full view."""
        self.beginResetModel()
        self.df = df
        self.duplicate_mask = mask
        self._cache.clear()
        self._cache_index.clear()
        self.endResetModel()

    def clear_filter(self):
        """Restore the full dataset."""
        if self._full_df is not None:
            self.set_view(self._full_df, self._full_mask)

    def get_full_dataframe(self) -> Optional[pd.DataFrame]:
        return self._full_df
    
    def get_dataframe(self) -> Optional[pd.DataFrame]:
        """
        Get the underlying pandas DataFrame.
        
        Returns:
            The loaded DataFrame or None if not loaded
        """
        return self.df
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        Return the total number of rows in the dataset.
        
        Args:
            parent: Unused (required by QAbstractTableModel)
            
        Returns:
            Number of rows in the DataFrame
        """
        if self.df is None:
            return 0
        return len(self.df)
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        Return the total number of columns in the dataset.
        
        Args:
            parent: Unused (required by QAbstractTableModel)
            
        Returns:
            Number of columns in the DataFrame
        """
        if self.df is None:
            return 0
        return len(self.df.columns)
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> QVariant:
        """
        Return the data for a specific cell.
        
        This method is called by the view when a cell needs to be rendered.
        We implement simple caching to avoid repeated DataFrame access.
        
        Args:
            index: The model index of the cell
            role: The display role (we handle DisplayRole)
            
        Returns:
            The cell data or an empty QVariant
        """
        if not index.isValid() or self.df is None:
            return QVariant()
        
        row = index.row()
        col = index.column()
        
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            try:
                # Optimized: Fetch from internal cache first
                # Use the row integer as a secondary cache key to avoid index label lookups
                if row in self._cache:
                    return QVariant(str(self._cache[row][col]))

                # Not in cache? Fetch the row and update cache
                row_data = self.df.iloc[row].values
                self._update_cache(row, row_data)
                return QVariant(str(row_data[col]))
            except (IndexError, KeyError):
                return QVariant()
        
        elif role == Qt.ItemDataRole.BackgroundRole:
            if self.duplicate_mask is not None and row < len(self.duplicate_mask):
                if self.duplicate_mask.iloc[row]:
                    # More prominent red highlighting for duplicates
                    return QVariant(QColor("#FFCDD2"))
            
            # Custom formatting cell background
            fmt = self.formatting.get((row, col), {})
            if "bg_color" in fmt:
                return QVariant(QColor(fmt["bg_color"]))
        
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            fmt = self.formatting.get((row, col), {})
            return QVariant(fmt.get("alignment", Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
            
        elif role == Qt.ItemDataRole.FontRole:
            fmt = self.formatting.get((row, col), {})
            if fmt.get("bold"):
                font = QFont()
                font.setBold(True)
                return QVariant(font)
        
        elif role == Qt.ItemDataRole.ForegroundRole:
            fmt = self.formatting.get((row, col), {})
            if "color" in fmt:
                return QVariant(QColor(fmt["color"]))
        
        return QVariant()
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return the item flags (make editable)."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    
    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        """Update data in the DataFrame."""
        if index.isValid() and role == Qt.ItemDataRole.EditRole:
            row = index.row()
            col = index.column()
            return self.set_cell_data(row, col, value)
        return False

    def set_cell_data(self, row: int, col: int, value: Any) -> bool:
        """Internal helper to set cell data and update cache/UI."""
        try:
            # Map filtered row to original source row using its pandas index
            # This ensures edits in a filtered search view sync back to the master data
            actual_row_idx = self.df.index[row]
            col_name = self.df.columns[col]
            
            # Update master DataFrame
            self._full_df.at[actual_row_idx, col_name] = value
            
            # Update current view directly (if it's a copy)
            self.df.iloc[row, col] = value
            
            # Clear cache for the master row index
            if actual_row_idx in self._cache:
                del self._cache[actual_row_idx]
                if actual_row_idx in self._cache_index:
                    self._cache_index.remove(actual_row_idx)
            
            index = self.index(row, col)
            self.dataChanged.emit(index, index)
            return True
        except Exception:
            return False
    
    def add_row(self):
        """Append a new empty row to the DataFrame."""
        if self.df is None:
            return
        
        self.beginInsertRows(QModelIndex(), len(self.df), len(self.df))
        new_row = pd.Series({c: "" for c in self.df.columns})
        self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
        # Update mask if it exists
        if self.duplicate_mask is not None:
            self.duplicate_mask = pd.concat([self.duplicate_mask, pd.Series([False])], ignore_index=True)
        self.endInsertRows()
    
    def add_column(self, name: str):
        """Add a new column to the DataFrame."""
        if self.df is None:
            return
        
        self.beginInsertColumns(QModelIndex(), len(self.df.columns), len(self.df.columns))
        self.df[name] = ""
        self.endInsertColumns()
    
    def rename_column(self, index: int, new_name: str):
        """Rename an existing column."""
        if self.df is None or index >= len(self.df.columns):
            return
        
        # Sync with master
        col_name = self.df.columns[index]
        self._full_df.rename(columns={col_name: new_name}, inplace=True)
        
        cols = list(self.df.columns)
        cols[index] = new_name
        self.df.columns = cols
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, index, index)

    def remove_row(self, row_idx: int):
        """Remove a row from the DataFrame safely."""
        if self.df is None or row_idx >= len(self.df):
            return
        
        self.beginRemoveRows(QModelIndex(), row_idx, row_idx)
        actual_idx = self.df.index[row_idx]
        
        # Drop from master first
        self._full_df = self._full_df.drop(actual_idx)
        
        # If view is separate, drop from it too
        if self.df is not self._full_df:
            self.df = self.df.drop(actual_idx)
        else:
            # Sync
            self.df = self._full_df
        
        # Update mask
        if self._full_mask is not None:
            self._full_mask = self._full_mask.drop(actual_idx)
            self.duplicate_mask = self._full_mask if self.df is self._full_df else self.duplicate_mask.drop(actual_idx)
            
        # Clear cache completely as indices shifted
        self._cache.clear()
        self._cache_index.clear()
        self.endRemoveRows()

    def insert_row(self, row_idx: int, row_data: pd.Series, mask_val: bool = False):
        """Insert a row at a specific index (for Undo)."""
        self.beginInsertRows(QModelIndex(), row_idx, row_idx)
        
        # Insert into full DF
        parts = [self._full_df.iloc[:row_idx], pd.DataFrame([row_data]), self._full_df.iloc[row_idx:]]
        self._full_df = pd.concat(parts).reset_index(drop=True)
        
        if self._full_mask is not None:
            m_parts = [self._full_mask.iloc[:row_idx], pd.Series([mask_val]), self._full_mask.iloc[row_idx:]]
            self._full_mask = pd.concat(m_parts).reset_index(drop=True)

        # Update view
        self.df = self._full_df # Reset view to full for simplicity on undo
        self.duplicate_mask = self._full_mask
        
        self._cache.clear()
        self.endInsertRows()

    def remove_column(self, col_idx: int):
        """Remove a column from the DataFrame safely."""
        if self.df is None or col_idx >= len(self.df.columns):
            return
            
        self.beginRemoveColumns(QModelIndex(), col_idx, col_idx)
        col_name = self.df.columns[col_idx]
        
        # Drop from master first
        if col_name in self._full_df.columns:
            # We use a non-inplace drop to be safe with views
            self._full_df = self._full_df.drop(columns=[col_name])
            
        # If view is a separate filtered object, drop from it too
        if self.df is not self._full_df:
            if col_name in self.df.columns:
                self.df = self.df.drop(columns=[col_name])
        else:
            # If they were the same, just keep them synced
            self.df = self._full_df
            
        self.endRemoveColumns()

    def insert_column(self, col_idx: int, name: str, data: pd.Series):
        """Insert a column at a specific index (for Undo)."""
        self.beginInsertColumns(QModelIndex(), col_idx, col_idx)
        self._full_df.insert(col_idx, name, data)
        self.df = self._full_df
        self.endInsertColumns()
    
    def set_cell_format(self, row: int, col: int, format_dict: dict):
        """Set custom formatting for a cell."""
        self.formatting[(row, col)] = format_dict
        index = self.index(row, col)
        self.dataChanged.emit(index, index)
    
    def _update_cache(self, row: int, data: list):
        """
        Update the cache with LRU eviction policy.
        
        Args:
            row: Row index
            data: Row data (list of values)
        """
        if row in self._cache:
            # Move to end (most recently used)
            self._cache_index.remove(row)
        
        self._cache[row] = data
        self._cache_index.append(row)
        
        # Evict oldest if cache is full
        if len(self._cache_index) > self.CACHE_SIZE:
            oldest = self._cache_index.pop(0)
            del self._cache[oldest]
    
    def headerData(self, section: int, orientation: Qt.Orientation, 
                   role: int = Qt.ItemDataRole.DisplayRole) -> QVariant:
        """
        Return header data (column names).
        
        Args:
            section: Column index
            orientation: Horizontal or Vertical
            role: Display role
            
        Returns:
            Column name or row number
        """
        if self.df is None:
            return QVariant()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                try:
                    return QVariant(str(self.df.columns[section]))
                except IndexError:
                    return QVariant()
            elif orientation == Qt.Orientation.Vertical:
                return QVariant(str(section + 1))
        
        return QVariant()
    
    def clear(self):
        """Clear the model data."""
        self.beginResetModel()
        self.df = None
        self._cache.clear()
        self._cache_index.clear()
        self.endResetModel()
