# Template Assistant

**Interactive Jinja2 Template Rendering with Python Integration**

Template Assistant provides a Metasploit-inspired interactive shell for rendering Jinja2 templates with full Python integration, variable persistence, and crash recovery.

## ✨ Features

- 🔄 **Interactive shell** with tab completion and command history
- 📄 **Jinja2 template rendering** with color formatting support
- ⚙️ **Variable management** (set/unset/save/load)
- 💾 **Automatic state persistence** with crash recovery
- ⏪ **Smart revert functionality** (skips duplicate templates, toggle behavior)
- 📜 **Command audit trail** (.history file)
- 🐍 **Python module integration** (`{{ utils.format_date() }}`)
- 🎨 **Rich terminal output** with colors and formatting
- 📐 **Adaptive display** with automatic terminal width detection and intelligent word wrapping

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch Interactive Shell
```bash
python main.py
```

### 3. Example Session
```
╔═══════════════════════════════════════════════════════════════════════════╗
║                       TEMPLATE ASSISTANT v1.0.0                        ║
╚═══════════════════════════════════════════════════════════════════════════╝

[cyan]Configuration:[/cyan]
  Templates: ./templates
  Saves:     ./saves
  Modules:   ./modules
  State:     .state
  History:   .history

template-assistant > use example.template
[green]Loaded: example.template[/green]
template-assistant (example.template) > set client_name "Acme Corp"
[green]Set client_name = Acme Corp[/green]
template-assistant (example.template) > r
[bold]Report for Acme Corp[/bold]
====================================
Type: [green]weekly[/green]
template-assistant (example.template) > ls
```

### 🚀 Quick Launch Mode

Start Template Assistant with pre-loaded template and save file:

```bash
# Load template and save file, auto-render, then enter interactive mode
python main.py --template example.template --save example

# Load only template, enter interactive mode
python main.py --template reports/monthly.template

# Normal interactive mode (no pre-loading)
python main.py
```

**Quick launch workflow:**
1. Displays startup banner and configuration
2. Loads specified template (and save file if provided)
3. Auto-renders output if save file is provided
4. Drops into interactive mode for further commands

## 💻 Interactive Shell

**Metasploit-inspired CLI** with **tab completion**, **command aliases**, **rich output**, **session persistence**, and **adaptive display**.

### ⌨️ Tab Completion Contexts

| Context | Trigger | Examples |
|---------|---------|----------|
| **Commands** | Empty input or space | `r↹` → `render`, `ll↹` → `ls` |
| **Templates** | `use ` | `use rep↹` → `reports/monthly.template` |
| **Saves** | `load `, `save ` | `load cli↹` → `clients/demo` |
| **Variables** | `set `, `unset ` | `set cli↹` → `client_name` |
| **Options** | `set var ` | `set type↹` → `daily`, `weekly` |

### 📋 Command Reference

| Command | Aliases | Syntax | Description |
|---------|---------|---------|-------------|
| `use` | `load_template` | `use <template> [save]` | Load template (+ optional auto-render) |
| `load` | - | `load <save>` | Load variables from save file |
| `set` | - | `set <var> <value>` | Set variable (tab-complete vars/options) |
| `unset` | - | `unset <var>` | Remove variable |
| `save` | - | `save <save>` | Save current variables |
| `render` | `r`, `re` | `render` | Render current template (auto-wrapped to terminal width) |
| `ls` | `ll` | `ls` | Show variables table (adaptive column widths) |
| `help` | `h`, `?` | `help [command]` | Show available commands or detailed help |
| `revert` | - | `revert` | Toggle previous template state |
| `exit` | - | `exit` | Exit shell |

**Pro Tips:**
- `help` or `?` shows all commands
- `help <command>` shows detailed usage for a specific command
- `use template.save` → loads + auto-renders
- `python main.py --template X --save Y` → quick launch with auto-render
- `Ctrl+C` cancels input, `Ctrl+D` exits
- `revert` toggles between template states
- Session auto-saves to `.state`

## � Display & Output Management

The Template Assistant automatically adapts its output to your terminal dimensions for optimal readability.

### Terminal Width Detection

- **Automatic Detection**: On startup, the application detects your terminal width using `shutil.get_terminal_size()`
- **Dynamic Updates**: Window resize events (SIGWINCH on Unix-like systems) automatically update the display width
- **Fallback**: If detection fails (e.g., piped output), defaults to 80 columns
- **Configuration**: Set `AUTO_DETECT_WIDTH = False` in `configuration.py` to always use `DEFAULT_WIDTH`

### Intelligent Word Wrapping

All rendered output is automatically wrapped to fit your terminal width:

- **Color Preservation**: ANSI color codes and formatting (bold, backgrounds) are preserved across line breaks
- **No Horizontal Scrolling**: Long lines wrap intelligently at word boundaries
- **Configurable**: Disable with `WORD_WRAP_ENABLED = False` in `configuration.py`

**Example:**
```
# Terminal Width: 80 columns
[green][bold]Client Report[/bold][/green]
================================================================================

This is a very long line of text that will automatically wrap to the next line
when it reaches the edge of the terminal window, maintaining proper formatting
and ensuring readability without requiring horizontal scrolling.
```

### Adaptive Table Formatting

The `ls` command displays variable tables that automatically adjust to your terminal:

- **Dynamic Column Widths**: Columns expand/contract based on content and available space
- **Smart Truncation**: Long values are truncated with "..." when necessary
- **Minimum Widths**: Ensures columns remain readable even in narrow terminals
- **Configuration**: Adjust `MAX_TABLE_COLUMN_WIDTH` and `MIN_TABLE_COLUMN_WIDTH` in `configuration.py`

**Example:**
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

Customize display behavior in `configuration.py`:

```python
# Terminal Width & Wrapping
AUTO_DETECT_WIDTH = True           # Automatically detect terminal width
DEFAULT_WIDTH = 80                 # Fallback width if detection fails
WORD_WRAP_ENABLED = True           # Enable intelligent word wrapping
PRESERVE_FORMATTING_ON_WRAP = True # Maintain colors/bold across wrapped lines

# Table Formatting
MAX_TABLE_COLUMN_WIDTH = 40        # Maximum width for table columns
MIN_TABLE_COLUMN_WIDTH = 10        # Minimum width for table columns
TRUNCATE_INDICATOR = "..."         # Indicator for truncated content
```

## �📁 Project Structure

```
template-assistant/
├── main.py                   # Entry point with argparse
├── configuration.py          # Settings & aliases
├── interactive_shell.py      # Interactive CLI with tab completion
├── shell_completers.py       # Context-aware completion logic
├── display_manager.py        # Terminal width detection & adaptive formatting
├── state_manager.py          # Session persistence (.state)
├── history_logger.py         # Command audit (.history)
├── template_parser.py        # .template parsing
├── template_renderer.py      # Jinja2 engine + colors
├── module_loader.py          # Python modules (utils.py, helpers.py)
├── saves/                    # .save files
├── templates/                # .template files
├── modules/                  # Python functions
├── tests/                    # Unit tests
└── requirements.txt
```

**Note:** Save files (in `saves/`) no longer require `.save` extension and can be organized in subdirectories with any naming convention.

## 🐍 Python Module System

**Call custom Python functions directly from templates!**

### 📂 Directory Structure
```
modules/
├── utils.py      # Text processing, date formatting, truncation
└── helpers.py    # Calculations, currency formatting, pluralization
```

### ✨ Creating Custom Modules

Add `.py` files to `modules/` directory:

```python
# modules/my_functions.py
def my_function(param):
    """Docstring shows in template autocomplete."""
    return f"Processed: {param}"
```

### 📝 Usage in Templates

```jinja2
{{ utils.format_date('2024-01-15', '%B %d, %Y') }}  → 'January 15, 2024'
{{ utils.truncate(description, 100) }}              → 'First 100 chars...'
{{ helpers.format_currency(1234.56) }}              → '$1,234.56'
{{ helpers.pluralize(item_count, 'item') }}         → '5 items'
{{ helpers.calculate_total(items, 'price') }}       → '245.50'
```

### 🛠️ Built-in Example Modules

**`utils.py`:**
| Function | Example | Output |
|----------|---------|--------|
| `format_date(date, fmt)` | `{{ utils.format_date('2024-01-15', '%B %d') }}` | `January 15` |
| `truncate(text, length)` | `{{ utils.truncate(long_text, 50) }}` | `First 50 chars...` |
| `word_count(text)` | `{{ utils.word_count(paragraph) }}` | `247` |
| `slugify(text)` | `{{ utils.slugify('Hello World!') }}` | `hello-world` |

**`helpers.py`:**
| Function | Example | Output |
|----------|---------|--------|
| `format_currency(amount)` | `{{ helpers.format_currency(1234.56) }}` | `$1,234.56` |
| `calculate_total(items, key)` | `{{ helpers.calculate_total(items, 'price') }}` | `245.50` |
| `percentage(value, total)` | `{{ helpers.percentage(85, 100) }}` | `85.0%` |
| `pluralize(count, singular)` | `{{ helpers.pluralize(1, 'item') }}` | `item` |

### ⚙️ Configuration
```bash
export TEMPLATE_ASSISTANT_MODULES=/custom/modules
```

### 🔧 Features
- **Lazy Loading**: Modules loaded only when first accessed
- **Error Recovery**: Template continues rendering if module fails
- **Automatic Caching**: Modules loaded once per session
- **Thread-Safe**: Safe for concurrent rendering

### ✅ Test Module Demo
```bash
use module_demo.template module_demo
render
```

## ⚙️ Configuration

Customize via `configuration.py` or environment variables:

```bash
export TEMPLATE_ASSISTANT_TEMPLATES=/custom/templates
export TEMPLATE_ASSISTANT_SAVES=/custom/saves  
export TEMPLATE_ASSISTANT_MODULES=/custom/modules
```

**Key Settings:**
- `PROMPT_TEMPLATE`: Shell prompt format
- `COMMAND_ALIASES`: `render` → `r`, `re`
- `AUTO_DETECT_WIDTH`: Dynamic terminal sizing
- `UNDEFINED_VARIABLE_TEMPLATE`: `[red]<<var>>[/red]`

## 💾 State Management

- **`.state`** (JSON): Session persistence & crash recovery
  ```json
  {
    "current_template": "example.template",
    "variables": {"client_name": "Acme Corp"},
    "history": [...]
  }
  ```
- **`.history`** (text): Command audit trail
  ```
  2024-01-15 10:00:00 | use example.template
  2024-01-15 10:01:30 | set client_name "Acme Corp"
  ```

## 💾 Save File Management

Save files use **INI format** with intelligent section hierarchy:

### 📋 Section Types
- **`[general]`** - Applies to **all templates** (base variables)
- **`[reports/monthly.template]`** - Template-specific variables
- **`[common/header.template]`** - **Auto-loaded** for subtemplates

### ⚖️ Hierarchy Rules
```
template-specific OVERRIDES [general]
[reports/monthly.template.client_name] → "Acme Corp"
[general.company_name] → "Example Corp" (ignored for this template)
```

### 📁 Example: `saves/example`
```ini
[general]
company_name = Example Corp

[example.template]
client_name = Acme Corporation  # OVERRIDES general.company_name

[common/header.template]
logo_path = ./logos/company.png  # Auto-loaded for subtemplates
```

**Note:** Save files can be named with or without extensions and organized in subdirectories (e.g., `saves/projects/client_a`).

### 🔧 API

**SaveFileManager** (production-ready):
```python
# Load merged variables for template
vars = save_file_manager.load_variables_for_template("client", "example.template")

# Save template-specific variables
save_file_manager.save_variables("projects/client", vars, "reports/monthly.template")

# Full save file access
data = save_file_manager.load("client")
sections = save_file_manager.get_template_sections("client")
```

**Convenience functions:**
```python
load_save_file("client")
save_variables_to_file("new_save", vars, "my.template")
```

## 📝 Template Format

**.template** files have two sections:

```yaml
VARS:                    # Variable definitions (optional fields)
  - client_name:
      description: Client name
      default: "Unknown"
      options: ['Acme', 'Contoso']

### TEMPLATE ###          # Jinja2 content

Report for [bold]{{ client_name }}[/bold]
====================================
```

**Color/Formatting Syntax:**
```
[red]Red text[/red]
[bold]Bold[/bold] 
[green][bold]Green+Bold[/bold][/green]
```

## 🧪 Development

### Run Tests
```bash
python -m unittest discover tests
python -m unittest tests.test_module_loader     # Module system
python -m unittest tests.test_template_renderer # Rendering pipeline
```

### Test Specific Module
```bash
python -m unittest tests.test_template_parser
python -m unittest tests.test_state_manager
```

## 📚 References

- [Full Design Specification](AGENTS.md)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
- [Configuration Options](configuration.py)

## 🔧 Troubleshooting

### Display Issues

**Q: Output is not wrapping correctly**
- Check that `WORD_WRAP_ENABLED = True` in `configuration.py`
- Verify your terminal supports ANSI color codes
- Try resizing your terminal window to trigger width re-detection

**Q: Tables are too narrow/wide**
- Adjust `MAX_TABLE_COLUMN_WIDTH` and `MIN_TABLE_COLUMN_WIDTH` in `configuration.py`
- Ensure `AUTO_DETECT_WIDTH = True` for automatic detection

**Q: Colors are broken after wrapping**
- Set `PRESERVE_FORMATTING_ON_WRAP = True` in `configuration.py`
- Check that your terminal supports ANSI escape sequences

## License

MIT License - see [LICENSE](LICENSE) file or contact maintainer.
