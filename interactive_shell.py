"""
Interactive Shell for Template Assistant

Metasploit-inspired CLI with tab completion, command aliases, rich output, and full integration
with all core components (StateManager, SaveFileManager, TemplateParser, TemplateRenderer, 
HistoryLogger, ModuleLoader).

Supports both interactive mode and quick launch mode for programmatic command execution.
"""

import sys
import shlex
from typing import Optional, Dict, Any
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style

import colorama
from colorama import Fore, Back, Style as ColoramaStyle

from configuration import (
    BANNER_ASCII, PROMPT_TEMPLATE, COMMAND_ALIASES, SHOW_CONFIG_ON_STARTUP,
    SHOW_UNDEFINED_SUMMARY, TEMPLATES_DIR, SAVES_DIR, STATE_FILE, HISTORY_FILE, 
    VERSION, APP_NAME, MODULES_DIR
)

from state_manager import state_manager
from save_file_manager import save_file_manager
from template_parser import TemplateParser, TemplateNotFoundError, TemplateParseError, TemplateDefinition
from template_renderer import template_renderer, RenderResult
from history_logger import history_logger
from shell_completers import ShellCompleter
from display_manager import display_manager


class InteractiveShell:
    """Main interactive shell orchestrating all components."""
    
    def __init__(self):
        self.template_parser = TemplateParser(TEMPLATES_DIR)
        self.renderer = template_renderer
        self.display_manager = display_manager
        self.current_template: Optional['TemplateDefinition'] = None
        self.current_save_path: Optional[str] = None
        
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
        
        colorama.init()
    
    def start(self):
        """Main entry point - display banner and start command loop."""
        self.display_banner()
        if SHOW_CONFIG_ON_STARTUP:
            self.display_configuration()
        
        # Load existing state using public API
        template_path = state_manager.get_current_template()
        if template_path:
            try:
                self.current_template = self.template_parser.parse(template_path)
                self.completer.update_template(self.current_template)
                print(f"[green]Restored session: {template_path}[/green]")
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
        2. Loads the template (and save file if provided)
        3. Auto-renders if save file is provided
        4. Drops into interactive mode
        """
        # Display startup information
        self.display_banner()
        if SHOW_CONFIG_ON_STARTUP:
            self.display_configuration()
        
        try:
            # Execute use command with template (and optionally save)
            if save_path:
                # Use command with both template and save triggers auto-render
                print(f"[cyan]Quick launch: Loading {template_path} with {save_path}[/cyan]")
                self.cmd_use([template_path, save_path])
            else:
                # Just load the template
                print(f"[cyan]Quick launch: Loading {template_path}[/cyan]")
                self.cmd_use([template_path])
            
            print()  # Add blank line before interactive prompt
            
        except Exception as e:
            # Display error but continue to interactive mode
            self._display_error(f"Quick launch failed: {e}")
            print("[yellow]Entering interactive mode...[/yellow]\n")
        
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
        print(self.display_manager.wrap_text(config_text))
    
    def run(self):
        """Main command loop."""
        try:
            while True:
                prompt = self._get_prompt()
                try:
                    with patch_stdout():
                        user_input = self.session.prompt(prompt)
                except KeyboardInterrupt:
                    print("\n[red]Command cancelled.[/red]")
                    continue
                
                if not user_input.strip():
                    continue
                
                self._handle_command(user_input)
                
        except EOFError:
            self._exit()
    
    def _get_prompt(self) -> str:
        """Generate dynamic prompt."""
        template_part = f" ({self.current_template.relative_path})" if self.current_template else ""
        return PROMPT_TEMPLATE.format(template=template_part)
    
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
        
        self._display_success(f"Loaded: {canonical_path}")
        
        if save_path:
            self.cmd_load([save_path])
            if self.current_template:
                self.cmd_render([])
    
    def cmd_load(self, args: list[str]):
        """Load variables from save file."""
        if not self.current_template:
            self._display_error("Load template first with 'use'")
            return
        
        if not args:
            self._display_error("Usage: load <save_path>")
            return
        
        save_path = args[0]
        
        # Delegate extension resolution to SaveFileManager
        try:
            variables = save_file_manager.load_variables_for_template(
                save_path, self.current_template.relative_path
            )
        except Exception as e:
            self._display_error(f"Failed to load save file: {e}")
            return
        
        # Use canonical path with extension for persistence
        canonical_save_path = save_path if save_path.endswith('.save') else save_path + '.save'
        state_manager.set_variables(variables)
        self.current_save_path = canonical_save_path
        
        self._display_success(f"Loaded variables from: {canonical_save_path}")
    
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
    
    def cmd_save(self, args: list[str]):
        """Save current variables to file."""
        if not self.current_template:
            self._display_error("Load template first with 'use'")
            return
        
        if not args:
            self._display_error("Usage: save <save_path>")
            return
        
        save_path = args[0]
        # Add .save extension if not present
        if not save_path.endswith('.save'):
            save_path = save_path + '.save'
        
        try:
            variables = state_manager.get_all_variables()
            save_file_manager.save_variables(save_path, variables, self.current_template.relative_path)
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
                print(f"\n[red]{result.format_error()}[/red]")
            
            if result.undefined_variables and SHOW_UNDEFINED_SUMMARY:
                print(f"\n[red]Undefined variables: {', '.join(result.undefined_variables)}[/red]")
                
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
        print("\n[cyan][bold]Available Commands:[/bold][/cyan]\n")
        
        headers = ["Command", "Aliases", "Syntax", "Description"]
        rows = [
            ["use", self._get_aliases_for('use'), "use <template> [save]", "Load template (+ optional auto-render)"],
            ["load", self._get_aliases_for('load'), "load <save>", "Load variables from save file"],
            ["set", self._get_aliases_for('set'), "set <var> <value>", "Set variable value"],
            ["unset", self._get_aliases_for('unset'), "unset <var>", "Remove variable"],
            ["save", self._get_aliases_for('save'), "save <save>", "Save current variables to file"],
            ["render", self._get_aliases_for('render'), "render", "Render current template"],
            ["ls", self._get_aliases_for('ls'), "ls", "Show variables table"],
            ["revert", self._get_aliases_for('revert'), "revert", "Toggle previous template state"],
            ["help", self._get_aliases_for('help'), "help [command]", "Show this help or command details"],
            ["exit", self._get_aliases_for('exit'), "exit", "Exit the shell"],
        ]
        
        table = self._format_table(headers, rows)
        print(table)
        print("\n[green]Tip: Type 'help <command>' for detailed information about a specific command.[/green]\n")
    
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
  load client              # Load client.save
  load projects/demo       # Load from subdirectory

[bold]Related:[/bold] use, save, set
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
  save client              # Save to client.save
  save projects/demo       # Save to subdirectory

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
            print(help_text[command])
        else:
            self._display_error(f"Unknown command: {command}")
            print("[yellow]Type 'help' to see all available commands.[/yellow]")
    
    def _display_variables_table(self):
        """Display formatted variables table."""
        if not self.current_template.variables:
            print("[yellow]No variables defined in template.[/yellow]")
            return
        
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
    
    def cmd_exit(self, args: list[str]):
        """Exit shell."""
        self._exit()
    
    def _exit(self):
        """Clean exit."""
        print("\n[green]Goodbye![/green]")
        sys.exit(0)
    
    def _format_table(self, headers: list[str], rows: list[list[str]]) -> str:
        """Format data as aligned table using DisplayManager."""
        return self.display_manager.format_table(headers, rows)
    
    def _display_error(self, message: str):
        """Display formatted error."""
        print(f"[red][bold]Error:[/bold][/red] {message}")
    
    def _display_success(self, message: str):
        """Display formatted success."""
        print(f"[green]{message}[/green]")


def main():
    """Entry point for interactive shell."""
    shell = InteractiveShell()
    shell.start()


if __name__ == "__main__":
    main()
