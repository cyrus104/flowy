"""
Utility functions for templates.

Usage in templates:
    {{ utils.format_date('2024-01-15', '%B %d, %Y') }}  → 'January 15, 2024'
    {{ utils.truncate(description, 100) }}              → 'First 100 chars...'
    {{ utils.word_count(content) }}                      → '247'
"""

from datetime import datetime
from typing import Optional


def format_date(date_string: str, format_str: str = '%Y-%m-%d') -> str:
    """
    Format a date string to a readable format.
    
    Args:
        date_string: Input date (ISO, US, EU formats supported)
        format_str: Output format string (strftime format)
    
    Returns:
        Formatted date string or original input if parsing fails.
    
    Examples:
        format_date('2024-01-15')                    → '2024-01-15'
        format_date('2024-01-15', '%B %d, %Y')       → 'January 15, 2024'
        format_date('01/15/2024', '%A, %B %d')       → 'Monday, January 15'
    """
    formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_string, fmt)
            return parsed.strftime(format_str)
        except ValueError:
            continue
    
    return date_string  # Return original if parsing fails


def truncate(text: str, length: int = 50, suffix: str = '...') -> str:
    """
    Truncate text to specified length.
    
    Args:
        text: Input text
        length: Maximum length
        suffix: String to append if truncated
    
    Returns:
        Truncated text or original if already short enough.
    """
    if length <= 0:
        return ''
    if len(text) <= length:
        return text
    return text[:length - len(suffix)] + suffix


def capitalize_words(text: str) -> str:
    """Capitalize first letter of each word."""
    return text.title()


def slugify(text: str) -> str:
    """
    Convert text to URL-friendly slug.
    
    Args:
        text: Input text
    
    Returns:
        Lowercase slug with hyphens instead of spaces.
    
    Example:
        slugify('Hello World! 2024')  → 'hello-world-2024'
    """
    import re
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text).strip('-')
    return text.lower()


def word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def format_number(number: float, decimals: int = 2) -> str:
    """
    Format number with thousand separators.
    
    Args:
        number: Number to format
        decimals: Decimal places
    
    Returns:
        Formatted string.
    
    Examples:
        format_number(1234.567, 1)  → '1,234.6'
        format_number(1234567.89)   → '1,234,567.89'
    """
    return f'{number:,.{decimals}f}'
