"""
Unit Tests for Template Renderer Module

Comprehensive test suite for template_renderer.py covering all rendering features.
"""

import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jinja2
from jinja2.exceptions import UndefinedError
from colorama import Fore, Back, Style

from template_renderer import (
    TemplateRenderer, RenderResult, HighlightUndefined, ColorFormatter,
    render_template, CustomTemplateLoader, _local_undefined_vars
)
from template_parser import TemplateParser, TemplateDefinition
from save_file_manager import SaveFileManager
import configuration


class TestHighlightUndefined(unittest.TestCase):
    """Test custom undefined variable handling."""
    
    def setUp(self):
        self.undefined = HighlightUndefined(name="test_var")
    
    def test_str_mark_behavior(self):
        """Test undefined renders as marked variable."""
        with patch('template_renderer.configuration.UNDEFINED_BEHAVIOR', 'mark'):
            with patch('template_renderer.configuration.UNDEFINED_VARIABLE_TEMPLATE', '[red]<<{var}>>[/red]'):
                self.assertEqual(str(self.undefined), '[red]<<test_var>>[/red]')
    
    def test_str_empty_behavior(self):
        """Test undefined renders as empty string."""
        with patch('template_renderer.configuration.UNDEFINED_BEHAVIOR', 'empty'):
            self.assertEqual(str(self.undefined), '')
    
    def test_attribute_chaining(self):
        """Test undefined attribute chaining builds full path."""
        chained = self.undefined.test_attr
        self.assertEqual(chained._undefined_name, 'test_var.test_attr')
        
        further = chained.subattr
        self.assertEqual(further._undefined_name, 'test_var.test_attr.subattr')
        
        # Trigger tracking by converting to string
        str(further)
        
        # Verify tracking
        self.assertIn('test_var.test_attr.subattr', _local_undefined_vars.undefined_vars)
    
    def test_error_behavior(self):
        """Test error behavior raises exception."""
        with patch('template_renderer.configuration.UNDEFINED_BEHAVIOR', 'error'):
            with self.assertRaises(UndefinedError):
                str(self.undefined)


class TestColorFormatter(unittest.TestCase):
    """Test color syntax parsing."""
    
    def setUp(self):
        self.formatter = ColorFormatter()
    
    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_simple_color(self):
        """Test basic [red]text[/red]."""
        result = self.formatter.format('[red]error[/red]')
        self.assertIn('\x1b[31m', result)  # Red ANSI code
        self.assertIn('error', result)
        self.assertIn('\x1b[0m', result)   # Reset
    
    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_bold(self):
        """Test [bold]text[/bold]."""
        result = self.formatter.format('[bold]important[/bold]')
        self.assertIn('\x1b[1m', result)   # Bright/bold
        self.assertIn('important', result)
    
    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_nested_colors(self):
        """Test nested formatting."""
        result = self.formatter.format('[green][bold]success[/bold][/green]')
        self.assertIn('\x1b[32m', result)  # Green
        self.assertIn('\x1b[1m', result)   # Bold
        self.assertIn('success', result)
    
    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_combined_syntax(self):
        """Test [red:bg:yellow]warning[/red:bg:yellow]."""
        result = self.formatter.format('[red:bg:yellow]warning[/red:bg:yellow]')
        self.assertIn('\x1b[31m', result)  # Red foreground
        self.assertIn('\x1b[43m', result)  # Yellow background
    
    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', False)
    def test_colors_disabled(self):
        """Test colors stripped when disabled."""
        result = self.formatter.format('[red]test[/red]')
        self.assertEqual(result, 'test')  # No ANSI codes
    
    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_standalone_bg_enabled(self):
        """Test standalone background color tags."""
        result = self.formatter.format('[bg:blue]bg text[/bg:blue]')
        self.assertIn('\x1b[44m', result)  # Blue background ANSI code
        self.assertIn('bg text', result)
        self.assertIn('\x1b[0m', result)   # Reset
    
    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', False)
    def test_standalone_bg_disabled(self):
        """Test standalone bg tags stripped when disabled."""
        result = self.formatter.format('[bg:blue]bg text[/bg:blue]')
        self.assertEqual(result, 'bg text')  # No tags or ANSI codes
    
    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_nested_bg(self):
        """Test nested foreground and background colors."""
        result = self.formatter.format('[red][bg:blue]inner[/bg:blue][/red]')
        self.assertIn('\x1b[31m', result)  # Red foreground
        self.assertIn('\x1b[44m', result)  # Blue background
        self.assertIn('inner', result)
        # Should have multiple resets for nested structure
        self.assertEqual(result.count('\x1b[0m'), 2)
    
    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_all_colors(self):
        """Test all supported colors including backgrounds."""
        colors = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
        
        # Test foreground colors
        for color in colors:
            result = self.formatter.format(f'[{color}]test[/{color}]')
            self.assertNotEqual(result, f'[{color}]test[/{color}]')  # Changed
        
        # Test background colors
        for color in colors:
            result = self.formatter.format(f'[bg:{color}]test[/bg:{color}]')
            self.assertNotEqual(result, f'[bg:{color}]test[/bg:{color}]')  # Changed
            self.assertIn('test', result)  # Content preserved


class TestRenderResult(unittest.TestCase):
    """Test RenderResult dataclass."""
    
    def test_success_result(self):
        """Test successful rendering result."""
        result = RenderResult(output="test output", success=True, undefined_variables=['var1'])
        self.assertTrue(result.success)
        self.assertEqual(result.undefined_variables, ['var1'])
        self.assertTrue(result.has_undefined())
    
    def test_error_result(self):
        """Test error result creation."""
        result = RenderResult(
            output="", success=False, 
            error_message="Syntax error", error_line=42,
            template_path="test.template"
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_line, 42)
    
    def test_format_error(self):
        """Test error formatting."""
        result = RenderResult(
            success=False,
            error_message="Syntax error",
            error_line=10,
            template_path="test.template"
        )
        formatted = result.format_error()
        self.assertIn("Template: test.template", formatted)
        self.assertIn("Line: 10", formatted)


class TestTemplateRenderer(unittest.TestCase):
    """Test main renderer integration."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.templates_dir = os.path.join(self.temp_dir, 'templates')
        self.saves_dir = os.path.join(self.temp_dir, 'saves')
        os.makedirs(self.templates_dir)
        os.makedirs(self.saves_dir)
        self.renderer = TemplateRenderer(self.templates_dir, self.saves_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def create_test_template(self, filename, content):
        """Helper to create test template."""
        path = os.path.join(self.templates_dir, filename)
        # Create subdirectories if needed
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path
    
    def create_test_save(self, filename, sections):
        """Helper to create test save file."""
        path = os.path.join(self.saves_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        import configparser
        config = configparser.ConfigParser()
        for section, vars in sections.items():
            config[section] = vars
        
        with open(path, 'w', encoding='utf-8') as f:
            config.write(f)
        return path
    
    def test_basic_rendering(self):
        """Test basic template rendering."""
        content = """VARS:
  - name:
      default: World

### TEMPLATE ###
Hello {{ name }}!
"""
        self.create_test_template('test.template', content)
        parser = TemplateParser(self.templates_dir)
        template_def = parser.parse('test.template')
        
        result = self.renderer.render(template_def, {'name': 'Alice'})
        self.assertTrue(result.success)
        self.assertIn("Hello Alice!", result.output)
    
    def test_undefined_variables(self):
        """Test undefined variable handling."""
        content = """VARS:

### TEMPLATE ###
Hello {{ missing_var }}!
"""
        path = self.create_test_template(content)
        parser = TemplateParser(self.temp_dir)
        template_def = parser.parse('test.template')
        
        result = self.renderer.render(template_def, {})
        self.assertTrue(result.success)
        self.assertIn("missing_var", result.undefined_variables)
    
    @patch('configuration.COLOR_OUTPUT_ENABLED', True)
    def test_color_formatting(self):
        """Test color syntax rendering."""
        content = """VARS:

### TEMPLATE ###
[red]Error[/red] [green]Success[/green]
"""
        path = self.create_test_template(content)
        parser = TemplateParser(self.temp_dir)
        template_def = parser.parse('test.template')
        
        result = self.renderer.render(template_def, {})
        self.assertTrue(result.success)
        self.assertIn('\x1b[31m', result.output)  # Red
        self.assertIn('\x1b[32m', result.output)  # Green
    
    def test_error_handling(self):
        """Test Jinja2 syntax error handling."""
        content = """VARS:

### TEMPLATE ###
{% if missing %}
Invalid syntax
"""
        path = self.create_test_template(content)
        parser = TemplateParser(self.temp_dir)
        template_def = parser.parse('test.template')
        
        result = self.renderer.render(template_def, {})
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_line)
        self.assertIsNotNone(result.error_message)


if __name__ == '__main__':
    unittest.main()
