"""
Interactive Shell for Flowy

Metasploit-inspired CLI with tab completion, command aliases, rich output, and full integration
with all core components (StateManager, SaveFileManager, TemplateParser, TemplateRenderer,
HistoryLogger, ModuleLoader).

Supports both interactive mode and quick launch mode for programmatic command execution.
"""

import sys
import os
import shlex
import subprocess
import re
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import ANSI

import colorama
from colorama import Fore, Back, Style as ColoramaStyle

from configuration import (
    BANNER_ASCII, PROMPT_TEMPLATE, COMMAND_ALIASES, SHOW_CONFIG_ON_STARTUP,
    SHOW_UNDEFINED_SUMMARY, TEMPLATES_DIR, SAVES_DIR, STATE_FILE, HISTORY_FILE,
    VERSION, APP_NAME, MODULES_DIR, VALIDATE_ON_STARTUP, DEFAULT_EDITOR,
    SHOW_GLOBALS_IN_LS, PROMPT_STYLE, COLOR_PROMPT_TEMPLATE, COLOR_ERROR,
    COLOR_ERROR_BOLD, COLOR_SUCCESS, COLOR_INFO, COLOR_WARNING, COLOR_CANCELLED,
    COLOR_HELP_COMMAND, COLOR_HELP_BOLD, COLOR_TIP, COLOR_VAR_GLOBAL,
    COLOR_VAR_GENERAL, COLOR_VAR_TEMPLATE, COLOR_VAR_DEFAULT, COLOR_VAR_UNSET,
    COLOR_VALIDATION_SUCCESS, COLOR_VALIDATION_ERROR, COLOR_GOODBYE, COLOR_NO_DATA,
    COLOR_SECTION_HEADER
)

from state_manager import state_manager
from save_file_manager import save_file_manager
from template_parser import TemplateParser, TemplateNotFoundError, TemplateParseError, TemplateDefinition
from template_renderer import template_renderer, RenderResult, ColorFormatter
from history_logger import history_logger
from shell_completers import ShellCompleter, _get_template_files, _get_save_files
from display_manager import display_manager
from file_validator import FileValidator, ValidationResult


class InteractiveShell:
    """Main interactive shell orchestrating all components."""
    
    def __init__(self, restore_on_start: bool = False):
        self.template_parser = TemplateParser(TEMPLATES_DIR)
        self.renderer = template_renderer
        self.display_manager = display_manager
        self.color_formatter = ColorFormatter()
        self.file_validator = FileValidator(TEMPLATES_DIR, SAVES_DIR)
        self.current_template: Optional['TemplateDefinition'] = None
        self.current_save_path: Optional[str] = None
        self.restore_on_start = restore_on_start

        # Completer with current template state
        self.completer = ShellCompleter()

        # Prompt session with custom style
        style = Style.from_dict(PROMPT_STYLE)

        self.session = PromptSession(
            style=style,
            completer=self.completer,
            complete_while_typing=True,
        )
    
    def start(self):
        """Main entry point - display banner and start command loop."""
        self.display_banner()
        if SHOW_CONFIG_ON_STARTUP:
            self.display_configuration()

        if VALIDATE_ON_STARTUP:
            self._run_validation(show_success=False)

        # Handle restore flag
        if not self.restore_on_start:
            # Default behavior: backup existing state and start fresh
            state_manager.backup_state()
            state_manager.clear_state()
        else:
            # Restore mode: explicitly load existing state
            try:
                state_manager._load_state()
            except Exception:
                pass  # Missing or corrupted state file - start fresh

            template_path = state_manager.get_current_template()
            if template_path:
                try:
                    self.current_template = self.template_parser.parse(template_path)
                    self.completer.update_template(self.current_template)
                    print(self.color_formatter.format(f"[{COLOR_SUCCESS}]Restored session: {template_path}[/{COLOR_SUCCESS}]"))
                except Exception:
                    pass  # Ignore corrupted template on startup

        self.run()
    
    def quick_launch(self, template_path: str, save_path: Optional[str] = None):
        """
        Quick launch mode - programmatically execute commands before interactive loop.

        Args:
            template_path: Path to template file to load
            save_path: Optional path to save file for variables

        This method:
        1. Displays banner and configuration
        2. Handles restore_on_start flag semantics (backup/clear or restore)
        3. Loads the template (and save file if provided)
        4. Auto-renders if save file is provided
        5. Drops into interactive mode
        """
        # Display startup information
        self.display_banner()
        if SHOW_CONFIG_ON_STARTUP:
            self.display_configuration()

        if VALIDATE_ON_STARTUP:
            self._run_validation(show_success=False)

        # Handle restore flag (same semantics as start())
        if not self.restore_on_start:
            # Default behavior: backup existing state and start fresh
            state_manager.backup_state()
            state_manager.clear_state()
        else:
            # Restore mode: explicitly load existing state
            try:
                state_manager._load_state()
            except Exception:
                pass  # Missing or corrupted state file - start fresh

            existing_template = state_manager.get_current_template()
            if existing_template:
                try:
                    self.current_template = self.template_parser.parse(existing_template)
                    self.completer.update_template(self.current_template)
                    print(self.color_formatter.format(f"[{COLOR_SUCCESS}]Restored session: {existing_template}[/{COLOR_SUCCESS}]"))
                except Exception:
                    pass  # Ignore corrupted template on startup

        try:
            # Execute use command with template (and optionally save)
            if save_path:
                # Use command with both template and save triggers auto-render
                print(self.color_formatter.format(f"[{COLOR_INFO}]Quick launch: Loading {template_path} with {save_path}[/{COLOR_INFO}]"))
                self.cmd_use([template_path, save_path])
            else:
                # Just load the template
                print(self.color_formatter.format(f"[{COLOR_INFO}]Quick launch: Loading {template_path}[/{COLOR_INFO}]"))
                self.cmd_use([template_path])

            print()  # Add blank line before interactive prompt

        except Exception as e:
            # Display error but continue to interactive mode
            self._display_error(f"Quick launch failed: {e}")
            print(self.color_formatter.format(f"[{COLOR_WARNING}]Entering interactive mode...[/{COLOR_WARNING}]\n"))

        # Enter interactive command loop
        self.run()
    
    def display_banner(self):
        """Display ASCII art banner."""
        banner = BANNER_ASCII.format(version=VERSION)
        print(banner)
    
    def display_configuration(self):
        """Display current configuration paths."""
        config_text = f"""[{COLOR_INFO}]Configuration:[/{COLOR_INFO}]
  Templates: {TEMPLATES_DIR}
  Saves:     {SAVES_DIR}
  Modules:   {MODULES_DIR}
  State:     {STATE_FILE}
  History:   {HISTORY_FILE}
"""
        formatted_text = self.color_formatter.format(config_text)
        print(self.display_manager.wrap_text(formatted_text))
    
    def run(self):
        """Main command loop."""
        try:
            while True:
                prompt = self._get_prompt()
                try:
                    with patch_stdout():
                        user_input = self.session.prompt(prompt)
                except KeyboardInterrupt:
                    print(self.color_formatter.format(f"\n[{COLOR_CANCELLED}]Command cancelled.[/{COLOR_CANCELLED}]"))
                    continue
                
                if not user_input.strip():
                    continue
                
                self._handle_command(user_input)
                
        except EOFError:
            self._exit()
    
    def _get_prompt(self) -> str:
        """Generate dynamic prompt."""
        if self.current_template:
            template_path = self.current_template.relative_path
            if template_path.endswith('.template'):
                display_name = template_path[:-len('.template')]
            else:
                display_name = template_path
            template_part = f" ([{COLOR_PROMPT_TEMPLATE}]{display_name}[/{COLOR_PROMPT_TEMPLATE}])"
        else:
            template_part = ""
        return ANSI(self.color_formatter.format(PROMPT_TEMPLATE.format(template=template_part)))
    
    def _handle_command(self, user_input: str):
        """Parse and dispatch command."""
        # Log before execution
        history_logger.log_command(user_input)
        
        command, args = self._parse_arguments(user_input)
        if not command:
            return
        
        # Resolve aliases
        command = self._resolve_alias(command)
        
        try:
            handler = getattr(self, f'cmd_{command}', None)
            if handler:
                handler(args)
            else:
                self._display_error(f"Unknown command: {command}")
        except Exception as e:
            self._display_error(f"Command failed: {e}")
    
    def _parse_arguments(self, text: str) -> tuple[str, list[str]]:
        """Parse command and arguments with quote handling."""
        try:
            parts = shlex.split(text)
            return parts[0], parts[1:]
        except ValueError as e:
            self._display_error(f"Parse error: {e}")
            return '', []
    
    def _resolve_alias(self, command: str) -> str:
        """Resolve command alias to canonical name."""
        for canonical, aliases in COMMAND_ALIASES.items():
            if command in aliases:
                return canonical
        return command
    
    def cmd_use(self, args: list[str]):
        """Load template (optionally with save file)."""
        if not args:
            self._display_error("Usage: use <template_path> [save_path]")
            return
        
        template_path = args[0]
        save_path = args[1] if len(args) > 1 else None
        
        # Delegate extension resolution to TemplateParser
        try:
            self.current_template = self.template_parser.parse(template_path)
        except TemplateNotFoundError as e:
            self._display_error(f"Template not found: {e}")
            return
        except TemplateParseError as e:
            self._display_error(f"Template parse error: {e}")
            return
        
        # Use canonical path from parsed template
        canonical_path = self.current_template.relative_path
        self.completer.update_template(self.current_template)
        state_manager.set_template(canonical_path)

        # Strip .template extension for display (only if it's the suffix)
        if canonical_path.endswith('.template'):
            display_name = canonical_path[:-len('.template')]
        else:
            display_name = canonical_path
        self._display_success(f"Loaded: {display_name}")
        
        if save_path:
            self.cmd_load([save_path])
            if self.current_template:
                self.cmd_render([])
    
    def cmd_push(self, args: list[str]):
        """Load a new template while preserving current variables.
        
        Args:
            args: Template name to load
        """
        # Validate that a template name argument is provided
        if not args:
            self._display_error("Usage: push <template>")
            return
        
        template_name = args[0]
        
        # Capture current variables before loading new template
        captured_variables = state_manager.get_all_variables()
        
        # Parse and load the new template
        try:
            self.current_template = self.template_parser.parse(template_name)
            canonical_path = self.current_template.relative_path
            
            # Update the completer with the new template
            self.completer.update_template(self.current_template)
            
            # Set the new template in state manager
            state_manager.set_template(canonical_path)
            
            # Restore the captured variables
            state_manager.set_variables(captured_variables)
            
            # Display success message
            display_name = canonical_path.replace('.template', '')
            self._display_success(f"Pushed template: {display_name}")
            print(self.color_formatter.format(f"[{COLOR_INFO}]Preserved {len(captured_variables)} variable(s)[/{COLOR_INFO}]"))
            
        except TemplateNotFoundError as e:
            self._display_error(f"Template not found: {e}")
            return
        except TemplateParseError as e:
            self._display_error(f"Template error: {e}")
            return
    
    def cmd_load(self, args: list[str]):
        """Load variables from save file."""
        if not self.current_template:
            self._display_error("Load template first with 'use'")
            return

        if not args:
            self._display_error("Usage: load <save_path>")
            return

        save_path = args[0]

        # Capture current variable state before loading
        current_variables = state_manager.get_all_variables()

        # Delegate extension resolution to SaveFileManager
        try:
            variables = save_file_manager.load_variables_for_template(
                save_path, self.current_template.relative_path
            )
        except Exception as e:
            self._display_error(f"Failed to load save file: {e}")
            return

        # Use save path as-is (no extension modification)
        state_manager.set_variables(variables)
        self.current_save_path = save_path

        # Also load global variables from the same save file
        try:
            save_data = save_file_manager.load(save_path)
            global_vars = save_data.get_global_variables()
            if global_vars:
                state_manager.set_global_variables(global_vars)
        except Exception:
            pass  # Ignore errors loading globals

        # Build comparison table
        headers = ["Variable", "Current Value", "Loaded Value"]
        rows = []

        for var_name, loaded_value in variables.items():
            current_value = current_variables.get(var_name)
            current_display = f'"{current_value}"' if current_value is not None else "<not set>"
            loaded_display = f'"{loaded_value}"'

            rows.append([var_name, current_display, loaded_display])

        # Handle empty variables case
        if not rows:
            self._display_success(f"Loaded save file: {save_path} (no variables found)")
            return

        # Display the comparison table with wrapping
        table = self._format_table(headers, rows)
        wrapped_table = self.display_manager.wrap_text(table)
        print(wrapped_table)

        # Add success message
        self._display_success(f"Loaded save file: {save_path}")

    def cmd_list(self, args: list[str]):
        """List all sections from a save file."""
        if not args:
            self._display_error("Usage: list <save_path>")
            return

        save_path = args[0]

        try:
            sections = save_file_manager.get_template_sections(save_path)
        except Exception as e:
            self._display_error(f"Failed to list sections: {e}")
            return

        if not sections:
            print(self.color_formatter.format(f"[{COLOR_WARNING}]No template sections found in save file: {save_path}[/{COLOR_WARNING}]"))
            return

        # Display each section name wrapped in square brackets with cyan color
        for section in sections:
            formatted_section = self.color_formatter.format(f"[{COLOR_INFO}][{section}][/{COLOR_INFO}]")
            print(formatted_section)

    def cmd_set(self, args: list[str]):
        """Set variable value."""
        # Parse -g or --global flag
        is_global = False
        filtered_args = []
        for arg in args:
            if arg in ('-g', '--global'):
                is_global = True
            else:
                filtered_args.append(arg)

        # When setting globals, we don't need a template loaded
        if not is_global and not self.current_template:
            self._display_error("Load template first with 'use'")
            return

        if len(filtered_args) < 2:
            self._display_error("Usage: set [-g|--global] <variable> <value>")
            return

        var_name = filtered_args[0]
        value = ' '.join(filtered_args[1:])

        # Validate variable name against template (skip for global variables)
        if not is_global and var_name not in self.current_template.variables:
            self._display_error(f"Unknown variable: {var_name}")
            return

        try:
            if is_global:
                # Get old value for global variable
                old_value = state_manager.get_global_variable(var_name)
                old_display = f'"{old_value}"' if old_value is not None else "<not set>"

                # Set the global variable
                state_manager.set_global_variable(var_name, value)

                # Display success message
                print(self.color_formatter.format(f"  [{COLOR_INFO}]{var_name}[/{COLOR_INFO}] from {old_display} to \"{value}\""))
            else:
                # Get old value before setting new one
                old_value = state_manager.get_variable(var_name)

                # Set the new value
                state_manager.set_variable(var_name, value)

                # Format old value for display
                old_display = f'"{old_value}"' if old_value is not None else "<not set>"

                # Display indented transition message using display helper
                message = f"  {var_name} from {old_display} to \"{value}\""
                wrapped_message = self.display_manager.wrap_text(message)
                print(wrapped_message)
        except Exception as e:
            self._display_error(f"Failed to set variable: {e}")
    
    def cmd_unset(self, args: list[str]):
        """Unset variable."""
        # Parse -g or --global flag
        is_global = False
        filtered_args = []
        for arg in args:
            if arg in ('-g', '--global'):
                is_global = True
            else:
                filtered_args.append(arg)

        # When unsetting globals, we don't need a template loaded
        if not is_global and not self.current_template:
            self._display_error("Load template first with 'use'")
            return

        if not filtered_args:
            self._display_error("Usage: unset [-g|--global] <variable>")
            return

        var_name = filtered_args[0]

        try:
            if is_global:
                # Check if global variable exists
                if state_manager.get_global_variable(var_name) is None:
                    self._display_error(f"Global variable '{var_name}' not found")
                    return

                # Remove the global variable
                state_manager.unset_global_variable(var_name)
                self._display_success(f"Removed global variable: {var_name}")
            else:
                # Check if template variable exists before unsetting
                current_value = state_manager.get_variable(var_name)
                if current_value is None and var_name not in self.current_template.variables:
                    self._display_error(f"Variable '{var_name}' is not set and not defined in template")
                    return

                # Unset template-specific variable
                state_manager.unset_variable(var_name)
                self._display_success(f"Unset {var_name}")
        except Exception as e:
            self._display_error(f"Failed to unset variable: {e}")
    
    def cmd_setglobal(self, args: list[str]):
        """Set a global variable that applies across all templates."""
        if len(args) < 2:
            self._display_error("Usage: setglobal <variable> <value>")
            return
        
        var_name = args[0]
        value = ' '.join(args[1:])
        
        # Get old value for display
        old_value = state_manager.get_global_variable(var_name)
        old_display = f'"{old_value}"' if old_value is not None else "<not set>"
        
        # Set the global variable
        state_manager.set_global_variable(var_name, value)
        
        # Display success message
        print(self.color_formatter.format(f"  [{COLOR_INFO}]{var_name}[/{COLOR_INFO}] from {old_display} to \"{value}\""))
    
    def cmd_unsetglobal(self, args: list[str]):
        """Remove a global variable."""
        if not args:
            self._display_error("Usage: unsetglobal <variable>")
            return
        
        var_name = args[0]
        
        # Check if variable exists
        if state_manager.get_global_variable(var_name) is None:
            self._display_error(f"Global variable '{var_name}' not found")
            return
        
        # Remove the global variable
        state_manager.unset_global_variable(var_name)
        self._display_success(f"Removed global variable: {var_name}")
    
    def cmd_listglobals(self, args: list[str]):
        """Display all global variables in a formatted table."""
        global_vars = state_manager.get_all_global_variables()

        if not global_vars:
            print(self.color_formatter.format(f"[{COLOR_WARNING}]No global variables set.[/{COLOR_WARNING}]"))
            return
        
        print(self.color_formatter.format(f"\n[{COLOR_INFO}][bold]Global Variables:[/bold][/{COLOR_INFO}]\n"))
        
        # Format as table
        headers = ["Variable", "Value"]
        rows = []
        for var_name, value in sorted(global_vars.items()):
            # Format value for display
            if isinstance(value, str):
                display_value = f'"{value}"'
            else:
                display_value = str(value)
            
            # Wrap long values
            wrapped_value = self.display_manager.wrap_text(display_value, width=60)
            rows.append([var_name, wrapped_value])
        
        # Display table
        table_output = self._format_table(headers, rows)
        print(table_output)
    
    def cmd_save(self, args: list[str]):
        """Save current variables to file."""
        # Parse optional --globals or -g flag
        save_globals = False
        filtered_args = []
        for arg in args:
            if arg in ('--globals', '-g'):
                save_globals = True
            else:
                filtered_args.append(arg)

        # When saving globals, we don't need a template loaded
        if not save_globals and not self.current_template:
            self._display_error("Load template first with 'use'")
            return

        # Handle default save file prompt when no args provided
        if not filtered_args:
            if self.current_save_path:
                try:
                    response = input(f"Save to {self.current_save_path}? (Y/n): ")
                    response = response.strip().lower()
                    # Accept empty string or 'y' as confirmation
                    if response in ("", "y"):
                        save_path = self.current_save_path
                    elif response in ("n",):
                        self._display_error("Save operation cancelled.")
                        return
                    else:
                        # Invalid input - treat as cancellation
                        self._display_error("Save operation cancelled.")
                        return
                except (EOFError, KeyboardInterrupt):
                    print()  # New line after Ctrl+C/Ctrl+D
                    self._display_error("Save operation cancelled.")
                    return
            else:
                self._display_error("Usage: save <save_path> [--globals|-g]")
                return
        else:
            save_path = filtered_args[0]

        # Check if file exists and prompt for merge confirmation
        full_path = os.path.normpath(os.path.join(SAVES_DIR, save_path))
        if os.path.exists(full_path):
            try:
                response = input("Save file exists. Merge variables? (Y/n): ")
                response = response.strip().lower()
                # Accept empty string or 'y' as confirmation
                if response in ("", "y"):
                    pass  # Proceed with saving
                elif response in ("n",):
                    self._display_error("Save operation cancelled.")
                    return
                else:
                    # Invalid input - treat as cancellation
                    self._display_error("Save operation cancelled.")
                    return
            except (EOFError, KeyboardInterrupt):
                print()  # New line after Ctrl+C/Ctrl+D
                self._display_error("Save operation cancelled.")
                return

        try:
            if save_globals:
                # Save global variables to [globals] section
                global_variables = state_manager.get_all_global_variables()
                save_file_manager.save_variables(save_path, global_variables, is_global=True)

                # Display saved global variables
                for var_name, value in global_variables.items():
                    print(f"  Saved [globals] {var_name} = {value}")

                self._display_success(f"Saved global variables to: {save_path}")
            else:
                # Save template-specific variables
                variables = state_manager.get_all_variables()
                save_file_manager.save_variables(save_path, variables, self.current_template.relative_path)

                # Display saved variables
                section = self.current_template.relative_path
                for var_name, value in variables.items():
                    print(f"  Saved [{section}] {var_name} = {value}")

                self._display_success(f"Saved variables to: {save_path}")
        except Exception as e:
            self._display_error(f"Failed to save: {e}")
    
    def cmd_render(self, args: list[str]):
        """Render current template."""
        if not self.current_template:
            self._display_error("Load template first with 'use'")
            return
        
        try:
            variables = state_manager.get_all_variables()
            result = self.renderer.render(
                self.current_template, variables, self.current_save_path
            )
            
            # Wrap output to terminal width
            wrapped_output = self.display_manager.wrap_text(result.output)
            print(wrapped_output)

            if not result.success:
                print(self.color_formatter.format(f"\n[{COLOR_ERROR}]{result.format_error()}[/{COLOR_ERROR}]"))

            if result.undefined_variables and SHOW_UNDEFINED_SUMMARY:
                print(self.color_formatter.format(f"\n[{COLOR_ERROR}]Undefined variables: {', '.join(result.undefined_variables)}[/{COLOR_ERROR}]"))
                
        except Exception as e:
            self._display_error(f"Render failed: {e}")
    
    def cmd_ls(self, args: list[str]):
        """List current variables."""
        if not self.current_template:
            self._display_error("Load template first with 'use'")
            return
        
        self._display_variables_table()
    
    def cmd_help(self, args: list[str]):
        """Display help information for commands."""
        if not args:
            # Display general help overview
            self._display_general_help()
        else:
            # Display detailed help for specific command
            command = self._resolve_alias(args[0])
            self._display_command_help(command)
    
    def _get_aliases_for(self, command: str) -> str:
        """Get formatted alias string for a command."""
        aliases = COMMAND_ALIASES.get(command, [])
        return ', '.join(aliases) if aliases else '-'
    
    def _display_general_help(self):
        """Display overview of all available commands."""
        print(self.color_formatter.format(f"\n[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Available Commands:[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]\n"))

        headers = ["Command", "Aliases", "Syntax", "Description"]
        rows = [
            ["use", self._get_aliases_for('use'), "use <template> [save]", "Load template (+ optional auto-render)"],
            ["push", self._get_aliases_for('push'), "push <template>", "Load template while preserving variables"],
            ["load", self._get_aliases_for('load'), "load <save>", "Load variables from save file"],
            ["list", self._get_aliases_for('list'), "list <save>", "Show sections in save file"],
            ["set", self._get_aliases_for('set'), "set [-g] <var> <value>", "Set variable value (-g for global)"],
            ["unset", self._get_aliases_for('unset'), "unset [-g] <var>", "Remove variable (-g for global)"],
            ["setglobal", self._get_aliases_for('setglobal'), "setglobal <var> <value>", "Set global variable"],
            ["unsetglobal", self._get_aliases_for('unsetglobal'), "unsetglobal <var>", "Remove global variable"],
            ["listglobals", self._get_aliases_for('listglobals'), "listglobals", "Show all global variables"],
            ["save", self._get_aliases_for('save'), "save <save>", "Save current variables to file"],
            ["render", self._get_aliases_for('render'), "render", "Render current template"],
            ["ls", self._get_aliases_for('ls'), "ls", "Show variables table"],
            ["edit", self._get_aliases_for('edit'), "edit <template|save>", "Open template or save file in editor"],
            ["revert", self._get_aliases_for('revert'), "revert", "Toggle previous template state"],
            ["restore", self._get_aliases_for('restore'), "restore", "Restore state from before last program start"],
            ["validate", self._get_aliases_for('validate'), "validate", "Check for duplicate filenames"],
            ["reload", self._get_aliases_for('reload'), "reload", "Reload templates and saves dynamically"],
            ["help", self._get_aliases_for('help'), "help [command]", "Show this help or command details"],
            ["exit", self._get_aliases_for('exit'), "exit", "Exit the shell"],
        ]

        table = self._format_table(headers, rows)
        print(table)
        print(self.color_formatter.format(f"\n[{COLOR_TIP}]Tip: Type 'help <command>' for detailed information about a specific command.[/{COLOR_TIP}]\n"))
    
    def _display_command_help(self, command: str):
        """Display detailed help for a specific command."""
        # Get aliases dynamically
        aliases_str = self._get_aliases_for(command)
        
        help_text = {
            'use': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: use[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Aliases:[/{COLOR_HELP_BOLD}] {self._get_aliases_for('use')}
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  use <template_path> [save_path]

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Load a template file for rendering. Optionally provide a save file path as the
second argument to automatically load variables and render the template.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  use example              # Load example.template
  use example.template     # Load with full extension
  use reports/monthly      # Load from subdirectory
  use example client       # Load template + save file, auto-render

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] load, render, ls
""",
            'load': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: load[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  load <save_path>

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Load variables from a save file for the currently loaded template.
The save file should contain a section matching the template name.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  load client              # Load from save file named 'client' in SAVES_DIR
  load projects/demo       # Load from subdirectory (respects paths as-is)

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] use, save, set
""",
            'list': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: list[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  list <save_path>

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Display all sections (in square brackets) from a save file. Each section typically
corresponds to a different template's saved variables.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  list client              # Show all sections in 'client' save file
  list projects/demo       # Show sections from subdirectory

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] load, save, use
""",
            'set': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: set[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  set [-g|--global] <variable> <value>

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Set a variable value for the current template or set a global variable that applies
across all templates. Template variables must be defined in the template's VARS section.
Global variables can have any name and don't require a template to be loaded.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  set client_name "Acme Corp"       # Set template-specific variable
  set report_type monthly           # Set template-specific variable
  set -g client_name "Acme Corp"    # Set global variable
  set --global api_key "secret123"  # Set global variable (long form)

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] unset, setglobal, ls, render
""",
            'unset': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: unset[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  unset [-g|--global] <variable>

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Remove a template-specific variable assignment or remove a global variable.
For template variables, this reverts to the template's default value if specified.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  unset client_name           # Unset template-specific variable
  unset report_type           # Unset template-specific variable
  unset -g client_name        # Remove global variable
  unset --global api_key      # Remove global variable (long form)

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] set, unsetglobal, ls
""",
            'save': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: save[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  save <save_path>

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Save the current variable values to a save file. Creates subdirectories as needed.
The variables are saved in a section matching the current template name.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  save client              # Create or update file 'client' in SAVES_DIR
  save projects/demo       # Save to subdirectory (respects paths as-is)

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] load, set
""",
            'render': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: render[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Aliases:[/{COLOR_HELP_BOLD}] {self._get_aliases_for('render')}
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  render

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Render the current template with all set variables. Output is automatically
wrapped to fit your terminal width. Undefined variables are highlighted in red.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  render
  r        # Using alias

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] use, set, ls
""",
            'ls': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: ls[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Aliases:[/{COLOR_HELP_BOLD}] {self._get_aliases_for('ls')}
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  ls

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Display a table of all variables defined in the current template, showing their
current values, descriptions, defaults, and available options.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  ls
  ll       # Using alias

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] set, unset
""",
            'revert': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: revert[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  revert

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Revert to the previous template state. Running revert again toggles back to the
latest state. Skips duplicate template states in history.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  revert   # Go back to previous template
  revert   # Toggle back to latest

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] use
""",
            'restore': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: restore[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Aliases:[/{COLOR_HELP_BOLD}] {self._get_aliases_for('restore')}
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  restore

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Restore state from before the last program start. When the program starts without
the --restore flag, it backs up the current state and starts fresh. This command
allows you to restore that backup at any time during the session.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  restore   # Restore state from before last program start
  res       # Using alias

[{COLOR_HELP_BOLD}]Use Cases:[/{COLOR_HELP_BOLD}]
- You started fresh but want to recover previous work
- Accidentally started without --restore flag
- Want to switch back to previous session mid-work

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] revert, use
""",
            'validate': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: validate[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  validate

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Check templates/ and saves/ directories for duplicate filenames (ignoring
extensions) within the same directory. Duplicates across different subdirectories
are allowed and will not be reported.

This same validation can be run automatically on startup by setting
VALIDATE_ON_STARTUP = True in configuration.py.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  validate   # Check for duplicate filenames

[{COLOR_HELP_BOLD}]Use Cases:[/{COLOR_HELP_BOLD}]
- Ensure no naming conflicts before creating new templates/saves
- Verify directory structure after bulk file operations
- Troubleshoot unexpected file loading behavior

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] use, load, save
""",
            'reload': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: reload[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  reload

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Dynamically reload all template and save files without restarting the program.
Clears all internal caches (template renderer, Jinja2 environments, and file lists)
so that any changes to template or save files are immediately available.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  reload   # Refresh all templates and saves

[{COLOR_HELP_BOLD}]Use Cases:[/{COLOR_HELP_BOLD}]
- You edited a template file and want to see changes immediately
- You added new template or save files to the directories
- You modified save file contents and want to reload them
- You want to clear cached Jinja2 environments after template changes

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] use, load, save, validate
""",
            'edit': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: edit[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Aliases:[/{COLOR_HELP_BOLD}] {self._get_aliases_for('edit')}
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  edit <template_path|save_path>

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Open a template or save file in the configured editor. The command first attempts
to resolve the path as a template file, then falls back to save files if not found.
The editor is launched with the full system path to the file.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  edit example              # Open example.template in editor
  edit example.template     # Open with full extension
  edit reports/monthly      # Open from subdirectory
  edit client               # Open save file named 'client'
  edit projects/demo        # Open save from subdirectory

[{COLOR_HELP_BOLD}]Note:[/{COLOR_HELP_BOLD}]
Editor command is configured via DEFAULT_EDITOR in configuration.py or FLOWY_EDITOR
environment variable (current: {DEFAULT_EDITOR})

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] use, load, save, validate
""",
            'help': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: help[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Aliases:[/{COLOR_HELP_BOLD}] {self._get_aliases_for('help')}
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  help [command]

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Display help information. Without arguments, shows an overview of all commands.
With a command name, shows detailed help for that specific command.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  help         # Show all commands
  help use     # Detailed help for 'use'
  ?            # Using alias

[{COLOR_HELP_BOLD}]Related:[/{COLOR_HELP_BOLD}] All commands
""",
            'exit': f"""
[{COLOR_HELP_COMMAND}][{COLOR_HELP_BOLD}]Command: exit[/{COLOR_HELP_BOLD}][/{COLOR_HELP_COMMAND}]
[{COLOR_HELP_BOLD}]Syntax:[/{COLOR_HELP_BOLD}]  exit

[{COLOR_HELP_BOLD}]Description:[/{COLOR_HELP_BOLD}]
Exit the interactive shell. You can also use Ctrl+D to exit.

[{COLOR_HELP_BOLD}]Examples:[/{COLOR_HELP_BOLD}]
  exit
""",
        }
        
        if command in help_text:
            print(self.color_formatter.format(help_text[command]))
        else:
            self._display_error(f"Unknown command: {command}")
            print(self.color_formatter.format(f"[{COLOR_WARNING}]Type 'help' to see all available commands.[/{COLOR_WARNING}]"))
    
    def _display_variables_table(self):
        """Display formatted variables table grouped by template sections with color-coded values."""
        # Check if template is loaded
        if not self.current_template:
            print(self.color_formatter.format(f"[{COLOR_WARNING}]No template loaded.[/{COLOR_WARNING}]"))
            return

        # Get main template path
        template_path = self.current_template.relative_path

        # Normalize template path for section header (strip .template extension)
        normalized_path = template_path.replace('.template', '') if template_path.endswith('.template') else template_path

        # Display main template section header
        if COLOR_SECTION_HEADER:
            print(self.color_formatter.format(f"\n[{COLOR_SECTION_HEADER}][{normalized_path}][/{COLOR_SECTION_HEADER}]"))
        else:
            print(self.color_formatter.format(f"\n[{normalized_path}]"))

        # Build table for main template variables
        headers = ["Name", "Current Value", "Description", "Default", "Options"]

        if not self.current_template.variables:
            print(self.color_formatter.format(f"[{COLOR_WARNING}]No variables defined.[/{COLOR_WARNING}]"))
        else:
            rows = []
            for var_name, var_def in self.current_template.variables.items():
                # Determine variable source and value
                source, value = self._determine_variable_source(var_name, template_path, self.current_template)

                # Format Current Value with color
                if source == 'unset':
                    colored_current_value = ""
                else:
                    color = self._get_value_color(source)
                    if isinstance(value, str):
                        display_value = f'"{value}"'
                    else:
                        display_value = str(value)

                    if color:
                        colored_current_value = self.color_formatter.format(f"[{color}]{display_value}[/{color}]")
                    else:
                        colored_current_value = display_value

                # Format Default value with light grey color
                if var_def.default is not None:
                    default_value = self.color_formatter.format(f"[{COLOR_VAR_DEFAULT}]{var_def.default}[/{COLOR_VAR_DEFAULT}]")
                else:
                    default_value = "-"

                # Format options
                options = ", ".join(var_def.options) if var_def.options else "-"

                rows.append([
                    var_name,
                    colored_current_value,
                    var_def.description or "-",
                    default_value,
                    options
                ])

            print(self._format_table(headers, rows))

        # Parse included subtemplates
        subtemplates = self._parse_included_subtemplates(self.current_template.template_content)

        # Display each subtemplate section
        for subtemplate_path in subtemplates:
            try:
                # Try to parse subtemplate
                subtemplate_def = self.template_parser.parse(subtemplate_path)

                # Normalize subtemplate path for section header
                normalized_subtemplate_path = subtemplate_path.replace('.template', '') if subtemplate_path.endswith('.template') else subtemplate_path

                # Display section header
                if COLOR_SECTION_HEADER:
                    print(self.color_formatter.format(f"\n[{COLOR_SECTION_HEADER}][{normalized_subtemplate_path}][/{COLOR_SECTION_HEADER}]"))
                else:
                    print(self.color_formatter.format(f"\n[{normalized_subtemplate_path}]"))

                # Check if subtemplate has variables
                if not subtemplate_def.variables:
                    print(self.color_formatter.format(f"[{COLOR_WARNING}]No variables defined.[/{COLOR_WARNING}]"))
                else:
                    rows = []
                    for var_name, var_def in subtemplate_def.variables.items():
                        # Determine variable source and value
                        source, value = self._determine_variable_source(var_name, subtemplate_path, subtemplate_def)

                        # Format Current Value with color
                        if source == 'unset':
                            colored_current_value = ""
                        else:
                            color = self._get_value_color(source)
                            if isinstance(value, str):
                                display_value = f'"{value}"'
                            else:
                                display_value = str(value)

                            if color:
                                colored_current_value = self.color_formatter.format(f"[{color}]{display_value}[/{color}]")
                            else:
                                colored_current_value = display_value

                        # Format Default value with light grey color
                        if var_def.default is not None:
                            default_value = self.color_formatter.format(f"[{COLOR_VAR_DEFAULT}]{var_def.default}[/{COLOR_VAR_DEFAULT}]")
                        else:
                            default_value = "-"

                        # Format options
                        options = ", ".join(var_def.options) if var_def.options else "-"

                        rows.append([
                            var_name,
                            colored_current_value,
                            var_def.description or "-",
                            default_value,
                            options
                        ])

                    print(self._format_table(headers, rows))

            except (TemplateNotFoundError, TemplateParseError):
                # Skip this subtemplate if it can't be parsed
                continue

    def _parse_included_subtemplates(self, template_content: str) -> List[str]:
        """Parse template content to find all included subtemplates.

        Args:
            template_content: The template file content to parse

        Returns:
            List of unique subtemplate paths found in {% include %} statements
        """
        # Pattern to match {% include 'path' %} or {% include "path" %}
        pattern = r"{%\s*include\s+['\"]([^'\"]+)['\"]\s*%}"
        matches = re.findall(pattern, template_content)

        # Return unique paths while preserving order
        seen = set()
        unique_paths = []
        for path in matches:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)

        return unique_paths

    def _determine_variable_source(self, var_name: str, template_path: str,
                                   template_def: Optional['TemplateDefinition'] = None) -> Tuple[str, Any]:
        """Determine the source and value of a variable.

        Args:
            var_name: Name of the variable to check
            template_path: Path of the template being checked
            template_def: Optional TemplateDefinition to use for checking defaults

        Returns:
            Tuple of (source, value) where source is one of:
            'global', 'save_global', 'general', 'template', 'user_set', 'default', 'unset'
        """
        # Use provided template_def or fall back to current_template
        template_to_check = template_def if template_def is not None else self.current_template

        # First, check if user has set the variable in current session (highest priority)
        # This mirrors Layer 6 in _merge_variables
        current_vars = state_manager.get_all_variables()
        if var_name in current_vars:
            return ('user_set', current_vars[var_name])

        # Load save file once if available
        save_data = None
        if self.current_save_path:
            try:
                save_data = save_file_manager.load(self.current_save_path)
            except Exception:
                pass  # Save file doesn't exist or can't be loaded

        # Check save file template-specific section (Layer 5)
        if save_data:
            # Normalize template path (remove .template extension if present)
            normalized_path = template_path.replace('.template', '') if template_path.endswith('.template') else template_path

            # Check normalized path first
            if hasattr(save_data, 'template_sections') and normalized_path in save_data.template_sections:
                template_vars = save_data.template_sections[normalized_path]
                if var_name in template_vars:
                    return ('template', template_vars[var_name])
            # Also check original template_path for backward compatibility (legacy .template sections)
            elif hasattr(save_data, 'template_sections') and template_path in save_data.template_sections:
                template_vars = save_data.template_sections[template_path]
                if var_name in template_vars:
                    return ('template', template_vars[var_name])

        # Check template defaults (Layer 4)
        if template_to_check and var_name in template_to_check.variables:
            var_def = template_to_check.variables[var_name]
            if var_def.default is not None:
                return ('default', var_def.default)

        # Check save file [general] section (Layer 3)
        if save_data and hasattr(save_data, 'general_variables') and var_name in save_data.general_variables:
            return ('general', save_data.general_variables[var_name])

        # Check save file [globals] section (Layer 2)
        if save_data and hasattr(save_data, 'globals_variables') and var_name in save_data.globals_variables:
            return ('save_global', save_data.globals_variables[var_name])

        # Check global variables from state manager (Layer 1, lowest priority)
        global_vars = state_manager.get_all_global_variables()
        if var_name in global_vars:
            return ('global', global_vars[var_name])

        # Variable is unset
        return ('unset', None)

    def _get_value_color(self, source: str) -> str:
        """Get the color code for a variable value based on its source.

        Args:
            source: The source of the variable value

        Returns:
            Color string for use with ColorFormatter
        """
        color_map = {
            'global': COLOR_VAR_GLOBAL,
            'save_global': COLOR_VAR_GLOBAL,  # Save-file [globals] use same color as global
            'general': COLOR_VAR_GENERAL,
            'template': COLOR_VAR_TEMPLATE,
            'user_set': COLOR_VAR_TEMPLATE,
            'default': COLOR_VAR_DEFAULT,
            'unset': COLOR_VAR_UNSET
        }
        return color_map.get(source, '')

    def cmd_revert(self, args: list[str]):
        """Revert to previous template state."""
        try:
            if state_manager.revert():
                template_path = state_manager.get_current_template()
                if template_path:
                    self.current_template = self.template_parser.parse(template_path)
                    self.completer.update_template(self.current_template)
                    self._display_success(f"Reverted to: {template_path}")
                else:
                    self._display_success("Reverted to empty state")
            else:
                self._display_error("No previous state to revert to")
        except Exception as e:
            self._display_error(f"Revert failed: {e}")

    def cmd_restore(self, args: list[str]):
        """Restore state from before last program start."""
        try:
            if state_manager.restore_from_backup():
                template_path = state_manager.get_current_template()
                if template_path:
                    try:
                        self.current_template = self.template_parser.parse(template_path)
                        self.completer.update_template(self.current_template)
                        self._display_success(f"Restored from backup: {template_path}")
                    except Exception as e:
                        # Template load failed - synchronize shell UI with failed state
                        self.current_template = None
                        self.completer.update_template(None)
                        self._display_error(f"Restored state but failed to load template: {e}")
                else:
                    # Empty state - synchronize shell UI
                    self.current_template = None
                    self.completer.update_template(None)
                    self._display_success("Restored to empty state from backup")
            else:
                self._display_error("No backup state available")
        except Exception as e:
            self._display_error(f"Restore failed: {e}")

    def cmd_validate(self, args: list[str]):
        """Validate templates and saves directories for duplicate filenames."""
        self._run_validation(show_success=True)

    def cmd_reload(self, args: list[str]):
        """Reload templates and saves dynamically without restarting."""
        # Clear template renderer caches (environment and loader caches)
        self.renderer.clear_caches()

        # Refresh shell completer's template and save file lists
        self.completer._templates = _get_template_files()
        self.completer._saves = _get_save_files()

        # Display success message
        self._display_success("Reloaded templates, saves, and cleared render cache")

    def cmd_edit(self, args: list[str]):
        """Open template or save file in editor."""
        if not args:
            self._display_error("Usage: edit <template_path|save_path>")
            return

        file_path = args[0]
        full_path = None

        # Try to resolve as template first (without parsing to allow editing broken templates)
        # Try with and without .template extension
        candidate_paths = []
        if file_path.endswith('.template'):
            candidate_paths.append(file_path)
        else:
            candidate_paths.append(file_path + '.template')
            candidate_paths.append(file_path)

        # Check if any template file exists on disk
        template_found = False
        for candidate_path in candidate_paths:
            test_path = os.path.normpath(os.path.join(TEMPLATES_DIR, candidate_path))
            if os.path.exists(test_path):
                full_path = os.path.abspath(test_path)
                template_found = True
                break

        if not template_found:
            # Not a template, try as save file
            save_full_path = os.path.normpath(os.path.join(SAVES_DIR, file_path))
            if os.path.exists(save_full_path):
                full_path = os.path.abspath(save_full_path)
            else:
                # Try with .save extension fallback
                save_full_path_with_ext = save_full_path + '.save'
                if os.path.exists(save_full_path_with_ext):
                    full_path = os.path.abspath(save_full_path_with_ext)
                else:
                    self._display_error(f"File not found in templates or saves: {file_path}")
                    return

        # Launch editor with resolved path
        try:
            # Split editor command to handle arguments (e.g., "code -w")
            editor_tokens = shlex.split(DEFAULT_EDITOR)
            editor_tokens.append(full_path)
            subprocess.run(editor_tokens)
        except FileNotFoundError:
            self._display_error(f"Editor command not found: {DEFAULT_EDITOR}")
        except subprocess.SubprocessError as e:
            self._display_error(f"Failed to launch editor: {e}")

    def _run_validation(self, show_success: bool = True):
        """
        Run file validation and display results.

        Args:
            show_success: Whether to display success message when no duplicates found
        """
        result = self.file_validator.validate()

        if not result.has_duplicates:
            if show_success:
                success_msg = f"No duplicates found. Checked {result.templates_checked} files in templates directory and {result.saves_checked} files in saves directory."
                print(self.color_formatter.format(f"[{COLOR_VALIDATION_SUCCESS}]{success_msg}[/{COLOR_VALIDATION_SUCCESS}]"))
        else:
            # Build table data for duplicates
            headers = ["Directory", "Basename", "Conflicting Files"]
            rows = []

            for dup in result.duplicates:
                rows.append([
                    dup.directory,
                    dup.basename,
                    ", ".join(dup.files)
                ])

            # Display the table
            table_output = self._format_table(headers, rows)
            print(self.color_formatter.format(f"[{COLOR_VALIDATION_ERROR}]{table_output}[/{COLOR_VALIDATION_ERROR}]"))

            # Display summary
            summary = f"Found {result.get_duplicate_count()} duplicate(s) in {result.templates_checked} files in templates directory and {result.saves_checked} files in saves directory"
            print(self.color_formatter.format(f"[{COLOR_VALIDATION_ERROR}]{summary}[/{COLOR_VALIDATION_ERROR}]"))

    def cmd_exit(self, args: list[str]):
        """Exit shell."""
        self._exit()
    
    def _exit(self):
        """Clean exit."""
        print(self.color_formatter.format(f"\n[{COLOR_GOODBYE}]Goodbye![/{COLOR_GOODBYE}]"))
        sys.exit(0)
    
    def _format_table(self, headers: list[str], rows: list[list[str]]) -> str:
        """Format data as aligned table using DisplayManager."""
        return self.display_manager.format_table(headers, rows)
    
    def _display_error(self, message: str):
        """Display formatted error."""
        print(self.color_formatter.format(f"[{COLOR_ERROR_BOLD}][bold]Error:[/bold][/{COLOR_ERROR_BOLD}] [{COLOR_ERROR}]{message}[/{COLOR_ERROR}]"))

    def _display_success(self, message: str):
        """Display formatted success."""
        print(self.color_formatter.format(f"[{COLOR_SUCCESS}]{message}[/{COLOR_SUCCESS}]"))


def main():
    """Entry point for interactive shell."""
    shell = InteractiveShell()
    shell.start()


if __name__ == "__main__":
    main()
