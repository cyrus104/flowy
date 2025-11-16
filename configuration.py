"""
Configuration Module for Template Assistant

This module centralizes all configuration settings for the Template Assistant application.
It provides centralized access to paths, display settings, interface customization, and
behavioral options. All settings support environment variable overrides for flexible deployment.

Usage:
    from configuration import TEMPLATES_DIR, COMMAND_ALIASES, BANNER_ASCII
    
    # Customize behavior via environment variables
    export TEMPLATE_ASSISTANT_TEMPLATES=/custom/path
"""

import os

# ============================================================================
# Version Information
# ============================================================================

VERSION = "1.0.0"
APP_NAME = "Template Assistant"


# ============================================================================
# Folder Locations
# ============================================================================
# Each location supports environment variable override for flexible deployment

TEMPLATES_DIR = os.getenv('TEMPLATE_ASSISTANT_TEMPLATES', './templates')
"""Path to directory containing template files (.template extension)"""

SAVES_DIR = os.getenv('TEMPLATE_ASSISTANT_SAVES', './saves')
"""Path to directory containing save files (.save extension)"""

MODULES_DIR = os.getenv('TEMPLATE_ASSISTANT_MODULES', './modules')
"""Path to directory containing Python module files for template functions"""


# ============================================================================
# State Management
# ============================================================================

STATE_FILE = os.getenv('TEMPLATE_ASSISTANT_STATE', './.state')
"""Path to state file for session persistence and crash recovery (JSON format)"""

HISTORY_FILE = os.getenv('TEMPLATE_ASSISTANT_HISTORY', './.history')
"""Path to history file for command audit trail (plain text format)"""


# ============================================================================
# Interface Customization
# ============================================================================

PROMPT_TEMPLATE = "template-assistant{template} > "
"""
Prompt template for interactive shell.
{template} will be replaced with:
  - Current template path if one is loaded
  - Empty string if no template is loaded
Examples:
  template-assistant > 
  template-assistant (reports/monthly.template) > 
"""

BANNER_ASCII = r"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                       TEMPLATE ASSISTANT v{version}                        ║
║                                                                           ║
║       Interactive Jinja2 Template Rendering with Python Integration      ║
╚═══════════════════════════════════════════════════════════════════════════╝
""".format(version=VERSION)
"""ASCII art banner displayed on startup"""


# ============================================================================
# Command Aliases
# ============================================================================

COMMAND_ALIASES = {
    'render': ['r', 're'],
    'ls': ['ll'],
    'use': ['load_template'],
    # Users can add custom aliases here as needed
}
"""
Command aliases for shorthand notation.
Maps primary command name to list of alias names.
Example: To use 'r' as alias for 'render', user types 'r' and it executes 'render'
"""


# ============================================================================
# Display Options
# ============================================================================

SHOW_CONFIG_ON_STARTUP = True
"""Display configuration paths and settings when application starts"""

COLOR_OUTPUT_ENABLED = True
"""Enable terminal color formatting for output"""


# ============================================================================
# Display Settings - Terminal Width & Wrapping
# ============================================================================

AUTO_DETECT_WIDTH = True
"""Automatically detect current terminal width on startup and resize"""

DEFAULT_WIDTH = 80
"""Fallback terminal width (columns) when auto-detection is unavailable or fails"""

WORD_WRAP_ENABLED = True
"""Enable intelligent word wrapping for all rendered output"""

PRESERVE_FORMATTING_ON_WRAP = True
"""Maintain text formatting (colors, bold) when wrapping lines"""

MAX_TABLE_COLUMN_WIDTH = 40
"""Maximum width for table columns (ls command output)"""

MIN_TABLE_COLUMN_WIDTH = 10
"""Minimum width for table columns (ls command output)"""

TRUNCATE_INDICATOR = "..."
"""Indicator appended when content is truncated to fit available space"""


# ============================================================================
# Undefined Variable Handling
# ============================================================================

UNDEFINED_VARIABLE_TEMPLATE = "[red]<<{var}>>[/red]"
"""
Template for rendering undefined variables in output.
{var} will be replaced with the variable name.
Uses rich markup syntax for colors: [red]...[/red]

Examples of rendering undefined variables:
  Expected: [red]<<client_name>>[/red]
  Expected: [red]<<project_id>>[/red]
"""

UNDEFINED_BEHAVIOR = "mark"
"""
Behavior when undefined variables are encountered during rendering.
Options:
  - "mark": Render as [red]<<variable_name>>[/red] and continue
  - "error": Raise exception and stop rendering
  - "empty": Render as empty string and continue
"""

SHOW_UNDEFINED_SUMMARY = True
"""
Display summary of undefined variables encountered after rendering.
Helps users identify which variables need to be set for complete output.
"""
