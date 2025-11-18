"""
Save File Manager Module

This module provides comprehensive INI-format save file management for the Template Assistant.
Save files store variable configurations in sections with hierarchy: [general] + template-specific.

Format example:
[general]
company_name = Example Corp

[reports/monthly.template]
client_name = Acme Corp  # Overrides general for this template

Subtemplates automatically load their context: [common/header.template]

Template-specific sections override [general]. Supports subdirectories and flexible file naming
(no extension required). Files can be organized in subdirectories with any naming convention.
"""

import os
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
# SaveFileData Dataclass
# ============================================================================

@dataclass(frozen=True)
class SaveFileData:
    """
    Immutable representation of parsed save file data.
    
    Fields:
        path: Save file path
        general_variables: Variables from [general] section
        template_sections: Dict of template_path -> variables dict
    """
    path: str
    general_variables: Dict[str, Any] = field(default_factory=dict)
    template_sections: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    @classmethod
    def from_configparser(cls, config: configparser.ConfigParser, path: str) -> 'SaveFileData':
        """Deserialize from ConfigParser object."""
        general_vars = {}
        template_sections = {}
        
        # Parse [general] section
        if config.has_section('general'):
            general_vars = dict(config['general'])
        
        # Parse all other sections as template-specific
        for section in config.sections():
            if section != 'general':
                template_sections[section] = dict(config[section])
        
        # Type coercion
        general_vars = cls._parse_values(general_vars)
        template_sections = {k: cls._parse_values(v) for k, v in template_sections.items()}
        
        return cls(path, general_vars, template_sections)
    
    def to_configparser(self) -> configparser.ConfigParser:
        """Serialize to ConfigParser object."""
        config = configparser.ConfigParser(allow_no_value=True)
        
        # Add [general] section
        if self.general_variables:
            config['general'] = self.general_variables
        
        # Add template-specific sections
        for template_path, vars_dict in self.template_sections.items():
            config[template_path] = vars_dict
        
        return config
    
    def get_variables_for_template(self, template_path: str) -> Dict[str, Any]:
        """
        Get merged variables for template: general + template-specific (template overrides).
        
        Args:
            template_path: Template path (e.g., 'reports/monthly.template')
        Returns:
            Merged variables dict
        """
        result = self.general_variables.copy()
        result.update(self.template_sections.get(template_path, {}))
        return result
    
    @staticmethod
    def _parse_values(values: Dict[str, str]) -> Dict[str, Any]:
        """Type coerce INI string values."""
        result = {}
        for key, value in values.items():
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
    
    def __repr__(self) -> str:
        gen_count = len(self.general_variables)
        temp_count = len(self.template_sections)
        return f"SaveFileData(path='{self.path}', general={gen_count}, templates={temp_count})"


# ============================================================================
# SaveFileManager Class
# ============================================================================

class SaveFileManager:
    """
    Manages INI-format save files with section hierarchy support.
    
    Sections: [general] + template-specific (e.g., [reports/monthly.template])
    Template sections override [general]. Supports subdirectories.
    """
    
    def __init__(self, saves_dir: str = None):
        self.saves_dir = saves_dir or SAVES_DIR
    
    def load(self, save_path: str) -> SaveFileData:
        """
        Load save file and return SaveFileData object.

        Args:
            save_path: Relative path (e.g., 'client_a' or 'projects/client')
        """
        # Use the path as provided by the user
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
            save_path: Relative path (e.g., 'client_a' or 'projects/client')
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
                      template_path: Optional[str] = None) -> None:
        """
        Save variables to save file (general or template-specific section).

        Args:
            save_path: Save file path (e.g., 'client_a' or 'projects/client')
            variables: Variables to save
            template_path: Template section name or None for [general]
        """
        full_path = os.path.normpath(os.path.join(self.saves_dir, save_path))
        
        # Load existing or create new
        try:
            save_data = self.load(save_path)
        except SaveFileNotFoundError:
            save_data = SaveFileData(full_path)
        
        section_name = template_path or 'general'
        
        if template_path:
            # Create new immutable instance with updated template section
            new_template_sections = save_data.template_sections.copy()
            new_template_sections[section_name] = variables.copy()
            new_save_data = SaveFileData(
                save_data.path,
                save_data.general_variables,
                new_template_sections
            )
        else:
            # Create new immutable instance with updated general variables
            new_save_data = SaveFileData(
                save_data.path,
                variables.copy(),
                save_data.template_sections
            )
        
        self.save(save_path, new_save_data)
    
    def load_variables_for_template(self, save_path: str, template_path: str) -> Dict[str, Any]:
        """
        Load merged variables for specific template from save file.
        
        Args:
            save_path: Save file path
            template_path: Template path (e.g., 'reports/monthly.template')
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
