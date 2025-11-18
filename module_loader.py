"""
Module Loader for Template Assistant

Dynamically loads Python modules from MODULES_DIR for use in Jinja2 templates.
Supports lazy loading, error handling, and ModuleProxy for transparent access.

Usage:
    loader = ModuleLoader(configuration.MODULES_DIR)
    modules_dict = loader.load_modules_for_jinja()  # For Jinja2 globals
    utils = loader.get_module('utils')  # Lazy load specific module
"""

import os
import sys
import importlib.util
import importlib
from pathlib import Path
from typing import Dict, Any, Optional
import threading

from configuration import MODULES_DIR


class ModuleLoaderError(Exception):
    """Base exception for module loading errors."""
    pass


class ModuleNotFoundError(ModuleLoaderError):
    """Raised when a module file doesn't exist."""
    pass


class ModuleImportError(ModuleLoaderError):
    """Raised when module import fails (syntax errors, runtime errors)."""
    pass


class ModuleProxy:
    """Proxy that implements lazy loading via __getattr__."""
    
    def __init__(self, loader: 'ModuleLoader', module_name: str):
        self._loader = loader
        self._module_name = module_name
        self._module = None
    
    def __getattr__(self, name: str):
        """Trigger module loading when first attribute accessed."""
        if self._module is None:
            try:
                self._module = self._loader.get_module(self._module_name)
            except ModuleLoaderError as e:
                # Return error object that provides helpful message
                class ErrorAttr:
                    def __init__(self, msg):
                        self._msg = msg
                    
                    def __call__(self, *args, **kwargs):
                        raise ModuleImportError(f"{self._msg} (called with {args}, {kwargs})")
                    
                    def __repr__(self):
                        return f"<ModuleError: {self._msg}>"
                
                setattr(self, name, ErrorAttr(f"Failed to load module '{self._module_name}': {e}"))
                return getattr(self, name)
        
        return getattr(self._module, name)


class ModuleLoader:
    """Dynamically loads Python modules from modules directory."""
    
    def __init__(self, modules_dir: str):
        self.modules_dir = Path(modules_dir).resolve()
        self._cache: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._module_names = []
        
        # Graceful handling of missing/non-directory
        if self.modules_dir.exists() and self.modules_dir.is_dir():
            self._discover_modules()
        else:
            self._module_names = []
    
    def _discover_modules(self) -> None:
        """Scan modules directory for .py files."""
        self._module_names = []
        for path in self.modules_dir.glob("*.py"):
            if path.stem != "__init__":
                self._module_names.append(path.stem)
    
    def _import_module(self, module_name: str) -> Any:
        """Dynamically import a module using importlib."""
        module_path = self.modules_dir / f"{module_name}.py"
        
        if not module_path.exists():
            raise ModuleNotFoundError(f"Module file not found: {module_path}")
        
        # Temporarily add modules dir to path for relative imports
        old_path = sys.path.copy()
        sys.path.insert(0, str(self.modules_dir))
        
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None:
                raise ModuleImportError(f"Could not create spec for {module_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # This can raise SyntaxError/ImportError
            
            return module
        finally:
            sys.path[:] = old_path
    
    def load_module(self, module_name: str) -> Any:
        """Load specific module and cache it."""
        with self._lock:
            if module_name in self._cache:
                return self._cache[module_name]
            
            try:
                module = self._import_module(module_name)
                self._cache[module_name] = module
                return module
            except ModuleLoaderError:
                raise
            except Exception as e:
                raise ModuleImportError(f"Failed to import {module_name}: {e}")
    
    def get_module(self, module_name: str) -> Any:
        """Get cached module or load it (lazy loading)."""
        return self.load_module(module_name)
    
    def load_all_modules(self) -> Dict[str, Any]:
        """Load all discovered modules."""
        result = {}
        for name in self._module_names:
            try:
                result[name] = self.load_module(name)
            except ModuleLoaderError:
                pass  # Skip failed modules
        return result
    
    def get_modules_dict(self) -> Dict[str, ModuleProxy]:
        """Return dictionary of ModuleProxy objects for Jinja2 context."""
        return {name: ModuleProxy(self, name) for name in self._module_names}
    
    def get_module_names(self) -> list[str]:
        """Get list of discovered module names."""
        return self._module_names


# Lazy global instance (created on first use)
_module_loader = None


def load_modules_for_jinja() -> Dict[str, ModuleProxy]:
    """
    Convenience function for Jinja2 globals.
    
    Returns dictionary of ModuleProxy objects ready for env.globals.
    Never raises exceptions - returns empty dict if modules unavailable.
    """
    global _module_loader
    try:
        if _module_loader is None:
            _module_loader = ModuleLoader(MODULES_DIR)
        return _module_loader.get_modules_dict()
    except (ModuleLoaderError, FileNotFoundError, NotADirectoryError):
        return {}
