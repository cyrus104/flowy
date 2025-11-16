"""
Unit Tests for Module Loader System

Comprehensive test suite for module_loader.py covering all loading scenarios.
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

from module_loader import (
    ModuleLoader, ModuleProxy, ModuleLoaderError, 
    ModuleNotFoundError, ModuleImportError,
    load_modules_for_jinja
)
from configuration import MODULES_DIR


class TestModuleLoader(unittest.TestCase):
    """Test module loader functionality."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.modules_dir = Path(self.temp_dir) / 'modules'
        self.modules_dir.mkdir()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def create_test_module(self, name: str, content: str) -> Path:
        """Create test module file."""
        path = self.modules_dir / f"{name}.py"
        path.write_text(content, encoding='utf-8')
        return path
    
    def test_discover_modules(self):
        """Test module discovery."""
        self.create_test_module('utils', 'def test(): pass')
        self.create_test_module('helpers', 'def test(): pass')
        
        loader = ModuleLoader(str(self.modules_dir))
        self.assertEqual(sorted(loader.get_module_names()), ['helpers', 'utils'])
    
    def test_load_simple_module(self):
        """Test loading simple module."""
        content = """
def format_date(date):
    return f"Formatted: {{date}}"

def test_func():
    return "success"
"""
        self.create_test_module('utils', content)
        
        loader = ModuleLoader(str(self.modules_dir))
        module = loader.load_module('utils')
        
        self.assertIn('format_date', module.__dict__)
        self.assertIn('test_func', module.__dict__)
        self.assertEqual(module.test_func(), 'success')
    
    def test_lazy_loading(self):
        """Test ModuleProxy lazy loading."""
        content = 'def test(): return "loaded"'
        self.create_test_module('lazy', content)
        
        loader = ModuleLoader(str(self.modules_dir))
        proxy = ModuleProxy(loader, 'lazy')
        
        # Verify not loaded yet
        self.assertIsNone(proxy._module)
        
        # Access triggers loading
        result = proxy.test()
        self.assertEqual(result, 'loaded')
        self.assertIsNotNone(proxy._module)
    
    def test_module_caching(self):
        """Test module caching."""
        content = 'value = 42'
        self.create_test_module('cached', content)
        
        loader = ModuleLoader(str(self.modules_dir))
        module1 = loader.load_module('cached')
        module2 = loader.load_module('cached')
        
        self.assertIs(module1, module2)  # Same cached instance
        self.assertEqual(module1.value, 42)
    
    def test_module_not_found(self):
        """Test non-existent module handling."""
        loader = ModuleLoader(str(self.modules_dir))
        with self.assertRaises(ModuleNotFoundError):
            loader.load_module('missing')
    
    def test_module_syntax_error(self):
        """Test syntax error handling."""
        self.create_test_module('syntax_error', 'def invalid():  # Missing body')
        
        loader = ModuleLoader(str(self.modules_dir))
        with self.assertRaises(ModuleImportError):
            loader.load_module('syntax_error')
    
    def test_load_modules_for_jinja(self):
        """Test Jinja2 integration convenience function."""
        content = 'def test(): pass'
        self.create_test_module('utils', content)
        self.create_test_module('helpers', content)
        
        modules_dict = load_modules_for_jinja()
        self.assertIn('utils', modules_dict)
        self.assertIn('helpers', modules_dict)
        self.assertIsInstance(modules_dict['utils'], ModuleProxy)
    
    def test_proxy_error_handling(self):
        """Test ModuleProxy error handling."""
        loader = ModuleLoader(str(self.modules_dir))
        proxy = ModuleProxy(loader, 'nonexistent')
        
        # First access triggers error
        with self.assertRaises(ModuleImportError):
            proxy.test()
    
    def test_empty_modules_directory(self):
        """Test empty modules directory."""
        loader = ModuleLoader(str(self.modules_dir))
        self.assertEqual(loader.get_module_names(), [])
        modules_dict = loader.get_modules_dict()
        self.assertEqual(modules_dict, {})
    
    def test_nonexistent_modules_directory(self):
        """Test nonexistent modules directory."""
        bad_dir = self.temp_dir + '/nonexistent'
        with self.assertRaises(ModuleNotFoundError):
            ModuleLoader(bad_dir)
    
    def test_multiple_modules_integration(self):
        """Test loading multiple modules works together."""
        utils_content = """
def format_date(date):
    return f"{{date}} formatted"
"""
        helpers_content = """
def calculate_total(items):
    return sum(float(i) for i in items)
"""
        
        self.create_test_module('utils', utils_content)
        self.create_test_module('helpers', helpers_content)
        
        loader = ModuleLoader(str(self.modules_dir))
        modules_dict = loader.get_modules_dict()
        
        self.assertIn('utils', modules_dict)
        self.assertIn('helpers', modules_dict)
        
        # Verify proxies work
        utils = modules_dict['utils']
        helpers = modules_dict['helpers']
        
        self.assertEqual(utils.format_date('2024-01-01'), '2024-01-01 formatted')
        self.assertEqual(helpers.calculate_total([10, 20, 30]), 60.0)


if __name__ == '__main__':
    unittest.main()
