"""
Helper functions for calculations and data manipulation in templates.

Usage in templates:
    {{ helpers.calculate_total(items, 'price') }}        → '245.50'
    {{ helpers.format_currency(1234.56) }}               → '$1,234.56'
    {{ helpers.percentage(25, 100) }}                    → '25.0%'
    {{ helpers.pluralize(1, 'item') }}                   → 'item'
    {{ helpers.pluralize(2, 'item') }}                   → 'items'
"""

from typing import List, Any, Optional
import re


def calculate_total(items: List[Any], key: Optional[str] = None) -> float:
    """
    Calculate total of numeric values in a list.
    
    Args:
        items: List of numbers or dicts with numeric values
        key: If provided, extract value from dict using this key
    
    Returns:
        Sum of numeric values (0.0 for empty list).
    
    Examples:
        calculate_total([10, 20, 30.5])                    → 60.5
        calculate_total([{'price': 10}, {'price': 20.5}])  → 30.5
    """
    total = 0.0
    for item in items or []:
        try:
            if key and isinstance(item, dict):
                value = item.get(key)
            else:
                value = item
            total += float(value)
        except (ValueError, TypeError):
            continue  # Skip non-numeric values
    return total


def format_currency(amount: float, symbol: str = '$', decimals: int = 2) -> str:
    """
    Format amount as currency.
    
    Args:
        amount: Amount to format
        symbol: Currency symbol
        decimals: Decimal places
    
    Returns:
        Formatted currency string.
    
    Examples:
        format_currency(1234.56)         → '$1,234.56'
        format_currency(-123.45, '€')    → '€(123.45)'
    """
    formatted = f'{abs(amount):,.{decimals}f}'
    if amount < 0:
        formatted = f'({formatted})'
    return f'{symbol}{formatted}'


def percentage(value: float, total: float, decimals: int = 1) -> str:
    """
    Calculate and format percentage.
    
    Args:
        value: Numerator
        total: Denominator
        decimals: Decimal places
    
    Returns:
        Percentage string (handles division by zero).
    
    Examples:
        percentage(25, 100)     → '25.0%'
        percentage(0, 50)       → '0.0%'
    """
    if total == 0:
        return '0.0%'
    return f'{100 * value / total:.{decimals}f}%'


def average(numbers: List[Any], key: Optional[str] = None) -> float:
    """
    Calculate average of numeric values in a list.
    
    Args:
        numbers: List of numbers or dicts with numeric values
        key: If provided, extract value from dict using this key
    
    Returns:
        Average of numeric values (0.0 for empty list).
    
    Examples:
        average([10, 20, 30])                    → 20.0
        average([{'price': 10}, {'price': 20}])  → 15.0
    """
    total = 0.0
    count = 0
    for item in numbers or []:
        try:
            if key and isinstance(item, dict):
                value = item.get(key)
            else:
                value = item
            total += float(value)
            count += 1
        except (ValueError, TypeError):
            continue  # Skip non-numeric values
    return total / count if count > 0 else 0.0


def join_with_and(items: List[str], separator: str = ', ', final: str = ' and ') -> str:
    """
    Join list items with Oxford comma and 'and'.
    
    Args:
        items: List of strings
        separator: Separator between items
        final: Separator before last item
    
    Examples:
        join_with_and(['a', 'b', 'c'])      → 'a, b and c'
        join_with_and(['a', 'b'])           → 'a and b'
        join_with_and(['a'])                → 'a'
    """
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f'{items[0]}{final}{items[1]}'
    return f'{separator.join(items[:-1])}{final}{items[-1]}'


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    """
    Return singular or plural form based on count.
    
    Args:
        count: Number determining form
        singular: Singular form
        plural: Plural form (auto-generates with 's' if None)
    
    Examples:
        pluralize(1, 'item')        → 'item'
        pluralize(2, 'item')        → 'items'
        pluralize(0, 'box', 'boxes')→ 'boxes'
    """
    if count == 1:
        return singular
    if plural:
        return plural
    return singular + 's'
