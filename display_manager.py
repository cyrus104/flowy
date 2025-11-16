"""
Display Manager for Template Assistant

Handles terminal width detection, intelligent word wrapping with color preservation,
window resize handling, and adaptive table formatting.
"""

import re
import shutil
import signal
import sys
import textwrap
from typing import List, Optional, Tuple

from configuration import (
    AUTO_DETECT_WIDTH, DEFAULT_WIDTH, WORD_WRAP_ENABLED,
    PRESERVE_FORMATTING_ON_WRAP, MAX_TABLE_COLUMN_WIDTH,
    MIN_TABLE_COLUMN_WIDTH, TRUNCATE_INDICATOR
)


class DisplayManager:
    """Manages terminal display operations with width awareness and intelligent formatting."""
    
    def __init__(self):
        """Initialize display manager with terminal width detection and signal handling."""
        self.terminal_width = DEFAULT_WIDTH
        self._ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')
        
        # Detect initial terminal width
        if AUTO_DETECT_WIDTH:
            self._detect_terminal_width()
        
        # Setup window resize handler (Unix/Linux/Mac only)
        self._setup_resize_handler()
    
    def _detect_terminal_width(self) -> None:
        """Detect current terminal width using shutil."""
        try:
            size = shutil.get_terminal_size(fallback=(DEFAULT_WIDTH, 24))
            width = size.columns
            if width > 0:
                self.terminal_width = width
            else:
                self.terminal_width = DEFAULT_WIDTH
        except (OSError, ValueError):
            # Fallback for non-TTY environments
            self.terminal_width = DEFAULT_WIDTH
    
    def _setup_resize_handler(self) -> None:
        """Setup SIGWINCH signal handler for terminal resize events."""
        try:
            # Only works on Unix-like systems
            def handle_resize(signum, frame):
                if AUTO_DETECT_WIDTH:
                    self._detect_terminal_width()
            
            signal.signal(signal.SIGWINCH, handle_resize)
        except (AttributeError, ValueError):
            # SIGWINCH not available on Windows, skip gracefully
            pass
    
    def get_terminal_width(self) -> int:
        """Get current terminal width."""
        return self.terminal_width
    
    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        return self._ansi_pattern.sub('', text)
    
    def _measure_visible_length(self, text: str) -> int:
        """Measure visible text length excluding ANSI codes."""
        return len(self._strip_ansi_codes(text))
    
    def _extract_ansi_codes(self, text: str) -> List[Tuple[int, str]]:
        """Extract ANSI codes with their positions in the original text."""
        codes = []
        for match in self._ansi_pattern.finditer(text):
            codes.append((match.start(), match.group()))
        return codes
    
    def wrap_text(self, text: str, width: Optional[int] = None) -> str:
        """
        Wrap text to specified width while preserving ANSI color codes.
        
        Args:
            text: Text to wrap (may contain ANSI codes)
            width: Target width (uses terminal_width if not specified)
        
        Returns:
            Wrapped text with ANSI codes preserved
        """
        if not WORD_WRAP_ENABLED:
            return text
        
        if width is None:
            width = self.terminal_width
        
        if width <= 0:
            width = DEFAULT_WIDTH
        
        # Handle empty text
        if not text:
            return text
        
        # Split into lines and process each
        lines = text.split('\n')
        wrapped_lines = []
        
        for line in lines:
            # Extract clean text for wrapping
            clean_line = self._strip_ansi_codes(line)
            
            # If line is short enough, keep as-is
            if len(clean_line) <= width:
                wrapped_lines.append(line)
                continue
            
            # Wrap the clean text
            wrapped_segments = textwrap.wrap(clean_line, width=width, break_long_words=True, 
                                            break_on_hyphens=False)
            
            if not wrapped_segments:
                wrapped_lines.append(line)
                continue
            
            # Build a map of clean char index to original string index
            clean_to_orig = []
            orig_idx = 0
            for char in line:
                # Check if we're at the start of an ANSI sequence
                if self._ansi_pattern.match(line[orig_idx:]):
                    # Skip the entire ANSI sequence
                    match = self._ansi_pattern.match(line[orig_idx:])
                    orig_idx += len(match.group())
                else:
                    # Regular character
                    clean_to_orig.append(orig_idx)
                    orig_idx += 1
            
            # Track active ANSI codes across wrapped lines
            active_codes = []
            
            # Process each wrapped segment
            clean_start = 0
            for wrap_idx, segment in enumerate(wrapped_segments):
                result_line = ""
                
                # Apply active codes from previous line if preserving formatting
                if wrap_idx > 0 and PRESERVE_FORMATTING_ON_WRAP and active_codes:
                    result_line = ''.join(active_codes)
                
                # Map segment back to original string
                clean_end = clean_start + len(segment)
                
                # Find the original string span for this segment
                if clean_start < len(clean_to_orig):
                    orig_start = clean_to_orig[clean_start]
                    orig_end = clean_to_orig[min(clean_end - 1, len(clean_to_orig) - 1)] + 1 if clean_end <= len(clean_to_orig) else len(line)
                    
                    # Extract the segment from original string, including ANSI codes
                    segment_with_codes = line[orig_start:orig_end]
                    
                    # Track active codes in this segment
                    for match in self._ansi_pattern.finditer(segment_with_codes):
                        code = match.group()
                        if '\x1b[0m' in code:
                            active_codes = []
                        else:
                            active_codes.append(code)
                    
                    result_line += segment_with_codes
                else:
                    # Fallback for edge cases
                    result_line += segment
                
                # Add reset at line end if needed
                if PRESERVE_FORMATTING_ON_WRAP and active_codes and wrap_idx < len(wrapped_segments) - 1:
                    result_line += '\x1b[0m'
                
                wrapped_lines.append(result_line)
                clean_start = clean_end
        
        return '\n'.join(wrapped_lines)
    
    def format_table(self, headers: List[str], rows: List[List[str]], 
                    title: Optional[str] = None) -> str:
        """
        Format data as an adaptive table based on terminal width.
        
        Args:
            headers: Column headers
            rows: Data rows (list of lists)
            title: Optional table title
        
        Returns:
            Formatted table string
        """
        if not rows and not headers:
            return "[yellow]No data[/yellow]"
        
        if not rows:
            return "[yellow]No data[/yellow]"
        
        num_columns = len(headers)
        if num_columns == 0:
            return "[yellow]No columns defined[/yellow]"
        
        # Calculate available width (accounting for separators)
        separator_width = (num_columns - 1) * 2  # Two spaces between columns
        available_width = self.terminal_width - separator_width
        
        # Check if we have enough width for minimum column widths
        min_required_width = num_columns * MIN_TABLE_COLUMN_WIDTH
        if available_width < min_required_width:
            # Terminal is too narrow - use degraded layout
            # Option 1: Show fewer columns (drop least important)
            # For now, we'll clamp to minimum and accept overflow
            available_width = min_required_width
        
        # Calculate content-based widths
        column_widths = []
        for i in range(num_columns):
            # Start with header width
            max_width = self._measure_visible_length(headers[i])
            
            # Check all rows for this column
            for row in rows:
                if i < len(row):
                    cell_width = self._measure_visible_length(str(row[i]))
                    max_width = max(max_width, cell_width)
            
            column_widths.append(max_width)
        
        # Apply min/max constraints
        for i in range(num_columns):
            column_widths[i] = max(MIN_TABLE_COLUMN_WIDTH, 
                                  min(column_widths[i], MAX_TABLE_COLUMN_WIDTH))
        
        # If total width exceeds available, proportionally reduce
        total_width = sum(column_widths)
        if total_width > available_width:
            # Ensure we don't go below minimum widths
            if available_width >= min_required_width:
                scale_factor = available_width / total_width
                for i in range(num_columns):
                    column_widths[i] = max(MIN_TABLE_COLUMN_WIDTH, 
                                          int(column_widths[i] * scale_factor))
            else:
                # Force minimum widths even if it overflows
                for i in range(num_columns):
                    column_widths[i] = MIN_TABLE_COLUMN_WIDTH
        
        # Final check: ensure total doesn't exceed terminal width
        final_total = sum(column_widths) + separator_width
        if final_total > self.terminal_width and self.terminal_width > 40:
            # Last resort: equally distribute available space
            per_column = (self.terminal_width - separator_width) // num_columns
            for i in range(num_columns):
                column_widths[i] = max(5, per_column)  # Absolute minimum of 5
        
        # Build the table
        lines = []
        
        # Add title if provided
        if title:
            lines.append(title)
            lines.append("=" * min(self.terminal_width, len(title)))
            lines.append("")
        
        # Format header row
        header_parts = []
        for i, header in enumerate(headers):
            width = column_widths[i]
            # Truncate if needed
            if self._measure_visible_length(header) > width:
                truncated = self._truncate_with_indicator(header, width)
                header_parts.append(f"{truncated:<{width}}")
            else:
                # Pad to width
                padding = width - self._measure_visible_length(header)
                header_parts.append(header + " " * padding)
        
        header_line = "  ".join(header_parts)
        lines.append(header_line)
        
        # Add separator
        separator_parts = ["-" * width for width in column_widths]
        separator_line = "  ".join(separator_parts)
        lines.append(separator_line)
        
        # Format data rows
        for row in rows:
            row_parts = []
            for i in range(num_columns):
                width = column_widths[i]
                cell = str(row[i]) if i < len(row) else ""
                
                # Handle cells with ANSI codes
                visible_len = self._measure_visible_length(cell)
                
                if visible_len > width:
                    # Truncate with indicator
                    truncated = self._truncate_with_indicator(cell, width)
                    row_parts.append(truncated)
                else:
                    # Pad to width (accounting for ANSI codes)
                    padding = width - visible_len
                    row_parts.append(cell + " " * padding)
            
            row_line = "  ".join(row_parts)
            lines.append(row_line)
        
        return "\n".join(lines)
    
    def _truncate_with_indicator(self, text: str, max_width: int) -> str:
        """Truncate text to max_width with indicator, preserving ANSI codes."""
        indicator = TRUNCATE_INDICATOR
        indicator_len = len(indicator)
        
        if max_width <= indicator_len:
            return indicator[:max_width]
        
        # Strip ANSI codes for measurement
        clean_text = self._strip_ansi_codes(text)
        target_len = max_width - indicator_len
        
        if len(clean_text) <= max_width:
            return text
        
        # Tokenize the text into ANSI sequences and plain text segments
        tokens = []
        current_pos = 0
        active_codes = []
        
        for match in self._ansi_pattern.finditer(text):
            # Add text before this ANSI code
            if match.start() > current_pos:
                tokens.append(('text', text[current_pos:match.start()]))
            # Add the ANSI code
            ansi_code = match.group()
            tokens.append(('ansi', ansi_code))
            # Track active formatting
            if '\x1b[0m' in ansi_code:
                active_codes = []
            else:
                active_codes.append(ansi_code)
            current_pos = match.end()
        
        # Add any remaining text
        if current_pos < len(text):
            tokens.append(('text', text[current_pos:]))
        
        # Build truncated result
        result = ""
        visible_len = 0
        
        for token_type, token_text in tokens:
            if token_type == 'ansi':
                # Always include ANSI codes (they don't count toward visible length)
                result += token_text
            else:  # text token
                # Add as much of this text token as we can
                remaining = target_len - visible_len
                if remaining <= 0:
                    break
                
                if len(token_text) <= remaining:
                    # Can include entire token
                    result += token_text
                    visible_len += len(token_text)
                else:
                    # Truncate this token
                    result += token_text[:remaining]
                    visible_len += remaining
                    break
        
        # Add truncation indicator
        result += indicator
        
        # Add reset if there are active codes
        if active_codes:
            result += '\x1b[0m'
        
        return result


# Singleton instance for easy import
display_manager = DisplayManager()