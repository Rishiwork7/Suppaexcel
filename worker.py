"""
Worker threads for background data processing operations.

These workers run in separate threads to keep the UI responsive during
long-running operations like file loading, deduplication, and export.
"""

from PyQt6.QtCore import QThread, pyqtSignal
import pandas as pd
from typing import Optional
import traceback


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
            error_msg = f"Error loading file: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)


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
        self.df = df.copy()  # Work on a copy to avoid modifying original
    
    def run(self):
        """
        Remove duplicate rows in the background thread.
        
        Uses pandas drop_duplicates() which is highly optimized for large datasets.
        """
        try:
            original_count = len(self.df)
            self.progress.emit("Removing duplicates...")
            
            # keep='first' ensures one original row remains while removing others
            self.df = self.df.drop_duplicates(keep='first')
            
            removed_count = original_count - len(self.df)
            self.progress.emit(f"Removed {removed_count:,} duplicate rows")
            
            # Recalculate duplicate mask for remaining data (should be all False)
            duplicate_mask = self.df.duplicated(keep=False)
            
            self.finished.emit(self.df, removed_count, duplicate_mask)
            
        except Exception as e:
            error_msg = f"Error removing duplicates: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)


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
                    # Support both delimited and plain text
                    try:
                        # Try to detect delimiter automatically
                        df = pd.read_csv(file_path, sep=None, engine='python')
                    except Exception:
                        # Fallback for plain text: each line is a row
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
            
            self.progress.emit("Concatenating datasets into single column...")
            # Combine all data into a single column
            all_data = []
            for df in dfs:
                # Flatten all values from the dataframe into a single column
                for col in df.columns:
                    all_data.extend(df[col].astype(str).values)
            
            # Create a new dataframe with single column
            merged_df = pd.DataFrame(all_data, columns=['Data'])
            
            self.progress.emit(f"Merged {len(merged_df):,} rows into single column. Identifying duplicates...")
            
            # Identify duplicates across all merged files (keep=False marks ALL copies)
            duplicate_mask = merged_df.duplicated(keep=False)
            dup_count = duplicate_mask.sum()
            
            self.progress.emit(f"Final dataset: {len(merged_df):,} rows in 1 column. Found {dup_count:,} duplicates.")
            self.finished.emit(merged_df, duplicate_mask)
            
        except Exception as e:
            error_msg = f"Error merging files: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)


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
            error_msg = f"Error exporting file: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)


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
    
    def run(self):
        """
        Filter the DataFrame based on the search query.
        """
        try:
            if not self.query:
                self.finished.emit(self.df, self.mask)
                return
            
            # Optimized: Combine column searches into a single loop using bitwise OR
            # Use 'case=False' and 'na=False' with optimized string access
            query_lower = self.query.lower()
            condition = pd.Series(False, index=self.df.index)
            
            for col in self.df.columns:
                # Optimized search: only cast to string once
                # and use a faster contains check if possible
                try:
                    condition |= self.df[col].astype(str).str.lower().str.contains(query_lower, regex=False, na=False)
                except Exception:
                    continue
            
            filtered_df = self.df[condition]
            filtered_mask = self.mask[condition] if self.mask is not None else None
            
            self.finished.emit(filtered_df, filtered_mask)
            
        except Exception as e:
            self.error.emit(f"Search Error: {str(e)}")

