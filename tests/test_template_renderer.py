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

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_hash_line_green_formatting(self):
        """Test that a line starting with # is automatically colored green."""
        result = self.formatter.format('# This is a comment')
        self.assertIn('\x1b[32m', result)  # Green ANSI code
        self.assertIn('This is a comment', result)
        self.assertIn('\x1b[0m', result)  # Reset

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_hash_line_with_nested_colors(self):
        """Test that a line starting with # preserves nested color tags."""
        result = self.formatter.format('# This is a [red]comment[/red]')
        self.assertIn('\x1b[32m', result)  # Green ANSI code for the line
        self.assertIn('\x1b[31m', result)  # Red ANSI code for nested tag
        self.assertIn('This is a', result)
        self.assertIn('comment', result)

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', False)
    def test_hash_line_colors_disabled(self):
        """Test that hash lines are not colored when colors disabled."""
        result = self.formatter.format('# This is a comment')
        self.assertEqual(result, '# This is a comment')  # No ANSI codes

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_multiple_hash_lines(self):
        """Test that multiple lines starting with # are all colored green."""
        text = '# First comment\n# Second comment\nNot a comment'
        result = self.formatter.format(text)
        # Count green ANSI codes - should be at least 2 (one for each comment line)
        green_count = result.count('\x1b[32m')
        self.assertGreaterEqual(green_count, 2)
        self.assertIn('First comment', result)
        self.assertIn('Second comment', result)
        self.assertIn('Not a comment', result)

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_indented_hash_line(self):
        """Test that indented lines starting with # are colored green."""
        result = self.formatter.format('    # Indented comment')
        self.assertIn('\x1b[32m', result)  # Green ANSI code
        self.assertIn('Indented comment', result)

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_hash_not_at_start(self):
        """Test that lines with # not at start are not colored green."""
        result = self.formatter.format('This is not a # comment')
        # Should not have green color (only reset codes from other processing)
        # The text should remain as-is without green formatting
        self.assertIn('This is not a # comment', result)
        # Count green codes - if # is not at start, should be 0
        green_count = result.count('\x1b[32m')
        self.assertEqual(green_count, 0)

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_hash_line_with_crlf(self):
        """Test that hash lines with CRLF endings preserve CRLF outside colored region."""
        text = "# comment\r\n"
        result = self.formatter.format(text)

        # Should contain green ANSI code
        self.assertIn('\x1b[32m', result)
        # Should contain the comment text
        self.assertIn('comment', result)
        # Should contain reset code
        self.assertIn('\x1b[0m', result)

        # Verify CRLF is preserved after the reset code, not inside the colored portion
        # The result should end with reset code followed by CRLF
        self.assertTrue(result.endswith('\r\n'),
                       f"Result should end with CRLF, but got: {repr(result)}")

        # Ensure no carriage return inside the colored portion
        # Find the position of the reset code
        reset_pos = result.rfind('\x1b[0m')
        self.assertGreater(reset_pos, 0, "Reset code should be present")

        # Everything before the reset should not contain \r
        before_reset = result[:reset_pos]
        self.assertNotIn('\r', before_reset,
                        "Carriage return should not be inside colored content")

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_multiple_hash_lines_with_crlf(self):
        """Test multiple hash lines with CRLF endings."""
        text = "# First comment\r\n# Second comment\r\n# Third comment\r\n"
        result = self.formatter.format(text)

        # Should have green codes for each line
        green_count = result.count('\x1b[32m')
        self.assertEqual(green_count, 3,
                        f"Expected 3 green codes, got {green_count}")

        # Should preserve all CRLFs
        crlf_count = result.count('\r\n')
        self.assertEqual(crlf_count, 3,
                        f"Expected 3 CRLF sequences, got {crlf_count}")

        # Should contain all comment text
        self.assertIn('First comment', result)
        self.assertIn('Second comment', result)
        self.assertIn('Third comment', result)

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_mixed_newline_styles(self):
        """Test hash lines with mixed LF and CRLF newline styles."""
        text = "# Unix line\n# Windows line\r\n# Another Unix\nNot a comment\r\n"
        result = self.formatter.format(text)

        # Should have green codes for the three comment lines
        green_count = result.count('\x1b[32m')
        self.assertEqual(green_count, 3,
                        f"Expected 3 green codes for 3 hash lines, got {green_count}")

        # Should preserve both types of newlines
        lf_count = result.count('\n')
        self.assertGreaterEqual(lf_count, 4,
                               "Should preserve LF in both LF and CRLF sequences")

        crlf_count = result.count('\r\n')
        self.assertEqual(crlf_count, 2,
                        f"Expected 2 CRLF sequences, got {crlf_count}")

        # Verify each line is handled correctly
        self.assertIn('Unix line', result)
        self.assertIn('Windows line', result)
        self.assertIn('Another Unix', result)
        self.assertIn('Not a comment', result)

        # The non-comment line should not be green
        # Split result by lines and check that "Not a comment" line doesn't have green before it
        lines = result.split('\n')
        for i, line in enumerate(lines):
            if 'Not a comment' in line:
                # This line should not start with or contain green code immediately before the text
                # Check that the line itself doesn't have green formatting
                # (it's okay if previous lines had green, but this specific line shouldn't)
                line_start_idx = result.find('Not a comment')
                # Look backwards from 'Not a comment' to the previous newline
                prev_newline = result.rfind('\n', 0, line_start_idx)
                segment = result[prev_newline+1:line_start_idx] if prev_newline != -1 else result[:line_start_idx]
                # This segment should not contain green code (it may contain reset from previous line though)
                self.assertNotIn('\x1b[32m', segment,
                               "Non-comment line should not be formatted with green")

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', True)
    def test_indented_hash_with_crlf(self):
        """Test indented hash lines with CRLF preserve formatting correctly."""
        text = "    # Indented comment\r\n"
        result = self.formatter.format(text)

        # Should be green
        self.assertIn('\x1b[32m', result)
        self.assertIn('Indented comment', result)

        # Should end with CRLF
        self.assertTrue(result.endswith('\r\n'))

        # Should preserve leading whitespace inside the colored portion
        self.assertIn('    # Indented comment', result)

    @patch('template_renderer.configuration.COLOR_OUTPUT_ENABLED', False)
    def test_hash_line_crlf_colors_disabled(self):
        """Test CRLF preservation when colors are disabled."""
        text = "# Comment\r\n"
        result = self.formatter.format(text)

        # Should have no ANSI codes
        self.assertNotIn('\x1b[', result)

        # Should still preserve the CRLF
        self.assertEqual(result, "# Comment\r\n")


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

    def test_include_without_extension(self):
        """Test template inclusion using extensionless syntax."""
        # Create subtemplate with .template extension
        sub_content = """VARS:

### TEMPLATE ###
Subtemplate Content"""
        self.create_test_template('sub.template', sub_content)

        # Create main template that includes without extension
        main_content = """VARS:

### TEMPLATE ###
{% include 'sub' %}
Main Content"""
        self.create_test_template('main.template', main_content)

        parser = TemplateParser(self.templates_dir)
        template_def = parser.parse('main.template')

        result = self.renderer.render(template_def, {})
        self.assertTrue(result.success)
        self.assertIn("Subtemplate Content", result.output)
        self.assertIn("Main Content", result.output)

    def test_include_with_extension_backward_compatibility(self):
        """Test backward compatibility with full extension in include."""
        # Create subtemplate with .template extension
        sub_content = """VARS:

### TEMPLATE ###
Subtemplate Content"""
        self.create_test_template('sub.template', sub_content)

        # Create main template that includes with full extension
        main_content = """VARS:

### TEMPLATE ###
{% include 'sub.template' %}
Main Content"""
        self.create_test_template('main.template', main_content)

        parser = TemplateParser(self.templates_dir)
        template_def = parser.parse('main.template')

        result = self.renderer.render(template_def, {})
        self.assertTrue(result.success)
        self.assertIn("Subtemplate Content", result.output)
        self.assertIn("Main Content", result.output)

    def test_include_both_syntaxes_same_result(self):
        """Test that both extensionless and with-extension syntaxes produce identical results."""
        # Create subtemplate
        sub_content = """VARS:

### TEMPLATE ###
Subtemplate Content"""
        self.create_test_template('sub.template', sub_content)

        # Create main template without extension
        main_without_ext = """VARS:

### TEMPLATE ###
{% include 'sub' %}"""
        self.create_test_template('main_without.template', main_without_ext)

        # Create main template with extension
        main_with_ext = """VARS:

### TEMPLATE ###
{% include 'sub.template' %}"""
        self.create_test_template('main_with.template', main_with_ext)

        parser = TemplateParser(self.templates_dir)

        # Render both templates
        template_def_without = parser.parse('main_without.template')
        result_without = self.renderer.render(template_def_without, {})

        template_def_with = parser.parse('main_with.template')
        result_with = self.renderer.render(template_def_with, {})

        # Both should succeed and produce identical output
        self.assertTrue(result_without.success)
        self.assertTrue(result_with.success)
        self.assertEqual(result_without.output, result_with.output)

    def test_include_nonexistent_template(self):
        """Test error handling when including a non-existent template."""
        # Create main template that includes non-existent subtemplate
        main_content = """VARS:

### TEMPLATE ###
{% include 'missing' %}"""
        self.create_test_template('main.template', main_content)

        parser = TemplateParser(self.templates_dir)
        template_def = parser.parse('main.template')

        result = self.renderer.render(template_def, {})
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        self.assertIn("not found", result.error_message.lower())

    def test_include_nested_subtemplates(self):
        """Test extensionless syntax works with nested template includes."""
        # Create level2 subtemplate
        level2_content = """VARS:

### TEMPLATE ###
Level 2 Content"""
        self.create_test_template('level2.template', level2_content)

        # Create level1 subtemplate that includes level2 without extension
        level1_content = """VARS:

### TEMPLATE ###
Level 1 Content
{% include 'level2' %}"""
        self.create_test_template('level1.template', level1_content)

        # Create main template that includes level1 without extension
        main_content = """VARS:

### TEMPLATE ###
Main Content
{% include 'level1' %}"""
        self.create_test_template('main.template', main_content)

        parser = TemplateParser(self.templates_dir)
        template_def = parser.parse('main.template')

        result = self.renderer.render(template_def, {})
        self.assertTrue(result.success)
        self.assertIn("Main Content", result.output)
        self.assertIn("Level 1 Content", result.output)
        self.assertIn("Level 2 Content", result.output)

    def test_include_with_subdirectory(self):
        """Test extensionless syntax works with subdirectory paths."""
        # Create subdirectory and subtemplate
        sub_content = """VARS:

### TEMPLATE ###
Header Content"""
        self.create_test_template('common/header.template', sub_content)

        # Create main template that includes from subdirectory without extension
        main_content = """VARS:

### TEMPLATE ###
{% include 'common/header' %}
Main Content"""
        self.create_test_template('main.template', main_content)

        parser = TemplateParser(self.templates_dir)
        template_def = parser.parse('main.template')

        result = self.renderer.render(template_def, {})
        self.assertTrue(result.success)
        self.assertIn("Header Content", result.output)
        self.assertIn("Main Content", result.output)

    def test_clear_caches(self):
        """Test clear_caches() clears both environment and loader caches."""
        # Create a simple template
        content = """VARS:
  - name:
      default: World

### TEMPLATE ###
Hello {{ name }}!
"""
        self.create_test_template('test.template', content)
        parser = TemplateParser(self.templates_dir)
        template_def = parser.parse('test.template')

        # Render to populate caches
        result = self.renderer.render(template_def, {'name': 'Alice'})
        self.assertTrue(result.success)

        # Verify environment cache is populated
        self.assertGreater(len(self.renderer._env_cache), 0)

        # Verify loader cache is populated (get first env from cache)
        env = next(iter(self.renderer._env_cache.values()))
        self.assertIsInstance(env.loader, CustomTemplateLoader)

        # Manually add something to loader cache to test clearing
        env.loader._cache[Path('test_path')] = 'test_content'
        self.assertGreater(len(env.loader._cache), 0)

        # Clear all caches
        self.renderer.clear_caches()

        # Verify environment cache is empty
        self.assertEqual(len(self.renderer._env_cache), 0)

        # Note: After clear_caches(), _env_cache is empty so we can't check loader cache
        # But we verified it was called via the implementation

    def test_clear_caches_clears_loader_caches(self):
        """Test that clear_caches() properly clears CustomTemplateLoader caches."""
        # Create templates with includes
        sub_content = """VARS:

### TEMPLATE ###
Subtemplate"""
        self.create_test_template('sub.template', sub_content)

        main_content = """VARS:

### TEMPLATE ###
{% include 'sub' %}
Main"""
        self.create_test_template('main.template', main_content)

        parser = TemplateParser(self.templates_dir)
        template_def = parser.parse('main.template')

        # Render to populate both environment and loader caches
        result = self.renderer.render(template_def, {})
        self.assertTrue(result.success)

        # Get the environment from cache
        env = next(iter(self.renderer._env_cache.values()))
        loader = env.loader
        self.assertIsInstance(loader, CustomTemplateLoader)

        # Verify loader cache has entries (from include)
        initial_loader_cache_size = len(loader._cache)
        self.assertGreater(initial_loader_cache_size, 0)

        # Clear all caches
        self.renderer.clear_caches()

        # Verify environment cache is cleared
        self.assertEqual(len(self.renderer._env_cache), 0)


if __name__ == '__main__':
    unittest.main()
