"""
Shell Completers for Interactive Template Assistant

Provides context-aware tab completion for commands, templates, saves (with any name/extension),
variables, and options.
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Generator
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document

from configuration import TEMPLATES_DIR, SAVES_DIR, COMMAND_ALIASES
from template_parser import TemplateParser


def _get_template_files() -> List[str]:
    """Get all relative template paths recursively (without .template extension)."""
    templates = []
    templates_path = Path(TEMPLATES_DIR)
    if templates_path.exists():
        for path in templates_path.rglob("*.template"):
            # Strip the .template extension for display
            rel_path = path.relative_to(templates_path).as_posix()
            display_name = rel_path[:-9] if rel_path.endswith('.template') else rel_path
            templates.append(display_name)
    return sorted(templates)


def _get_save_files() -> List[str]:
    """Get all relative save paths recursively with exact names/extensions.

    Returns all save files with any name/extension. Files are returned with their
    exact names as stored in the saves directory. Filters out hidden files and
    directories (names starting with '.') to avoid surfacing system artifacts
    like .DS_Store, .gitkeep, etc.
    """
    saves = []
    saves_path = Path(SAVES_DIR)
    if saves_path.exists():
        for path in saves_path.rglob("*"):
            # Skip hidden files and directories (names starting with '.')
            if any(part.startswith('.') for part in path.parts):
                continue

            if path.is_file():
                # Return relative paths as-is without extension manipulation
                rel_path = path.relative_to(saves_path).as_posix()
                saves.append(rel_path)
    return sorted(saves)


def _get_variable_names(template_def) -> List[str]:
    """Get variable names from template definition."""
    if template_def is None:
        return []
    return list(template_def.variables.keys())


def _get_variable_options(template_def, var_name: str) -> List[str]:
    """Get options for specific variable."""
    if template_def is None or var_name not in template_def.variables:
        return []
    var_def = template_def.variables[var_name]
    options = getattr(var_def, 'options', [])
    if not options:
        return []
    try:
        return list(options)
    except TypeError:
        return []


def _parse_command_line(text: str) -> tuple[str, List[str]]:
    """Parse input into command and arguments."""
    # Simple split handling quoted strings
    import shlex
    try:
        parts = shlex.split(text)
    except ValueError:
        parts = text.split()
    return parts[0] if parts else '', parts[1:] if len(parts) > 1 else []


class ShellCompleter(Completer):
    """Context-aware completer for interactive shell."""

    def __init__(self, template_def=None):
        self.template_def = template_def
        self.template_parser = TemplateParser(TEMPLATES_DIR)
        self._templates = _get_template_files()
        self._saves = _get_save_files()

        # Build complete command list: all canonical commands + their aliases
        all_commands = set()
        # Add all canonical command names (keys)
        all_commands.update(COMMAND_ALIASES.keys())
        # Add all aliases (values)
        for aliases in COMMAND_ALIASES.values():
            all_commands.update(aliases)
        # Add commands that don't have aliases
        all_commands.update(['load', 'save', 'list', 'set', 'unset', 'exit', 'revert', 'edit'])
        self._commands = sorted(all_commands)
    
    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Generator[Completion, None, None]:
        """Generate completions based on current input context."""
        text_before_cursor = document.text_before_cursor
        word_before_cursor = document.text_before_cursor.lstrip()
        word = document.current_line_before_cursor.lstrip().rsplit(' ', 1)[-1]
        
        command, args = _parse_command_line(text_before_cursor)
        
        # Check if we're completing a command or its arguments
        # If no command yet, or still typing the command itself (no space after)
        if not command or (len(args) == 0 and not text_before_cursor.endswith(' ')):
            for cmd in self._commands:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))
            return
        
        # If command expects files and user typed space after command, complete files
        if len(args) == 0 and text_before_cursor.endswith(' '):
            if command == 'use':
                # Complete templates for 'use' command
                for path in self._templates:
                    yield Completion(path, start_position=0)
                return
            elif command in ['load', 'save', 'list']:
                # Complete save files for 'load', 'save', and 'list' commands
                for path in self._saves:
                    yield Completion(path, start_position=0)
                return
            elif command == 'edit':
                # Complete both templates and saves for 'edit' command
                for path in self._templates:
                    yield Completion(path, start_position=0)
                for path in self._saves:
                    yield Completion(path, start_position=0)
                return
        
        # Context-specific completion for arguments
        if command in ['use', 'load', 'save', 'list']:
            # First arg: template/save path completion
            if len(args) == 1:
                paths = self._templates if command == 'use' else self._saves
                for path in paths:
                    if path.startswith(word):
                        yield Completion(path, start_position=-len(word))
            elif command == 'use' and len(args) == 2:
                # Second arg for use: save path completion
                for path in self._saves:
                    if path.startswith(word):
                        yield Completion(path, start_position=-len(word))

        elif command == 'edit':
            # First arg: complete both templates and saves
            if len(args) == 1:
                for path in self._templates:
                    if path.startswith(word):
                        yield Completion(path, start_position=-len(word))
                for path in self._saves:
                    if path.startswith(word):
                        yield Completion(path, start_position=-len(word))
        
        elif command in ['set', 'unset']:
            # First arg: variable name completion
            if len(args) == 1 and not text_before_cursor.endswith(' '):
                vars = _get_variable_names(self.template_def)
                for var in vars:
                    if var.startswith(word):
                        yield Completion(var, start_position=-len(word))
            # Second arg for set: variable option completion
            elif command == 'set' and len(args) >= 1:
                # Two cases for completing option values:
                # 1. User has typed space after variable name (e.g., "set var_name ")
                has_space_after_var_name = len(args) == 1 and text_before_cursor.endswith(' ')
                # 2. User is typing the option value (e.g., "set var_name opt")
                is_typing_option_value = len(args) == 2

                if has_space_after_var_name or is_typing_option_value:
                    # Get the variable name from the first argument
                    var_name = args[0]
                    # Get options for this variable
                    options = _get_variable_options(self.template_def, var_name)
                    # Yield completions for matching options
                    for option in options:
                        option_str = str(option)
                        if option_str.startswith(word):
                            yield Completion(option_str, start_position=-len(word))
        
        elif command == 'help' or command in COMMAND_ALIASES.get('help', []):
            # First arg: command name completion (works for help, h, and ?)
            if len(args) == 1:
                for cmd in self._commands:
                    if cmd.startswith(word):
                        yield Completion(cmd, start_position=-len(word))
        
        # Path-like completion fallback (directories)
        if '/' in word:
            base_path = word.rsplit('/', 1)[0] + '/'
            if base_path.startswith(word):
                for path in self._templates + self._saves:
                    if path.startswith(base_path):
                        rel_path = path[len(base_path):]
                        if '/' in rel_path:
                            dir_name = rel_path.split('/')[0]
                            if dir_name.startswith(word.split('/')[-1]):
                                yield Completion(base_path + dir_name + '/', 
                                               start_position=-len(word.split('/')[-1]))
    
    def update_template(self, template_def):
        """Update current template for variable completion."""
        self.template_def = template_def