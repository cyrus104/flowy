"""
Template Renderer Module

Comprehensive Jinja2 rendering engine with color formatting, subtemplate support,
undefined variable handling, and detailed error reporting.

Integrates with TemplateParser and SaveFileManager for complete rendering pipeline.
Supports design-spec formatting: [red]...[/red], undefined marking, legacy filters.
"""

import re
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import jinja2
from jinja2 import BaseLoader, TemplateError, UndefinedError, TemplateSyntaxError

import colorama
from colorama import Fore, Back, Style

import configuration
from template_parser import TemplateDefinition, TemplateParser
from save_file_manager import SaveFileManager, save_file_manager

# Module loader integration
from module_loader import load_modules_for_jinja, ModuleLoaderError

# Add module loader import
from module_loader import load_modules_for_jinja, ModuleLoaderError


# ============================================================================
# Global Undefined Tracker (Thread-Safe)
# ============================================================================

_local_undefined_vars = threading.local()


class HighlightUndefined(jinja2.runtime.Undefined):
    """Custom Undefined handler for marking undefined variables."""
    
    def __init__(self, hint=None, obj=None, name=None, exc=tuple()):
        super().__init__(hint, obj, name, exc)
        self._undefined_name = name or str(hint) if hint else 'UNKNOWN'
        self._undefined_exception = exc[0] if exc else None
    
    def __str__(self):
        self.track()  # Always track before returning
        if configuration.UNDEFINED_BEHAVIOR == 'mark':
            return configuration.UNDEFINED_VARIABLE_TEMPLATE.format(var=self._undefined_name)
        elif configuration.UNDEFINED_BEHAVIOR == 'empty':
            return ''
        else:  # 'error'
            raise self._undefined_exception if hasattr(self, '_undefined_exception') else jinja2.exceptions.UndefinedError(self._undefined_name)
    
    def __getattr__(self, name):
        """Handle attribute access: undefined.user → <<undefined.user>>."""
        self.track()
        return self.__class__(name=f"{self._undefined_name}.{name}")
    
    def __add__(self, other):
        return str(self)
    
    def __radd__(self, other):
        return str(other) + str(self)
    
    def track(self):
        """Track this undefined variable for summary."""
        if not hasattr(_local_undefined_vars, 'undefined_vars'):
            _local_undefined_vars.undefined_vars = set()
        _local_undefined_vars.undefined_vars.add(self._undefined_name)


# ============================================================================
# Color Formatter
# ============================================================================

class ColorFormatter:
    """Convert template color syntax to ANSI escape codes."""
    
    COLORS = {
        'black': Fore.BLACK, 'red': Fore.RED, 'green': Fore.GREEN,
        'yellow': Fore.YELLOW, 'blue': Fore.BLUE, 'magenta': Fore.MAGENTA,
        'cyan': Fore.CYAN, 'white': Fore.WHITE
    }
    
    BG_COLORS = {
        'bg:black': Back.BLACK, 'bg:red': Back.RED, 'bg:green': Back.GREEN,
        'bg:yellow': Back.YELLOW, 'bg:blue': Back.BLUE, 
        'bg:magenta': Back.MAGENTA, 'bg:cyan': Back.CYAN, 'bg:white': Back.WHITE
    }
    
    def __init__(self):
        if configuration.COLOR_OUTPUT_ENABLED:
            colorama.init()
        
        # Separate patterns for different tag types
        self.FG_PATTERN = re.compile(
            r'\[([a-z]+)(?::bg:([a-z]+))?\](.*?)\[/\1(?::bg:\2)?\]',
            re.IGNORECASE | re.DOTALL
        )  # group1=fg (e.g., 'red'), group2=bg opt (e.g., 'yellow'), group3=content
        
        self.BG_PATTERN = re.compile(
            r'\[bg:([a-z]+)\](.*?)\[/bg:\1\]',
            re.IGNORECASE | re.DOTALL
        )  # group1=bg_color (e.g., 'blue'), group2=content
        
        self.BOLD_PATTERN = re.compile(
            r'\[bold\](.*?)\[/bold\]',
            re.DOTALL | re.IGNORECASE
        )  # group1=content

    def _preprocess_hash_lines(self, text: str) -> str:
        """Preprocess text to wrap lines starting with # in [green]...[/green] tags."""
        lines = text.splitlines(keepends=True)
        processed_lines = []

        for line in lines:
            # Check if the line (after stripping leading whitespace) starts with #
            stripped = line.lstrip()
            if stripped.startswith('#'):
                # Wrap the entire line with [green]...[/green] tags
                # Keep line ending outside the tags to avoid recursion issues
                # Check CRLF before LF since CRLF also ends with LF
                if line.endswith('\r\n'):
                    processed_lines.append(f'[green]{line[:-2]}[/green]\r\n')
                elif line.endswith('\n'):
                    processed_lines.append(f'[green]{line[:-1]}[/green]\n')
                else:
                    processed_lines.append(f'[green]{line}[/green]')
            else:
                processed_lines.append(line)

        return ''.join(processed_lines)

    def format(self, text: str, _skip_preprocess: bool = False) -> str:
        """Convert color syntax to ANSI codes."""
        # Preprocess hash lines first (before color output check)
        # Skip preprocessing during recursive calls to avoid infinite loops
        if not _skip_preprocess:
            text = self._preprocess_hash_lines(text)

        if not configuration.COLOR_OUTPUT_ENABLED:
            return self._remove_tags(text)

        # Handle nested/combined tags
        text = self._process_tags(text)
        text = self._process_bold(text)
        return text

    def _process_tags(self, text: str) -> str:
        """Process color tags with proper fg/bg/combined support."""
        def replace_fg(match):
            fg = match.group(1).lower()
            bg = match.group(2)
            content = match.group(3)

            result = ''
            if fg in self.COLORS:
                result += self.COLORS[fg]
            if bg and bg.lower() in self.BG_COLORS:
                result += self.BG_COLORS[f'bg:{bg.lower()}']

            result += self.format(content, _skip_preprocess=True)  # Recursive for nested tags
            result += Style.RESET_ALL
            return result

        def replace_bg(match):
            bg_color = match.group(1).lower()
            content = match.group(2)

            if f'bg:{bg_color}' in self.BG_COLORS:
                return self.BG_COLORS[f'bg:{bg_color}'] + self.format(content, _skip_preprocess=True) + Style.RESET_ALL
            return match.group(0)  # Return unchanged if invalid color
        
        # Process fg-only and combined first
        text = self.FG_PATTERN.sub(replace_fg, text)
        # Then process standalone bg tags
        text = self.BG_PATTERN.sub(replace_bg, text)
        
        return text
    
    def _process_bold(self, text: str) -> str:
        """Process [bold]text[/bold]."""
        def replace_bold(match):
            return Style.BRIGHT + self.format(match.group(1), _skip_preprocess=True) + Style.RESET_ALL

        return self.BOLD_PATTERN.sub(replace_bold, text)
    
    def _remove_tags(self, text: str) -> str:
        """Strip all color/formatting tags when colors disabled."""
        # Remove fg-only and combined tags
        text = self.FG_PATTERN.sub(lambda m: m.group(3), text)  # Keep content (group3)
        # Remove standalone bg tags
        text = self.BG_PATTERN.sub(lambda m: m.group(2), text)  # Keep content (group2)
        # Remove bold tags
        text = self.BOLD_PATTERN.sub(r'\1', text)  # Keep content (group1)
        return text


# ============================================================================
# Auto Context Environment and Template Wrapper
# ============================================================================

class _AutoContextTemplateWrapper:
    """Wrapper that automatically merges subtemplate variables on render."""
    
    def __init__(self, template: jinja2.Template, save_path: Optional[str], save_manager: SaveFileManager):
        self.template = template
        self.save_path = save_path
        self.save_manager = save_manager
    
    def render(self, *args, **kwargs) -> str:
        """Render with automatic subtemplate variable merging."""
        # Get parent context
        context = args[0] if args else kwargs
        
        # Load subtemplate-specific variables if save file provided
        sub_vars = {}
        if self.save_path:
            try:
                # Template name from Jinja2 (e.g., 'subtemplate_example.template')
                sub_relative_path = self.template.name
                if sub_relative_path and sub_relative_path != '(string)':
                    sub_vars = self.save_manager.load_variables_for_template(
                        self.save_path, sub_relative_path
                    )
            except Exception:
                pass  # Graceful fallback to parent context + defaults
        
        # Merge: parent context + subtemplate overrides
        merged_context = {**context, **sub_vars}
        
        # Render with merged context
        return self.template.render(merged_context)
    
    # Proxy other template attributes
    def __getattr__(self, name):
        return getattr(self.template, name)


class AutoContextEnvironment(jinja2.Environment):
    """Jinja2 environment that automatically merges subtemplate variables."""
    
    def __init__(self, *args, save_path: Optional[str] = None, 
                 save_manager: Optional[SaveFileManager] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.save_path = save_path
        self.save_manager = save_manager
    
    def get_template(self, name: str, *args, **kwargs) -> jinja2.Template:
        """Get template with automatic context wrapper."""
        template = super().get_template(name, *args, **kwargs)
        
        # Wrap template for automatic variable merging
        if self.save_path and self.save_manager:
            return _AutoContextTemplateWrapper(template, self.save_path, self.save_manager)
        
        return template


# ============================================================================
# Custom Template Loader
# ============================================================================

class CustomTemplateLoader(BaseLoader):
    """Custom loader for template inclusion with save file context."""
    
    def __init__(self, templates_dir: str, parser: TemplateParser, save_manager: SaveFileManager):
        self.templates_dir = Path(templates_dir)
        self.parser = parser
        self.save_manager = save_manager
        self._cache = {}
        self._include_stack = threading.local()
    
    def get_source(self, environment, template_path):
        """Load template source with circular detection and save context."""
        if not hasattr(self._include_stack, 'stack'):
            self._include_stack.stack = []
        
        if template_path in self._include_stack.stack:
            raise jinja2.TemplateNotFound(f"Circular template inclusion: {template_path}")
        
        self._include_stack.stack.append(template_path)
        
        try:
            full_path = (self.templates_dir / template_path).resolve()
            if not full_path.is_relative_to(self.templates_dir):
                raise jinja2.TemplateNotFound(f"Template outside templates dir: {template_path}")
            
            if full_path in self._cache:
                return self._cache[full_path], full_path.as_posix(), lambda: True
            
            source = full_path.read_text(encoding='utf-8')
            self._cache[full_path] = source
            
            return source, full_path.as_posix(), lambda: True
            
        finally:
            self._include_stack.stack.pop()


# ============================================================================
# RenderResult Dataclass
# ============================================================================

@dataclass(frozen=True)
class RenderResult:
    """Immutable result of template rendering."""
    output: str
    success: bool
    undefined_variables: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    error_line: Optional[int] = None
    error_context: Optional[str] = None
    template_path: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON."""
        result = {
            'output': self.output,
            'success': self.success,
            'undefined_variables': self.undefined_variables,
        }
        if not self.success:
            result.update({
                'error_message': self.error_message,
                'error_line': self.error_line,
                'error_context': self.error_context,
                'template_path': self.template_path,
            })
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderResult':
        """Deserialize from dict."""
        return cls(
            output=data['output'],
            success=data['success'],
            undefined_variables=data['undefined_variables'],
            error_message=data.get('error_message'),
            error_line=data.get('error_line'),
            error_context=data.get('error_context'),
            template_path=data.get('template_path', '')
        )
    
    def has_undefined(self) -> bool:
        """Check if undefined variables were encountered."""
        return bool(self.undefined_variables)
    
    def format_error(self) -> str:
        """Format error for display."""
        if self.success:
            return ""
        
        lines = [f"Template: {self.template_path}"]
        if self.error_line:
            lines.append(f"Line: {self.error_line}")
        if self.error_message:
            lines.append(f"Error: {self.error_message}")
        if self.error_context:
            lines.extend(["", "Context:", self.error_context])
        
        return "\n".join(lines)


# ============================================================================
# TemplateRenderer Class
# ============================================================================

class TemplateRenderer:
    """
    Main rendering engine integrating all components.
    
    Handles: Jinja2 rendering, color formatting, undefined variables,
    subtemplate inclusion, save file context, error extraction.
    """
    
    def __init__(self, templates_dir: str = configuration.TEMPLATES_DIR, saves_dir: str = configuration.SAVES_DIR):
        self.templates_dir = templates_dir
        self.saves_dir = saves_dir
        self.parser = TemplateParser(templates_dir)
        self.save_manager = SaveFileManager(saves_dir)
        self.color_formatter = ColorFormatter()
        self._env_cache = {}
    
    def render(self, template_def: TemplateDefinition, 
               variables: Dict[str, Any] = None, 
               save_path: Optional[str] = None) -> RenderResult:
        """
        Render template with full pipeline.
        
        Args:
            template_def: Parsed TemplateDefinition
            variables: User-provided variables
            save_path: Optional save file path for additional variables
        """
        try:
            # Reset undefined tracker
            if hasattr(_local_undefined_vars, 'undefined_vars'):
                delattr(_local_undefined_vars, 'undefined_vars')
            
            # Merge variables: user > save file > template defaults
            merged_vars = self._merge_variables(template_def, variables, save_path)
            
            # Setup Jinja2 environment with save_path for subtemplate auto-loading
            env = self._setup_jinja_environment(template_def.path, save_path)
            
            # Compile template
            template = env.from_string(template_def.template_content)
            
            # Render
            raw_output = template.render(**merged_vars)
            
            # Format colors
            formatted_output = self.color_formatter.format(raw_output)
            
            # Collect undefined variables
            undefined_vars = []
            if hasattr(_local_undefined_vars, 'undefined_vars'):
                undefined_vars = sorted(list(_local_undefined_vars.undefined_vars))
            
            return RenderResult(
                output=formatted_output,
                success=True,
                undefined_variables=undefined_vars,
                template_path=template_def.path
            )
            
        except (TemplateSyntaxError, TemplateError) as e:
            return self._create_error_result(template_def, e)
        except Exception as e:
            return RenderResult(
                output="",
                success=False,
                error_message=f"Unexpected rendering error: {e}",
                template_path=template_def.path
            )
    
    def render_string(self, template_string: str, variables: Dict[str, Any]) -> RenderResult:
        """Render template string directly."""
        env = self._setup_jinja_environment("(string)", None)  # No save_path for string rendering
        template = env.from_string(template_string)
        raw_output = template.render(**variables)
        formatted = self.color_formatter.format(raw_output)
        return RenderResult(output=formatted, success=True)
    
    def _merge_variables(self, template_def: TemplateDefinition, 
                        user_vars: Dict[str, Any], 
                        save_path: Optional[str]) -> Dict[str, Any]:
        """Merge variables: user > save file > template defaults."""
        variables = {}
        
        # Template defaults from VARS section
        for var_def in template_def.variables.values():
            if var_def.default is not None:
                variables[var_def.name] = var_def.default
        
        # Save file variables (if provided)
        if save_path:
            try:
                save_vars = self.save_manager.load_variables_for_template(save_path, template_def.relative_path)
                variables.update(save_vars)
            except Exception:
                pass  # Ignore save file errors during rendering
        
        # User variables override everything
        if user_vars:
            variables.update(user_vars)
        
        return variables
    
    def _setup_jinja_environment(self, template_path: str, save_path: Optional[str] = None) -> jinja2.Environment:
        """Create configured Jinja2 environment with automatic subtemplate variable loading."""
        # Cache key includes save_path for different contexts
        cache_key = (template_path, save_path)
        if cache_key in self._env_cache:
            return self._env_cache[cache_key]
        
        # Use AutoContextEnvironment for automatic subtemplate variable merging
        env = AutoContextEnvironment(
            loader=CustomTemplateLoader(self.templates_dir, self.parser, self.save_manager),
            undefined=HighlightUndefined,
            autoescape=False,  # Templates handle their own escaping
            trim_blocks=True,
            lstrip_blocks=True,
            save_path=save_path,
            save_manager=self.save_manager
        )
        
        # Load Python modules for template functions
        try:
            modules_dict = load_modules_for_jinja()
            env.globals.update(modules_dict)
        except ModuleLoaderError:
            # Log warning but don't fail rendering
            pass
        
        # Add manual subtemplate context function (fallback/compatibility)
        def get_subtemplate_vars(template_name):
            if not save_path:
                return {}
            try:
                return self.save_manager.load_variables_for_template(save_path, template_name)
            except:
                return {}
        env.globals['get_subtemplate_vars'] = get_subtemplate_vars
        
        # Legacy filters for backward compatibility
        self._add_legacy_filters(env)
        
        self._env_cache[cache_key] = env
        return env
    
    def _add_legacy_filters(self, env: jinja2.Environment) -> None:
        """Add legacy color/bold filters."""
        def color_filter(value, color_name):
            if not configuration.COLOR_OUTPUT_ENABLED:
                return str(value)
            color = ColorFormatter.COLORS.get(color_name.lower())
            if color:
                return f"{color}{value}{Style.RESET_ALL}"
            return str(value)
        
        def bgcolor_filter(value, color_name):
            if not configuration.COLOR_OUTPUT_ENABLED:
                return str(value)
            bg_key = f'bg:{color_name.lower()}'
            bg_color = ColorFormatter.BG_COLORS.get(bg_key)
            if bg_color:
                return f"{bg_color}{value}{Style.RESET_ALL}"
            return str(value)
        
        def bold_filter(value):
            if not configuration.COLOR_OUTPUT_ENABLED:
                return str(value)
            return f"{Style.BRIGHT}{value}{Style.RESET_ALL}"
        
        env.filters['color'] = color_filter
        env.filters['bgcolor'] = bgcolor_filter
        env.filters['bold'] = bold_filter
    
    def _create_error_result(self, template_def: TemplateDefinition, 
                           error: TemplateError) -> RenderResult:
        """Create RenderResult from Jinja2 error with subtemplate awareness."""
        error_line = getattr(error, 'lineno', None)
        error_msg = str(error)
        
        template_path = template_def.path
        content = template_def.template_content
        
        # Detect if error originated in a subtemplate
        sub_path = getattr(error, 'filename', None)
        if sub_path and sub_path != template_def.path:
            try:
                sub_full_path = Path(sub_path)
                # Check if subtemplate is within templates directory
                if sub_full_path.is_relative_to(Path(self.templates_dir)):
                    # Load subtemplate content for accurate context
                    content = sub_full_path.read_text(encoding='utf-8')
                    template_path = sub_path  # Use absolute path for precision
                else:
                    # External include: annotate path
                    template_path = f'{template_def.path} (included from: {sub_path})'
            except Exception:
                # Fallback: use parent content with annotation
                content = template_def.template_content
                template_path = f'{template_def.path} (sub read error: {sub_path})'
        
        error_context = None
        if error_line:
            error_context = self._extract_error_context(content, error_line)
        
        return RenderResult(
            output="",
            success=False,
            error_message=error_msg,
            error_line=error_line,
            error_context=error_context,
            template_path=template_path
        )
    
    def _extract_error_context(self, content: str, line_number: int, context_lines: int = 2) -> str:
        """Extract error context with surrounding lines and visual marker."""
        lines = content.splitlines()
        
        # Validate line number
        if line_number < 1 or line_number > len(lines):
            return f'Line {line_number} beyond content (total: {len(lines)} lines)'
        
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        
        context = []
        for i, line in enumerate(lines[start:end], start + 1):
            context.append(f"{i:3d}: {line}")
            if i == line_number:
                # Add marker pointing to the error line
                marker = ' ' * 5 + '^' * len(line.rstrip())
                context.append(marker)
        
        return '\n'.join(context)


# ============================================================================
# Module Convenience Functions
# ============================================================================

def render_template(template_path: str, variables: Dict[str, Any] = None, 
                   save_path: Optional[str] = None) -> RenderResult:
    """Convenience: Render template by path."""
    parser = TemplateParser()
    template_def = parser.parse(template_path)
    renderer = TemplateRenderer()
    return renderer.render(template_def, variables or {}, save_path)


def render_template_def(template_def: TemplateDefinition, 
                       variables: Dict[str, Any] = None, 
                       save_path: Optional[str] = None) -> RenderResult:
    """Convenience: Render parsed TemplateDefinition."""
    renderer = TemplateRenderer()
    return renderer.render(template_def, variables or {}, save_path)


# Default renderer instance
template_renderer = TemplateRenderer()
