"""
Unit Tests for Save File Manager Module

Comprehensive test suite for save_file_manager.py covering:
- SaveFileData serialization/deserialization
- SaveFileManager load/save operations
- Variable merging with hierarchy
- Error handling and edge cases
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from save_file_manager import (
    SaveFileManager, SaveFileData, SaveFileNotFoundError, 
    SaveFileFormatError, SaveFileSaveError, load_save_file, load_variables_for_template
)
from configuration import SAVES_DIR


class TestSaveFileData(unittest.TestCase):
    """Test SaveFileData dataclass."""
    
    def test_from_configparser_deserialization(self):
        """Test deserialization from ConfigParser."""
        import configparser
        config = configparser.ConfigParser(allow_no_value=True)
        config['general'] = {'company': 'Test Corp', 'debug': 'true'}
        config['example.template'] = {'client': 'Acme', 'debug': 'false'}

        data = SaveFileData.from_configparser(config, '/test')
        
        self.assertEqual(data.path, '/test')
        self.assertEqual(data.general_variables, {'company': 'Test Corp', 'debug': True})
        self.assertEqual(data.template_sections['example.template'], 
                        {'client': 'Acme', 'debug': False})
    
    def test_to_configparser_serialization(self):
        """Test serialization to ConfigParser round-trip."""
        data = SaveFileData(
            '/test',
            general_variables={'company': 'Test Corp'},
            template_sections={'test.template': {'client': 'Acme'}}
        )
        
        config = data.to_configparser()
        self.assertIn('general', config.sections())
        self.assertIn('test.template', config.sections())
        self.assertEqual(dict(config['general']), {'company': 'Test Corp'})
    
    def test_get_variables_for_template_general_only(self):
        """Test template with only general variables."""
        data = SaveFileData('/test',
                           general_variables={'company': 'Test Corp'})
        result = data.get_variables_for_template('missing.template')
        self.assertEqual(result, {'company': 'Test Corp'})
    
    def test_get_variables_for_template_specific_only(self):
        """Test template with only specific variables."""
        data = SaveFileData('/test',
                           template_sections={'test.template': {'client': 'Acme'}})
        result = data.get_variables_for_template('test.template')
        self.assertEqual(result, {'client': 'Acme'})
    
    def test_get_variables_for_template_override(self):
        """Test template-specific overrides general."""
        data = SaveFileData('/test',
                           general_variables={'debug': True},
                           template_sections={'test.template': {'debug': False}})
        result = data.get_variables_for_template('test.template')
        self.assertEqual(result['debug'], False)  # Template overrides general
    
    def test_type_coercion(self):
        """Test INI value type coercion including all boolean forms."""
        values = {
            # Boolean - all forms
            'true1': 'true', 'true2': 'True', 'true3': 'TRUE',
            'yes1': 'yes', 'yes2': 'Yes', 'yes3': 'YES',
            'on1': 'on', 'on2': 'On', 'on3': 'ON',
            'one': '1',
            'false1': 'false', 'false2': 'False', 'false3': 'FALSE',
            'no1': 'no', 'no2': 'No', 'no3': 'NO',
            'off1': 'off', 'off2': 'Off', 'off3': 'OFF',
            'zero': '0',
            # Numbers
            'int_pos': '42', 'int_neg': '-5',
            'float': '3.14',
            # String
            'string': 'hello world'
        }
        coerced = SaveFileData._parse_values(values)
        
        # Verify booleans
        self.assertEqual(coerced['true1'], True)
        self.assertEqual(coerced['yes1'], True)
        self.assertEqual(coerced['on1'], True)
        self.assertEqual(coerced['one'], True)
        self.assertEqual(coerced['false1'], False)
        self.assertEqual(coerced['no1'], False)
        self.assertEqual(coerced['off1'], False)
        self.assertEqual(coerced['zero'], False)
        
        # Verify numbers/strings
        self.assertEqual(coerced['int_pos'], 42)
        self.assertEqual(coerced['float'], 3.14)
        self.assertEqual(coerced['string'], 'hello world')

    def test_parse_python_literals(self):
        """Test parsing of Python literals (lists, dicts, tuples, sets)."""
        values = {
            # List parsing
            'simple_list': "['item1', 'item2', 'item3']",
            'mixed_list': "[1, 'two', 3.0, True]",
            'empty_list': '[]',
            'nested_list': "[['a', 'b'], ['c', 'd']]",

            # Dict parsing
            'simple_dict': "{'key1': 'value1', 'key2': 'value2'}",
            'mixed_dict': "{'name': 'John', 'age': 30, 'active': True}",
            'empty_dict': '{}',
            'nested_dict': "{'outer': {'inner': 'value'}}",

            # Tuple parsing
            'simple_tuple': '(1, 2, 3)',
            'single_element_tuple': '(42,)',

            # Set parsing
            'simple_set': '{1, 2, 3}',

            # Whitespace handling
            'list_with_spaces': "  ['a', 'b']  ",

            # Fallback behavior (malformed literals)
            'unclosed_bracket': "['incomplete'",
            'non_literal_code': '[x for x in range(5)]',
        }
        coerced = SaveFileData._parse_values(values)

        # Verify list parsing
        self.assertIsInstance(coerced['simple_list'], list)
        self.assertEqual(len(coerced['simple_list']), 3)
        self.assertEqual(coerced['simple_list'][0], 'item1')
        self.assertEqual(coerced['simple_list'][1], 'item2')
        self.assertEqual(coerced['simple_list'][2], 'item3')

        self.assertIsInstance(coerced['mixed_list'], list)
        self.assertEqual(coerced['mixed_list'], [1, 'two', 3.0, True])

        self.assertIsInstance(coerced['empty_list'], list)
        self.assertEqual(len(coerced['empty_list']), 0)

        self.assertIsInstance(coerced['nested_list'], list)
        self.assertEqual(coerced['nested_list'], [['a', 'b'], ['c', 'd']])

        # Verify dict parsing
        self.assertIsInstance(coerced['simple_dict'], dict)
        self.assertEqual(coerced['simple_dict']['key1'], 'value1')
        self.assertEqual(coerced['simple_dict']['key2'], 'value2')

        self.assertIsInstance(coerced['mixed_dict'], dict)
        self.assertEqual(coerced['mixed_dict']['name'], 'John')
        self.assertEqual(coerced['mixed_dict']['age'], 30)
        self.assertEqual(coerced['mixed_dict']['active'], True)

        self.assertIsInstance(coerced['empty_dict'], dict)
        self.assertEqual(len(coerced['empty_dict']), 0)

        self.assertIsInstance(coerced['nested_dict'], dict)
        self.assertEqual(coerced['nested_dict']['outer']['inner'], 'value')

        # Verify tuple parsing
        self.assertIsInstance(coerced['simple_tuple'], tuple)
        self.assertEqual(coerced['simple_tuple'], (1, 2, 3))

        self.assertIsInstance(coerced['single_element_tuple'], tuple)
        self.assertEqual(coerced['single_element_tuple'], (42,))

        # Verify set parsing
        self.assertIsInstance(coerced['simple_set'], set)
        self.assertEqual(coerced['simple_set'], {1, 2, 3})

        # Verify whitespace handling
        self.assertIsInstance(coerced['list_with_spaces'], list)
        self.assertEqual(coerced['list_with_spaces'], ['a', 'b'])

        # Verify fallback behavior (malformed literals should be strings)
        self.assertIsInstance(coerced['unclosed_bracket'], str)
        self.assertEqual(coerced['unclosed_bracket'], "['incomplete'")

        self.assertIsInstance(coerced['non_literal_code'], str)
        self.assertEqual(coerced['non_literal_code'], '[x for x in range(5)]')

    def test_parse_literals_integration(self):
        """Test end-to-end parsing of Python literals in save files."""
        import configparser

        # Create a config with Python literals
        config = configparser.ConfigParser(allow_no_value=True)
        config['general'] = {
            'project_list': "['Project Alpha', 'Project Beta']",
            'config_dict': "{'debug': True, 'port': 8080}",
            'coordinates': '(10, 20, 30)'
        }

        data = SaveFileData.from_configparser(config, '/test')

        # Verify project_list is a Python list (not a string)
        project_list = data.general_variables['project_list']
        self.assertIsInstance(project_list, list)
        self.assertEqual(len(project_list), 2)
        self.assertEqual(project_list[0], 'Project Alpha')
        self.assertEqual(project_list[1], 'Project Beta')

        # Verify we can iterate over the list correctly
        projects = []
        for project in project_list:
            projects.append(project)
        self.assertEqual(projects, ['Project Alpha', 'Project Beta'])

        # Verify config_dict is a Python dict (not a string)
        config_dict = data.general_variables['config_dict']
        self.assertIsInstance(config_dict, dict)
        self.assertEqual(config_dict['debug'], True)
        self.assertEqual(config_dict['port'], 8080)

        # Verify coordinates is a Python tuple (not a string)
        coordinates = data.general_variables['coordinates']
        self.assertIsInstance(coordinates, tuple)
        self.assertEqual(coordinates, (10, 20, 30))


class TestSaveFileManager(unittest.TestCase):
    """Test SaveFileManager functionality."""
    
    def setUp(self):
        """Create temporary saves directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.saves_dir = os.path.join(self.temp_dir, 'saves')
        os.mkdir(self.saves_dir)
        os.environ['TEMPLATE_ASSISTANT_SAVES'] = self.saves_dir
    
    def tearDown(self):
        """Cleanup temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_manager(self) -> SaveFileManager:
        return SaveFileManager(self.saves_dir)
    
    def test_load_valid_save_file(self):
        """Test loading valid save file (extensionless format)."""
        # Create test save file
        test_path = os.path.join(self.saves_dir, 'test')
        content = """[general]
company = Test Corp
debug = true

[test.template]
client = Acme
debug = false
"""
        with open(test_path, 'w') as f:
            f.write(content)

        manager = self._create_test_manager()
        data = manager.load('test')

        self.assertEqual(data.general_variables['company'], 'Test Corp')
        self.assertEqual(data.template_sections['test.template']['client'], 'Acme')
    
    def test_load_missing_file(self):
        """Test missing file raises SaveFileNotFoundError."""
        manager = self._create_test_manager()
        with self.assertRaises(SaveFileNotFoundError):
            manager.load('missing')
    
    def test_load_invalid_ini(self):
        """Test invalid INI raises SaveFileFormatError."""
        test_path = os.path.join(self.saves_dir, 'invalid')
        with open(test_path, 'w') as f:
            f.write("[invalid\nmissing = value")

        manager = self._create_test_manager()
        with self.assertRaises(SaveFileFormatError):
            manager.load('invalid')
    
    def test_save_new_file(self):
        """Test saving to new file."""
        manager = self._create_test_manager()
        data = SaveFileData(
            os.path.join(self.saves_dir, 'new'),
            general_variables={'test': 'value'}
        )
        manager.save('new', data)

        self.assertTrue(os.path.exists(os.path.join(self.saves_dir, 'new')))
    
    def test_save_subdirectories(self):
        """Test saving with subdirectories."""
        manager = self._create_test_manager()
        data = SaveFileData(os.path.join(self.saves_dir, 'projects/test'))
        manager.save('projects/test', data)

        self.assertTrue(os.path.exists(os.path.join(self.saves_dir, 'projects', 'test')))
    
    def test_save_variables_general(self):
        """Test saving to general section."""
        manager = self._create_test_manager()
        manager.save_variables('test', {'company': 'Acme'})

        data = manager.load('test')
        self.assertEqual(data.general_variables['company'], 'Acme')
    
    def test_save_variables_template_specific(self):
        """Test saving to template-specific section."""
        manager = self._create_test_manager()
        manager.save_variables('test', {'client': 'Acme'}, 'test.template')

        data = manager.load('test')
        self.assertEqual(data.template_sections['test.template']['client'], 'Acme')
    
    def test_save_variables_merge_existing(self):
        """Test saving merges with existing file."""
        manager = self._create_test_manager()

        # Initial save
        manager.save_variables('merge', {'first': 'value1'})

        # Update with new variables
        manager.save_variables('merge', {'second': 'value2'})

        data = manager.load('merge')
        self.assertEqual(data.general_variables, {'first': 'value1', 'second': 'value2'})
    
    def test_load_variables_for_template(self):
        """Test loading merged variables for template."""
        test_path = os.path.join(self.saves_dir, 'test')
        content = """[general]
debug = true
company = General Corp

[test.template]
client = Acme Corp
debug = false
"""
        with open(test_path, 'w') as f:
            f.write(content)

        manager = self._create_test_manager()
        result = manager.load_variables_for_template('test', 'test.template')

        self.assertEqual(result['company'], 'General Corp')  # General
        self.assertEqual(result['client'], 'Acme Corp')     # Template-specific
        self.assertEqual(result['debug'], False)            # Template overrides general
    
    def test_get_template_sections(self):
        """Test getting list of template sections."""
        manager = self._create_test_manager()
        manager.save_variables('sections', {}, 'reports/daily.template')
        manager.save_variables('sections', {}, 'common/header.template')

        sections = manager.get_template_sections('sections')
        self.assertIn('reports/daily.template', sections)
        self.assertIn('common/header.template', sections)
    
    def test_convenience_functions(self):
        """Test module-level convenience functions (extensionless format)."""
        manager = self._create_test_manager()

        # load_save_file
        manager.save_variables('conv', {'test': 'value'})
        data = load_save_file('conv', self.saves_dir)
        self.assertEqual(data.general_variables['test'], 'value')

        # load_variables_for_template
        result = load_variables_for_template('conv', 'test.template', self.saves_dir)
        self.assertEqual(result['test'], 'value')

    def test_load_with_explicit_extension(self):
        """Test loading files with .save extension when explicitly specified."""
        manager = self._create_test_manager()

        # Create a save file with .save extension
        legacy_path = os.path.join(self.saves_dir, 'legacy.save')
        content = """[general]
company = Legacy Corp
"""
        with open(legacy_path, 'w') as f:
            f.write(content)

        # Load with explicit .save extension
        data = manager.load('legacy.save')
        self.assertEqual(data.general_variables['company'], 'Legacy Corp')

    def test_save_with_any_extension(self):
        """Test that files can be saved with various extensions."""
        manager = self._create_test_manager()

        # Test saving with different extensions
        extensions = ['.save', '.config', '.data', '.txt', '']
        for ext in extensions:
            filename = f'test{ext}'
            manager.save_variables(filename, {'extension': ext})

            # Verify file exists with exact name
            file_path = os.path.join(self.saves_dir, filename)
            self.assertTrue(os.path.exists(file_path), f"File {filename} should exist")

            # Verify content
            data = manager.load(filename)
            self.assertEqual(data.general_variables['extension'], ext)

    def test_error_message_shows_exact_path(self):
        """Test that error message shows only the exact path that was attempted."""
        manager = self._create_test_manager()

        # Try to load non-existent file
        with self.assertRaises(SaveFileNotFoundError) as cm:
            manager.load('nonexistent')

        # Error message should show only the exact path attempted
        error_msg = str(cm.exception)
        self.assertIn('nonexistent', error_msg)
        self.assertNotIn('tried:', error_msg)

    def test_load_save_with_various_extensions(self):
        """Test comprehensive saving and loading with different extensions."""
        manager = self._create_test_manager()

        # Test different extension scenarios
        test_cases = [
            ('project.save', {'type': 'save'}),
            ('config.json', {'type': 'json'}),
            ('data.txt', {'type': 'text'}),
            ('settings.config', {'type': 'config'}),
            ('extensionless', {'type': 'none'})
        ]

        for filename, variables in test_cases:
            # Save with specific extension
            manager.save_variables(filename, variables)

            # Verify file exists with exact name
            file_path = os.path.join(self.saves_dir, filename)
            self.assertTrue(os.path.exists(file_path), f"File {filename} should exist")

            # Load with exact name and verify content
            data = manager.load(filename)
            self.assertEqual(data.general_variables, variables)

    def test_subdirectory_with_extensions(self):
        """Test that subdirectory paths work correctly with various extensions."""
        manager = self._create_test_manager()

        # Test subdirectories with different extensions
        test_cases = [
            ('projects/client.save', {'client': 'A'}),
            ('projects/client.config', {'client': 'B'}),
            ('configs/database.json', {'db': 'test'}),
            ('data/export', {'export': 'data'})
        ]

        for filepath, variables in test_cases:
            # Save to subdirectory with extension
            manager.save_variables(filepath, variables)

            # Verify file exists with exact path
            file_path = os.path.join(self.saves_dir, filepath)
            self.assertTrue(os.path.exists(file_path), f"File {filepath} should exist")

            # Load with exact path and verify content
            data = manager.load(filepath)
            self.assertEqual(data.general_variables, variables)


if __name__ == '__main__':
    unittest.main()
