"""
Configuration Module for Flowy

This module centralizes all configuration settings for the Flowy application.
It provides centralized access to paths, display settings, interface customization, and
behavioral options. All settings support environment variable overrides for flexible deployment.

Usage:
    from configuration import TEMPLATES_DIR, COMMAND_ALIASES, BANNER_ASCII

    # Customize behavior via environment variables
    export FLOWY_TEMPLATES=/custom/path
"""

import os

# ============================================================================
# Version Information
# ============================================================================

VERSION = "1.0.0"
APP_NAME = "Flowy"


# ============================================================================
# Folder Locations
# ============================================================================
# Each location supports environment variable override for flexible deployment

TEMPLATES_DIR = os.getenv('FLOWY_TEMPLATES', os.getenv('TEMPLATE_ASSISTANT_TEMPLATES', './templates'))
"""Path to directory containing template files (.template extension)"""

SAVES_DIR = os.getenv('FLOWY_SAVES', os.getenv('TEMPLATE_ASSISTANT_SAVES', './saves'))
"""Path to directory containing save files (no extension required)"""

MODULES_DIR = os.getenv('FLOWY_MODULES', os.getenv('TEMPLATE_ASSISTANT_MODULES', './modules'))
"""Path to directory containing Python module files for template functions"""


# ============================================================================
# State Management
# ============================================================================

STATE_FILE = os.getenv('FLOWY_STATE', os.getenv('TEMPLATE_ASSISTANT_STATE', './.state'))
"""Path to state file for session persistence and crash recovery (JSON format)"""

STATE_BACKUP_FILE = os.getenv('FLOWY_STATE_BACKUP', os.getenv('TEMPLATE_ASSISTANT_STATE_BACKUP', './.state.backup'))
"""Path to backup state file storing state from before last program start for restore command"""

HISTORY_FILE = os.getenv('FLOWY_HISTORY', os.getenv('TEMPLATE_ASSISTANT_HISTORY', './.history'))
"""Path to history file for command audit trail (plain text format)"""


# ============================================================================
# Interface Customization
# ============================================================================

PROMPT_TEMPLATE = "flowy{template} > "
"""
Prompt template for interactive shell.
{template} will be replaced with:
  - Current template path if one is loaded
  - Empty string if no template is loaded
Examples:
  flowy >
  flowy (reports/monthly.template) >
"""

BANNER_ASCII = r"""
    ╔══════════════════════════════════════════════════════╗
    ║                                                      ║
    ║     ███████╗██╗      ██████╗ ██╗    ██╗██╗   ██╗     ║
    ║     ██╔════╝██║     ██╔═══██╗██║    ██║╚██╗ ██╔╝     ║
    ║     █████╗  ██║     ██║   ██║██║ █╗ ██║ ╚████╔╝      ║
    ║     ██╔══╝  ██║     ██║   ██║██║███╗██║  ╚██╔╝       ║
    ║     ██║     ███████╗╚██████╔╝╚███╔███╔╝   ██║        ║
    ║     ╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝    ╚═╝        ║
    ║                                                      ║
    ║                                                      ║
    ║     Templating the world one render at a time.       ║
    ║                                                      ║
    ╚══════════════════════════════════════════════════════╝
                   Version {version} 
"""
"""ASCII art banner displayed on startup"""


# ============================================================================
# Editor Settings
# ============================================================================

DEFAULT_EDITOR = os.getenv('FLOWY_EDITOR', os.getenv('TEMPLATE_ASSISTANT_EDITOR', 'code'))
"""
Editor command to launch when using the edit command.

Default: 'code' (Visual Studio Code)

The editor command will be invoked with the full system path to the file.
Can be overridden via FLOWY_EDITOR environment variable.
Legacy TEMPLATE_ASSISTANT_EDITOR variable is also honored for backward compatibility.

Common editor commands:
  - 'code': Visual Studio Code
  - 'vim': Vim editor
  - 'nano': Nano editor
  - 'emacs': Emacs editor
  - 'subl': Sublime Text
  - 'atom': Atom editor

Example usage:
  export FLOWY_EDITOR=vim
"""


# ============================================================================
# Command Aliases
# ============================================================================

COMMAND_ALIASES = {
    'render': ['r', 're'],
    'ls': ['ll'],
    'use': [],
    'push': [],
    'setglobal': ['sg'],
    'unsetglobal': ['ug'],
    'listglobals': ['lg', 'globals'],
    'help': ['h', '?'],
    'restore': ['res'],
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

SHOW_GLOBALS_IN_LS = True
"""Display global variables section in the 'ls' command output"""

VALIDATE_ON_STARTUP = False
"""
Run file validation check on startup to detect duplicate filenames.
Validation checks for duplicate filenames (ignoring extensions) within the same directory.
Duplicates across different subdirectories are allowed.
Only checks within templates/ and saves/ directories.

This validation runs before both standard interactive startup (start()) and quick-launch mode
(quick_launch()), ensuring file integrity is checked regardless of how the application starts.
"""


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
