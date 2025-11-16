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

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create a Template
Create `templates/example.template`:
```yaml
VARS:
  - client_name:
      description: Client organization
  - report_type:
      description: Report type
      options: ['daily', 'weekly', 'monthly']

### TEMPLATE ###

[bold]Report for {{ client_name }}[/bold]
====================================

Type: [green]{{ report_type }}[/green]

{% if report_type == 'weekly' %}
Weekly summary generated on {{ current_date }}.
{% endif %}
```

### 3. Launch Interactive Shell
```bash
python main.py
```

### 4. Basic Usage
```
template-assistant > use example.template
template-assistant (example.template) > ls
template-assistant (example.template) > set client_name "Acme Corp"
template-assistant (example.template) > set report_type weekly
template-assistant (example.template) > render
```

## 📁 Project Structure

```
template-assistant/
├── configuration.py          # App settings & environment vars
├── main.py                  # Interactive shell entry point
├── state_manager.py         # Session persistence (.state)
├── history_logger.py        # Command audit trail (.history)
├── template_parser.py       # Template parsing & validation
├── template_renderer.py     # Jinja2 rendering engine with color formatting, subtemplate support, undefined handling
├── module_loader.py         # Dynamic Python module loading for templates
├── saves/                   # .save variable files
├── templates/               # .template files
├── modules/                 # Python functions for templates (utils.py, helpers.py)
├── tests/                   # Unit tests
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── AGENTS.md                # Detailed design spec
```

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
use module_demo.template module_demo.save
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

### 📁 Example: `saves/example.save`
```ini
[general]
company_name = Example Corp

[example.template]
client_name = Acme Corporation  # OVERRIDES general.company_name

[common/header.template]
logo_path = ./logos/company.png  # Auto-loaded for subtemplates
```

### 🔧 API

**SaveFileManager** (production-ready):
```python
# Load merged variables for template
vars = save_file_manager.load_variables_for_template("client.save", "example.template")

# Save template-specific variables
save_file_manager.save_variables("projects/client.save", vars, "reports/monthly.template")

# Full save file access
data = save_file_manager.load("client.save")
sections = save_file_manager.get_template_sections("client.save")
```

**Convenience functions:**
```python
load_save_file("client.save")
save_variables_to_file("new.save", vars, "my.template")
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

## License

MIT License - see [LICENSE](LICENSE) file or contact maintainer.
