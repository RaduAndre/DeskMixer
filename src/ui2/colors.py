"""
Color configuration for DeskMixer UI.
Supports Dynamic Accent Color Switching.
"""

# Accent Colors Preset
ACCENT_COLORS = {
    "teal": "#00EAD0",
    "blue": "#007AFF",
    "purple": "#AF52DE",
    "red": "#FF3B30",
    "orange": "#FF9500",
    "green": "#34C759"
}

# Fixed Dark Theme Colors
BACKGROUND = "#191919"
WHITE = "#FBFBFB"
BLACK = "#000000"
BORDER = "#2A2A2A"

# Status colors (Fixed)
STATUS_CONNECTED = "#79E053"
STATUS_TRYING = "#F88379"
STATUS_DISCONNECTED = "#FF2400"

# Dynamic Accent (Default: Teal)
CURRENT_ACCENT_NAME = "teal"
ACCENT = ACCENT_COLORS["teal"]

_observers = []

def add_observer(callback):
    """Add a callback to be notified when theme changes."""
    _observers.append(callback)

def set_accent(color_name: str):
    """
    Set the active accent color.
    Updates global ACCENT variable and notifies observers.
    Accepts preset names ('teal', 'blue') or Hex strings ('#FF0000').
    """
    global CURRENT_ACCENT_NAME, ACCENT
    
    # Check if it's a Hex code
    if color_name.startswith('#'):
        CURRENT_ACCENT_NAME = color_name # Store hex as name for now, or "Custom"
        ACCENT = color_name
    else:
        # Check presets
        color_name = color_name.lower()
        if color_name in ACCENT_COLORS:
            CURRENT_ACCENT_NAME = color_name
            ACCENT = ACCENT_COLORS[color_name]
        else:
            # Fallback or ignore
            print(f"Warning: Invalid accent color '{color_name}'")
            return

    # Notify Observers
    for callback in _observers:
        try:
            callback()
        except Exception as e:
            print(f"Error in theme observer: {e}")

def get_accent_name():
    return CURRENT_ACCENT_NAME

# Deprecated/Alias for compatibility during refactor if needed, 
# but we will update callers.
def set_theme(name):
    print("WARNING: set_theme is deprecated, use set_accent")
    pass 

