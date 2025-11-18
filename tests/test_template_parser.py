"""
Unit Tests for Template Parser Module

Comprehensive test suite for the template_parser module, covering:
- Valid template parsing
- Variable definition parsing
- Error handling
- Edge cases
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from template_parser import (
    TemplateParser,
    TemplateDefinition,
    VariableDefinition,
    TemplateNotFoundError,
    TemplateFormatError,
    VariableDefinitionError,
    parse_template
)


class TestTemplateParser(unittest.TestCase):
    """Test suite for the TemplateParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test templates
        self.temp_dir = tempfile.mkdtemp()
        self.parser = TemplateParser(self.temp_dir)
        
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def create_temp_template(self, content: str, filename: str = "test.template") -> str:
        """
        Create a temporary template file with given content.
        
        Args:
            content: Template file content
            filename: Name of the template file
            
        Returns:
            Path to the created template file
        """
        template_path = os.path.join(self.temp_dir, filename)
        # Ensure subdirectories exist if filename contains path
        os.makedirs(os.path.dirname(template_path), exist_ok=True)
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return filename
    
    def create_valid_template(self) -> str:
        """Return content for a valid template with VARS and TEMPLATE sections."""
        return """VARS:
  - client_name:
      description: Name of the client organization
  - report_type:
      description: Type of report to generate
      default: weekly
      options: ['daily', 'weekly', 'monthly']
  - include_charts:
      description: Include visualization charts
      default: true
      options: [true, false]

### TEMPLATE ###

Client Report for {{ client_name }}
Report Type: {{ report_type }}
Include Charts: {{ include_charts }}
"""
    
    def create_minimal_template(self) -> str:
        """Return content for a template with empty VARS section."""
        return """VARS:

### TEMPLATE ###

This is a simple template with no variables.
"""
    
    # ========================================================================
    # Test Valid Template Parsing
    # ========================================================================
    
    def test_parse_valid_template_with_all_fields(self):
        """Test parsing a template with variables that have all fields."""
        filename = self.create_temp_template(self.create_valid_template())
        result = self.parser.parse(filename)
        
        # Check TemplateDefinition attributes
        self.assertIsInstance(result, TemplateDefinition)
        self.assertEqual(result.name, "test.template")
        self.assertTrue(result.path.endswith("test.template"))
        self.assertEqual(len(result.variables), 3)
        
        # Check specific variables
        client_var = result.get_variable("client_name")
        self.assertIsNotNone(client_var)
        self.assertEqual(client_var.name, "client_name")
        self.assertEqual(client_var.description, "Name of the client organization")
        self.assertIsNone(client_var.default)
        self.assertIsNone(client_var.options)
        
        report_var = result.get_variable("report_type")
        self.assertIsNotNone(report_var)
        self.assertEqual(report_var.default, "weekly")
        self.assertEqual(report_var.options, ['daily', 'weekly', 'monthly'])
    
    def test_parse_minimal_template(self):
        """Test parsing a template with only variable names and descriptions."""
        content = """VARS:
  - simple_var:
      description: A simple variable
  - another_var:
      description: Another variable

### TEMPLATE ###

Template content here.
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        self.assertEqual(len(result.variables), 2)
        self.assertIn("simple_var", result.variables)
        self.assertIn("another_var", result.variables)
        self.assertIn("Template content here.", result.template_content)
    
    def test_parse_empty_vars_section(self):
        """Test parsing a template with no variables defined."""
        filename = self.create_temp_template(self.create_minimal_template())
        result = self.parser.parse(filename)
        
        self.assertEqual(len(result.variables), 0)
        self.assertIn("This is a simple template with no variables.", result.template_content)
    
    def test_template_without_vars_header(self):
        """Test template without VARS: header - should treat as empty VARS."""
        content = """Some text before template marker

### TEMPLATE ###

Template content without VARS header
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        self.assertEqual(len(result.variables), 0)
        self.assertEqual(result.template_content, "Template content without VARS header")
    
    def test_parse_template_with_subdirectory(self):
        """Test parsing a template in a subdirectory path."""
        content = self.create_valid_template()
        filename = self.create_temp_template(content, "reports/monthly.template")
        result = self.parser.parse(filename)
        
        self.assertEqual(result.name, "monthly.template")
        self.assertTrue(result.path.endswith(os.path.join("reports", "monthly.template")))
    
    def test_duplicate_variable_names_error(self):
        """Test that duplicate variable names raise an error."""
        content = """VARS:
  - client_name:
      description: First definition
  - client_name:
      description: Duplicate definition

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        
        with self.assertRaises(VariableDefinitionError) as context:
            self.parser.parse(filename)
        
        self.assertIn("Duplicate variable definition for 'client_name'", str(context.exception))
        self.assertIn("at line", str(context.exception))
    
    # ========================================================================
    # Test Variable Definition Parsing
    # ========================================================================
    
    def test_variable_with_description_only(self):
        """Test variable with just description field."""
        content = """VARS:
  - test_var:
      description: Test variable description

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        var = result.get_variable("test_var")
        self.assertEqual(var.description, "Test variable description")
        self.assertIsNone(var.default)
        self.assertIsNone(var.options)
    
    def test_variable_with_default_value(self):
        """Test variable with default value of various types."""
        content = """VARS:
  - string_var:
      default: "default string"
  - int_var:
      default: 42
  - bool_var:
      default: true
  - list_var:
      default: ['item1', 'item2']

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        self.assertEqual(result.get_variable("string_var").default, "default string")
        self.assertEqual(result.get_variable("int_var").default, 42)
        self.assertEqual(result.get_variable("bool_var").default, True)
        self.assertEqual(result.get_variable("list_var").default, ['item1', 'item2'])
    
    def test_variable_with_options_list(self):
        """Test variable with options list."""
        content = """VARS:
  - choice_var:
      options: ['option1', 'option2', 'option3']

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        var = result.get_variable("choice_var")
        self.assertEqual(var.options, ['option1', 'option2', 'option3'])
    
    def test_variable_with_all_fields(self):
        """Test variable with description, default, and options."""
        content = """VARS:
  - complete_var:
      description: A complete variable
      default: 'option2'
      options: ['option1', 'option2', 'option3']

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        var = result.get_variable("complete_var")
        self.assertEqual(var.description, "A complete variable")
        self.assertEqual(var.default, 'option2')
        self.assertEqual(var.options, ['option1', 'option2', 'option3'])
    
    # ========================================================================
    # Test Error Handling
    # ========================================================================
    
    def test_template_not_found(self):
        """Verify TemplateNotFoundError raised for missing file."""
        with self.assertRaises(TemplateNotFoundError) as context:
            self.parser.parse("nonexistent.template")
        
        self.assertIn("Template file not found", str(context.exception))
        self.assertIn("nonexistent.template", str(context.exception))
    
    def test_missing_template_marker(self):
        """Verify TemplateFormatError for missing ### TEMPLATE ###."""
        content = """VARS:
  - test_var:
      description: Test variable

This is template content without the marker.
"""
        filename = self.create_temp_template(content)
        
        with self.assertRaises(TemplateFormatError) as context:
            self.parser.parse(filename)
        
        self.assertIn("Missing '### TEMPLATE ###' section marker", str(context.exception))
    
    def test_invalid_yaml_syntax(self):
        """Verify VariableDefinitionError for malformed YAML."""
        content = """VARS:
  - test_var:
      description: Missing closing quote
      default: "unclosed string
  - another_var:

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        
        with self.assertRaises(VariableDefinitionError) as context:
            self.parser.parse(filename)
        
        self.assertIn("YAML syntax error", str(context.exception))
    
    def test_invalid_vars_structure(self):
        """Verify error when VARS is not a list of dicts."""
        content = """VARS:
  test_var: "This should be a list, not a dict"

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        
        with self.assertRaises(VariableDefinitionError) as context:
            self.parser.parse(filename)
        
        self.assertIn("Expected a list", str(context.exception))
    
    def test_multiple_keys_in_variable(self):
        """Verify error when variable dict has multiple top-level keys."""
        content = """VARS:
  - var1: {}
    var2: {}

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        
        with self.assertRaises(VariableDefinitionError) as context:
            self.parser.parse(filename)
        
        self.assertIn("Expected exactly one variable name", str(context.exception))
    
    def test_invalid_options_type(self):
        """Verify error when options is not a list."""
        content = """VARS:
  - test_var:
      options: "should be a list"

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        
        with self.assertRaises(VariableDefinitionError) as context:
            self.parser.parse(filename)
        
        self.assertIn("Expected list but got str", str(context.exception))
        self.assertIn("at line", str(context.exception))
    
    def test_unknown_keys_validation_error(self):
        """Verify unknown keys error includes line number."""
        content = """VARS:
  - test_var:
      invalid_key: "unknown"
      description: Valid description

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        
        with self.assertRaises(VariableDefinitionError) as context:
            self.parser.parse(filename)
        
        self.assertIn("Unknown keys in variable 'test_var'", str(context.exception))
        self.assertIn("at line", str(context.exception))
    
    def test_invalid_dict_value_validation_error(self):
        """Verify invalid dict value error includes line number."""
        content = """VARS:
  - test_var: "should be dict"

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        
        with self.assertRaises(VariableDefinitionError) as context:
            self.parser.parse(filename)
        
        self.assertIn("Expected dictionary but got str", str(context.exception))
        self.assertIn("at line", str(context.exception))
    
    # ========================================================================
    # Test TemplateDefinition Class
    # ========================================================================
    
    def test_template_definition_attributes(self):
        """Verify all attributes are correctly set."""
        filename = self.create_temp_template(self.create_valid_template())
        result = self.parser.parse(filename)
        
        self.assertIsNotNone(result.path)
        self.assertIsNotNone(result.name)
        self.assertIsNotNone(result.variables)
        self.assertIsNotNone(result.template_content)
        self.assertIsNotNone(result.raw_vars_section)
    
    def test_get_variable_method(self):
        """Test retrieving variables by name."""
        filename = self.create_temp_template(self.create_valid_template())
        result = self.parser.parse(filename)
        
        # Test existing variable
        var = result.get_variable("client_name")
        self.assertIsNotNone(var)
        self.assertEqual(var.name, "client_name")
        
        # Test non-existing variable
        var = result.get_variable("nonexistent")
        self.assertIsNone(var)
    
    def test_variables_dict_structure(self):
        """Verify variables dict maps names to VariableDefinition objects."""
        filename = self.create_temp_template(self.create_valid_template())
        result = self.parser.parse(filename)
        
        for var_name, var_def in result.variables.items():
            self.assertIsInstance(var_def, VariableDefinition)
            self.assertEqual(var_name, var_def.name)
    
    # ========================================================================
    # Test VariableDefinition Class
    # ========================================================================
    
    def test_variable_definition_repr(self):
        """Verify string representation."""
        var = VariableDefinition(
            name="test_var",
            description="Test description",
            default="default_value",
            options=['opt1', 'opt2']
        )
        
        repr_str = repr(var)
        self.assertIn("test_var", repr_str)
        self.assertIn("description", repr_str)
        self.assertIn("default", repr_str)
        self.assertIn("options", repr_str)
    
    def test_variable_definition_optional_fields(self):
        """Verify None values for optional fields."""
        var = VariableDefinition(name="test_var")
        
        self.assertEqual(var.name, "test_var")
        self.assertIsNone(var.description)
        self.assertIsNone(var.default)
        self.assertIsNone(var.options)
    
    # ========================================================================
    # Test Edge Cases
    # ========================================================================
    
    def test_template_marker_case_insensitive(self):
        """Verify marker works with different cases."""
        content = """VARS:
  - test_var:
      description: Test

### template ###

Content
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        self.assertEqual(result.template_content, "Content")
    
    def test_template_marker_with_extra_whitespace(self):
        """Verify marker works with spaces/tabs."""
        content = """VARS:
  - test_var:
      description: Test

###   TEMPLATE   ###

Content
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        self.assertEqual(result.template_content, "Content")
    
    def test_unicode_in_template(self):
        """Verify Unicode characters handled correctly."""
        content = """VARS:
  - test_var:
      description: Variable with émojis 🎉
      default: "Unicode: 你好"

### TEMPLATE ###

Template with Unicode: 你好世界 🌍
Special chars: é à ñ ü
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        var = result.get_variable("test_var")
        self.assertIn("🎉", var.description)
        self.assertEqual(var.default, "Unicode: 你好")
        self.assertIn("🌍", result.template_content)
    
    def test_multiline_variable_values(self):
        """Verify multiline strings in YAML work correctly."""
        content = """VARS:
  - multiline_var:
      description: |
        This is a multiline
        description that spans
        multiple lines.
      default: |
        Default value
        on multiple lines

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        var = result.get_variable("multiline_var")
        self.assertIn("multiline", var.description)
        self.assertIn("multiple lines", var.description)
        self.assertIn("Default value", var.default)
    
    def test_template_with_comment_before_vars(self):
        """Test template with comment lines before VARS: header."""
        content = """# This is a comment before VARS
# Another comment line

VARS:
  - test_var:
      description: Test variable

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        self.assertEqual(len(result.variables), 1)
        var = result.get_variable("test_var")
        self.assertIsNotNone(var)
        self.assertEqual(var.description, "Test variable")
    
    def test_template_with_indented_vars(self):
        """Test template with indented VARS: header."""
        content = """    VARS:
  - indented_var:
      description: Variable with indented VARS header

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        result = self.parser.parse(filename)
        
        self.assertEqual(len(result.variables), 1)
        var = result.get_variable("indented_var")
        self.assertIsNotNone(var)
        self.assertEqual(var.description, "Variable with indented VARS header")
    
    def test_structural_error_line_numbers(self):
        """Test that structural validation errors include line numbers."""
        # Test non-list structure
        content = """VARS:
  test_var: "This should be a list"

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        
        with self.assertRaises(VariableDefinitionError) as context:
            self.parser.parse(filename)
        
        # Check that line number is included in the error
        self.assertIn("at line", str(context.exception))
    
    def test_invalid_item_error_line_numbers(self):
        """Test that invalid item errors include line numbers."""
        content = """VARS:
  - test_var:
      description: First variable
  - "This should be a dict not a string"
  - another_var:
      description: Another variable

### TEMPLATE ###

Content
"""
        filename = self.create_temp_template(content)
        
        with self.assertRaises(VariableDefinitionError) as context:
            self.parser.parse(filename)
        
        # Check that line number is included for the invalid item
        error_str = str(context.exception)
        self.assertIn("at line", error_str)
        self.assertIn("position 2", error_str)  # The string is at position 2
    
    # ========================================================================
    # Test Module-Level Function
    # ========================================================================
    
    def test_parse_template_function(self):
        """Test the module-level parse_template convenience function."""
        filename = self.create_temp_template(self.create_valid_template())
        result = parse_template(filename, self.temp_dir)
        
        self.assertIsInstance(result, TemplateDefinition)
        self.assertEqual(len(result.variables), 3)


if __name__ == '__main__':
    unittest.main()