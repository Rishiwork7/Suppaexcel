"""
Undo/Redo system implementation using the Command pattern.
Limits history to 15 steps.
"""

from collections import deque
from typing import Any, List, Optional
import pandas as pd


class Command:
    """Base class for undoable commands."""
    def redo(self):
        raise NotImplementedError
    
    def undo(self):
        raise NotImplementedError


class UndoStack:
    """
    Manages a stack of Commands with a limited history.
    """
    def __init__(self, limit=15):
        self.stack = deque(maxlen=limit)
        self.undoing = False

    def push(self, command: Command):
        if not self.undoing:
            self.stack.append(command)

    def undo(self):
        if not self.stack:
            return None
        
        self.undoing = True
        command = self.stack.pop()
        command.undo()
        self.undoing = False
        return command


# --- Concrete Commands ---

class EditCellCommand(Command):
    def __init__(self, model, row, col, old_val, new_val):
        self.model = model
        self.row = row
        self.col = col
        self.old_val = old_val
        self.new_val = new_val

    def undo(self):
        self.model.set_cell_data(self.row, self.col, self.old_val)

    def redo(self):
        self.model.set_cell_data(self.row, self.col, self.new_val)


class AddRowCommand(Command):
    def __init__(self, model, row_idx):
        self.model = model
        self.row_idx = row_idx

    def undo(self):
        self.model.remove_row(self.row_idx)

    def redo(self):
        self.model.add_row()


class AddColCommand(Command):
    def __init__(self, model, col_idx, name):
        self.model = model
        self.col_idx = col_idx
        self.name = name

    def undo(self):
        self.model.remove_column(self.col_idx)

    def redo(self):
        self.model.add_column(self.name)


class RenameColCommand(Command):
    def __init__(self, model, col_idx, old_name, new_name):
        self.model = model
        self.col_idx = col_idx
        self.old_name = old_name
        self.new_name = new_name

    def undo(self):
        self.model.rename_column(self.col_idx, self.old_name)

    def redo(self):
        self.model.rename_column(self.col_idx, self.new_name)


class DeduplicateCommand(Command):
    def __init__(self, model, old_df, old_mask):
        self.model = model
        self.old_df = old_df
        self.old_mask = old_mask
        self.new_df = None
        self.new_mask = None

    def capture_new(self, new_df, new_mask):
        self.new_df = new_df
        self.new_mask = new_mask

    def undo(self):
        self.model.load_dataframe(self.old_df, self.old_mask)

    def redo(self):
        if self.new_df is not None:
            self.model.load_dataframe(self.new_df, self.new_mask)


class DeleteRowCommand(Command):
    def __init__(self, model, row_idx, row_data, mask_val):
        self.model = model
        self.row_idx = row_idx
        self.row_data = row_data
        self.mask_val = mask_val

    def undo(self):
        self.model.insert_row(self.row_idx, self.row_data, self.mask_val)

    def redo(self):
        self.model.remove_row(self.row_idx)


class DeleteColCommand(Command):
    def __init__(self, model, col_idx, col_name, col_data):
        self.model = model
        self.col_idx = col_idx
        self.col_name = col_name
        self.col_data = col_data

    def undo(self):
        self.model.insert_column(self.col_idx, self.col_name, self.col_data)

    def redo(self):
        self.model.remove_column(self.col_idx)

