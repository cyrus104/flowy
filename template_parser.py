"""
Template Parser Module

This module provides functionality to parse .template files with a two-section format:
1. VARS section: YAML-formatted variable definitions
2. TEMPLATE section: Jinja2 template content

The parser validates template structure, extracts variable definitions, and returns
structured data that can be consumed by the rendering engine and interactive shell.
"""

import os
import yaml
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from configuration import TEMPLATES_DIR


# ============================================================================
# Custom Exception Classes
# ============================================================================

class TemplateParseError(Exception):
    """Base exception class for template parsing errors."""
    def __init__(self, message: str, template_path: str = None):
        self.template_path = template_path
        super().__init__(f"{message}" + (f" in {template_path}" if template_path else ""))


class TemplateNotFoundError(TemplateParseError):
    """Raised when a template file cannot be found."""
    def __init__(self, template_path: str):
        super().__init__(f"Template file not found: {template_path}", template_path)


class TemplateFormatError(TemplateParseError):
    """Raised when template structure is invalid."""
    def __init__(self, message: str, template_path: str = None, line_number: int = None):
        self.line_number = line_number
        if line_number:
            message = f"{message} at line {line_number}"
        super().__init__(message, template_path)


class VariableDefinitionError(TemplateParseError):
    """Raised when YAML variable definitions are invalid."""
    def __init__(self, message: str, template_path: str = None, line_number: int = None):
        self.line_number = line_number
        if line_number:
            message = f"{message} at line {line_number}"
        super().__init__(message, template_path)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class VariableDefinition:
    """
    Represents a single variable definition from the VARS section.
    
    Attributes:
        name: Variable identifier
        description: Human-readable description (optional)
        default: Default value if not set by user (optional)
        options: List of valid values for the variable (optional)
    """
    name: str
    description: Optional[str] = None
    default: Any = None
    options: Optional[List[Any]] = None
    
    def __repr__(self) -> str:
        parts = [f"VariableDefinition(name='{self.name}'"]
        if self.description is not None:
            desc = self.description[:30]
            if len(self.description) > 30:
                desc += "..."
            parts.append(f"description='{desc}'")
        if self.default is not None:
            parts.append(f"default={repr(self.default)}")
        if self.options is not None:
            parts.append(f"options={self.options}")
        return ", ".join(parts) + ")"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {'name': self.name}
        if self.description is not None:
            result['description'] = self.description
        if self.default is not None:
            result['default'] = self.default
        if self.options is not None:
            result['options'] = self.options
        return result


@dataclass
class TemplateDefinition:
    """
    Represents a complete parsed template.
    
    Attributes:
        path: Full path to the template file
        name: Template filename without path
        relative_path: Original relative path used for parsing
        variables: Dictionary mapping variable names to VariableDefinition objects
        template_content: Raw Jinja2 template content from TEMPLATE section
        raw_vars_section: Original VARS section text for debugging (optional)
    """
    path: str
    name: str
    relative_path: str
    variables: Dict[str, VariableDefinition] = field(default_factory=dict)
    template_content: str = ""
    raw_vars_section: Optional[str] = None
    
    def __repr__(self) -> str:
        var_count = len(self.variables)
        return (f"TemplateDefinition(name='{self.name}', "
                f"path='{self.path}', "
                f"variables={var_count} defined)")
    
    def get_variable(self, name: str) -> Optional[VariableDefinition]:
        """Get a variable definition by name."""
        return self.variables.get(name)


# ============================================================================
# Template Parser Class
# ============================================================================

class TemplateParser:
    """
    Parser for .template files with VARS and TEMPLATE sections.
    
    The parser reads template files, validates their structure, extracts
    variable definitions from the VARS section, and returns structured data.
    """
    
    def __init__(self, templates_dir: str = None):
        """
        Initialize the parser with a templates directory.
        
        Args:
            templates_dir: Path to templates directory (defaults to TEMPLATES_DIR from config)
        """
        self.templates_dir = templates_dir or TEMPLATES_DIR
        
    def parse(self, template_path: str) -> TemplateDefinition:
        """
        Parse a template file and return its definition.
        
        Args:
            template_path: Relative path to template file from templates directory
            
        Returns:
            TemplateDefinition object containing parsed template data
            
        Raises:
            TemplateNotFoundError: If template file doesn't exist
            TemplateParseError: If template format is invalid
            VariableDefinitionError: If VARS section contains invalid YAML
        """
        # Try with and without .template extension
        paths_to_try = []
        if template_path.endswith('.template'):
            paths_to_try.append(template_path)
        else:
            # Try with extension first, then as-is
            paths_to_try.append(template_path + '.template')
            paths_to_try.append(template_path)
        
        full_path = None
        actual_template_path = None
        for path in paths_to_try:
            test_path = os.path.normpath(os.path.join(self.templates_dir, path))
            if os.path.exists(test_path):
                full_path = test_path
                actual_template_path = path
                break
        
        if full_path is None:
            # Provide helpful error message about attempted paths
            attempted = ', '.join(paths_to_try)
            error_msg = f"Template not found. Tried: {attempted}"
            # Keep template_path as first argument for exception contract
            raise TemplateNotFoundError(template_path) from TemplateParseError(error_msg, template_path)
        
        # Read file content
        content = self._read_file(full_path)
        
        # Split into sections
        vars_section, template_section = self._split_sections(content, full_path)
        
        # Parse VARS section
        variables = self._parse_vars_section(vars_section, full_path)
        
        # Extract template content
        template_content = self._extract_template_content(template_section)
        
        # Create and return TemplateDefinition
        template_name = os.path.basename(actual_template_path)
        return TemplateDefinition(
            path=full_path,
            name=template_name,
            relative_path=actual_template_path,
            variables=variables,
            template_content=template_content,
            raw_vars_section=vars_section
        )
    
    def _read_file(self, full_path: str) -> str:
        """
        Read the template file content.
        
        Args:
            full_path: Full path to the template file
            
        Returns:
            Raw file content as string
            
        Raises:
            TemplateNotFoundError: If file doesn't exist
        """
        if not os.path.exists(full_path):
            raise TemplateNotFoundError(full_path)
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except IOError as e:
            raise TemplateParseError(f"Error reading template file: {e}", full_path)
    
    def _split_sections(self, content: str, template_path: str) -> Tuple[str, str]:
        """
        Split content into VARS and TEMPLATE sections.
        
        Args:
            content: Raw template file content
            template_path: Full path to the template file for error reporting
            
        Returns:
            Tuple of (vars_section, template_section)
            
        Raises:
            TemplateFormatError: If marker is missing or appears multiple times
        """
        # Look for the template marker (case-insensitive, flexible whitespace)
        import re
        marker_pattern = r'###\s*TEMPLATE\s*###'
        matches = list(re.finditer(marker_pattern, content, re.IGNORECASE))
        
        if not matches:
            raise TemplateFormatError(
                "Invalid template format: Missing '### TEMPLATE ###' section marker",
                template_path=template_path
            )
        
        if len(matches) > 1:
            raise TemplateFormatError(
                "Invalid template format: Multiple '### TEMPLATE ###' markers found",
                template_path=template_path
            )
        
        # Split at the marker
        marker_pos = matches[0].start()
        vars_section = content[:marker_pos].strip()
        
        # Remove the marker itself and get template content (preserve whitespace)
        template_section = content[matches[0].end():]
        
        # Process VARS section more robustly
        # Split into lines and look for VARS: header line
        # Note: VARS header is case-sensitive by design and must be exactly 'VARS:'
        # (supports indentation via strip() but requires exact casing)
        vars_lines = vars_section.split('\n')
        vars_header_found = False
        vars_content_lines = []
        
        for i, line in enumerate(vars_lines):
            if not vars_header_found and line.strip() == 'VARS:':
                vars_header_found = True
                # Start collecting lines after VARS: header
                continue
            elif vars_header_found:
                vars_content_lines.append(line)
        
        if vars_header_found:
            # Use only the lines after VARS: header as YAML content
            vars_section = '\n'.join(vars_content_lines)
        else:
            # No VARS: header found - treat as empty VARS section for safety
            # This prevents arbitrary pre-marker text from being parsed as YAML
            # Templates should explicitly use VARS: header for variable definitions
            if vars_section.startswith('VARS:'):
                # Handle edge case where VARS: is at the start without newline
                vars_section = vars_section[5:].strip()
            else:
                # No VARS header - treat as empty VARS section
                vars_section = ''
        
        return vars_section, template_section
    
    def _parse_vars_section(self, vars_content: str, template_path: str) -> Dict[str, VariableDefinition]:
        """
        Parse the YAML VARS section into variable definitions.
        
        Args:
            vars_content: VARS section content (without VARS: prefix)
            template_path: Full path to the template file for error reporting
            
        Returns:
            Dictionary mapping variable names to VariableDefinition objects
            
        Raises:
            VariableDefinitionError: For YAML syntax errors or invalid structure
        """
        # Handle empty VARS section
        if not vars_content:
            return {}
        
        # Keep original content split into lines for line number mapping
        vars_lines = vars_content.split('\n')
        
        try:
            # Parse YAML
            parsed = yaml.safe_load(vars_content)
        except yaml.YAMLError as e:
            # Extract line number if available
            line_num = getattr(e, 'problem_mark', None)
            if line_num:
                line_num = line_num.line + 1  # YAML uses 0-based line numbers
            raise VariableDefinitionError(
                f"YAML syntax error in VARS section: {e}",
                template_path=template_path,
                line_number=line_num
            )
        
        # Handle None result (empty YAML)
        if parsed is None:
            return {}
        
        # Validate structure: should be a list
        if not isinstance(parsed, list):
            # Try to find approximate line number for the error
            # The error is at the start of the YAML content
            line_num = 1
            for i, line in enumerate(vars_lines, 1):
                if line.strip() and not line.strip().startswith('#'):
                    line_num = i
                    break
            raise VariableDefinitionError(
                "Invalid VARS structure: Expected a list of variable definitions",
                template_path=template_path,
                line_number=line_num
            )
        
        # Parse each variable definition
        variables = {}
        for idx, item in enumerate(parsed, 1):
            # Try to find the line number for this item
            item_line_num = None
            if isinstance(item, dict) and item:
                # Get the first key (variable name) to search for
                var_name = list(item.keys())[0] if item else None
                if var_name:
                    # Search for the variable name in the original text
                    for line_idx, line in enumerate(vars_lines, 1):
                        if f'- {var_name}:' in line or f'-{var_name}:' in line:
                            item_line_num = line_idx
                            break
            else:
                # For non-dict items, search for the serialized representation
                item_str = str(item)
                for line_idx, line in enumerate(vars_lines, 1):
                    # Look for lines starting with - that might contain this item
                    if line.strip().startswith('-'):
                        # Check if the item representation appears in the line
                        if item_str in line or (isinstance(item, str) and f'"{item}"' in line) or (isinstance(item, str) and f"'{item}'" in line):
                            item_line_num = line_idx
                            break
            
            if not isinstance(item, dict):
                raise VariableDefinitionError(
                    f"Invalid variable definition at position {idx}: Expected a dictionary",
                    template_path=template_path,
                    line_number=item_line_num
                )
            
            # Each item should have exactly one top-level key (the variable name)
            if len(item) != 1:
                raise VariableDefinitionError(
                    f"Invalid variable definition at position {idx}: "
                    f"Expected exactly one variable name, got {len(item)}",
                    template_path=template_path,
                    line_number=item_line_num
                )
            
            # Extract variable name and data
            var_name = list(item.keys())[0]
            var_data = item[var_name]
            
            # Check for duplicate variable names
            if var_name in variables:
                raise VariableDefinitionError(
                    f"Duplicate variable definition for '{var_name}'",
                    template_path=template_path,
                    line_number=item_line_num
                )
            
            # Validate and create VariableDefinition
            var_def = self._validate_variable_definition(var_name, var_data, template_path, item_line_num)
            variables[var_name] = var_def
        
        return variables
    
    def _validate_variable_definition(self, var_name: str, var_data: Any, template_path: str, line_number: int = None) -> VariableDefinition:
        """
        Validate a single variable definition and create VariableDefinition object.
        
        Args:
            var_name: Variable name
            var_data: Variable data (dict or None)
            template_path: Full path to the template file for error reporting
            line_number: Approximate line number for error reporting
            
        Returns:
            VariableDefinition object
            
        Raises:
            VariableDefinitionError: If definition is invalid
        """
        # Handle minimal definition (just variable name)
        if var_data is None:
            return VariableDefinition(name=var_name)
        
        # Validate that var_data is a dictionary
        if not isinstance(var_data, dict):
            raise VariableDefinitionError(
                f"Invalid variable definition for '{var_name}': "
                f"Expected dictionary but got {type(var_data).__name__}",
                template_path=template_path,
                line_number=line_number
            )
        
        # Validate known keys
        valid_keys = {'description', 'default', 'options'}
        unknown_keys = set(var_data.keys()) - valid_keys
        if unknown_keys:
            raise VariableDefinitionError(
                f"Unknown keys in variable '{var_name}': {', '.join(unknown_keys)}",
                template_path=template_path,
                line_number=line_number
            )
        
        # Validate options is a list if present
        if 'options' in var_data and not isinstance(var_data['options'], list):
            raise VariableDefinitionError(
                f"Invalid 'options' for variable '{var_name}': Expected list but got {type(var_data['options']).__name__}",
                template_path=template_path,
                line_number=line_number
            )
        
        # Create VariableDefinition
        return VariableDefinition(
            name=var_name,
            description=var_data.get('description'),
            default=var_data.get('default'),
            options=var_data.get('options')
        )
    
    def _extract_template_content(self, template_section: str) -> str:
        """
        Extract the Jinja2 template content preserving original whitespace.
        
        Args:
            template_section: Raw template section content
            
        Returns:
            Template content as-is (preserves leading/trailing newlines)
        """
        # Preserve all original whitespace as authored by template writer
        return template_section


# ============================================================================
# Module-Level Convenience Function
# ============================================================================

def parse_template(template_path: str, templates_dir: str = None) -> TemplateDefinition:
    """
    Convenience function to parse a template file.
    
    Args:
        template_path: Relative path to template file
        templates_dir: Optional templates directory path
        
    Returns:
        TemplateDefinition object containing parsed template data
        
    Raises:
        TemplateNotFoundError: If template file doesn't exist
        TemplateFormatError: If template structure is invalid
        VariableDefinitionError: If VARS section contains invalid YAML
    """
    parser = TemplateParser(templates_dir)
    return parser.parse(template_path)