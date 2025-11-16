"""
Shell Completers for Interactive Template Assistant

Provides context-aware tab completion for commands, templates, saves, variables, and options.
"""

import os
import re
from pathlib import Path
from typing import List, Optional
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document

from configuration import TEMPLATES_DIR, SAVES_DIR, COMMAND_ALIASES
from template_parser import TemplateParser


def _get_template_files() -> List[str]:
    """Get all relative template paths recursively."""
    templates = []
    templates_path = Path(TEMPLATES_DIR)
    if templates_path.exists():
        for path in templates_path.rglob("*.template"):
            templates.append(path.relative_to(templates_path).as_posix())
    return sorted(templates)


def _get_save_files() -> List[str]:
    """Get all relative save paths recursively."""
    saves = []
    saves_path = Path(SAVES_DIR)
    if saves_path.exists():
        for path in saves_path.rglob("*.save"):
            saves.append(path.relative_to(saves_path).as_posix())
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
    return getattr(var_def, 'options', [])


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
        self._commands = list(COMMAND_ALIASES.keys()) + [alias for aliases in COMMAND_ALIASES.values() for alias in aliases]
        self._commands = sorted(set(self._commands))
    
    def get_completions(self, document: Document, complete_event: CompleteEvent) -> List[Completion]:
        """Generate completions based on current input context."""
        text_before_cursor = document.text_before_cursor
        word_before_cursor = document.text_before_cursor.lstrip()
        word = document.current_line_before_cursor.lstrip().rsplit(' ', 1)[-1]
        
        command, args = _parse_command_line(text_before_cursor)
        
        # Command completion (no args typed yet)
        if len(args) == 0:
            for cmd in self._commands:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))
            return
        
        # Context-specific completion for arguments
        if command in ['use', 'load', 'save']:
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
        
        elif command in ['set', 'unset']:
            # First arg: variable name completion
            if len(args) == 1:
                vars = _get_variable_names(self.template_def)
                for var in vars:
                    if var.startswith(word):
                        yield Completion(var, start_position=-len(word))
            elif command == 'set' and len(args) == 2:
                # Second arg: variable options completion
                var_name = args[0]
                options = _get_variable_options(self.template_def, var_name)
                for opt in options:
                    if opt.startswith(word):
                        yield Completion(opt, start_position=-len(word))
        
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