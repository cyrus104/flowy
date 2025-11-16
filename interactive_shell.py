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
from template_parser import TemplateParser, TemplateNotFoundError, TemplateParseError
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
        
        try:
            self.current_template = self.template_parser.parse(template_path)
            self.completer.update_template(self.current_template)
            state_manager.set_template(template_path)
            
            self._display_success(f"Loaded: {template_path}")
            
            if save_path:
                self.cmd_load([save_path])
                if self.current_template:
                    self.cmd_render([])
                    
        except TemplateNotFoundError:
            self._display_error(f"Template not found: {template_path}")
        except TemplateParseError as e:
            self._display_error(f"Template parse error: {e}")
    
    def cmd_load(self, args: list[str]):
        """Load variables from save file."""
        if not self.current_template:
            self._display_error("Load template first with 'use'")
            return
        
        if not args:
            self._display_error("Usage: load <save_path>")
            return
        
        try:
            save_path = args[0]
            variables = save_file_manager.load_variables_for_template(
                save_path, self.current_template.relative_path
            )
            state_manager.set_variables(variables)
            self.current_save_path = save_path
            
            self._display_success(f"Loaded variables from: {save_path}")
            
        except Exception as e:
            self._display_error(f"Failed to load save file: {e}")
    
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
            state_manager.set_variable(var_name, value)
            self._display_success(f"Set {var_name} = {value}")
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
        
        try:
            save_path = args[0]
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
