"""
History Logger Module

This module provides simple, append-only command history logging for the Template Assistant.
Each command is logged with a precise timestamp in the format specified in the design document.

Format: `2024-01-15 10:00:00 | use reports/monthly.template`
"""

import os
from typing import List, Tuple
from datetime import datetime
from pathlib import Path

from configuration import HISTORY_FILE


# ============================================================================
# Custom Exception Classes
# ============================================================================

class HistoryError(Exception):
    """Base exception class for history logging errors."""
    def __init__(self, message: str, history_file: str = None):
        self.history_file = history_file
        super().__init__(f"{message}" + (f" in {history_file}" if history_file else ""))


class HistoryWriteError(HistoryError):
    """Raised when history file cannot be written."""
    pass


# ============================================================================
# HistoryLogger Class
# ============================================================================

class HistoryLogger:
    """
    Simple append-only command history logger.
    
    Logs commands with timestamps in exact format: YYYY-MM-DD HH:MM:SS | command
    Supports reading recent commands for debugging.
    """
    
    def __init__(self, history_file_path: str = None):
        self.history_file = history_file_path or HISTORY_FILE
    
    def log_command(self, command: str) -> None:
        """Log a command with timestamp."""
        self._ensure_file_exists()
        
        timestamp = self._generate_timestamp()
        log_line = f"{timestamp} | {command}\n"
        
        try:
            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
                f.flush()  # Ensure immediate persistence
        except OSError as e:
            raise HistoryWriteError(f"Failed to write to history file: {e}")
    
    def get_recent_commands(self, count: int = 10) -> List[Tuple[str, str]]:
        """
        Get last N commands from history.
        
        Returns list of (timestamp, command) tuples.
        """
        if not os.path.exists(self.history_file):
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except OSError:
            return []
        
        recent = []
        for line in reversed(lines[-count:]):
            line = line.strip()
            if line and ' | ' in line:
                timestamp, cmd = line.split(' | ', 1)
                recent.append((timestamp, cmd))
        
        return list(reversed(recent))  # Return in chronological order
    
    def clear_history(self) -> None:
        """Clear all history entries."""
        self._ensure_file_exists()
        try:
            open(self.history_file, 'w').close()
        except OSError as e:
            raise HistoryWriteError(f"Failed to clear history file: {e}")
    
    def _generate_timestamp(self) -> str:
        """Generate timestamp in format: YYYY-MM-DD HH:MM:SS."""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def _ensure_file_exists(self) -> None:
        """Create history file and directories if needed."""
        if os.path.exists(self.history_file):
            return
        
        Path(self.history_file).parent.mkdir(parents=True, exist_ok=True)
        open(self.history_file, 'w').close()


# Module convenience instance (uses default config)
history_logger = HistoryLogger()
