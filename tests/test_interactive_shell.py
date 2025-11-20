"""
Unit Tests for Interactive Shell

Comprehensive test suite for interactive_shell.py and shell_completers.py.
"""

import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interactive_shell import InteractiveShell
from shell_completers import ShellCompleter, _get_template_files, _get_save_files
from template_parser import TemplateParser, TemplateDefinition
from template_renderer import RenderResult


class TestShellCompleters(unittest.TestCase):
    """Test tab completion logic."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.templates_dir = Path(self.temp_dir) / 'templates'
        self.saves_dir = Path(self.temp_dir) / 'saves'
        self.templates_dir.mkdir()
        self.saves_dir.mkdir()
        
        # Patch configuration paths for test isolation
        self.patcher = patch.dict('configuration.__dict__', {
            'TEMPLATES_DIR': str(self.templates_dir),
            'SAVES_DIR': str(self.saves_dir)
        })
        self.patcher.start()
        
        # Reload shell_completers to pick up patched config
        import importlib
        import shell_completers
        importlib.reload(shell_completers)
    
    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    def create_test_template(self, name: str):
        """Create test template file."""
        (self.templates_dir / name).touch()
    
    def create_test_save(self, name: str):
        """Create test save file."""
        (self.saves_dir / name).touch()
    
    def test_get_template_files(self):
        """Test template file discovery."""
        self.create_test_template('test.template')
        self.create_test_template('reports/monthly.template')
        
        templates = _get_template_files()
        self.assertIn('test', templates)
        self.assertIn('reports/monthly', templates)
    
    def test_get_save_files(self):
        """Test save file discovery with extensionless format."""
        self.create_test_save('test')
        self.create_test_save('projects/client')

        saves = _get_save_files()
        self.assertIn('test', saves)
        self.assertIn('projects/client', saves)

    def test_get_save_files_filters_hidden_files(self):
        """Test that _get_save_files excludes hidden files and directories."""
        # Create normal save files
        self.create_test_save('normal_file')

        # Create subdirectory for nested save
        (self.saves_dir / 'projects').mkdir(exist_ok=True)
        self.create_test_save('projects/client')

        # Create hidden files that should be filtered out
        (self.saves_dir / '.DS_Store').touch()
        (self.saves_dir / '.gitkeep').touch()

        # Create hidden directory with file inside
        hidden_dir = self.saves_dir / '.hidden'
        hidden_dir.mkdir()
        (hidden_dir / 'secret').touch()

        # Create file in directory that starts with dot
        dotdir = self.saves_dir / '.cache'
        dotdir.mkdir()
        (dotdir / 'file').touch()

        saves = _get_save_files()

        # Normal files should be included
        self.assertIn('normal_file', saves)
        self.assertIn('projects/client', saves)

        # Hidden files should be excluded
        self.assertNotIn('.DS_Store', saves)
        self.assertNotIn('.gitkeep', saves)
        self.assertNotIn('.hidden/secret', saves)
        self.assertNotIn('.cache/file', saves)

    def test_command_completion(self):
        """Test command completion."""
        test_aliases = {
            'render': ['r', 're'],
            'ls': ['ll'],
            'use': ['load_template']
        }
        
        with patch('shell_completers.COMMAND_ALIASES', test_aliases):
            # Reload to pick up patched aliases
            import importlib
            import shell_completers
            importlib.reload(shell_completers)
            from shell_completers import ShellCompleter
            
            completer = ShellCompleter()
            
            # Mock document for testing
            class MockDocument:
                def __init__(self, text_before_cursor):
                    self.text_before_cursor = text_before_cursor
                    self.current_line_before_cursor = text_before_cursor
            
            # Test 'r' → should include 'r', 're', and 'render'
            completions = list(completer.get_completions(MockDocument('r'), None))
            completion_texts = [c.text for c in completions]
            self.assertIn('render', completion_texts)
            self.assertIn('re', completion_texts)
            
            # Test 'l' → should include 'ls', 'll', and 'load_template'
            completions = list(completer.get_completions(MockDocument('l'), None))
            completion_texts = [c.text for c in completions]
            self.assertIn('ls', completion_texts)
            self.assertIn('ll', completion_texts)
            self.assertIn('load_template', completion_texts)

    def test_non_aliased_command_completion(self):
        """Test completion of non-aliased commands like exit and revert."""
        completer = ShellCompleter()

        # Mock document for testing
        class MockDocument:
            def __init__(self, text_before_cursor):
                self.text_before_cursor = text_before_cursor
                self.current_line_before_cursor = text_before_cursor

        # Test 'e' → should include 'exit'
        completions = list(completer.get_completions(MockDocument('e'), None))
        completion_texts = [c.text for c in completions]
        self.assertIn('exit', completion_texts)

        # Test 'rev' → should include 'revert'
        completions = list(completer.get_completions(MockDocument('rev'), None))
        completion_texts = [c.text for c in completions]
        self.assertIn('revert', completion_texts)

    def test_template_completion_context(self):
        """Test template completion for 'use' command."""
        self.create_test_template('report.template')
        self.create_test_template('docs/guide.template')
        
        completer = ShellCompleter()
        
        # Test 'use ' with space should complete templates, not commands
        class MockDocumentSpace:
            text_before_cursor = 'use '
            current_line_before_cursor = 'use '
        doc = MockDocumentSpace()
        completions = list(completer.get_completions(doc, None))
        completion_texts = [c.text for c in completions]
        # Should show template names without .template extension
        self.assertIn('report', completion_texts)
        self.assertIn('docs/guide', completion_texts)
        # Should NOT show commands
        self.assertNotIn('render', completion_texts)
        self.assertNotIn('load', completion_texts)
        
        # Test 'use rep' should filter templates
        class MockDocumentPartial:
            text_before_cursor = 'use rep'
            current_line_before_cursor = 'use rep'
        doc = MockDocumentPartial()
        completions = list(completer.get_completions(doc, None))
        completion_texts = [c.text for c in completions]
        self.assertIn('report', completion_texts)
        self.assertNotIn('docs/guide', completion_texts)
    
    def test_save_completion_for_use_command(self):
        """Test save file completion as second argument for 'use' command."""
        self.create_test_template('report.template')
        (self.saves_dir / 'client_a').write_text('[general]\nname=Test')
        (self.saves_dir / 'project_x').write_text('[general]\nname=Test')

        completer = ShellCompleter()

        # Test 'use report ' should complete save files
        class MockDocument:
            text_before_cursor = 'use report '
            current_line_before_cursor = 'use report '
        doc = MockDocument()
        completions = list(completer.get_completions(doc, None))
        completion_texts = [c.text for c in completions]
        # Should show save names with extensionless format
        self.assertIn('client_a', completion_texts)
        self.assertIn('project_x', completion_texts)
    
    def test_extension_optional_use_command(self):
        """Test cmd_use handles template names without .template extension."""
        # Create template without relying on setUp
        example_template = self.templates_dir / 'example.template'
        example_template.write_text("""
VARS:
  - title:
      description: Example title

### TEMPLATE ###
{{ title }}
        """)

        with patch('interactive_shell.TEMPLATES_DIR', str(self.templates_dir)), \
             patch('interactive_shell.SAVES_DIR', str(self.saves_dir)), \
             patch('interactive_shell.state_manager.set_template'), \
             patch('interactive_shell.save_file_manager'), \
             patch('interactive_shell.history_logger'):
            
            shell = InteractiveShell()
            
            # Test loading without extension
            shell.cmd_use(['example'])
            shell.template_parser.parse.assert_called_once()
            # Should have resolved to example.template
            self.assertIsNotNone(shell.current_template)
    
    def test_extension_optional_load_command(self):
        """Test cmd_load handles save files with extensionless format."""
        # Create save file
        example_save = self.saves_dir / 'example'
        example_save.write_text('[general]\ntitle=Test')

        with patch('interactive_shell.TEMPLATES_DIR', str(self.templates_dir)), \
             patch('interactive_shell.SAVES_DIR', str(self.saves_dir)), \
             patch('interactive_shell.state_manager'), \
             patch('interactive_shell.save_file_manager.load_variables_for_template') as mock_load_vars, \
             patch('interactive_shell.history_logger'):

            mock_load_vars.return_value = {'title': 'Test'}
            shell = InteractiveShell()
            shell.current_template = Mock(relative_path='test.template')  # Mock current template

            shell.cmd_load(['example'])
            mock_load_vars.assert_called()
    
    def test_tab_completion_use_space(self):
        """Test 'use ' + TAB shows templates, not commands."""
        self.create_test_template('example.template')
        self.create_test_template('test.template')

        completer = ShellCompleter(template_def=None)
        
        # Mock document for 'use '
        class MockDocUseSpace:
            text_before_cursor = 'use '
            current_line_before_cursor = 'use '
        
        completions = list(completer.get_completions(MockDocUseSpace(), None))
        texts = [c.text for c in completions]
        self.assertIn('example', texts)
        self.assertIn('test', texts)
        self.assertNotIn('render', texts)
        self.assertNotIn('load', texts)
    
    def test_tab_completion_use_example_space(self):
        """Test 'use example ' + TAB shows saves with extensionless format."""
        self.create_test_save('client')
        self.create_test_save('project')

        completer = ShellCompleter(template_def=None)

        class MockDocUseExampleSpace:
            text_before_cursor = 'use example '
            current_line_before_cursor = 'use example '

        completions = list(completer.get_completions(MockDocUseExampleSpace(), None))
        texts = [c.text for c in completions]
        self.assertIn('client', texts)
        self.assertIn('project', texts)

    def test_variable_option_completion_for_set_command(self):
        """Test tab completion for variable options in set command."""
        # Create mock template definition with a variable that has options
        from template_parser import VariableDefinition
        mock_template_def = Mock()
        mock_var = VariableDefinition(
            name='report_type',
            description='Report type',
            default='daily',
            options=['daily', 'weekly', 'monthly', 'quarterly']
        )
        mock_template_def.variables = {'report_type': mock_var, 'client_name': VariableDefinition(
            name='client_name',
            description='Client name',
            default='',
            options=[]
        )}

        completer = ShellCompleter(template_def=mock_template_def)

        # Test 'set report_type ' with trailing space shows all options
        class MockDocSetSpace:
            text_before_cursor = 'set report_type '
            current_line_before_cursor = 'set report_type '

        completions = list(completer.get_completions(MockDocSetSpace(), None))
        texts = [c.text for c in completions]
        self.assertIn('daily', texts)
        self.assertIn('weekly', texts)
        self.assertIn('monthly', texts)
        self.assertIn('quarterly', texts)

        # Test 'set report_type w' shows only matching options
        class MockDocSetPartial:
            text_before_cursor = 'set report_type w'
            current_line_before_cursor = 'set report_type w'

        completions = list(completer.get_completions(MockDocSetPartial(), None))
        texts = [c.text for c in completions]
        self.assertIn('weekly', texts)
        self.assertNotIn('daily', texts)
        self.assertNotIn('monthly', texts)
        self.assertNotIn('quarterly', texts)

    def test_variable_option_completion_no_options(self):
        """Test that variables without options don't show completions."""
        # Create mock template definition with a variable that has no options
        from template_parser import VariableDefinition
        mock_template_def = Mock()
        mock_var = VariableDefinition(
            name='client_name',
            description='Client name',
            default='',
            options=[]
        )
        mock_template_def.variables = {'client_name': mock_var}

        completer = ShellCompleter(template_def=mock_template_def)

        # Test 'set client_name ' should show no completions
        class MockDocSetNoOptions:
            text_before_cursor = 'set client_name '
            current_line_before_cursor = 'set client_name '

        completions = list(completer.get_completions(MockDocSetNoOptions(), None))
        texts = [c.text for c in completions]
        # Should be empty since there are no options defined
        self.assertEqual(len(texts), 0)


# Insert after the existing test_template_completion_context method or before TestInteractiveShell class
class TestInteractiveShell(unittest.TestCase):
    """Test interactive shell command handlers."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.templates_dir = Path(self.temp_dir) / 'templates'
        self.saves_dir = Path(self.temp_dir) / 'saves'
        self.templates_dir.mkdir()
        self.saves_dir.mkdir()
        
        # Create test template
        test_template = self.templates_dir / 'test.template'
        test_template.write_text("""
VARS:
  - name:
      description: Test variable
      default: World
      options: [Alice, Bob]

### TEMPLATE ###
Hello {{ name }}!
        """)
        
        # Create another template for extension testing
        example_template = self.templates_dir / 'example.template'
        example_template.write_text("""
VARS:
  - title:
      description: Title

### TEMPLATE ###
Title: {{ title }}
        """)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.save_file_manager')
    @patch('interactive_shell.TemplateParser')
    @patch('interactive_shell.template_renderer')
    @patch('interactive_shell.history_logger')
    def test_cmd_use(self, mock_history, mock_renderer, mock_parser, mock_save, mock_state):
        """Test use command."""
        mock_template_def = Mock()
        mock_template_def.relative_path = 'test.template'
        mock_parser.parse.return_value = mock_template_def
        
        shell = InteractiveShell()
        
        # Test basic use
        shell.cmd_use(['test.template'])
        mock_parser.parse.assert_called_once_with('test.template')
        mock_state.set_template.assert_called_once_with('test.template')
        
        # Test use with save
        shell.cmd_use(['test.template', 'test'])
        mock_save.load_variables_for_template.assert_called()
    
    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.save_file_manager')
    def test_cmd_load(self, mock_save, mock_state):
        """Test load command with extensionless format."""
        mock_variables = {'name': 'Alice'}
        mock_save.load_variables_for_template.return_value = mock_variables

        shell = InteractiveShell()
        shell.current_template = Mock()
        shell.current_template.relative_path = 'test.template'

        shell.cmd_load(['test'])
        mock_save.load_variables_for_template.assert_called_once_with(
            'test', 'test.template'
        )
        mock_state.set_variables.assert_called_once_with(mock_variables)
    
    @patch('interactive_shell.state_manager')
    def test_cmd_set(self, mock_state):
        """Test set command."""
        mock_template = Mock()
        mock_template.variables = {'name': Mock()}
        
        shell = InteractiveShell()
        shell.current_template = mock_template
        
        shell.cmd_set(['name', 'Alice'])
        mock_state.set_variable.assert_called_once_with('name', 'Alice')
    
    @patch('interactive_shell.state_manager')
    def test_cmd_render(self, mock_state):
        """Test render command."""
        mock_variables = {'name': 'Alice'}
        mock_result = RenderResult(output='Hello Alice!', success=True)
        mock_state.get_all_variables.return_value = mock_variables
        
        shell = InteractiveShell()
        shell.renderer.render.return_value = mock_result
        shell.current_template = Mock()
        
        shell.cmd_render([])
        shell.renderer.render.assert_called_once()
    
    def test_cmd_ls(self):
        """Test ls command table formatting."""
        shell = InteractiveShell()
        shell.current_template = Mock()
        shell.current_template.variables = {
            'name': Mock(description='Test variable', default='World', options=['Alice', 'Bob'])
        }
        shell.current_template.relative_path = 'test.template'
        
        with patch('interactive_shell.state_manager.get_all_variables', return_value={'name': 'Alice'}):
            shell.cmd_ls([])

    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.TemplateParser')
    def test_cmd_revert(self, mock_parser, mock_state):
        """Test revert command."""
        mock_template = Mock()
        mock_template.relative_path = 'previous.template'
        mock_parser.parse.return_value = mock_template
        mock_state.revert.return_value = True
        mock_state.get_current_template.return_value = 'previous.template'

        shell = InteractiveShell()
        shell.cmd_revert([])

        mock_state.revert.assert_called_once()
        mock_parser.parse.assert_called_once_with('previous.template')

    @patch('interactive_shell._get_template_files')
    @patch('interactive_shell._get_save_files')
    def test_cmd_reload(self, mock_get_saves, mock_get_templates):
        """Test reload command clears caches and refreshes file lists."""
        from template_renderer import CustomTemplateLoader

        # Setup mocks
        mock_get_templates.return_value = ['new_template']
        mock_get_saves.return_value = ['new_save']

        shell = InteractiveShell()

        # Create a real CustomTemplateLoader instance with a cache
        from template_parser import TemplateParser
        from save_file_manager import SaveFileManager
        import tempfile
        temp_dir = tempfile.mkdtemp()

        loader = CustomTemplateLoader(temp_dir, TemplateParser(temp_dir), SaveFileManager(temp_dir))
        loader._cache = {'cached_template': 'cached_content'}

        # Create mock environment with real loader
        mock_env = Mock()
        mock_env.loader = loader

        # Add dummy entries to caches
        shell.renderer._env_cache = {('test', None): mock_env}
        shell.completer._templates = ['old_template']
        shell.completer._saves = ['old_save']

        with patch.object(shell, '_display_success') as mock_success:
            shell.cmd_reload([])

            # Verify environment cache was cleared
            assert len(shell.renderer._env_cache) == 0
            # Verify loader cache was cleared
            assert len(loader._cache) == 0
            # Verify completer lists were refreshed
            assert shell.completer._templates == ['new_template']
            assert shell.completer._saves == ['new_save']
            mock_success.assert_called_once()

        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)

    def test_command_aliases(self):
        """Test command alias resolution."""
        shell = InteractiveShell()
        
        # Test r → render
        with patch.object(shell, 'cmd_render'):
            shell._handle_command('r')
            shell.cmd_render.assert_called_once()
        
        # Test ll → ls
        with patch.object(shell, 'cmd_ls'):
            shell._handle_command('ll')
            shell.cmd_ls.assert_called_once()
        
        # Test h → help
        with patch.object(shell, 'cmd_help'):
            shell._handle_command('h')
            shell.cmd_help.assert_called_once()
        
        # Test ? → help
        with patch.object(shell, 'cmd_help'):
            shell._handle_command('?')
            shell.cmd_help.assert_called_once()
    
    def test_error_handling_no_template(self):
        """Test commands requiring template."""
        shell = InteractiveShell()
        
        shell.cmd_render([])
        shell.cmd_set(['name', 'value'])
        shell.cmd_ls([])
    
    def test_cmd_help_no_args(self):
        """Test help command without arguments shows all commands."""
        shell = InteractiveShell()
        
        with patch('builtins.print') as mock_print:
            shell.cmd_help([])
            
            # Verify print was called
            self.assertTrue(mock_print.called)
            
            # Get all printed output
            printed_text = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
            
            # Verify all commands appear in output
            self.assertIn('use', printed_text)
            self.assertIn('load', printed_text)
            self.assertIn('set', printed_text)
            self.assertIn('render', printed_text)
            self.assertIn('help', printed_text)
    
    def test_cmd_help_with_command(self):
        """Test help command with specific command shows detailed help."""
        shell = InteractiveShell()
        
        with patch('builtins.print') as mock_print:
            shell.cmd_help(['use'])
            
            printed_text = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
            
            # Verify detailed help for 'use' command
            self.assertIn('use', printed_text.lower())
            self.assertIn('template', printed_text.lower())
            self.assertIn('syntax', printed_text.lower() or 'Syntax' in printed_text)
    
    def test_cmd_help_invalid_command(self):
        """Test help with invalid command shows error."""
        shell = InteractiveShell()
        
        with patch.object(shell, '_display_error') as mock_error:
            with patch('builtins.print'):
                shell.cmd_help(['invalid_command'])
                
                # Verify error was displayed
                mock_error.assert_called_once()
                self.assertIn('Unknown command', mock_error.call_args[0][0])
    
    def test_cmd_help_with_alias(self):
        """Test help command resolves aliases correctly."""
        shell = InteractiveShell()
        
        with patch('builtins.print') as mock_print:
            # Test with 'r' alias for 'render'
            shell.cmd_help(['r'])
            
            printed_text = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
            
            # Should show help for 'render' command
            self.assertIn('render', printed_text.lower())


class TestQuickLaunch(unittest.TestCase):
    """Test quick launch functionality."""
    
    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.save_file_manager')
    @patch('interactive_shell.TemplateParser')
    @patch('interactive_shell.template_renderer')
    @patch('interactive_shell.history_logger')
    def test_quick_launch_with_template_only(self, mock_history, mock_renderer, 
                                            mock_parser_class, mock_save, mock_state):
        """Test quick launch with template only."""
        mock_template_def = Mock()
        mock_template_def.relative_path = 'test.template'
        mock_parser = Mock()
        mock_parser.parse.return_value = mock_template_def
        mock_parser_class.return_value = mock_parser
        
        shell = InteractiveShell()
        
        with patch.object(shell, 'run'):
            with patch.object(shell, 'display_banner'):
                with patch.object(shell, 'display_configuration'):
                    with patch.object(shell, 'cmd_use') as mock_cmd_use:
                        shell.quick_launch('test.template')
                        
                        # Verify banner and config displayed
                        shell.display_banner.assert_called_once()
                        shell.display_configuration.assert_called_once()
                        
                        # Verify cmd_use called with template only
                        mock_cmd_use.assert_called_once_with(['test.template'])
                        
                        # Verify interactive loop started
                        shell.run.assert_called_once()
    
    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.save_file_manager')
    @patch('interactive_shell.TemplateParser')
    @patch('interactive_shell.template_renderer')
    @patch('interactive_shell.history_logger')
    def test_quick_launch_with_template_and_save(self, mock_history, mock_renderer,
                                                 mock_parser_class, mock_save, mock_state):
        """Test quick launch with template and save file."""
        mock_template_def = Mock()
        mock_template_def.relative_path = 'test.template'
        mock_parser = Mock()
        mock_parser.parse.return_value = mock_template_def
        mock_parser_class.return_value = mock_parser
        
        shell = InteractiveShell()
        
        with patch.object(shell, 'run'):
            with patch.object(shell, 'display_banner'):
                with patch.object(shell, 'display_configuration'):
                    with patch.object(shell, 'cmd_use') as mock_cmd_use:
                        shell.quick_launch('test.template', 'test')

                        # Verify cmd_use called with both template and save
                        mock_cmd_use.assert_called_once_with(['test.template', 'test'])

                        # Verify interactive loop started
                        shell.run.assert_called_once()
    
    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.save_file_manager')
    @patch('interactive_shell.TemplateParser')
    @patch('interactive_shell.template_renderer')
    @patch('interactive_shell.history_logger')
    def test_quick_launch_handles_template_not_found(self, mock_history, mock_renderer,
                                                     mock_parser_class, mock_save, mock_state):
        """Test quick launch handles template not found error."""
        mock_parser = Mock()
        mock_parser.parse.side_effect = Exception("Template not found")
        mock_parser_class.return_value = mock_parser
        
        shell = InteractiveShell()
        
        with patch.object(shell, 'run'):
            with patch.object(shell, 'display_banner'):
                with patch.object(shell, 'display_configuration'):
                    with patch.object(shell, 'cmd_use', side_effect=Exception("Template not found")):
                        with patch.object(shell, '_display_error') as mock_error:
                            shell.quick_launch('missing.template')
                            
                            # Verify error displayed
                            mock_error.assert_called_once()
                            
                            # Verify still enters interactive mode
                            shell.run.assert_called_once()
    
    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.save_file_manager')
    @patch('interactive_shell.TemplateParser')
    @patch('interactive_shell.template_renderer')
    @patch('interactive_shell.history_logger')
    def test_quick_launch_displays_banner(self, mock_history, mock_renderer,
                                         mock_parser_class, mock_save, mock_state):
        """Test quick launch displays banner and configuration."""
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        
        shell = InteractiveShell()
        
        with patch.object(shell, 'run'):
            with patch.object(shell, 'display_banner') as mock_banner:
                with patch.object(shell, 'display_configuration') as mock_config:
                    with patch.object(shell, 'cmd_use'):
                        with patch('interactive_shell.SHOW_CONFIG_ON_STARTUP', True):
                            shell.quick_launch('test.template')
                            
                            # Verify startup display methods called
                            mock_banner.assert_called_once()
                            mock_config.assert_called_once()


class TestRichMarkupToANSI(unittest.TestCase):
    """Test Rich-style markup conversion to ANSI escape codes."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.templates_dir = Path(self.temp_dir) / 'templates'
        self.saves_dir = Path(self.temp_dir) / 'saves'
        self.templates_dir.mkdir()
        self.saves_dir.mkdir()

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_display_error_converts_markup_to_ansi(self):
        """Test that _display_error converts Rich markup to ANSI codes."""
        with patch('interactive_shell.TEMPLATES_DIR', str(self.templates_dir)), \
             patch('interactive_shell.SAVES_DIR', str(self.saves_dir)), \
             patch('interactive_shell.state_manager'), \
             patch('interactive_shell.history_logger'):

            shell = InteractiveShell()

            # Patch print to capture output
            with patch('builtins.print') as mock_print:
                shell._display_error("Test error message")

                # Get the printed string
                self.assertEqual(mock_print.call_count, 1)
                printed_output = mock_print.call_args[0][0]

                # Verify markup is NOT present (should be converted)
                self.assertNotIn('[red]', printed_output)
                self.assertNotIn('[/red]', printed_output)
                self.assertNotIn('[bold]', printed_output)
                self.assertNotIn('[/bold]', printed_output)

                # Verify ANSI escape codes ARE present
                self.assertIn('\x1b[', printed_output)

                # Verify the actual message text is preserved
                self.assertIn('Test error message', printed_output)

    def test_display_success_converts_markup_to_ansi(self):
        """Test that _display_success converts Rich markup to ANSI codes."""
        with patch('interactive_shell.TEMPLATES_DIR', str(self.templates_dir)), \
             patch('interactive_shell.SAVES_DIR', str(self.saves_dir)), \
             patch('interactive_shell.state_manager'), \
             patch('interactive_shell.history_logger'):

            shell = InteractiveShell()

            # Patch print to capture output
            with patch('builtins.print') as mock_print:
                shell._display_success("Success message")

                # Get the printed string
                self.assertEqual(mock_print.call_count, 1)
                printed_output = mock_print.call_args[0][0]

                # Verify markup is NOT present
                self.assertNotIn('[green]', printed_output)
                self.assertNotIn('[/green]', printed_output)

                # Verify ANSI escape codes ARE present
                self.assertIn('\x1b[', printed_output)

                # Verify the actual message text is preserved
                self.assertIn('Success message', printed_output)

    def test_display_configuration_converts_markup_to_ansi(self):
        """Test that display_configuration converts Rich markup to ANSI codes."""
        with patch('interactive_shell.TEMPLATES_DIR', str(self.templates_dir)), \
             patch('interactive_shell.SAVES_DIR', str(self.saves_dir)), \
             patch('interactive_shell.state_manager'), \
             patch('interactive_shell.history_logger'):

            shell = InteractiveShell()

            # Patch print to capture output
            with patch('builtins.print') as mock_print:
                shell.display_configuration()

                # Get all printed strings
                self.assertGreater(mock_print.call_count, 0)
                all_output = ' '.join([str(call[0][0]) for call in mock_print.call_args_list])

                # Verify markup is NOT present
                self.assertNotIn('[cyan]', all_output)
                self.assertNotIn('[/cyan]', all_output)

                # Verify ANSI escape codes ARE present
                self.assertIn('\x1b[', all_output)

                # Verify configuration text is preserved
                self.assertIn('Configuration', all_output)

    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.save_file_manager')
    @patch('interactive_shell.TemplateParser')
    @patch('interactive_shell.template_renderer')
    @patch('interactive_shell.history_logger')
    @patch('builtins.print')
    def test_cmd_validate_no_duplicates(self, mock_print, mock_history, mock_renderer, mock_parser, mock_save, mock_state):
        """Test validate command with no duplicates."""
        # Patch configuration to use temp directories
        with patch('interactive_shell.TEMPLATES_DIR', str(self.templates_dir)), \
             patch('interactive_shell.SAVES_DIR', str(self.saves_dir)):

            shell = InteractiveShell()
            shell.cmd_validate([])

            # Verify success message was displayed
            self.assertGreater(mock_print.call_count, 0)
            all_output = ' '.join([str(call[0][0]) for call in mock_print.call_args_list])
            self.assertIn('No duplicates found', all_output)

    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.save_file_manager')
    @patch('interactive_shell.TemplateParser')
    @patch('interactive_shell.template_renderer')
    @patch('interactive_shell.history_logger')
    @patch('builtins.print')
    def test_cmd_validate_with_duplicates(self, mock_print, mock_history, mock_renderer, mock_parser, mock_save, mock_state):
        """Test validate command with duplicates present."""
        # Create duplicate files in templates directory
        (self.templates_dir / 'test.template').write_text('template content')
        (self.templates_dir / 'test.txt').write_text('test content')

        # Patch configuration to use temp directories
        with patch('interactive_shell.TEMPLATES_DIR', str(self.templates_dir)), \
             patch('interactive_shell.SAVES_DIR', str(self.saves_dir)):

            shell = InteractiveShell()
            shell.cmd_validate([])

            # Verify error message was displayed
            self.assertGreater(mock_print.call_count, 0)
            all_output = ' '.join([str(call[0][0]) for call in mock_print.call_args_list])

            # Should display duplicate information
            self.assertIn('duplicate', all_output.lower())
            self.assertIn('test', all_output)

    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.save_file_manager')
    @patch('interactive_shell.TemplateParser')
    @patch('interactive_shell.template_renderer')
    @patch('interactive_shell.history_logger')
    @patch('interactive_shell.VALIDATE_ON_STARTUP', False)
    def test_validate_on_startup_disabled(self, mock_history, mock_renderer, mock_parser, mock_save, mock_state):
        """Test that validation is not run when VALIDATE_ON_STARTUP is False."""
        with patch('interactive_shell.TEMPLATES_DIR', str(self.templates_dir)), \
             patch('interactive_shell.SAVES_DIR', str(self.saves_dir)), \
             patch.object(InteractiveShell, '_run_validation') as mock_validate:

            shell = InteractiveShell()
            # Mock run method to prevent actual execution
            with patch.object(shell, 'run'):
                shell.start()

            # Validation should not be called
            mock_validate.assert_not_called()

    @patch('interactive_shell.state_manager')
    @patch('interactive_shell.save_file_manager')
    @patch('interactive_shell.TemplateParser')
    @patch('interactive_shell.template_renderer')
    @patch('interactive_shell.history_logger')
    @patch('interactive_shell.VALIDATE_ON_STARTUP', True)
    @patch('builtins.print')
    def test_validate_on_startup_enabled(self, mock_print, mock_history, mock_renderer, mock_parser, mock_save, mock_state):
        """Test that validation runs when VALIDATE_ON_STARTUP is True."""
        # Create duplicate files
        (self.templates_dir / 'test.template').write_text('template content')
        (self.templates_dir / 'test.txt').write_text('test content')

        with patch('interactive_shell.TEMPLATES_DIR', str(self.templates_dir)), \
             patch('interactive_shell.SAVES_DIR', str(self.saves_dir)):

            shell = InteractiveShell()
            # Mock run method to prevent actual execution
            with patch.object(shell, 'run'):
                shell.start()

            # Validation should have been called
            # Since show_success=False, only errors are displayed
            # Check if validation ran by verifying duplicate message was shown
            all_output = ' '.join([str(call[0][0]) for call in mock_print.call_args_list if call[0]])
            self.assertIn('duplicate', all_output.lower())


if __name__ == '__main__':
    unittest.main()
