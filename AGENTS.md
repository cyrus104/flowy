# Flowy - Design Document

## Overview

A command-line Flowy application that provides an interactive, tab-completable interface for rendering Jinja2 templates with Python integration. The application features a Metasploit-inspired interface with state management, variable persistence, and modular Python function support.

## Core Architecture

### Application Structure

```
flowy/
├── configuration.py          # Configuration and environment settings
├── main.py                   # Entry point and CLI interface
├── templates/                # Template storage directory
│   ├── template1.template
│   └── subfolder/
│       └── template2.template
├── saves/                    # Variable save files (no extension required)
│   ├── default
│   └── subfolder/
│       └── custom
├── modules/                  # Python function modules
│   ├── utils.py
│   └── helpers.py
├── .history                  # Command history file
└── .state                    # Current session state file
```

## Interface Design

### Interactive Shell

The application launches into an interactive shell with tab completion support, similar to the Metasploit framework console. The prompt should clearly indicate the current loaded template (if any).

**Prompt Examples:**
```
flowy >
flowy (templates/report.template) >
```

### Startup Behavior

Upon launch, the application displays:
1. ASCII art banner with tool name
2. Version information
3. Configuration status showing:
   - Templates folder location
   - Saves folder location
   - Modules folder location
   - State file location
   - History file location

### Quick Launch Mode

The application supports command-line arguments for immediate rendering:

```bash
python main.py --template <template_path> --save <save_path>
```

**Note:** `<save_path>` does not require a file extension (e.g., `client` instead of `client.save`)

This mode will:
1. Display the startup banner and configuration
2. Load the specified template
3. Load the specified save file
4. Automatically render the output
5. Drop into interactive mode

## Command Reference

### Core Commands

#### `use <template_path>`
Loads a template for use. Supports tab completion of template names and folder structures.

**Examples:**
```
use report.template
use reports/monthly.template
```

**Extended Syntax:**
```
use <template_path> <save_path>
```
When a save file is provided as a second argument, the command will:
1. Load the template
2. Load the save file
3. Automatically render the output

#### `load <save_path>`
Loads variables from a save file into the current session. Supports tab completion of save files and folder structures.

**Example:**
```
load client_data
load projects/project_a
```

#### `set <variable> <value>`
Sets a variable value for the current template.

**Example:**
```
set client_name "Acme Corporation"
set report_date 2024-01-15
```

#### `unset <variable>`
Removes a variable assignment, reverting to default if specified in template.

**Example:**
```
unset client_name
```

#### `save <save_path>`
Saves the current variable state to a file in the saves directory. Creates subdirectories as needed.

**Example:**
```
save current_project
save projects/project_b
```

#### `render` (alias: `r`, `re`)
Renders the current template with set variables and displays output to the screen.

**Error Handling:**
- Displays precise line numbers for template syntax errors
- Shows context lines around errors for easy debugging
- Continues to allow commands after rendering errors

**Undefined Variables:**
- Missing variables appear as `[red]<<variable_name>>[/red]` in output
- Summary of undefined variables shown after render
- Template completes rendering even with missing data

#### `ls` (alias: `ll`)
Lists all variables for the current template and any loaded subtemplates in a Metasploit-style format showing:
- Variable name
- Current value
- Description
- Default value (if any)
- Available options (if any)

**Example Output:**
```
Template Variables (report.template)
=====================================

Name              Current Value    Description                    Default    Options
----              -------------    -----------                    -------    -------
client_name       Acme Corp        Client organization name       None       -
report_type       monthly          Type of report to generate     weekly     [daily, weekly, monthly]
include_charts    true             Include visualization charts   true       [true, false]

Subtemplate Variables (header.template)
========================================

Name              Current Value    Description                    Default    Options
----              -------------    -----------                    -------    -------
logo_path         ./logo.png       Path to company logo           None       -
```

#### `revert`
Reverts to the previous template state. Smart enough to skip back to the last different template if the same template was used multiple times. Running `revert` a second time will return to the latest state (toggle behavior).

**Example Usage Pattern:**
1. User loads template A, renders
2. User loads template B, renders
3. User loads template B again with different vars, renders
4. User runs `revert` → returns to template A state
5. User runs `revert` again → returns to latest template B state

### Command Aliasing

All commands can be aliased in `configuration.py`. Default aliases:
- `render` → `r`, `re`
- `ls` → `ll`

Additional aliases can be configured by the user.

## Template Format

### Template File Structure

Templates use a two-section format with a `.template` extension:

```
VARS:
  - variable_name:
      description: Description of the variable
      default: default_value
      options: ['option1', 'option2', 'option3']
  - another_var:
      description: Another description
      options: ['opt_a', 'opt_b']
  - simple_var:
      description: Just a description

### TEMPLATE ###

Your Jinja2 template content goes here...
{{ variable_name }}
{% for item in items %}
  - {{ item }}
{% endfor %}
```

### Variable Definition Format

Variables are defined in YAML-like format within the VARS section:

```yaml
VARS:
  - variable_name:
      description: Human-readable description
      default: default_value
      options: ['value1', 'value2', 'value3']
```

**Field Details:**
- **variable_name**: Required. The identifier for the variable (top-level key)
- **description**: Optional. Human-readable description (displayed in `ls` command)
- **default**: Optional. Default value if not set by user
- **options**: Optional. List of valid values (tab-completable in the interface)

**Minimal Variable Definition:**
```yaml
VARS:
  - client_name:
      description: Name of the client organization
```

**Complete Variable Definition:**
```yaml
VARS:
  - report_type:
      description: Type of report to generate
      default: weekly
      options: ['daily', 'weekly', 'monthly', 'quarterly']
  - include_charts:
      description: Include visualization charts in output
      default: 'y'
      options: ['y', 'n']
```

### Template Syntax Features

#### Color and Formatting

The template engine provides shorthand syntax using square brackets for terminal output formatting:

```jinja2
[red]This text is red[/red]
[bg:blue]This has a blue background[/bg:blue]
[bold]This text is bold[/bold]
[green][bold]This is green and bold[/bold][/green]

# Combined shorthand
[red:bg:yellow]Red text on yellow background[/red:bg:yellow]
```

**Supported Colors:** black, red, green, yellow, blue, magenta, cyan, white

**Supported Formatting:**
- `[color]...[/color]` - Text color
- `[bg:color]...[/bg:color]` - Background color
- `[bold]...[/bold]` - Bold text
- `[color:bg:bgcolor]...[/color:bg:bgcolor]` - Combined text and background

Legacy filter syntax is also supported for backward compatibility:
```jinja2
{{ text | color('red') }}
{{ text | bgcolor('blue') }}
{{ text | bold }}
```

#### Control Flow

Standard Jinja2 control structures are supported:

```jinja2
{% if condition %}
  Content when true
{% else %}
  Content when false
{% endif %}

{% for item in list_var %}
  {{ loop.index }}. {{ item }}
{% endfor %}
```

#### Subtemplate Inclusion

Templates can include other templates with automatic save file context passing:

```jinja2
{% include 'header.template' %}

Main content here...

{% include 'footer.template' %}
```

**Automatic Save File Loading:**
When a subtemplate is included, the current save file name is automatically passed to the subtemplate. This allows subtemplates to load their own section-specific variables from the same save file.

**Example Workflow:**
1. Main template: `reports/monthly.template` loaded with save file `client_a`
2. Main template includes: `{% include 'common/header.template' %}`
3. Header subtemplate automatically loads variables from `[common/header.template]` section in `client_a`

**Save File Structure for Subtemplates:**
```ini
[general]
company_name = Acme Corp

[reports/monthly.template]
report_date = 2024-01-15
client_name = Acme Corporation

[common/header.template]
logo_path = ./logos/acme.png
title = Monthly Report
show_date = true

[common/footer.template]
contact_email = reports@example.com
```

Subtemplates inherit the variable scope from the parent template and can define their own variables in the VARS section. Variables from the appropriate save file section are automatically loaded when the subtemplate is included.

#### Python Module Functions

Functions from the modules folder can be called within templates:

```jinja2
{{ utils.format_date(date_var) }}
{{ helpers.calculate_total(items) }}
```

## Modularity

### Python Modules

The `modules/` folder contains Python files with functions that can be called from templates. Each module is a standard Python file with function definitions.

**Example: `modules/utils.py`**
```python
def format_date(date_string):
    """Format a date string to a readable format."""
    # implementation
    return formatted_date

def truncate(text, length=50):
    """Truncate text to specified length."""
    return text[:length] + "..." if len(text) > length else text
```

**Usage in Template:**
```jinja2
Report Date: {{ utils.format_date(report_date) }}
```

### Template Organization

Templates can be organized into subdirectories for better management:

```
templates/
├── reports/
│   ├── daily.template
│   ├── weekly.template
│   └── monthly.template
├── letters/
│   ├── cover.template
│   └── formal.template
└── common/
    ├── header.template
    └── footer.template
```

All subdirectories are navigable via tab completion in the interface.

## State Management

### State File (`.state`)

Automatically maintains the current session state including:
- Currently loaded template
- All set variables and their values
- Last render timestamp
- State history for revert functionality

The state file enables crash recovery by allowing users to restore their exact working state.

**Format (JSON):**
```json
{
  "current_template": "reports/monthly.template",
  "variables": {
    "client_name": "Acme Corp",
    "report_date": "2024-01-15"
  },
  "timestamp": "2024-01-15T10:30:00",
  "history": [
    {
      "template": "reports/weekly.template",
      "variables": {...},
      "timestamp": "2024-01-15T10:00:00"
    }
  ]
}
```

### History File (`.history`)

Records every command executed across all sessions for audit and replay purposes.

**Format:**
```
2024-01-15 10:00:00 | use reports/monthly.template
2024-01-15 10:01:30 | set client_name "Acme Corp"
2024-01-15 10:02:15 | render
```

### Save Files

Save files store variable configurations that can be reused across sessions. They use an INI-style format with sections.

**Format:**
```ini
[general]
common_var1 = value1
common_var2 = value2

[reports/monthly.template]
client_name = Acme Corporation
report_date = 2024-01-15
include_charts = true

[reports/weekly.template]
client_name = Acme Corporation
report_frequency = weekly
```

**Section Behavior:**
- `[general]` section applies to all templates unless overridden
- Template-specific sections (matching template paths) override general values
- Supports folder structure in section names

**File Naming Convention:**
Save files do not require a file extension. The modern convention is to use extensionless names (e.g., `client`, `projects/demo`). For backward compatibility, files with `.save` extension (e.g., `client.save`) are still supported but considered legacy. When loading a save file, the system automatically checks for both the extensionless version first, then falls back to the `.save` extension if needed.

## Display and Output Management

### Terminal Window Optimization

The application intelligently manages terminal output to provide an optimal viewing experience:

**Width Detection:**
- Automatically detects current terminal width on launch and window resize
- Dynamically adjusts output formatting to match available space
- Ensures no content is cut off or requires horizontal scrolling

**Word Wrapping:**
- Intelligent word wrapping for all rendered output
- Preserves formatting (colors, bold) across wrapped lines
- Respects indentation and list structures when wrapping
- Breaks long words only when necessary to fit terminal width

**Output Rendering:**
```
# Terminal Width: 80 columns
[green][bold]Client Report[/bold][/green]
================================================================================

This is a very long line of text that will automatically wrap to the next line
when it reaches the edge of the terminal window, maintaining proper formatting
and ensuring readability without requiring horizontal scrolling.

    - Indented content is also properly wrapped while maintaining the
      indentation level for subsequent lines
    - [red]Colored text wraps correctly[/red] preserving all formatting
```

**Table Formatting:**
The `ls` command and other tabular outputs automatically adjust column widths based on:
- Terminal width
- Content length
- Minimum readable width for each column
- Truncation with ellipsis for extremely long values when necessary

**Example Adaptive Table:**
```
# Wide Terminal (120+ columns)
Name              Current Value              Description                           Default    Options
----              -------------              -----------                           -------    -------
client_name       Acme Corporation           Client organization name              None       -
report_type       monthly                    Type of report to generate            weekly     [daily, weekly, monthly]

# Narrow Terminal (80 columns)
Name           Current        Description                    Default  Options
----           -------        -----------                    -------  -------
client_name    Acme Corp...   Client organization name       None     -
report_type    monthly        Type of report to generate     weekly   [daily...]
```

### Display Configuration

Configure display behavior in `configuration.py`:

```python
# Display Settings
AUTO_DETECT_WIDTH = True           # Automatically detect terminal width
DEFAULT_WIDTH = 80                 # Fallback width if detection fails
WORD_WRAP_ENABLED = True           # Enable intelligent word wrapping
PRESERVE_FORMATTING_ON_WRAP = True # Maintain colors/bold across wrapped lines
MAX_TABLE_COLUMN_WIDTH = 40        # Maximum width for table columns
MIN_TABLE_COLUMN_WIDTH = 10        # Minimum width for table columns
TRUNCATE_INDICATOR = "..."         # Indicator for truncated content

# Undefined Variable Handling
UNDEFINED_VARIABLE_TEMPLATE = "[red]<<{var}>>[/red]"
UNDEFINED_BEHAVIOR = "mark"        # Options: "mark", "error", "empty"
SHOW_UNDEFINED_SUMMARY = True      # Show summary of undefined vars after render
```

### `configuration.py`

Centralized configuration file for customization and environment settings.

**Key Configuration Options:**

```python
# Folder Locations (can use environment variables)
TEMPLATES_DIR = os.getenv('FLOWY_TEMPLATES', './templates')
SAVES_DIR = os.getenv('FLOWY_SAVES', './saves')
MODULES_DIR = os.getenv('FLOWY_MODULES', './modules')

# State Management
STATE_FILE = os.getenv('FLOWY_STATE', './.state')
HISTORY_FILE = os.getenv('FLOWY_HISTORY', './.history')

# Interface Customization
PROMPT_TEMPLATE = "flowy{template} > "
BANNER_ASCII = """
[ASCII art here]
"""

# Command Aliases
COMMAND_ALIASES = {
    'render': ['r', 're'],
    'ls': ['ll'],
    'use': ['load_template'],
    # Add custom aliases here
}

# Display Options
SHOW_CONFIG_ON_STARTUP = True
COLOR_OUTPUT_ENABLED = True

# Display Settings
AUTO_DETECT_WIDTH = True           # Automatically detect terminal width
DEFAULT_WIDTH = 80                 # Fallback width if detection fails
WORD_WRAP_ENABLED = True           # Enable intelligent word wrapping
PRESERVE_FORMATTING_ON_WRAP = True # Maintain colors/bold across wrapped lines
MAX_TABLE_COLUMN_WIDTH = 40        # Maximum width for table columns
MIN_TABLE_COLUMN_WIDTH = 10        # Minimum width for table columns
TRUNCATE_INDICATOR = "..."         # Indicator for truncated content
```

**Environment Variable Support:**

Users can override default locations using environment variables:
```bash
export FLOWY_TEMPLATES=/path/to/templates
export FLOWY_SAVES=/path/to/saves
```

## Tab Completion

### Completion Contexts

1. **Command Completion**: All available commands and their aliases
2. **Template Completion**: All `.template` files in templates folder, including subfolder paths
3. **Save File Completion**: All save files in saves folder (with or without `.save` extension), including subfolder paths
4. **Variable Completion**: Available variables for `set` and `unset` commands
5. **Option Completion**: Valid options for variables that define them

### Completion Behavior

- Template and save file completion includes folder structure
- Variable option completion shows only valid values defined in template
- Partial matches are suggested
- Case-insensitive matching where appropriate

## Error Handling

### Graceful Degradation

- Missing templates: Clear error message with available templates
- Invalid variables: Warning with list of valid variables
- File not found: Helpful error with path information
- Syntax errors in templates: Line number and error description
- Module import failures: Warning with module name and error

### Template Rendering Error Handling

**Detailed Error Reporting:**

When a template rendering error occurs, the application provides precise error information:

```
[red][bold]Template Rendering Error[/bold][/red]
================================================================================
Template: reports/monthly.template
Line: 47
Error: unexpected end of template

Context:
  45: {% for item in client_list %}
  46:   - {{ item.name }}
  47: {% endfor
      ^^^^^^^^^
  48: 
  49: ### Summary ###

The template syntax is invalid. Check for missing closing tags or braces.
```

**Error Tracking Features:**
- Exact line number where the error occurred
- Surrounding lines for context (±2 lines)
- Visual indicator pointing to the error location
- Clear error message with actionable guidance
- Full template path for easy navigation
- Preserves ability to continue using the application after error

**Implementation Details:**
- Wrap Jinja2 rendering in try-except blocks
- Parse Jinja2 exceptions to extract line numbers
- Map error positions back to original template file
- Include subtemplate context if error occurs in included template
- Maintain line number accuracy across template sections (VARS vs TEMPLATE)

### Undefined Variable Handling

**Visual Indication of Missing Variables:**

Instead of raising errors for undefined variables, the application renders them with visual markers:

```
Client Report for [red]<<client_name>>[/red]
=====================================

Report Date: 2024-01-15
Project: [red]<<project_name>>[/red]
Status: Active

Summary:
The project is progressing well with deliverables on schedule.
Contact: [red]<<contact_email>>[/red]
```

**Behavior:**
- Undefined variables render as `[red]<<variable_name>>[/red]` (red text with angle brackets)
- Allows template to complete rendering even with missing data
- Makes it immediately obvious which variables need to be set
- User can identify all missing variables in a single render
- No need to set variables one at a time and re-render repeatedly

**Configuration:**

```python
# Undefined Variable Handling
UNDEFINED_VARIABLE_TEMPLATE = "[red]<<{var}>>[/red]"
UNDEFINED_BEHAVIOR = "mark"  # Options: "mark", "error", "empty"
SHOW_UNDEFINED_SUMMARY = True  # Show summary of undefined vars after render
```

**Post-Render Summary:**

After rendering, if undefined variables were encountered:

```
Template rendered with undefined variables:
  - client_name
  - project_name
  - contact_email

Use 'set <variable> <value>' to define these variables.
```

**Jinja2 Configuration:**

The application configures Jinja2's undefined behavior using a custom `Undefined` class:

```python
from jinja2 import Undefined

class HighlightUndefined(Undefined):
    def __str__(self):
        return f"[red]<<{self._undefined_name}>>[/red]"
    
    def __getattr__(self, name):
        return self.__class__(name=f"{self._undefined_name}.{name}")
```

### Validation

- Template file format validation on load
- YAML syntax validation for VARS section
- Variable type checking where applicable
- Save file format validation
- Circular subtemplate inclusion detection
- Pre-render syntax check option (dry-run mode)

## Future Enhancements

### Potential Features

1. **Output Export**: Save rendered output to file
2. **Template Validation**: Dry-run mode to check templates without rendering
3. **Variable Import**: Import variables from JSON/YAML/CSV files
4. **Batch Processing**: Render multiple templates with different save files
5. **Template Snippets**: Reusable template fragments library
6. **Interactive Variable Wizard**: Guided variable entry for complex templates
7. **Diff Mode**: Compare outputs from different variable sets
8. **Plugin System**: Extend functionality with custom plugins
9. **Remote Templates**: Fetch templates from remote repositories
10. **Encrypted Save Files**: Support for sensitive data in save files

## Implementation Notes

### Key Dependencies

- **Jinja2**: Template engine
- **prompt_toolkit**: Advanced CLI interface with tab completion
- **colorama** or **termcolor**: Terminal color support
- **configparser**: Save file parsing
- **PyYAML**: YAML parsing for VARS section in templates
- **shutil**: Terminal size detection (`shutil.get_terminal_size()`)
- **textwrap**: Intelligent word wrapping functionality

### Performance Considerations

- Cache parsed templates to avoid re-parsing on each render
- Lazy-load modules only when needed by templates
- Implement efficient tab completion with indexing
- Stream large template outputs rather than buffering
- Cache terminal width to avoid repeated system calls
- Pre-compile word wrap patterns for performance
- Handle window resize signals (SIGWINCH) to update width dynamically

### Testing Strategy

- Unit tests for each command handler
- Template parsing and rendering tests
- State management and revert logic tests
- Tab completion behavior tests
- Integration tests for common workflows
- Word wrapping tests with various terminal widths
- Color formatting preservation tests across line breaks
- Subtemplate save file loading tests
- Terminal width detection and resize handling tests
- Error handling tests with intentionally malformed templates
- Undefined variable rendering and marking tests
- Line number accuracy tests for error reporting

## Version History

- **v1.0.0** (Planned): Initial release with core functionality
  - Interactive shell with tab completion
  - Template loading and rendering
  - Variable management (set/unset/save/load)
  - State management and history
  - Module system
  - Subtemplate support