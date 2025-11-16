"""
State Manager Module

This module provides comprehensive session state management for the Template Assistant.
It handles persistence to JSON state files (.state), history tracking for revert functionality,
and crash recovery. The state manager automatically saves after significant operations
and supports intelligent revert behavior that skips duplicate templates.

Design spec compliance:
- JSON format with current_template, variables, timestamp, history array
- Atomic file writes (temp file + rename) for crash safety
- Smart revert with toggle behavior (skip duplicates, second call returns to latest)
"""

import os
import json
import tempfile
import shutil
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

from configuration import STATE_FILE


# ============================================================================
# Custom Exception Classes
# ============================================================================

class StateError(Exception):
    """Base exception class for state management errors."""
    def __init__(self, message: str, state_file: str = None):
        self.state_file = state_file
        super().__init__(f"{message}" + (f" in {state_file}" if state_file else ""))


class StateLoadError(StateError):
    """Raised when state file cannot be loaded (corrupted JSON, etc.)."""
    pass


class StateSaveError(StateError):
    """Raised when state file cannot be saved (permissions, disk full)."""
    pass


# ============================================================================
# SessionState Dataclass
# ============================================================================

@dataclass(frozen=True)
class SessionState:
    """
    Immutable representation of a single session state snapshot.
    
    Fields:
        template_path: Current template path or None
        variables: Current variable values as dict
        timestamp: ISO 8601 timestamp string
    """
    template_path: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            object.__setattr__(self, 'timestamp', self._generate_timestamp())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Deserialize from JSON dict with validation."""
        required_keys = {'template', 'variables', 'timestamp'}
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in state data: {missing_keys}")
        
        return cls(
            template_path=data.get('template'),
            variables=data.get('variables', {}),
            timestamp=data.get('timestamp')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict matching design spec."""
        return {
            'template': self.template_path,
            'variables': self.variables,
            'timestamp': self.timestamp
        }
    
    def copy_with(self, **changes) -> 'SessionState':
        """Create modified copy with updated fields; auto-generates fresh timestamp unless provided."""
        data = self.to_dict()
        data.update(changes)
        # Auto-generate fresh timestamp unless explicitly provided
        if 'timestamp' not in changes:
            del data['timestamp']  # Remove old timestamp to trigger __post_init__
        return SessionState.from_dict(data)
    
    def _generate_timestamp(self) -> str:
        """Generate ISO 8601 timestamp."""
        return datetime.now().isoformat()
    
    def __repr__(self) -> str:
        template = self.template_path or "none"
        var_count = len(self.variables)
        return f"SessionState(template='{template}', variables={var_count}, timestamp='{self.timestamp[:19]}...')"


# ============================================================================
# StateManager Class
# ============================================================================

class StateManager:
    """
    Manages session state persistence, history tracking, and revert functionality.
    
    Key features:
    - Automatic persistence after state changes
    - History stack for revert operations
    - Smart revert skipping duplicate templates
    - Toggle revert behavior (second call returns to latest state)
    - Atomic file operations for crash safety
    - JSON format matching exact design specification
    """
    
    MAX_HISTORY_SIZE = 50
    
    def __init__(self, state_file_path: str = None):
        self.state_file = state_file_path or STATE_FILE
        self.current_state: Optional[SessionState] = None
        self.history: List[SessionState] = []
        self.revert_toggle_state: Optional[SessionState] = None
        
        # Load existing state on initialization
        try:
            self._load_state()
        except StateLoadError:
            # Missing or corrupted state file - start fresh
            self.current_state = None
    
    def _load_state(self) -> None:
        """Load state from disk, handle missing file gracefully."""
        if not os.path.exists(self.state_file):
            return  # Fresh session
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Deserialize current state
            if data.get('current_template') is not None or data.get('variables'):
                self.current_state = SessionState.from_dict({
                    'template': data.get('current_template'),
                    'variables': data.get('variables', {}),
                    'timestamp': data.get('timestamp', '')
                })
            
            # Deserialize history
            history_data = data.get('history', [])
            self.history = [SessionState.from_dict(item) for item in history_data]
            
            # Deserialize toggle state if present
            toggle_data = data.get('revert_toggle_state')
            if toggle_data:
                self.revert_toggle_state = SessionState.from_dict(toggle_data)
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise StateLoadError(f"Failed to load state file: {e}")
    
    def save_state(self) -> None:
        """Save current state atomically to disk."""
        self._ensure_directory_exists()
        
        # Prepare data matching exact design spec
        data = {
            'current_template': self.current_state.template_path if self.current_state else None,
            'variables': self.current_state.variables if self.current_state else {},
            'timestamp': self.current_state.timestamp if self.current_state else '',
            'history': [state.to_dict() for state in self.history],
        }
        if self.revert_toggle_state:
            data['revert_toggle_state'] = self.revert_toggle_state.to_dict()
        
        # Atomic write: temp file -> rename
        with tempfile.NamedTemporaryFile(mode='w', suffix='.state.tmp', 
                                       dir=Path(self.state_file).parent, delete=False) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path = f.name
        
        try:
            shutil.move(temp_path, self.state_file)
        except OSError as e:
            # Cleanup temp file on failure
            os.unlink(temp_path)
            raise StateSaveError(f"Failed to save state: {e}")
    
    def set_template(self, template_path: str) -> None:
        """Set current template, always push previous state to history."""
        # Always push previous state to history (treats each template load as distinct)
        self._push_to_history()
        
        # Clear toggle state on template change (new revert chain)
        self.revert_toggle_state = None
        
        if self.current_state is None:
            self.current_state = SessionState(template_path=template_path)
        else:
            self.current_state = self.current_state.copy_with(template_path=template_path)
        
        self.save_state()
    
    def set_variable(self, name: str, value: Any) -> None:
        """Set single variable value."""
        # Clear toggle state on mutation (start new revert chain)
        self.revert_toggle_state = None
        
        if self.current_state is None:
            self.current_state = SessionState()
        
        new_vars = self.current_state.variables.copy()
        new_vars[name] = value
        self.current_state = self.current_state.copy_with(variables=new_vars)
        self.save_state()
    
    def set_variables(self, variables: Dict[str, Any]) -> None:
        """Bulk set variables."""
        # Clear toggle state on mutation
        self.revert_toggle_state = None
        
        if self.current_state is None:
            self.current_state = SessionState()
        
        current_vars = self.current_state.variables.copy()
        current_vars.update(variables)
        self.current_state = self.current_state.copy_with(variables=current_vars)
        self.save_state()
    
    def unset_variable(self, name: str) -> None:
        """Remove variable."""
        # Clear toggle state on mutation
        self.revert_toggle_state = None
        
        if self.current_state is None:
            return
        
        new_vars = self.current_state.variables.copy()
        new_vars.pop(name, None)
        self.current_state = self.current_state.copy_with(variables=new_vars)
        self.save_state()
    
    def get_variable(self, name: str) -> Any:
        """Get variable value or None."""
        return self.current_state.variables.get(name) if self.current_state else None
    
    def get_all_variables(self) -> Dict[str, Any]:
        """Get copy of all current variables."""
        return self.current_state.variables.copy() if self.current_state else {}
    
    def clear_variables(self) -> None:
        """Clear all variables while keeping template."""
        # Clear toggle state on mutation
        self.revert_toggle_state = None
        
        if self.current_state:
            self.current_state = self.current_state.copy_with(variables={})
            self.save_state()
    
    def get_current_template(self) -> Optional[str]:
        """Get current template path."""
        return self.current_state.template_path if self.current_state else None
    
    def has_template(self) -> bool:
        """Check if template is loaded."""
        return self.current_state is not None and self.current_state.template_path is not None
    
    def revert(self) -> bool:
        """
        Revert to previous state with smart duplicate skipping and toggle behavior.
        
        1. Toggle: If revert_toggle_state exists, swap back and clear
        2. Skip duplicates: Count consecutive same-template states from history end
           - If >1 consecutive, truncate entire chain, revert to state before chain
           - Single instances not skipped (normal revert)
           - Example: A→B→B→C reverts C→A (skips both B's)
           - Example: A→B→C reverts C→B (single B not skipped)
        3. Store current for next toggle opportunity
        Returns True if revert succeeded, False if no history/target available.
        """
        if not self.current_state:
            return False
        
        # Check for toggle revert first (NO premature clear)
        if self.revert_toggle_state is not None:
            # Swap current with toggle state
            self.current_state, self.revert_toggle_state = self.revert_toggle_state, self.current_state
            self.revert_toggle_state = None  # Clear toggle after swap
            self.save_state()
            return True
        
        if not self.history:
            return False
        
        # Skip consecutive duplicate templates from end of history
        # For A→B→B→C, history=[A,B1,B2], previous=B, skip all B's to find A
        previous_template = self.history[-1].template_path if self.history else None
        if previous_template == self.current_state.template_path:
            return False  # No meaningful revert possible
        
        # Count consecutive previous_template from end and truncate if >1
        i = len(self.history) - 1
        consecutive_count = 0
        while i >= 0 and self.history[i].template_path == previous_template:
            consecutive_count += 1
            i -= 1
        
        if consecutive_count > 1:
            # Skip entire chain of duplicates, keep only up to before the chain
            self.history = self.history[:i+1]
        
        # Now find target from (possibly truncated) history
        target_state = None
        for state in reversed(self.history):
            if state.template_path != self.current_state.template_path:
                target_state = state
                break
        
        if not target_state:
            return False
        
        # Store current state for toggle
        self.revert_toggle_state = self.current_state
        
        # Swap to target state
        self.current_state = target_state
        
        # Remove target from history
        self.history.remove(target_state)
        
        self.save_state()
        return True
    
    def _push_to_history(self) -> None:
        """Push current state to history stack."""
        if self.current_state:
            self.history.append(self.current_state)
            # Limit history size
            if len(self.history) > self.MAX_HISTORY_SIZE:
                self.history = self.history[-self.MAX_HISTORY_SIZE:]
    
    def _ensure_directory_exists(self) -> None:
        """Create parent directory if needed."""
        Path(self.state_file).parent.mkdir(parents=True, exist_ok=True)


# Module convenience instance (uses default config)
state_manager = StateManager()