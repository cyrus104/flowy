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
        
        data = SaveFileData.from_configparser(config, '/test.save')
        
        self.assertEqual(data.path, '/test.save')
        self.assertEqual(data.general_variables, {'company': 'Test Corp', 'debug': True})
        self.assertEqual(data.template_sections['example.template'], 
                        {'client': 'Acme', 'debug': False})
    
    def test_to_configparser_serialization(self):
        """Test serialization to ConfigParser round-trip."""
        data = SaveFileData(
            '/test.save',
            general_variables={'company': 'Test Corp'},
            template_sections={'test.template': {'client': 'Acme'}}
        )
        
        config = data.to_configparser()
        self.assertIn('general', config.sections())
        self.assertIn('test.template', config.sections())
        self.assertEqual(dict(config['general']), {'company': 'Test Corp'})
    
    def test_get_variables_for_template_general_only(self):
        """Test template with only general variables."""
        data = SaveFileData('/test.save', 
                           general_variables={'company': 'Test Corp'})
        result = data.get_variables_for_template('missing.template')
        self.assertEqual(result, {'company': 'Test Corp'})
    
    def test_get_variables_for_template_specific_only(self):
        """Test template with only specific variables."""
        data = SaveFileData('/test.save',
                           template_sections={'test.template': {'client': 'Acme'}})
        result = data.get_variables_for_template('test.template')
        self.assertEqual(result, {'client': 'Acme'})
    
    def test_get_variables_for_template_override(self):
        """Test template-specific overrides general."""
        data = SaveFileData('/test.save',
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
        """Test loading valid save file."""
        # Create test save file (extensionless)
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
        """Test module-level convenience functions."""
        manager = self._create_test_manager()

        # load_save_file
        manager.save_variables('conv', {'test': 'value'})
        data = load_save_file('conv', self.saves_dir)
        self.assertEqual(data.general_variables['test'], 'value')

        # load_variables_for_template
        result = load_variables_for_template('conv', 'test.template', self.saves_dir)
        self.assertEqual(result['test'], 'value')


if __name__ == '__main__':
    unittest.main()
