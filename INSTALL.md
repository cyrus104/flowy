# Installation Guide

This guide provides comprehensive installation instructions for the template-assistant CLI application.

## Prerequisites

Before installing template-assistant, ensure you have:

- **Python 3.8 or higher** - Check your version with:
  ```bash
  python --version
  # or
  python3 --version
  ```

- **pip package manager** - Usually included with Python. Verify with:
  ```bash
  pip --version
  ```

- **Optional**: virtualenv or venv for isolated environments (recommended)

## Installation Methods

### 1. Install from Wheel (Recommended for Users)

For users who have downloaded a pre-built wheel file:

1. Download the wheel file (e.g., `template_assistant-<version>-py3-none-any.whl`)

2. Install using pip:
   ```bash
   pip install template_assistant-<version>-py3-none-any.whl
   ```

   Or install any wheel file from the `dist/` directory:
   ```bash
   pip install dist/*.whl
   ```

3. Verify installation:
   ```bash
   template-assistant --help
   ```

4. **Note**: Replace `<version>` with the actual version number of your downloaded wheel file, or use the glob pattern `dist/*.whl` to install the latest built wheel.

### 2. Install from PyPI (Future)

Once published to PyPI, users will be able to install with:

```bash
# Install the latest version
pip install template-assistant

# Upgrade to the latest version
pip install --upgrade template-assistant
```

**Note**: This method is not yet available as the package hasn't been published to PyPI.

### 3. Development Mode (For Contributors)

For developers who want to modify the code and have changes take effect immediately:

1. Clone or download the repository

2. Navigate to the project directory:
   ```bash
   cd /path/to/template-assistant
   ```

3. Install in editable mode:
   ```bash
   pip install -e .
   ```

4. This creates a symlink to the source code, so any changes you make will take effect immediately without reinstalling

5. Verify installation:
   ```bash
   template-assistant --help
   ```

### 4. Install from Source

For users who want to build from source:

1. Clone or download the repository

2. Navigate to the project directory:
   ```bash
   cd /path/to/template-assistant
   ```

3. Install build dependencies:
   ```bash
   pip install build
   ```

4. Build the wheel:
   ```bash
   # Using the automated build script (Unix-like systems)
   ./build.sh

   # Or manually
   python -m build
   ```

5. Install the generated wheel:
   ```bash
   pip install dist/template_assistant-<version>-py3-none-any.whl
   ```

   Or install using a glob pattern:
   ```bash
   pip install dist/*.whl
   ```

## Virtual Environment (Recommended)

Using a virtual environment is recommended to isolate dependencies and avoid conflicts:

```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install template-assistant (replace <version> with actual version)
pip install template_assistant-<version>-py3-none-any.whl
# Or use glob pattern
pip install dist/*.whl

# Deactivate when done
deactivate
```

## Basic Usage

After installation, the `template-assistant` command is available system-wide (or within your virtual environment).

### Interactive Mode

Launch the interactive shell with tab completion and command history:

```bash
template-assistant
```

### Quick Launch Mode

Load templates and save files directly from the command line:

```bash
# Load template only
template-assistant --template example.template

# Load template and save file, auto-render
template-assistant --template example.template --save example
```

### Common Commands

Once in the interactive shell:

- `use <template>` - Load a template file
- `set <var> <value>` - Set a variable value
- `render` or `r` - Render the template with current variables
- `ls` or `ll` - List all variables and their values
- `help` or `?` - Show available commands
- `exit` - Exit the interactive shell

## Verifying Installation

Check that the installation was successful:

```bash
# Check command availability
template-assistant --help

# Check version programmatically
python -c "import configuration; print(configuration.VERSION)"

# Run a quick test
template-assistant --template templates/example.template
```

## Uninstallation

To remove template-assistant from your system:

```bash
pip uninstall template-assistant
```

## Troubleshooting

### Command Not Found

If the `template-assistant` command is not found after installation:

- Ensure pip's script directory is in your PATH
  - **Linux/macOS**: Add `~/.local/bin` to PATH
  - **Windows**: Add `%APPDATA%\Python\Scripts` to PATH

- Try using the module directly as an alternative:
  ```bash
  python -m main
  ```

- If using a virtual environment, ensure it's activated

### Permission Errors

If you encounter permission errors during installation:

- Use the `--user` flag to install for the current user only:
  ```bash
  pip install --user template_assistant-<version>-py3-none-any.whl
  # Or use glob pattern
  pip install --user dist/*.whl
  ```

- Use a virtual environment (recommended approach)

- **Avoid** using `sudo pip install` on Linux/macOS as it can cause system-wide conflicts

### Dependency Conflicts

If you experience issues with dependencies:

- Use a virtual environment to isolate dependencies (strongly recommended)

- Check installed dependency versions:
  ```bash
  pip list | grep -E "Jinja2|prompt_toolkit|PyYAML|colorama"
  ```

- Upgrade dependencies to their latest compatible versions:
  ```bash
  pip install --upgrade Jinja2 prompt_toolkit PyYAML colorama
  ```

### Import Errors

If you encounter import errors when running template-assistant:

- Verify all dependencies are correctly installed:
  ```bash
  pip check
  ```

- Try reinstalling the package:
  ```bash
  pip uninstall template-assistant
  pip install template_assistant-<version>-py3-none-any.whl
  # Or use glob pattern
  pip install dist/*.whl
  ```

- Ensure you're using the correct Python version (3.8+)

## Next Steps

For detailed usage instructions, features, and examples, see the comprehensive documentation:

- **[README.md](README.md)** - Complete user guide covering:
  - Template format and syntax
  - Variable management and save files
  - Python module integration
  - Display configuration
  - State management
  - Advanced features and examples

- **[AGENTS.md](AGENTS.md)** - Full design specification and architecture

## Dependencies

template-assistant requires the following packages (automatically installed):

- **Jinja2** - Template rendering engine
- **prompt_toolkit** - Interactive shell with autocomplete
- **PyYAML** - Save file parsing
- **colorama** - Cross-platform colored terminal output

These dependencies are specified in `pyproject.toml` and will be installed automatically when you install template-assistant.
