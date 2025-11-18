"""
Unit Tests for History Logger Module

Comprehensive test suite for history_logger.py covering:
- Command logging with correct timestamp format
- File creation and directory handling
- Recent command retrieval
- Error handling and edge cases
"""

import unittest
import os
import tempfile
import shutil
from datetime import datetime

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from history_logger import HistoryLogger, HistoryWriteError
from configuration import HISTORY_FILE


class TestHistoryLogger(unittest.TestCase):
    """Test HistoryLogger functionality."""
    
    def setUp(self):
        """Create temporary directory for test history files."""
        self.temp_dir = tempfile.mkdtemp()
        self.history_file = os.path.join(self.temp_dir, "test.history")
        os.environ['TEMPLATE_ASSISTANT_HISTORY'] = self.history_file
    
    def tearDown(self):
        """Cleanup temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_logger(self) -> HistoryLogger:
        """Create HistoryLogger with test history file."""
        return HistoryLogger(self.history_file)
    
    def test_initialization(self):
        """Test HistoryLogger initializes correctly."""
        logger = self._create_test_logger()
        self.assertEqual(logger.history_file, self.history_file)
    
    def test_log_single_command(self):
        """Test logging one command."""
        logger = self._create_test_logger()
        logger.log_command("use test.template")
        
        self.assertTrue(os.path.exists(self.history_file))
        with open(self.history_file, 'r') as f:
            line = f.read().strip()
            self.assertTrue(line.endswith("| use test.template"))
            self.assertRegex(line, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \|')
    
    def test_log_multiple_commands(self):
        """Test logging multiple commands appends correctly."""
        logger = self._create_test_logger()
        logger.log_command("command 1")
        logger.log_command("command 2")
        
        with open(self.history_file, 'r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("command 1", lines[0])
            self.assertIn("command 2", lines[1])
    
    def test_timestamp_format(self):
        """Test timestamp format is exactly YYYY-MM-DD HH:MM:SS."""
        logger = self._create_test_logger()
        logger.log_command("test")
        
        with open(self.history_file, 'r') as f:
            line = f.readline().strip()
            timestamp_part = line.split(' | ')[0]
            self.assertRegex(timestamp_part, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
    
    def test_file_creation(self):
        """Test history file created if missing."""
        logger = self._create_test_logger()
        logger.log_command("test")
        self.assertTrue(os.path.exists(self.history_file))
    
    def test_directory_creation(self):
        """Test parent directories created automatically."""
        nested_path = os.path.join(self.temp_dir, "logs", "test.history")
        logger = HistoryLogger(nested_path)
        logger.log_command("test")
        self.assertTrue(os.path.exists(nested_path))
    
    def test_append_mode(self):
        """Test new commands append without overwriting."""
        logger = self._create_test_logger()
        logger.log_command("first")
        
        # Log second command
        logger.log_command("second")
        
        with open(self.history_file, 'r') as f:
            content = f.read()
            self.assertIn("first", content)
            self.assertIn("second", content)
    
    def test_get_recent_commands(self):
        """Test retrieving recent commands."""
        logger = self._create_test_logger()
        logger.log_command("cmd1")
        logger.log_command("cmd2")
        logger.log_command("cmd3")
        
        recent = logger.get_recent_commands(2)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0][1], "cmd2")
        self.assertEqual(recent[1][1], "cmd3")
    
    def test_get_recent_commands_empty_file(self):
        """Test empty file returns empty list."""
        logger = self._create_test_logger()
        recent = logger.get_recent_commands()
        self.assertEqual(recent, [])
    
    def test_get_recent_commands_fewer_entries(self):
        """Test when fewer entries than requested."""
        logger = self._create_test_logger()
        logger.log_command("only one")
        recent = logger.get_recent_commands(5)
        self.assertEqual(len(recent), 1)
    
    def test_clear_history(self):
        """Test clearing history."""
        logger = self._create_test_logger()
        logger.log_command("test")
        logger.clear_history()
        
        self.assertTrue(os.path.exists(self.history_file))
        with open(self.history_file, 'r') as f:
            self.assertEqual(f.read().strip(), "")
    
    def test_special_characters_in_commands(self):
        """Test special characters in commands."""
        logger = self._create_test_logger()
        test_cmd = 'set "name" "Acme Corp | with pipe"'
        logger.log_command(test_cmd)
        
        with open(self.history_file, 'r') as f:
            content = f.read()
            self.assertIn(test_cmd, content)
    
    def test_unicode_in_commands(self):
        """Test unicode commands."""
        logger = self._create_test_logger()
        logger.log_command("use отчет.template")
        
        with open(self.history_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("отчет.template", content)
    
    def test_newline_in_command(self):
        """Test commands with newlines."""
        logger = self._create_test_logger()
        test_cmd = "set multiline 'value\\nwith\\nnewlines'"
        logger.log_command(test_cmd)
        
        with open(self.history_file, 'r') as f:
            content = f.read()
            self.assertIn(test_cmd, content)


if __name__ == '__main__':
    unittest.main()
