"""
Save File Manager Module

This module provides comprehensive INI-format save file management for the Template Assistant.
Save files store variable configurations in sections with hierarchy: [general] + template-specific.

Format example:
[general]
company_name = Example Corp

[reports/monthly]
client_name = Acme Corp  # Overrides general for this template

Subtemplates automatically load their context: [common/header]

Template-specific sections use extensionless format (e.g., [example] not [example.template]).
Template-specific sections override [general]. Supports subdirectories and flexible file naming
with any extension. Files can be organized in subdirectories with any naming convention.
Backward compatible with old format that included .template extension.
"""

import os
import ast
import configparser
import tempfile
import shutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

from configuration import SAVES_DIR


# ============================================================================
# Custom Exception Classes
# ============================================================================

class SaveFileError(Exception):
    """Base exception class for save file errors."""
    def __init__(self, message: str, save_file_path: str = None):
        self.save_file_path = save_file_path
        super().__init__(f"{message}" + (f" in {save_file_path}" if save_file_path else ""))


class SaveFileNotFoundError(SaveFileError):
    """Raised when save file cannot be found."""


class SaveFileFormatError(SaveFileError):
    """Raised when save file has invalid INI format."""


class SaveFileSaveError(SaveFileError):
    """Raised when save file cannot be written."""


# ============================================================================
# Helper Functions
# ============================================================================

def _normalize_template_path(template_path: str) -> str:
    """
    Normalize template path by stripping .template extension.

    Args:
        template_path: Template path (e.g., 'example.template' or 'reports/monthly.template')
    Returns:
        Normalized path without .template extension (e.g., 'example' or 'reports/monthly')
    """
    if template_path.endswith('.template'):
        return template_path[:-9]  # Remove '.template' (9 characters)
    return template_path


# ============================================================================
# SaveFileData Dataclass
# ============================================================================

@dataclass(frozen=True)
class SaveFileData:
    """
    Immutable representation of parsed save file data.
    
    Fields:
        path: Save file path
        globals_variables: Variables from [globals] section
        general_variables: Variables from [general] section
        template_sections: Dict of template_path -> variables dict
    """
    path: str
    globals_variables: Dict[str, Any] = field(default_factory=dict)
    general_variables: Dict[str, Any] = field(default_factory=dict)
    template_sections: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    @classmethod
    def from_configparser(cls, config: configparser.ConfigParser, path: str) -> 'SaveFileData':
        """Deserialize from ConfigParser object."""
        globals_vars = {}
        general_vars = {}
        template_sections = {}
        
        # Parse [globals] section
        if config.has_section('globals'):
            globals_vars = dict(config['globals'])
        
        # Parse [general] section
        if config.has_section('general'):
            general_vars = dict(config['general'])
        
        # Parse all other sections as template-specific
        for section in config.sections():
            if section not in ['globals', 'general']:
                template_sections[section] = dict(config[section])
        
        # Type coercion
        globals_vars = cls._parse_values(globals_vars)
        general_vars = cls._parse_values(general_vars)
        template_sections = {k: cls._parse_values(v) for k, v in template_sections.items()}
        
        return cls(path, globals_vars, general_vars, template_sections)
    
    def to_configparser(self) -> configparser.ConfigParser:
        """Serialize to ConfigParser object."""
        config = configparser.ConfigParser(allow_no_value=True)
        
        # Add [globals] section first (logical ordering)
        if self.globals_variables:
            config['globals'] = self.globals_variables
        
        # Add [general] section
        if self.general_variables:
            config['general'] = self.general_variables
        
        # Add template-specific sections
        for template_path, vars_dict in self.template_sections.items():
            config[template_path] = vars_dict
        
        return config
    
    def get_variables_for_template(self, template_path: str) -> Dict[str, Any]:
        """
        Get merged variables for template: globals + general + template-specific (CSS-like cascade).

        Section names use extensionless format (e.g., [example] not [example.template]).
        Backward compatible with old format that included .template extension.

        Args:
            template_path: Template path (e.g., 'reports/monthly.template' or 'reports/monthly')
        Returns:
            Merged variables dict
        """
        # Normalize the template path by stripping .template extension
        normalized_path = _normalize_template_path(template_path)

        # Start with globals, then general, then template-specific (CSS-like cascade)
        result = self.globals_variables.copy()
        result.update(self.general_variables)

        # Try normalized path first (new format)
        if normalized_path in self.template_sections:
            result.update(self.template_sections[normalized_path])
        # Fallback to original path for backward compatibility (old format)
        elif template_path in self.template_sections:
            result.update(self.template_sections[template_path])

        return result
    
    @staticmethod
    def _parse_values(values: Dict[str, str]) -> Dict[str, Any]:
        """Type coerce INI string values."""
        result = {}
        for key, value in values.items():
            value_stripped = value.strip()

            # Try to parse Python literals (lists, dicts, tuples, sets)
            if value_stripped.startswith(('[', '{', '(')):
                try:
                    result[key] = ast.literal_eval(value)
                    continue
                except (ValueError, SyntaxError):
                    # Fall through to existing type coercion logic
                    pass

            value_lower = value.lower().strip()

            # Boolean (direct parsing)
            if value_lower in ('true', 'yes', 'on', '1'):
                result[key] = True
            elif value_lower in ('false', 'no', 'off', '0'):
                result[key] = False
            # Integer
            elif value.lstrip('-').isdigit():
                result[key] = int(value)
            # Float
            elif '.' in value and value.replace('.', '').replace('-', '').replace('e', '').replace('E', '').isdigit():
                result[key] = float(value)
            # String (preserve as-is)
            else:
                result[key] = value
        return result
    
    def get_global_variables(self) -> Dict[str, Any]:
        """Return copy of globals_variables dictionary."""
        return self.globals_variables.copy()
    
    def __repr__(self) -> str:
        glob_count = len(self.globals_variables)
        gen_count = len(self.general_variables)
        temp_count = len(self.template_sections)
        return f"SaveFileData(path='{self.path}', globals={glob_count}, general={gen_count}, templates={temp_count})"


# ============================================================================
# SaveFileManager Class
# ============================================================================

class SaveFileManager:
    """
    Manages INI-format save files with section hierarchy support.

    Sections: [general] + template-specific (e.g., [reports/monthly])
    Section names use extensionless format (e.g., [example] not [example.template]).
    Template sections override [general]. Supports subdirectories and any file extension.
    Backward compatible with old format that included .template extension.
    """
    
    def __init__(self, saves_dir: str = None):
        self.saves_dir = saves_dir or SAVES_DIR
    
    def load(self, save_path: str) -> SaveFileData:
        """
        Load save file and return SaveFileData object.

        Args:
            save_path: Relative path with exact name/extension (e.g., 'client' or 'projects/client')
        """
        # Use the path exactly as provided by the user
        full_path = os.path.normpath(os.path.join(self.saves_dir, save_path))

        if not os.path.exists(full_path):
            raise SaveFileNotFoundError(f"Save file not found: {save_path}", save_path)

        try:
            config = configparser.ConfigParser(allow_no_value=True)
            config.read(full_path, encoding='utf-8')
            return SaveFileData.from_configparser(config, full_path)
        except configparser.Error as e:
            raise SaveFileFormatError(f"Invalid INI format: {e}", full_path)
    
    def save(self, save_path: str, save_data: SaveFileData) -> None:
        """
        Save SaveFileData to file atomically.

        Args:
            save_path: Relative path with exact name/extension (e.g., 'client' or 'projects/client')
            save_data: SaveFileData object to write
        """
        full_path = os.path.normpath(os.path.join(self.saves_dir, save_path))

        self._ensure_directory_exists(full_path)

        config = save_data.to_configparser()

        # Atomic write: temp file -> rename
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tmp',
                                       dir=Path(full_path).parent, delete=False) as f:
            config.write(f)
            temp_path = f.name

        try:
            shutil.move(temp_path, full_path)
        except OSError as e:
            os.unlink(temp_path)
            raise SaveFileSaveError(f"Failed to write save file: {e}", full_path)
    
    def save_variables(self, save_path: str, variables: Dict[str, Any],
                      template_path: Optional[str] = None, is_global: bool = False) -> None:
        """
        Save variables to save file (globals, general or template-specific section).

        Section names use extensionless format (e.g., [example] not [example.template]).

        Args:
            save_path: Save file path (e.g., 'client_a' or 'projects/client')
            variables: Variables to save
            template_path: Template section name (e.g., 'example.template') or None for [general]
            is_global: If True, save to [globals] section instead of [general] or template
        """
        full_path = os.path.normpath(os.path.join(self.saves_dir, save_path))

        # Load existing or create new
        try:
            save_data = self.load(save_path)
        except SaveFileNotFoundError:
            save_data = SaveFileData(full_path, {}, {}, {})

        # Normalize template_path by stripping .template extension for section name
        section_name = _normalize_template_path(template_path) if template_path else 'general'

        if is_global:
            # Create new immutable instance with updated global variables
            merged_globals = save_data.globals_variables.copy()
            merged_globals.update(variables)
            new_save_data = SaveFileData(
                save_data.path,
                merged_globals,
                save_data.general_variables,
                save_data.template_sections
            )
        elif template_path:
            # Create new immutable instance with updated template section
            # Merge existing template section variables with new ones
            new_template_sections = save_data.template_sections.copy()
            existing_template_vars = new_template_sections.get(section_name, {})
            merged_template_vars = existing_template_vars.copy()
            merged_template_vars.update(variables)
            new_template_sections[section_name] = merged_template_vars
            new_save_data = SaveFileData(
                save_data.path,
                save_data.globals_variables,
                save_data.general_variables,
                new_template_sections
            )
        else:
            # Create new immutable instance with updated general variables
            # Merge existing general variables with new ones
            merged_general = save_data.general_variables.copy()
            merged_general.update(variables)
            new_save_data = SaveFileData(
                save_data.path,
                save_data.globals_variables,
                merged_general,
                save_data.template_sections
            )

        self.save(save_path, new_save_data)
    
    def load_variables_for_template(self, save_path: str, template_path: str) -> Dict[str, Any]:
        """
        Load merged variables for specific template from save file.

        Normalization and backward compatibility handled by SaveFileData.get_variables_for_template().

        Args:
            save_path: Save file path
            template_path: Template path (e.g., 'reports/monthly.template' or 'reports/monthly')
        Returns:
            Merged dict: general + template-specific (template overrides)
        """
        save_data = self.load(save_path)
        return save_data.get_variables_for_template(template_path)
    
    def get_template_sections(self, save_path: str) -> List[str]:
        """Get list of template sections in save file."""
        save_data = self.load(save_path)
        return list(save_data.template_sections.keys())
    
    def _ensure_directory_exists(self, full_path: str) -> None:
        """Create parent directory if needed."""
        Path(full_path).parent.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Module-Level Convenience Functions & Instance
# ============================================================================

def load_save_file(save_path: str, saves_dir: str = None) -> SaveFileData:
    """Convenience: Load save file."""
    return SaveFileManager(saves_dir).load(save_path)


def save_variables_to_file(save_path: str, variables: Dict[str, Any], 
                          template_path: Optional[str] = None, saves_dir: str = None) -> None:
    """Convenience: Save variables to file."""
    SaveFileManager(saves_dir).save_variables(save_path, variables, template_path)


def load_variables_for_template(save_path: str, template_path: str, 
                               saves_dir: str = None) -> Dict[str, Any]:
    """Convenience: Load template variables from save file."""
    return SaveFileManager(saves_dir).load_variables_for_template(save_path, template_path)


# Default instance
save_file_manager = SaveFileManager()
