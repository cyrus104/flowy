"""
Unit Tests for Main Entry Point

Comprehensive test suite for main.py covering argument parsing and launch modes.
"""

import unittest
from unittest.mock import patch, Mock, MagicMock
import sys
import argparse

# Add parent directory to path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import parse_arguments, main


class TestArgumentParsing(unittest.TestCase):
    """Test command-line argument parsing."""
    
    def test_parse_arguments_no_args(self):
        """Test default behavior with no arguments."""
        with patch('sys.argv', ['main.py']):
            args = parse_arguments()
            self.assertIsNone(args.template)
            self.assertIsNone(args.save)
    
    def test_parse_arguments_template_only(self):
        """Test parsing with only --template argument."""
        with patch('sys.argv', ['main.py', '--template', 'example.template']):
            args = parse_arguments()
            self.assertEqual(args.template, 'example.template')
            self.assertIsNone(args.save)
    
    def test_parse_arguments_both_args(self):
        """Test parsing with both --template and --save arguments."""
        with patch('sys.argv', ['main.py', '--template', 'test.template', '--save', 'test.save']):
            args = parse_arguments()
            self.assertEqual(args.template, 'test.template')
            self.assertEqual(args.save, 'test.save')
    
    def test_parse_arguments_short_forms(self):
        """Test parsing with short form arguments (-t, -s)."""
        with patch('sys.argv', ['main.py', '-t', 'test.template', '-s', 'test.save']):
            args = parse_arguments()
            self.assertEqual(args.template, 'test.template')
            self.assertEqual(args.save, 'test.save')
    
    def test_parse_arguments_help(self):
        """Test --help displays usage information."""
        with patch('sys.argv', ['main.py', '--help']):
            with self.assertRaises(SystemExit) as cm:
                with patch('sys.stdout'):  # Suppress help output
                    parse_arguments()
            # argparse exits with 0 for help
            self.assertEqual(cm.exception.code, 0)


class TestMainFunction(unittest.TestCase):
    """Test main() function behavior."""
    
    @patch('main.InteractiveShell')
    @patch('sys.argv', ['main.py'])
    def test_main_no_arguments(self, mock_shell_class):
        """Test main() with no arguments calls start()."""
        mock_shell = Mock()
        mock_shell_class.return_value = mock_shell
        
        main()
        
        mock_shell_class.assert_called_once()
        mock_shell.start.assert_called_once()
        mock_shell.quick_launch.assert_not_called()
    
    @patch('main.InteractiveShell')
    @patch('sys.argv', ['main.py', '--template', 'test.template'])
    def test_main_with_template_only(self, mock_shell_class):
        """Test main() with template only calls quick_launch()."""
        mock_shell = Mock()
        mock_shell_class.return_value = mock_shell
        
        main()
        
        mock_shell_class.assert_called_once()
        mock_shell.quick_launch.assert_called_once_with('test.template', None)
        mock_shell.start.assert_not_called()
    
    @patch('main.InteractiveShell')
    @patch('sys.argv', ['main.py', '--template', 'test.template', '--save', 'test.save'])
    def test_main_with_both_arguments(self, mock_shell_class):
        """Test main() with both arguments calls quick_launch()."""
        mock_shell = Mock()
        mock_shell_class.return_value = mock_shell
        
        main()
        
        mock_shell_class.assert_called_once()
        mock_shell.quick_launch.assert_called_once_with('test.template', 'test.save')
        mock_shell.start.assert_not_called()
    
    @patch('main.InteractiveShell')
    @patch('sys.argv', ['main.py'])
    @patch('sys.exit')
    def test_main_handles_exceptions(self, mock_exit, mock_shell_class):
        """Test main() handles exceptions gracefully."""
        mock_shell_class.side_effect = Exception("Shell initialization failed")
        
        with patch('builtins.print'):  # Suppress error output
            main()
        
        mock_exit.assert_called_once_with(1)
    
    @patch('main.InteractiveShell')
    @patch('sys.argv', ['main.py'])
    @patch('sys.exit')
    def test_main_handles_keyboard_interrupt(self, mock_exit, mock_shell_class):
        """Test main() handles KeyboardInterrupt gracefully."""
        mock_shell = Mock()
        mock_shell.start.side_effect = KeyboardInterrupt()
        mock_shell_class.return_value = mock_shell
        
        with patch('builtins.print'):  # Suppress output
            main()
        
        mock_exit.assert_called_once_with(0)


if __name__ == '__main__':
    unittest.main()