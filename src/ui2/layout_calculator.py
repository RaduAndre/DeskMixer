"""
Layout calculation utilities for dynamic UI arrangement.
"""

import math

def calculate_button_layout(button_count: int, prefer_vertical: bool = True) -> tuple[int, int]:
    """
    Calculate optimal button layout (rows, cols) based on button count.
    
    Algorithm from build instructions:
    - Round half of button count to nearest lower integer for vertical/horizontal arrangement
    - For parity arrangements like 6 buttons: can be 3x2 or 2x3
    
    Args:
        button_count: Number of buttons to arrange
        prefer_vertical: If True, prefer vertical arrangement (more rows than cols)
    
    Returns:
        Tuple of (rows, cols)
    
    Examples:
        6 buttons, vertical: (3, 2) - 3 rows, 2 columns
        6 buttons, horizontal: (2, 3) - 2 rows, 3 columns
        4 buttons, vertical: (2, 2) - 2 rows, 2 columns
        5 buttons, vertical: (3, 2) - 3 rows, 2 columns
    """
    if button_count <= 0:
        return (0, 0)
    
    if button_count == 1:
        return (1, 1)
    
    # Calculate base column count by rounding half down
    half = button_count / 2
    base_cols = math.floor(half)
    
    # Calculate rows needed
    rows = math.ceil(button_count / base_cols)
    
    # Adjust for preference
    if prefer_vertical:
        # Prefer more rows than columns
        cols = base_cols
    else:
        # Prefer more columns than rows (swap)
        cols = rows
        rows = base_cols
    
    return (rows, cols)


def calculate_slider_layout(slider_count: int, max_columns: int = 5) -> tuple[int, int]:
    """
    Calculate slider layout with a maximum column constraint.
    
    Args:
        slider_count: Number of sliders to arrange
        max_columns: Maximum number of columns (default 5)
    
    Returns:
        Tuple of (rows, cols)
    """
    if slider_count <= 0:
        return (0, 0)
    
    cols = min(slider_count, max_columns)
    rows = math.ceil(slider_count / cols)
    
    return (rows, cols)
