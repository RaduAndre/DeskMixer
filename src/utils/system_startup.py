# utils/system_startup.py

import os
import sys
# Assuming utils.error_handler exists
from utils.error_handler import log_error 

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False
    pass

def _get_app_path():
    """Get the path to the executable, works for dev, PyInstaller and Nuitka"""
    # PyInstaller and Nuitka (usually) set sys.frozen
    if getattr(sys, 'frozen', False):
        return sys.executable
    
    # Nuitka specific check: if compiled and is an exe, use the executable path
    if "__compiled__" in globals() and sys.argv[0].lower().endswith(".exe"):
        return os.path.abspath(sys.argv[0])

    # Development mode: return python interpreter + script path
    return f'{sys.executable} "{os.path.abspath(sys.argv[0])}"'

def set_startup(should_start):
    """Sets or removes the application from Windows startup."""
    if not HAS_WINREG:
        return False
        
    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "DeskMixer"
    
    try:
        # Use KEY_SET_VALUE to gain write access (needed for both set and delete)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        
        if should_start:
            # Add to startup
            app_path = _get_app_path()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, app_path)
        else:
            # Remove from startup
            try:
                # Use DeleteValue, which works with a KEY_SET_VALUE opened key
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                # Value was not there, which is fine
                pass

        winreg.CloseKey(key)
        return True
        
    except Exception as e:
        # Handle case where the RUN_KEY cannot be opened (e.g., permissions)
        log_error(e, "Error setting Windows startup registry key")
        return False

def check_startup_status():
    """Checks if the application is set to start on Windows startup."""
    if not HAS_WINREG:
        return False
        
    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "DeskMixer"
    
    try:
        # Open key for read access
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        log_error(e, "Error checking Windows startup registry key")
        return False