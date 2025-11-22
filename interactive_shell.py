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
from typing import Optional, Dict, Any
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
    SHOW_GLOBALS_IN_LS
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
        style = Style.from_dict({
            'prompt': '#a5a5a5 bold',
        })

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
                    print(self.color_formatter.format(f"[green]Restored session: {template_path}[/green]"))
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
                    print(self.color_formatter.format(f"[green]Restored session: {existing_template}[/green]"))
                except Exception:
                    pass  # Ignore corrupted template on startup

        try:
            # Execute use command with template (and optionally save)
            if save_path:
                # Use command with both template and save triggers auto-render
                print(self.color_formatter.format(f"[cyan]Quick launch: Loading {template_path} with {save_path}[/cyan]"))
                self.cmd_use([template_path, save_path])
            else:
                # Just load the template
                print(self.color_formatter.format(f"[cyan]Quick launch: Loading {template_path}[/cyan]"))
                self.cmd_use([template_path])

            print()  # Add blank line before interactive prompt

        except Exception as e:
            # Display error but continue to interactive mode
            self._display_error(f"Quick launch failed: {e}")
            print(self.color_formatter.format("[yellow]Entering interactive mode...[/yellow]\n"))

        # Enter interactive command loop
        self.run()
    
    def display_banner(self):
        """Display ASCII art banner."""
        banner = BANNER_ASCII.format(version=VERSION)
        print(banner)
    
    def display_configuration(self):
        """Display current configuration paths."""
        config_text = f"""[cyan]Configuration:[/cyan]
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
                    print(self.color_formatter.format("\n[red]Command cancelled.[/red]"))
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
            template_part = f" ([orange]{display_name}[/orange])"
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
            print(self.color_formatter.format(f"[cyan]Preserved {len(captured_variables)} variable(s)[/cyan]"))
            
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
            print(self.color_formatter.format(f"[yellow]No template sections found in save file: {save_path}[/yellow]"))
            return

        # Display each section name wrapped in square brackets with cyan color
        for section in sections:
            formatted_section = self.color_formatter.format(f"[cyan][{section}][/cyan]")
            print(formatted_section)

    def cmd_set(self, args: list[str]):
        """Set variable value."""
        if not self.current_template:
            self._display_error("Load template first with 'use'")
            return

        if len(args) < 2:
            self._display_error("Usage: set <variable> <value>")
            return

        var_name = args[0]
        value = ' '.join(args[1:])

        if var_name not in self.current_template.variables:
            self._display_error(f"Unknown variable: {var_name}")
            return

        try:
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
        if not self.current_template:
            self._display_error("Load template first with 'use'")
            return
        
        if not args:
            self._display_error("Usage: unset <variable>")
            return
        
        var_name = args[0]
        try:
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
        print(self.color_formatter.format(f"  [cyan]{var_name}[/cyan] from {old_display} to \"{value}\""))
    
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
            print(self.color_formatter.format("[yellow]No global variables set.[/yellow]"))
            return
        
        print(self.color_formatter.format("\n[cyan][bold]Global Variables:[/bold][/cyan]\n"))
        
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
                print(self.color_formatter.format(f"\n[red]{result.format_error()}[/red]"))

            if result.undefined_variables and SHOW_UNDEFINED_SUMMARY:
                print(self.color_formatter.format(f"\n[red]Undefined variables: {', '.join(result.undefined_variables)}[/red]"))
                
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
        print(self.color_formatter.format("\n[cyan][bold]Available Commands:[/bold][/cyan]\n"))

        headers = ["Command", "Aliases", "Syntax", "Description"]
        rows = [
            ["use", self._get_aliases_for('use'), "use <template> [save]", "Load template (+ optional auto-render)"],
            ["push", self._get_aliases_for('push'), "push <template>", "Load template while preserving variables"],
            ["load", self._get_aliases_for('load'), "load <save>", "Load variables from save file"],
            ["list", self._get_aliases_for('list'), "list <save>", "Show sections in save file"],
            ["set", self._get_aliases_for('set'), "set <var> <value>", "Set variable value"],
            ["unset", self._get_aliases_for('unset'), "unset <var>", "Remove variable"],
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
        print(self.color_formatter.format("\n[green]Tip: Type 'help <command>' for detailed information about a specific command.[/green]\n"))
    
    def _display_command_help(self, command: str):
        """Display detailed help for a specific command."""
        # Get aliases dynamically
        aliases_str = self._get_aliases_for(command)
        
        help_text = {
            'use': f"""
[cyan][bold]Command: use[/bold][/cyan]
[bold]Aliases:[/bold] {self._get_aliases_for('use')}
[bold]Syntax:[/bold]  use <template_path> [save_path]

[bold]Description:[/bold]
Load a template file for rendering. Optionally provide a save file path as the
second argument to automatically load variables and render the template.

[bold]Examples:[/bold]
  use example              # Load example.template
  use example.template     # Load with full extension
  use reports/monthly      # Load from subdirectory
  use example client       # Load template + save file, auto-render

[bold]Related:[/bold] load, render, ls
""",
            'load': """
[cyan][bold]Command: load[/bold][/cyan]
[bold]Syntax:[/bold]  load <save_path>

[bold]Description:[/bold]
Load variables from a save file for the currently loaded template.
The save file should contain a section matching the template name.

[bold]Examples:[/bold]
  load client              # Load from save file named 'client' in SAVES_DIR
  load projects/demo       # Load from subdirectory (respects paths as-is)

[bold]Related:[/bold] use, save, set
""",
            'list': """
[cyan][bold]Command: list[/bold][/cyan]
[bold]Syntax:[/bold]  list <save_path>

[bold]Description:[/bold]
Display all sections (in square brackets) from a save file. Each section typically
corresponds to a different template's saved variables.

[bold]Examples:[/bold]
  list client              # Show all sections in 'client' save file
  list projects/demo       # Show sections from subdirectory

[bold]Related:[/bold] load, save, use
""",
            'set': """
[cyan][bold]Command: set[/bold][/cyan]
[bold]Syntax:[/bold]  set <variable> <value>

[bold]Description:[/bold]
Set a variable value for the current template. The variable must be defined
in the template's VARS section. Use tab completion to see available variables.

[bold]Examples:[/bold]
  set client_name "Acme Corp"
  set report_type monthly
  set include_charts true

[bold]Related:[/bold] unset, ls, render
""",
            'unset': """
[cyan][bold]Command: unset[/bold][/cyan]
[bold]Syntax:[/bold]  unset <variable>

[bold]Description:[/bold]
Remove a variable assignment, reverting to the template's default value if specified.

[bold]Examples:[/bold]
  unset client_name
  unset report_type

[bold]Related:[/bold] set, ls
""",
            'save': """
[cyan][bold]Command: save[/bold][/cyan]
[bold]Syntax:[/bold]  save <save_path>

[bold]Description:[/bold]
Save the current variable values to a save file. Creates subdirectories as needed.
The variables are saved in a section matching the current template name.

[bold]Examples:[/bold]
  save client              # Create or update file 'client' in SAVES_DIR
  save projects/demo       # Save to subdirectory (respects paths as-is)

[bold]Related:[/bold] load, set
""",
            'render': f"""
[cyan][bold]Command: render[/bold][/cyan]
[bold]Aliases:[/bold] {self._get_aliases_for('render')}
[bold]Syntax:[/bold]  render

[bold]Description:[/bold]
Render the current template with all set variables. Output is automatically
wrapped to fit your terminal width. Undefined variables are highlighted in red.

[bold]Examples:[/bold]
  render
  r        # Using alias

[bold]Related:[/bold] use, set, ls
""",
            'ls': f"""
[cyan][bold]Command: ls[/bold][/cyan]
[bold]Aliases:[/bold] {self._get_aliases_for('ls')}
[bold]Syntax:[/bold]  ls

[bold]Description:[/bold]
Display a table of all variables defined in the current template, showing their
current values, descriptions, defaults, and available options.

[bold]Examples:[/bold]
  ls
  ll       # Using alias

[bold]Related:[/bold] set, unset
""",
            'revert': """
[cyan][bold]Command: revert[/bold][/cyan]
[bold]Syntax:[/bold]  revert

[bold]Description:[/bold]
Revert to the previous template state. Running revert again toggles back to the
latest state. Skips duplicate template states in history.

[bold]Examples:[/bold]
  revert   # Go back to previous template
  revert   # Toggle back to latest

[bold]Related:[/bold] use
""",
            'restore': f"""
[cyan][bold]Command: restore[/bold][/cyan]
[bold]Aliases:[/bold] {self._get_aliases_for('restore')}
[bold]Syntax:[/bold]  restore

[bold]Description:[/bold]
Restore state from before the last program start. When the program starts without
the --restore flag, it backs up the current state and starts fresh. This command
allows you to restore that backup at any time during the session.

[bold]Examples:[/bold]
  restore   # Restore state from before last program start
  res       # Using alias

[bold]Use Cases:[/bold]
- You started fresh but want to recover previous work
- Accidentally started without --restore flag
- Want to switch back to previous session mid-work

[bold]Related:[/bold] revert, use
""",
            'validate': """
[cyan][bold]Command: validate[/bold][/cyan]
[bold]Syntax:[/bold]  validate

[bold]Description:[/bold]
Check templates/ and saves/ directories for duplicate filenames (ignoring
extensions) within the same directory. Duplicates across different subdirectories
are allowed and will not be reported.

This same validation can be run automatically on startup by setting
VALIDATE_ON_STARTUP = True in configuration.py.

[bold]Examples:[/bold]
  validate   # Check for duplicate filenames

[bold]Use Cases:[/bold]
- Ensure no naming conflicts before creating new templates/saves
- Verify directory structure after bulk file operations
- Troubleshoot unexpected file loading behavior

[bold]Related:[/bold] use, load, save
""",
            'reload': """
[cyan][bold]Command: reload[/bold][/cyan]
[bold]Syntax:[/bold]  reload

[bold]Description:[/bold]
Dynamically reload all template and save files without restarting the program.
Clears all internal caches (template renderer, Jinja2 environments, and file lists)
so that any changes to template or save files are immediately available.

[bold]Examples:[/bold]
  reload   # Refresh all templates and saves

[bold]Use Cases:[/bold]
- You edited a template file and want to see changes immediately
- You added new template or save files to the directories
- You modified save file contents and want to reload them
- You want to clear cached Jinja2 environments after template changes

[bold]Related:[/bold] use, load, save, validate
""",
            'edit': f"""
[cyan][bold]Command: edit[/bold][/cyan]
[bold]Aliases:[/bold] {self._get_aliases_for('edit')}
[bold]Syntax:[/bold]  edit <template_path|save_path>

[bold]Description:[/bold]
Open a template or save file in the configured editor. The command first attempts
to resolve the path as a template file, then falls back to save files if not found.
The editor is launched with the full system path to the file.

[bold]Examples:[/bold]
  edit example              # Open example.template in editor
  edit example.template     # Open with full extension
  edit reports/monthly      # Open from subdirectory
  edit client               # Open save file named 'client'
  edit projects/demo        # Open save from subdirectory

[bold]Note:[/bold]
Editor command is configured via DEFAULT_EDITOR in configuration.py or FLOWY_EDITOR
environment variable (current: {DEFAULT_EDITOR})

[bold]Related:[/bold] use, load, save, validate
""",
            'help': f"""
[cyan][bold]Command: help[/bold][/cyan]
[bold]Aliases:[/bold] {self._get_aliases_for('help')}
[bold]Syntax:[/bold]  help [command]

[bold]Description:[/bold]
Display help information. Without arguments, shows an overview of all commands.
With a command name, shows detailed help for that specific command.

[bold]Examples:[/bold]
  help         # Show all commands
  help use     # Detailed help for 'use'
  ?            # Using alias

[bold]Related:[/bold] All commands
""",
            'exit': """
[cyan][bold]Command: exit[/bold][/cyan]
[bold]Syntax:[/bold]  exit

[bold]Description:[/bold]
Exit the interactive shell. You can also use Ctrl+D to exit.

[bold]Examples:[/bold]
  exit
""",
        }
        
        if command in help_text:
            print(self.color_formatter.format(help_text[command]))
        else:
            self._display_error(f"Unknown command: {command}")
            print(self.color_formatter.format("[yellow]Type 'help' to see all available commands.[/yellow]"))
    
    def _display_variables_table(self):
        """Display formatted variables table with global variables section."""
        # First display global variables if any exist and flag is enabled
        global_vars = state_manager.get_all_global_variables()
        if SHOW_GLOBALS_IN_LS and global_vars:
            print(self.color_formatter.format("\n[cyan][bold]Global Variables[/bold][/cyan] (apply to all templates):\n"))

            headers = ["Name", "Value"]
            rows = []
            for var_name, value in sorted(global_vars.items()):
                # Format value for display
                if isinstance(value, str):
                    display_value = f'"{value}"'
                else:
                    display_value = str(value)
                rows.append([var_name, display_value])

            print(self._format_table(headers, rows))
            print()  # Add spacing between sections
        
        # Then display template variables
        if not self.current_template.variables:
            if not global_vars:
                print(self.color_formatter.format("[yellow]No variables defined.[/yellow]"))
            else:
                print(self.color_formatter.format("[yellow]No template-specific variables defined.[/yellow]"))
            return
        
        print(self.color_formatter.format("[green][bold]Template Variables[/bold][/green]:\n"))
        
        variables = state_manager.get_all_variables()
        headers = ["Name", "Current Value", "Description", "Default", "Options"]
        
        rows = []
        for var_name, var_def in self.current_template.variables.items():
            current = variables.get(var_name, "None")
            default = var_def.default if var_def.default is not None else "None"
            options = ", ".join(var_def.options) if var_def.options else "-"
            
            rows.append([
                var_name,
                str(current),  # No truncation - let DisplayManager handle it
                var_def.description or "-",  # No truncation
                default,
                options
            ])
        
        print(self._format_table(headers, rows))
    
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
                print(self.color_formatter.format(f"[green]{success_msg}[/green]"))
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
            print(self.color_formatter.format(f"[red]{table_output}[/red]"))

            # Display summary
            summary = f"Found {result.get_duplicate_count()} duplicate(s) in {result.templates_checked} files in templates directory and {result.saves_checked} files in saves directory"
            print(self.color_formatter.format(f"[red]{summary}[/red]"))

    def cmd_exit(self, args: list[str]):
        """Exit shell."""
        self._exit()
    
    def _exit(self):
        """Clean exit."""
        print(self.color_formatter.format("\n[green]Goodbye![/green]"))
        sys.exit(0)
    
    def _format_table(self, headers: list[str], rows: list[list[str]]) -> str:
        """Format data as aligned table using DisplayManager."""
        return self.display_manager.format_table(headers, rows)
    
    def _display_error(self, message: str):
        """Display formatted error."""
        print(self.color_formatter.format(f"[red][bold]Error:[/bold][/red] {message}"))

    def _display_success(self, message: str):
        """Display formatted success."""
        print(self.color_formatter.format(f"[green]{message}[/green]"))


def main():
    """Entry point for interactive shell."""
    shell = InteractiveShell()
    shell.start()


if __name__ == "__main__":
    main()
