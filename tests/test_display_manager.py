"""
Unit Tests for Display Manager

Comprehensive test suite for display_manager.py covering width detection,
word wrapping, table formatting, and edge cases.
"""

import unittest
from unittest.mock import patch, MagicMock
import signal

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from display_manager import DisplayManager
import configuration


class TestDisplayManager(unittest.TestCase):
    """Test display manager functionality."""
    
    def setUp(self):
        """Create fresh DisplayManager instance for each test."""
        # Reset configuration to defaults
        self.original_auto_detect = configuration.AUTO_DETECT_WIDTH
        self.original_wrap_enabled = configuration.WORD_WRAP_ENABLED
        self.original_preserve_formatting = configuration.PRESERVE_FORMATTING_ON_WRAP
        
    def tearDown(self):
        """Restore original configuration."""
        configuration.AUTO_DETECT_WIDTH = self.original_auto_detect
        configuration.WORD_WRAP_ENABLED = self.original_wrap_enabled
        configuration.PRESERVE_FORMATTING_ON_WRAP = self.original_preserve_formatting
    
    # Terminal Width Detection Tests
    
    @patch('display_manager.shutil.get_terminal_size')
    def test_detect_width_success(self, mock_get_size):
        """Test successful terminal width detection."""
        mock_get_size.return_value = MagicMock(columns=120, lines=40)
        configuration.AUTO_DETECT_WIDTH = True
        
        dm = DisplayManager()
        self.assertEqual(dm.get_terminal_width(), 120)
    
    @patch('display_manager.shutil.get_terminal_size')
    def test_detect_width_fallback(self, mock_get_size):
        """Test fallback to DEFAULT_WIDTH on error."""
        mock_get_size.side_effect = OSError("Not a terminal")
        configuration.AUTO_DETECT_WIDTH = True
        
        dm = DisplayManager()
        self.assertEqual(dm.get_terminal_width(), configuration.DEFAULT_WIDTH)
    
    def test_detect_width_disabled(self):
        """Test using DEFAULT_WIDTH when auto-detect disabled."""
        configuration.AUTO_DETECT_WIDTH = False
        
        dm = DisplayManager()
        self.assertEqual(dm.get_terminal_width(), configuration.DEFAULT_WIDTH)
    
    @patch('display_manager.shutil.get_terminal_size')
    def test_width_positive_validation(self, mock_get_size):
        """Test that negative/zero widths default to DEFAULT_WIDTH."""
        mock_get_size.return_value = MagicMock(columns=0, lines=40)
        configuration.AUTO_DETECT_WIDTH = True
        
        dm = DisplayManager()
        self.assertEqual(dm.get_terminal_width(), configuration.DEFAULT_WIDTH)
    
    # Word Wrapping Tests
    
    def test_wrap_basic_text(self):
        """Test basic text wrapping without colors."""
        dm = DisplayManager()
        dm.terminal_width = 20
        
        text = "This is a long line that needs to be wrapped"
        wrapped = dm.wrap_text(text, width=20)
        
        lines = wrapped.split('\n')
        self.assertTrue(all(len(line) <= 20 for line in lines))
        self.assertIn("This is a long line", lines[0])
    
    def test_wrap_preserves_ansi_codes(self):
        """Test that ANSI color codes are preserved during wrapping."""
        dm = DisplayManager()
        dm.terminal_width = 20
        
        text = "\x1b[31mThis is red text that needs wrapping\x1b[0m"
        wrapped = dm.wrap_text(text, width=20)
        
        # Check that ANSI codes are still present
        self.assertIn("\x1b[31m", wrapped)
        self.assertIn("\x1b[0m", wrapped)
    
    def test_wrap_multiple_colors(self):
        """Test wrapping with multiple color changes."""
        dm = DisplayManager()
        dm.terminal_width = 15
        
        text = "\x1b[31mRed\x1b[0m \x1b[32mGreen\x1b[0m \x1b[34mBlue text here\x1b[0m"
        wrapped = dm.wrap_text(text, width=15)
        
        # All color codes should be preserved
        self.assertIn("\x1b[31m", wrapped)
        self.assertIn("\x1b[32m", wrapped)
        self.assertIn("\x1b[34m", wrapped)
    
    def test_wrap_long_word(self):
        """Test wrapping of single word longer than width."""
        dm = DisplayManager()
        
        text = "supercalifragilisticexpialidocious"
        wrapped = dm.wrap_text(text, width=10)
        
        lines = wrapped.split('\n')
        self.assertTrue(len(lines) > 1)
        self.assertTrue(all(len(line) <= 10 for line in lines))
    
    def test_wrap_disabled(self):
        """Test that wrapping returns text unchanged when disabled."""
        configuration.WORD_WRAP_ENABLED = False
        dm = DisplayManager()
        
        text = "This is a very long line that would normally be wrapped"
        wrapped = dm.wrap_text(text, width=10)
        
        self.assertEqual(wrapped, text)
    
    def test_wrap_empty_string(self):
        """Test wrapping empty string."""
        dm = DisplayManager()
        
        self.assertEqual(dm.wrap_text(""), "")
        self.assertEqual(dm.wrap_text("", width=10), "")
    
    def test_wrap_custom_width(self):
        """Test using custom width parameter."""
        dm = DisplayManager()
        dm.terminal_width = 80
        
        text = "This text should wrap at 15 characters"
        wrapped = dm.wrap_text(text, width=15)
        
        lines = wrapped.split('\n')
        self.assertTrue(all(len(line) <= 15 for line in lines))
    
    # ANSI Code Utility Tests
    
    def test_strip_ansi_codes(self):
        """Test removal of ANSI codes."""
        dm = DisplayManager()
        
        text = "\x1b[31mRed\x1b[0m \x1b[1mBold\x1b[0m"
        stripped = dm._strip_ansi_codes(text)
        
        self.assertEqual(stripped, "Red Bold")
        self.assertNotIn("\x1b", stripped)
    
    def test_measure_visible_length(self):
        """Test measuring text length excluding ANSI codes."""
        dm = DisplayManager()
        
        text = "\x1b[31mHello\x1b[0m"
        self.assertEqual(dm._measure_visible_length(text), 5)
        
        text = "Plain text"
        self.assertEqual(dm._measure_visible_length(text), 10)
    
    def test_extract_ansi_codes(self):
        """Test extraction of ANSI codes with positions."""
        dm = DisplayManager()
        
        text = "\x1b[31mRed\x1b[0m"
        codes = dm._extract_ansi_codes(text)
        
        self.assertEqual(len(codes), 2)
        self.assertEqual(codes[0], (0, "\x1b[31m"))
        self.assertEqual(codes[1], (8, "\x1b[0m"))
    
    # Table Formatting Tests
    
    def test_format_table_basic(self):
        """Test basic table formatting."""
        dm = DisplayManager()
        dm.terminal_width = 80
        
        headers = ["Name", "Value", "Description"]
        rows = [
            ["var1", "test", "Test variable"],
            ["var2", "demo", "Demo variable"]
        ]
        
        table = dm.format_table(headers, rows)
        
        lines = table.split('\n')
        self.assertIn("Name", lines[0])
        self.assertIn("Value", lines[0])
        self.assertIn("----", lines[1])  # Separator
        self.assertIn("var1", lines[2])
        self.assertIn("var2", lines[3])
    
    def test_format_table_adaptive_width(self):
        """Test table adapts to terminal width."""
        dm = DisplayManager()
        
        headers = ["Column1", "Column2", "Column3"]
        rows = [["A" * 50, "B" * 50, "C" * 50]]
        
        # Wide terminal
        dm.terminal_width = 200
        wide_table = dm.format_table(headers, rows)
        
        # Narrow terminal
        dm.terminal_width = 50
        narrow_table = dm.format_table(headers, rows)
        
        # Narrow table should have truncation
        self.assertIn(configuration.TRUNCATE_INDICATOR, narrow_table)
        self.assertTrue(len(narrow_table.split('\n')[0]) <= 50)
    
    def test_format_table_truncation(self):
        """Test content truncation with indicator."""
        dm = DisplayManager()
        dm.terminal_width = 40
        
        headers = ["Name", "LongValue"]
        rows = [["test", "This is a very long value that needs truncation"]]
        
        table = dm.format_table(headers, rows)
        
        self.assertIn(configuration.TRUNCATE_INDICATOR, table)
    
    def test_format_table_empty_rows(self):
        """Test formatting with empty rows."""
        dm = DisplayManager()
        
        headers = ["Col1", "Col2"]
        rows = []
        
        table = dm.format_table(headers, rows)
        self.assertIn("No data", table)
    
    def test_format_table_with_title(self):
        """Test table with title."""
        dm = DisplayManager()
        
        headers = ["Name", "Value"]
        rows = [["test", "123"]]
        title = "Test Table"
        
        table = dm.format_table(headers, rows, title=title)
        
        lines = table.split('\n')
        self.assertEqual(lines[0], "Test Table")
        self.assertIn("=", lines[1])  # Title separator
    
    def test_format_table_ansi_in_cells(self):
        """Test table with ANSI codes in cells."""
        dm = DisplayManager()
        dm.terminal_width = 80
        
        headers = ["Name", "Status"]
        rows = [["test", "\x1b[32mPassed\x1b[0m"]]
        
        table = dm.format_table(headers, rows)
        
        # ANSI codes should be preserved
        self.assertIn("\x1b[32m", table)
        self.assertIn("Passed", table)
    
    # Window Resize Handling Tests
    
    @patch('display_manager.signal.signal')
    def test_resize_signal_handler(self, mock_signal):
        """Test SIGWINCH handler registration."""
        # This test will only work on Unix-like systems
        try:
            dm = DisplayManager()
            # Check if signal.signal was called with SIGWINCH
            if hasattr(signal, 'SIGWINCH'):
                mock_signal.assert_called()
        except AttributeError:
            # Windows doesn't have SIGWINCH
            pass
    
    # Enhanced ANSI Tests
    
    def test_multi_color_wrap_alignment(self):
        """Test wrapping with multiple color segments ensures proper alignment."""
        dm = DisplayManager()
        dm.terminal_width = 20
        
        # Text with multiple distinct color segments
        text = "\x1b[31mRed text\x1b[0m \x1b[32mGreen text\x1b[0m \x1b[34mBlue text here\x1b[0m"
        wrapped = dm.wrap_text(text, width=20)
        
        lines = wrapped.split('\n')
        # Verify each line has proper ANSI codes
        for line in lines:
            # Check that visible length is within width
            visible_len = dm._measure_visible_length(line)
            self.assertLessEqual(visible_len, 20)
            
            # Verify no partial escape sequences
            self.assertNotIn('\x1b[3', line)  # No cut-off color code
            self.assertNotIn('\x1b[', line[-2:])  # No escape at very end without completion
    
    def test_truncation_with_multiple_colors(self):
        """Test truncation preserves colors and adds reset when needed."""
        dm = DisplayManager()
        
        # Text with active color that gets truncated
        text = "\x1b[31mThis is red text that will be truncated\x1b[0m"
        truncated = dm._truncate_with_indicator(text, 15)
        
        # Check visible length matches target
        visible_len = dm._measure_visible_length(truncated)
        self.assertEqual(visible_len, 15)
        
        # Verify color code is present
        self.assertIn("\x1b[31m", truncated)
        
        # Verify truncation indicator is present
        self.assertIn(configuration.TRUNCATE_INDICATOR, truncated)
        
        # Verify reset code is added after indicator
        self.assertTrue(truncated.endswith(configuration.TRUNCATE_INDICATOR + '\x1b[0m') or
                       truncated.endswith(configuration.TRUNCATE_INDICATOR))
    
    def test_wrap_with_reset_codes(self):
        """Test wrapping handles reset codes correctly."""
        dm = DisplayManager()
        configuration.PRESERVE_FORMATTING_ON_WRAP = True
        dm.terminal_width = 15
        
        # Text with color and explicit reset
        text = "\x1b[31mRed text\x1b[0m normal text that wraps"
        wrapped = dm.wrap_text(text, width=15)
        
        lines = wrapped.split('\n')
        # First line should have red text
        self.assertIn("\x1b[31m", lines[0])
        
        # Second line should not have red (after reset)
        if len(lines) > 1:
            # The normal text should not be red
            self.assertNotIn("\x1b[31m", lines[1]) or self.assertIn("\x1b[0m", lines[0])
    
    def test_truncate_ansi_boundary(self):
        """Test truncation at ANSI code boundaries."""
        dm = DisplayManager()
        
        # Text where truncation point falls near ANSI code
        text = "Plain \x1b[31mRed\x1b[0m text"
        
        # Truncate at different points
        truncated_5 = dm._truncate_with_indicator(text, 8)
        self.assertEqual(dm._measure_visible_length(truncated_5), 8)
        
        # Verify no partial ANSI codes
        self.assertNotIn('\x1b[3', truncated_5)
        self.assertNotIn('1m', truncated_5) if '\x1b[31m' not in truncated_5 else None
    
    def test_table_cell_truncation_with_ansi(self):
        """Test table cells with ANSI codes truncate correctly."""
        dm = DisplayManager()
        dm.terminal_width = 40
        
        headers = ["Status", "Message"]
        rows = [["\x1b[32mPASSED\x1b[0m", "\x1b[31mVery long error message that needs truncation\x1b[0m"]]
        
        table = dm.format_table(headers, rows)
        
        # Verify ANSI codes are preserved
        self.assertIn("\x1b[32m", table)
        self.assertIn("\x1b[31m", table)
        
        # Verify table width constraint
        for line in table.split('\n'):
            # Account for ANSI codes when checking width
            visible_len = dm._measure_visible_length(line)
            self.assertLessEqual(visible_len, 40)
    
    # Integration Tests
    
    def test_full_pipeline_render_output(self):
        """Test full pipeline with colored output."""
        dm = DisplayManager()
        dm.terminal_width = 50
        
        # Simulate template output with colors
        output = "\x1b[32m[bold]Success!\x1b[0m This is a long line of output that needs to be wrapped properly while preserving all the color codes."
        
        wrapped = dm.wrap_text(output)
        lines = wrapped.split('\n')
        
        # Check wrapping occurred
        self.assertTrue(len(lines) > 1)
        # Check colors preserved
        self.assertIn("\x1b[32m", wrapped)
        # Check all lines fit width
        for line in lines:
            visible_len = dm._measure_visible_length(line)
            self.assertLessEqual(visible_len, 50)
    
    def test_full_pipeline_ls_command(self):
        """Test full pipeline for ls command table."""
        dm = DisplayManager()
        dm.terminal_width = 60
        
        headers = ["Variable", "Value", "Description", "Default"]
        rows = [
            ["client_name", "Acme Corporation", "The client organization name", "None"],
            ["report_type", "monthly", "Type of report to generate", "weekly"],
            ["include_charts", "true", "Include visualization charts", "false"]
        ]
        
        table = dm.format_table(headers, rows)
        lines = table.split('\n')
        
        # Check table fits width
        for line in lines:
            self.assertLessEqual(len(dm._strip_ansi_codes(line)), 60)
        
        # Check content is present (possibly truncated)
        self.assertIn("Variable", table)
        self.assertIn("client_name", table)


if __name__ == '__main__':
    unittest.main()