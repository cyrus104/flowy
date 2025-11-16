"""
Unit Tests for State Manager Module

Comprehensive test suite for state_manager.py covering:
- SessionState dataclass serialization/deserialization
- StateManager basic operations (set/get/clear)
- State persistence (save/load/atomic writes)
- History tracking and revert functionality
- Edge cases and error handling
"""

import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state_manager import (
    StateManager, SessionState, StateLoadError, StateSaveError
)
from configuration import STATE_FILE


class TestSessionState(unittest.TestCase):
    """Test SessionState dataclass."""
    
    def test_session_state_creation(self):
        """Test basic SessionState creation."""
        state = SessionState(
            template_path="test.template",
            variables={"test": "value"},
            timestamp="2024-01-01T00:00:00"
        )
        self.assertEqual(state.template_path, "test.template")
        self.assertEqual(state.variables["test"], "value")
        self.assertEqual(state.timestamp, "2024-01-01T00:00:00")
    
    def test_session_state_minimal(self):
        """Test minimal SessionState (no template)."""
        state = SessionState()
        self.assertIsNone(state.template_path)
        self.assertEqual(state.variables, {})
        self.assertTrue(state.timestamp)  # Auto-generated
    
    def test_to_dict_serialization(self):
        """Test to_dict() produces correct JSON structure."""
        state = SessionState(
            template_path="test.template",
            variables={"a": 1, "b": "two"},
            timestamp="2024-01-01T12:00:00"
        )
        data = state.to_dict()
        expected = {
            'template': 'test.template',
            'variables': {'a': 1, 'b': 'two'},
            'timestamp': '2024-01-01T12:00:00'
        }
        self.assertEqual(data, expected)
    
    def test_from_dict_deserialization(self):
        """Test from_dict() reconstructs state correctly."""
        data = {
            'template': 'test.template',
            'variables': {'key': 'value'},
            'timestamp': '2024-01-01T12:00:00'
        }
        state = SessionState.from_dict(data)
        self.assertEqual(state.template_path, 'test.template')
        self.assertEqual(state.variables['key'], 'value')
        self.assertEqual(state.timestamp, '2024-01-01T12:00:00')
    
    def test_from_dict_validation(self):
        """Test from_dict() validates required keys."""
        invalid_data = {'variables': {}, 'timestamp': ''}
        with self.assertRaises(ValueError):
            SessionState.from_dict(invalid_data)
    
    def test_copy_with_method(self):
        """Test copy_with() creates modified copies."""
        original = SessionState(template_path="old.template", variables={"old": 1})
        new_state = original.copy_with(template_path="new.template", variables={"new": 2})
        self.assertEqual(new_state.template_path, "new.template")
        self.assertEqual(new_state.variables["new"], 2)
        self.assertNotEqual(id(original), id(new_state))  # Different object
    
    def test_repr_output(self):
        """Test __repr__() produces readable output."""
        state = SessionState(template_path="test.template", variables={"a": 1})
        repr_str = repr(state)
        self.assertIn("test.template", repr_str)
        self.assertIn("variables=1", repr_str)


class TestStateManager(unittest.TestCase):
    """Test StateManager functionality."""
    
    def setUp(self):
        """Create temporary directory for test state files."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, "test.state")
        os.environ['TEMPLATE_ASSISTANT_STATE'] = self.state_file
    
    def tearDown(self):
        """Cleanup temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_manager(self) -> StateManager:
        """Create StateManager with test state file."""
        return StateManager(self.state_file)
    
    def test_initialization(self):
        """Test StateManager initializes empty."""
        manager = self._create_test_manager()
        self.assertIsNone(manager.current_state)
        self.assertEqual(manager.history, [])
        self.assertIsNone(manager.revert_toggle_state)
    
    def test_set_template(self):
        """Test setting template."""
        manager = self._create_test_manager()
        manager.set_template("test.template")
        self.assertEqual(manager.get_current_template(), "test.template")
        self.assertTrue(manager.has_template())
    
    def test_set_variable(self):
        """Test setting single variable."""
        manager = self._create_test_manager()
        manager.set_variable("test", "value")
        self.assertEqual(manager.get_variable("test"), "value")
        self.assertEqual(manager.get_all_variables(), {"test": "value"})
    
    def test_set_variables_bulk(self):
        """Test bulk variable setting."""
        manager = self._create_test_manager()
        manager.set_variables({"a": 1, "b": "two"})
        self.assertEqual(manager.get_all_variables(), {"a": 1, "b": "two"})
    
    def test_unset_variable(self):
        """Test unsetting variable."""
        manager = self._create_test_manager()
        manager.set_variables({"test": "value"})
        manager.unset_variable("test")
        self.assertIsNone(manager.get_variable("test"))
    
    def test_clear_variables(self):
        """Test clearing all variables."""
        manager = self._create_test_manager()
        manager.set_variables({"a": 1, "b": 2})
        manager.clear_variables()
        self.assertEqual(manager.get_all_variables(), {})
    
    def test_save_and_load_state(self):
        """Test round-trip save/load."""
        manager = self._create_test_manager()
        manager.set_template("test.template")
        manager.set_variables({"key": "value"})
        manager.save_state()
        
        # Create new manager to load state
        manager2 = self._create_test_manager()
        self.assertEqual(manager2.get_current_template(), "test.template")
        self.assertEqual(manager2.get_variable("key"), "value")
    
    def test_load_missing_file(self):
        """Test graceful handling of missing state file."""
        manager = self._create_test_manager()
        self.assertIsNone(manager.current_state)  # Starts empty
    
    def test_revert_basic(self):
        """Test basic revert functionality."""
        manager = self._create_test_manager()
        
        # State 1
        manager.set_template("template1.template")
        manager.set_variable("var1", "value1")
        
        # State 2
        manager.set_template("template2.template")
        manager.set_variable("var2", "value2")
        
        # Revert to state 1
        success = manager.revert()
        self.assertTrue(success)
        self.assertEqual(manager.get_current_template(), "template1.template")
        self.assertEqual(manager.get_variable("var1"), "value1")
    
    def test_revert_no_history(self):
        """Test revert with no history available."""
        manager = self._create_test_manager()
        success = manager.revert()
        self.assertFalse(success)
    
    def test_revert_toggle_behavior(self):
        """Test revert toggle behavior."""
        manager = self._create_test_manager()
        
        # Original state
        manager.set_template("A.template")
        
        # State 1 (B)
        manager.set_template("B.template")
        
        # State 2 (C)  
        manager.set_template("C.template")
        
        # First revert: C -> B
        manager.revert()
        self.assertEqual(manager.get_current_template(), "B.template")
        
        # Second revert: B -> C (toggle)
        manager.revert()
        self.assertEqual(manager.get_current_template(), "C.template")
    
    def test_revert_skips_duplicates(self):
        """Test revert skips duplicate templates."""
        manager = self._create_test_manager()
        
        manager.set_template("A.template")
        manager.set_template("B.template")  # First B
        manager.set_template("B.template")  # Duplicate B
        manager.set_template("C.template")
        
        # Revert should skip both B's → A
        success = manager.revert()
        self.assertTrue(success)
        self.assertEqual(manager.get_current_template(), "A.template")
    
    def test_revert_single_no_skip(self):
        """Test single template instance is not skipped."""
        manager = self._create_test_manager()
        
        manager.set_template("A.template")
        manager.set_template("B.template")  # Single B
        manager.set_template("C.template")
        
        # Revert should go to B (single instance, no skip)
        success = manager.revert()
        self.assertTrue(success)
        self.assertEqual(manager.get_current_template(), "B.template")
    
    def test_revert_multiple_duplicates(self):
        """Test revert skips longer chains of duplicates."""
        manager = self._create_test_manager()
        
        manager.set_template("A.template")
        manager.set_template("B.template")
        manager.set_template("B.template")  # 2nd B
        manager.set_template("B.template")  # 3rd B
        manager.set_template("C.template")
        
        # Revert should skip all 3 B's → A
        success = manager.revert()
        self.assertTrue(success)
        self.assertEqual(manager.get_current_template(), "A.template")
    
    def test_revert_no_duplicates_empty_history(self):
        """Test revert with empty history."""
        manager = self._create_test_manager()
        success = manager.revert()
        self.assertFalse(success)
    
    def test_history_size_limit(self):
        """Test history size is limited."""
        manager = self._create_test_manager()
        for i in range(60):
            manager.set_template(f"template{i}.template")
        self.assertEqual(len(manager.history), 50)  # MAX_HISTORY_SIZE
    
    def test_atomic_save(self):
        """Test atomic save prevents corruption."""
        manager = self._create_test_manager()
        manager.set_template("test.template")
        
        # Simulate interrupted save by checking temp file cleanup
        # (hard to test directly, but verify file exists and is valid JSON)
        manager.save_state()
        self.assertTrue(os.path.exists(manager.state_file))
        
        # Verify JSON structure
        with open(manager.state_file, 'r') as f:
            data = json.load(f)
        self.assertIn('current_template', data)
        self.assertIn('variables', data)
        self.assertIn('timestamp', data)
    
    def test_timestamp_updates_on_mutation(self):
        """Test that mutations generate fresh timestamps."""
        manager = self._create_test_manager()
        
        # Initial state
        manager.set_template("test.template")
        initial_ts = manager.current_state.timestamp
        
        import time
        time.sleep(0.1)  # Ensure measurable difference
        
        # Mutate
        manager.set_variable("key", "value")
        new_ts = manager.current_state.timestamp
        
        self.assertNotEqual(initial_ts, new_ts)
        self.assertTrue(datetime.fromisoformat(new_ts) > datetime.fromisoformat(initial_ts))
        
        # Test copy_with directly
        state1 = SessionState(template_path="test1")
        state2 = state1.copy_with(template_path="test2")
        self.assertNotEqual(state1.timestamp, state2.timestamp)


class TestStateManagerErrors(unittest.TestCase):
    """Test error handling."""
    
    def test_load_corrupted_json(self):
        """Test corrupted JSON handling starts fresh state."""
        temp_dir = tempfile.mkdtemp()
        state_file = os.path.join(temp_dir, "corrupted.state")
        
        # Create corrupted JSON
        with open(state_file, 'w') as f:
            f.write("invalid json")
        
        os.environ['TEMPLATE_ASSISTANT_STATE'] = state_file
        
        manager = StateManager(state_file)
        self.assertIsNone(manager.current_state)
        self.assertEqual(manager.history, [])
        shutil.rmtree(temp_dir)
    
    def test_save_permission_error(self):
        """Test save error handling (requires write-protected dir simulation)."""
        # Skip detailed permission test (OS-dependent)
        pass

    def test_revert_null_current_state(self):
        """Test revert returns False when current_state is None."""
        temp_dir = tempfile.mkdtemp()
        state_file = os.path.join(temp_dir, "test.state")
        os.environ['TEMPLATE_ASSISTANT_STATE'] = state_file
        
        manager = StateManager(state_file)
        # Force null current_state (simulate corrupted load)
        manager.current_state = None
        
        result = manager.revert()
        self.assertFalse(result)
        
        shutil.rmtree(temp_dir)


if __name__ == '__main__':
    unittest.main()
