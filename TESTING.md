# Testing Guide

This document provides comprehensive guidance for running and writing tests for the Flowy project. The project uses Python's `unittest` framework with 10 test modules covering all major components including template parsing, rendering, state management, display functionality, and the interactive shell.

All test files are located in the [`tests/`](tests/) directory.

---

## Quick Start

### Run All Tests

The easiest way to run the complete test suite:

```bash
./run_tests.sh
```

### Alternative Method

Run tests manually using Python's unittest:

```bash
python -m unittest discover tests
```

### Prerequisites

- Python 3.8 or higher
- All dependencies installed: `pip install -r requirements.txt`

---

## Test Execution Methods

### 1. Using the Test Runner Script

**Command:**
```bash
./run_tests.sh
```

**Benefits:**
- Colored output for easy readability
- Automatic summary of results
- Proper exit codes for CI/CD integration
- Pre-flight checks for Python and test directory

**Example Success Output:**
```
================================
  Flowy Test Suite Runner
================================

[INFO] Checking Python availability...
✓ Found Python 3: Python 3.10.0
[INFO] Checking tests/ directory...
✓ Found tests/ directory

[INFO] Running all tests in tests/ directory...
================================================

test_parse_valid_template_with_all_fields (tests.test_template_parser.TestTemplateParser) ... ok
test_parse_template_missing_vars_section (tests.test_template_parser.TestTemplateParser) ... ok
...

Ran X tests in Y.YYYs

OK

================================================
✓ All tests passed!
Test suite completed successfully.
```

**Example Failure Output:**
```
================================================
✗ Some tests failed!
Review the output above for details.
Run specific test files with: python -m unittest tests.test_<module>
```

### 2. Running All Tests Manually

**Command:**
```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

**Flags Explained:**
- `-s tests`: Start directory for test discovery
- `-p 'test_*.py'`: Pattern to match test files (all files starting with `test_`)
- `-v`: Verbose output showing individual test names

### 3. Running Individual Test Files

**Command Pattern:**
```bash
python -m unittest tests.test_<module>
```

**Examples:**
```bash
# Test template parsing functionality
python -m unittest tests.test_template_parser

# Test state management (session persistence, history)
python -m unittest tests.test_state_manager

# Test display and formatting functionality
python -m unittest tests.test_display_manager

# Test the main entry point
python -m unittest tests.test_main
```

**When to Use:** Testing specific functionality after making changes to a particular module.

### 4. Running Specific Test Classes

**Command Pattern:**
```bash
python -m unittest tests.test_<module>.TestClassName
```

**Example:**
```bash
python -m unittest tests.test_template_parser.TestTemplateParser
```

**When to Use:** Focusing on a specific component's tests within a test file.

### 5. Running Individual Test Methods

**Command Pattern:**
```bash
python -m unittest tests.test_<module>.TestClassName.test_method_name
```

**Example:**
```bash
python -m unittest tests.test_template_parser.TestTemplateParser.test_parse_valid_template_with_all_fields
```

**When to Use:** Debugging a specific failing test or verifying a particular fix.

---

## Test Coverage

The project includes 10 comprehensive test modules covering all major components:

| Test Module | Description |
|-------------|-------------|
| [`test_template_parser.py`](tests/test_template_parser.py) | Template file parsing, VARS section validation, metadata extraction |
| [`test_template_renderer.py`](tests/test_template_renderer.py) | Jinja2 rendering, color formatting, undefined variable handling |
| [`test_state_manager.py`](tests/test_state_manager.py) | Session persistence, history tracking, revert functionality |
| [`test_save_file_manager.py`](tests/test_save_file_manager.py) | INI file loading/saving, section hierarchy management |
| [`test_module_loader.py`](tests/test_module_loader.py) | Python module dynamic loading and function access |
| [`test_display_manager.py`](tests/test_display_manager.py) | Terminal width detection, word wrapping, table formatting |
| [`test_interactive_shell.py`](tests/test_interactive_shell.py) | Command parsing, shell lifecycle, command execution |
| [`test_file_validator.py`](tests/test_file_validator.py) | File duplicate detection, basename validation, directory structure validation |
| [`test_history_logger.py`](tests/test_history_logger.py) | Command audit trail and logging |
| [`test_main.py`](tests/test_main.py) | Argument parsing, entry point initialization |

**Total Test Count:** A comprehensive test suite covering normal operations, edge cases, and error conditions.

---

## Interpreting Test Results

### Success Output

```
...
----------------------------------------------------------------------
Ran X tests in Y.YYYs

OK
```

- **"Ran X tests in Y.YYYs"**: Shows total test count and execution time
- **"OK"**: All tests passed
- **Exit code 0**: Indicates success (important for CI/CD)

### Failure Output

```
======================================================================
FAIL: test_parse_template_missing_vars_section (tests.test_template_parser.TestTemplateParser)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/path/to/tests/test_template_parser.py", line 45, in test_parse_template_missing_vars_section
    self.assertIsNone(result)
AssertionError: {'name': 'test'} is not None

----------------------------------------------------------------------
Ran X tests in Y.YYYs

FAILED (failures=1)
```

**Understanding Failures:**
- **Test file and line number**: `tests/test_template_parser.py`, line 45
- **Assertion error message**: Shows what assertion failed
- **Expected vs actual values**: `{'name': 'test'} is not None`
- **Exit code 1**: Indicates failures

**Tip:** Focus on the first failure, as subsequent failures may be cascading effects of the initial issue.

### Error Output

```
======================================================================
ERROR: test_load_template (tests.test_template_parser.TestTemplateParser)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/path/to/tests/test_template_parser.py", line 30, in test_load_template
    result = parser.load_template('nonexistent.txt')
  File "/path/to/template_parser.py", line 55, in load_template
    with open(path, 'r') as f:
FileNotFoundError: [Errno 2] No such file or directory: 'nonexistent.txt'
```

**Distinguishing Errors from Failures:**
- **Failures**: Assertion methods returned False (expected behavior didn't match)
- **Errors**: Unexpected exceptions occurred during test execution

**Common Error Causes:**
- Missing dependencies
- File permission issues
- Environment variable problems
- Incorrect working directory

---

## Writing New Tests

### Test File Structure

Create new test files following this template:

```python
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module_name import ClassToTest

class TestModuleName(unittest.TestCase):
    def setUp(self):
        """Setup code run before each test method"""
        # Initialize test fixtures, create temp files, etc.
        pass

    def tearDown(self):
        """Cleanup code run after each test method"""
        # Clean up temp files, close connections, etc.
        pass

    def test_feature_name(self):
        """Test description explaining what this test verifies"""
        # Arrange: Set up test data
        expected = "expected result"

        # Act: Execute the code being tested
        actual = ClassToTest().method()

        # Assert: Verify the result
        self.assertEqual(expected, actual)
```

### Testing Patterns Used in This Project

**Comprehensive Test Organization** ([test_template_parser.py](tests/test_template_parser.py)):
- Multiple test methods covering different scenarios
- Separate tests for success cases, edge cases, and error conditions
- Descriptive test names following `test_<feature>_<scenario>_<expected_result>` pattern

**File-Based Testing with Temp Directories** ([test_state_manager.py](tests/test_state_manager.py)):
```python
import tempfile
import shutil

def setUp(self):
    self.test_dir = tempfile.mkdtemp()

def tearDown(self):
    shutil.rmtree(self.test_dir)
```

**Mocking External Dependencies** ([test_display_manager.py](tests/test_display_manager.py)):
```python
from unittest.mock import patch

def test_terminal_width(self):
    with patch('shutil.get_terminal_size') as mock_size:
        mock_size.return_value = (80, 24)
        # Test code using mocked terminal size
```

### Common Assertion Methods

| Assertion Method | Description |
|------------------|-------------|
| `assertEqual(a, b)` | Verify `a == b` |
| `assertNotEqual(a, b)` | Verify `a != b` |
| `assertTrue(x)` | Verify `x` is `True` |
| `assertFalse(x)` | Verify `x` is `False` |
| `assertIsNone(x)` | Verify `x is None` |
| `assertIsNotNone(x)` | Verify `x is not None` |
| `assertIn(item, container)` | Verify `item in container` |
| `assertNotIn(item, container)` | Verify `item not in container` |
| `assertRaises(Exception)` | Verify code raises specified exception |
| `assertRaisesRegex(Exception, regex)` | Verify exception message matches pattern |

For a complete list, see the [Python unittest documentation](https://docs.python.org/3/library/unittest.html#assert-methods).

### Test Naming Best Practices

Use descriptive names that explain what the test verifies:

✅ **Good:**
```python
def test_parse_template_with_all_fields_returns_complete_metadata(self):
def test_render_template_with_undefined_variable_raises_error(self):
def test_save_state_creates_new_file_when_none_exists(self):
```

❌ **Bad:**
```python
def test_parser(self):
def test_render(self):
def test_save(self):
```

---

## Continuous Integration

The `run_tests.sh` script is designed for CI/CD integration:

- **Exit code 0**: All tests passed (CI build succeeds)
- **Exit code 1**: Some tests failed (CI build fails)

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: ./run_tests.sh
```

### GitLab CI Example

```yaml
test:
  image: python:3.10
  before_script:
    - pip install -r requirements.txt
  script:
    - ./run_tests.sh
```

---

## Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'jinja2'" (or similar)

**Cause:** Missing dependencies

**Solution:**
```bash
pip install -r requirements.txt
```

### Problem: "Permission denied: ./run_tests.sh"

**Cause:** Script is not executable

**Solution:**
```bash
chmod +x run_tests.sh
```

### Problem: "No module named 'tests'"

**Cause:** Running from wrong directory

**Solution:** Always run tests from the project root directory:
```bash
cd /path/to/flowy
./run_tests.sh
```

### Problem: Tests pass locally but fail in CI

**Possible Causes:**
- Environment differences (Python version, OS)
- Missing environment variables
- File path assumptions (absolute vs relative paths)

**Solutions:**
- Check [configuration.py](configuration.py) for environment variables
- Use `os.path.join()` for path construction in tests
- Verify Python version compatibility

### Problem: Slow test execution

**Cause:** Many file I/O operations in the full test suite

**Solution:** During development, run specific test files:
```bash
# Only test the module you're working on
python -m unittest tests.test_template_parser
```

### Problem: Test fails with "AssertionError" but no clear reason

**Solution:** Add `-v` flag for verbose output:
```bash
python -m unittest tests.test_module -v
```

Or add debug prints in your test:
```python
def test_something(self):
    result = function_under_test()
    print(f"DEBUG: result = {result}")  # Will show in test output
    self.assertEqual(expected, result)
```

---

## Best Practices

1. **Run tests before committing code**
   ```bash
   ./run_tests.sh && git commit
   ```

2. **Write tests for new features before implementation (TDD)**
   - Write failing test first
   - Implement feature to make test pass
   - Refactor while keeping tests green

3. **Keep tests isolated**
   - No dependencies between test methods
   - Each test should work independently
   - Use `setUp()` and `tearDown()` for clean state

4. **Use descriptive test names**
   - Pattern: `test_<feature>_<scenario>_<expected_result>`
   - Example: `test_parse_template_with_missing_vars_section_returns_none`

5. **Clean up resources in `tearDown()`**
   - Remove temporary files
   - Close file handles
   - Reset global state
   - Prevents test pollution

6. **Mock external dependencies**
   - File system operations (when appropriate)
   - Network calls
   - System calls
   - Makes tests faster and more reliable

7. **Test both success and failure cases**
   - Happy path (normal operation)
   - Edge cases (boundary conditions)
   - Error conditions (invalid input, exceptions)

8. **Keep tests simple and focused**
   - One assertion per test (when possible)
   - Test one thing at a time
   - Avoid complex logic in tests

---

## Additional Resources

- **Python unittest documentation:** https://docs.python.org/3/library/unittest.html
- **Project README:** [README.md](README.md) - General development information
- **Installation Guide:** [INSTALL.md](INSTALL.md) - Setup instructions
- **Test Directory:** [tests/](tests/) - Browse all test files

---

**Need Help?** If you encounter issues not covered in this guide, check existing test files in the [`tests/`](tests/) directory for examples of similar testing scenarios.
