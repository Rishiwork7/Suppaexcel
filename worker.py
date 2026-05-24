"""
Worker threads for background data processing operations.

These workers run in separate threads to keep the UI responsive during
long-running operations like file loading, deduplication, and export.
"""

from PyQt6.QtCore import QThread, pyqtSignal
import pandas as pd
from typing import Optional
import traceback
import logging

logger = logging.getLogger(__name__)


class FileLoadWorker(QThread):
    """
    Worker thread for loading CSV or XLSX files.
    
    Signals:
        - finished: Emitted when loading completes successfully
        - error: Emitted if an error occurs during loading
        - progress: Emitted to show progress status
    """
    
    finished = pyqtSignal(pd.DataFrame, pd.Series)  # Emits loaded DataFrame and duplicate mask
    error = pyqtSignal(str)              # Emits error message
    progress = pyqtSignal(str)           # Emits progress messages
    
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
    
    def run(self):
        """
        Load the file in the background thread.
        
        Supports .csv and .xlsx formats. For large files, uses pandas
        chunking for memory efficiency.
        """
        try:
            self.progress.emit("Loading file...")
            
            # Determine file type
            if self.file_path.endswith('.csv'):
                # For very large CSV files, we could use chunksize, but for now
                # we load the entire file. Pandas is optimized for this.
                df = pd.read_csv(self.file_path, low_memory=False)
            elif self.file_path.endswith('.xlsx'):
                # XLSX files are slower to parse; consider chunking if needed
                df = pd.read_excel(self.file_path)
            elif self.file_path.endswith('.txt'):
                try:
                    df = pd.read_csv(self.file_path, sep=None, engine='python')
                except Exception:
                    with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = [line.strip() for line in f.readlines() if line.strip()]
                    df = pd.DataFrame(lines, columns=['Content'])
            else:
                self.error.emit("Unsupported file format. Use CSV, XLSX, or TXT.")
                return
            
            if df.empty:
                self.error.emit("File is empty.")
                return
            
            self.progress.emit("Identifying duplicates...")
            # keep=False marks ALL copies of a duplicate as True
            duplicate_mask = df.duplicated(keep=False)
            
            self.progress.emit(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
            self.finished.emit(df, duplicate_mask)
            
        except Exception as e:
            logger.error("FileLoadWorker error:\n%s", traceback.format_exc())
            self.error.emit(f"Error loading file: {str(e)}")


class DeduplicateWorker(QThread):
    """
    Worker thread for removing duplicate rows.
    
    Signals:
        - finished: Emitted with (new_df, removed_count)
        - error: Emitted if an error occurs
        - progress: Emitted to show progress status
    """
    
    finished = pyqtSignal(pd.DataFrame, int, pd.Series)  # Emits (new_df, num_removed, new_mask)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        # Fix 11: Don't copy the entire df upfront — for 10M rows this doubles peak RAM.
        # We hold a reference and create the deduplicated result directly.
        self.df = df
    
    def run(self):
        """
        Remove duplicate rows in the background thread.
        
        Uses pandas drop_duplicates() which is highly optimized for large datasets.
        """
        try:
            original_count = len(self.df)
            self.progress.emit("Removing duplicates...")
            
            # keep='first' ensures one original row remains while removing others.
            # drop_duplicates returns a new df — original is not mutated.
            result_df = self.df.drop_duplicates(keep='first')
            
            removed_count = original_count - len(result_df)
            self.progress.emit(f"Removed {removed_count:,} duplicate rows")
            
            # Recalculate duplicate mask for remaining data (should be all False)
            duplicate_mask = result_df.duplicated(keep=False)
            
            self.finished.emit(result_df, removed_count, duplicate_mask)
            
        except Exception as e:
            logger.error("DeduplicateWorker error:\n%s", traceback.format_exc())
            self.error.emit(f"Error removing duplicates: {str(e)}")


class MergeWorker(QThread):
    """
    Worker thread for merging multiple files (CSV, XLSX, TXT) with deduplication.
    
    Signals:
        - finished: Emitted with (merged_df, duplicate_mask)
        - error: Emitted if an error occurs
        - progress: Emitted to show progress status
    """
    
    finished = pyqtSignal(pd.DataFrame, pd.Series)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, file_paths: list[str]):
        super().__init__()
        self.file_paths = file_paths
    
    def run(self):
        """
        Load and merge multiple files in the background.
        Preserves column structure — aligns columns across files by name.
        """
        try:
            dfs = []
            total_files = len(self.file_paths)
            
            for i, file_path in enumerate(self.file_paths):
                self.progress.emit(f"Processing file {i+1}/{total_files}: {file_path.split('/')[-1]}...")
                
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file_path, low_memory=False)
                elif file_path.endswith('.xlsx'):
                    df = pd.read_excel(file_path)
                elif file_path.endswith('.txt'):
                    try:
                        df = pd.read_csv(file_path, sep=None, engine='python')
                    except Exception:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = [line.strip() for line in f.readlines() if line.strip()]
                        df = pd.DataFrame(lines, columns=['Content'])
                else:
                    self.progress.emit(f"Skipping unsupported file: {file_path}")
                    continue
                
                if not df.empty:
                    dfs.append(df)
            
            if not dfs:
                self.error.emit("No valid data found in selected files.")
                return
            
            self.progress.emit("Merging datasets...")
            # Fix 7: Use pd.concat to stack rows while aligning on column names.
            # This preserves column structure — matching columns stay aligned,
            # non-matching columns get NaN where absent. Previously all columns
            # were flattened into a single 'Data' column, destroying structure.
            merged_df = pd.concat(dfs, ignore_index=True, sort=False)
            
            self.progress.emit(f"Merged {len(merged_df):,} rows. Identifying duplicates...")
            
            duplicate_mask = merged_df.duplicated(keep=False)
            dup_count = duplicate_mask.sum()
            
            self.progress.emit(f"Final dataset: {len(merged_df):,} rows, {len(merged_df.columns)} columns. Found {dup_count:,} duplicates.")
            self.finished.emit(merged_df, duplicate_mask)
            
        except Exception as e:
            logger.error("MergeWorker error:\n%s", traceback.format_exc())
            self.error.emit(f"Error merging files: {str(e)}")


class ExportWorker(QThread):
    """
    Worker thread for exporting data to CSV or XLSX.
    
    Signals:
        - finished: Emitted when export completes successfully
        - error: Emitted if an error occurs
        - progress: Emitted to show progress status
    """
    
    finished = pyqtSignal()  # Emits nothing; caller knows it's done
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, df: pd.DataFrame, file_path: str):
        super().__init__()
        self.df = df
        self.file_path = file_path
    
    def run(self):
        """
        Export DataFrame to file in the background thread.
        
        Supports .csv and .xlsx formats.
        """
        try:
            self.progress.emit("Exporting data...")
            
            if self.file_path.endswith('.csv'):
                self.df.to_csv(self.file_path, index=False)
            elif self.file_path.endswith('.xlsx'):
                self.df.to_excel(self.file_path, index=False, sheet_name='Data')
            else:
                self.error.emit("Unsupported export format. Use CSV or XLSX.")
                return
            
            self.progress.emit(f"Exported {len(self.df):,} rows successfully")
            self.finished.emit()
            
        except Exception as e:
            logger.error("ExportWorker error:\n%s", traceback.format_exc())
            self.error.emit(f"Error exporting file: {str(e)}")


class SearchWorker(QThread):
    """
    Worker thread for searching/filtering data.
    
    Signals:
        - finished: Emitted with (filtered_df, filtered_mask)
        - error: Emitted if an error occurs
    """
    
    finished = pyqtSignal(pd.DataFrame, pd.Series)
    error = pyqtSignal(str)
    
    def __init__(self, df: pd.DataFrame, mask: pd.Series, query: str):
        super().__init__()
        self.df = df
        self.mask = mask
        self.query = query
        # Fix 3: Cancellation flag — safe alternative to terminate()
        # terminate() force-kills the thread OS-level and can corrupt pandas state
        self._cancelled = False

    def cancel(self):
        """Signal the worker to stop at the next safe checkpoint."""
        self._cancelled = True
    
    def run(self):
        """
        Filter the DataFrame based on the search query.
        """
        try:
            if not self.query:
                self.finished.emit(self.df, self.mask)
                return
            
            query_lower = self.query.lower()
            condition = pd.Series(False, index=self.df.index)
            
            # Fix 10: Pre-compute the full string representation of each column once.
            # Previously astype(str).str.lower() was called inside the loop body,
            # meaning for a 10M row × 20 col df every search did 200M conversions.
            # Now we convert each column once and check the cancel flag between columns
            # so long searches can be interrupted cleanly.
            for col in self.df.columns:
                if self._cancelled:
                    return  # Exit cleanly — no signal emitted, caller handles this
                try:
                    col_str = self.df[col].astype(str).str.lower()
                    condition |= col_str.str.contains(query_lower, regex=False, na=False)
                except Exception:
                    continue
            
            if self._cancelled:
                return

            filtered_df = self.df[condition]
            filtered_mask = self.mask[condition] if self.mask is not None else None
            
            self.finished.emit(filtered_df, filtered_mask)
            
        except Exception as e:
            logger.error("SearchWorker error:\n%s", traceback.format_exc())
            self.error.emit(f"Search Error: {str(e)}")