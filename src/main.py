# main.py

import tkinter as tk
import pystray
from PIL import Image
import threading
import os
import sys

# Windows-specific imports for single instance check
try:
    import win32event
    import winerror
    import win32api
    HAS_WIN32_MUTEX = True
except ImportError:
    HAS_WIN32_MUTEX = False

from ui.main_window import VolumeControllerUI
from utils.error_handler import setup_error_handling, log_error

# Helper function to get the resource path for PyInstaller
def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    if getattr(sys, 'frozen', False):
        # When bundled, the icon file is available in the temp directory if added with --add-data
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# --- TRAY ICON FUNCTIONS ---

def create_image():
    """Create a PIL image object for the tray icon."""
    try:
        # Load the icon from the bundled location
        icon_path = get_resource_path('src/icons/logo.png')
        return Image.open(icon_path)
    except Exception as e:
        log_error(e, "Could not load tray icon from 'icons/logo.png'. Using default icon.")
        # Create a simple, fallback image if the file is not found
        return Image.new('RGB', (64, 64), color = 'darkgrey')

def on_quit_callback(icon, item):
    """Handles the Quit menu item."""
    if hasattr(icon, 'ui_app'):
        # Call the application's close method on the main thread
        icon.ui_app.root.after(0, icon.ui_app.on_close)
    
def on_show_window_callback(icon, item):
    """Handles the Show Window menu item and double-click."""
    if hasattr(icon, 'ui_app'):
        # Show the window on the tkinter thread
        icon.ui_app.root.after(0, icon.ui_app.show_window)
        
# A constant for the mutex name
SINGLE_INSTANCE_MUTEX_NAME = "Global\\DeskMixer_SingleInstanceMutex"

def run_app():
    # 0. NEW: Check for a single instance using a named Mutex (Windows only)
    mutex = None
    if HAS_WIN32_MUTEX:
        try:
            # Create a named mutex. If it already exists, win32api.GetLastError will be ERROR_ALREADY_EXISTS.
            mutex = win32event.CreateMutex(None, 1, SINGLE_INSTANCE_MUTEX_NAME)
            
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                print("Another instance of DeskMixer is already running. Exiting.")
                win32api.CloseHandle(mutex)
                sys.exit(0)
        except Exception as e:
            log_error(e, "Error during single instance check; proceeding without mutex protection.")
            
    # 1. Initialize Tkinter
    root = tk.Tk()
    root.withdraw() # Start with the window hidden initially

    # 2. Create the System Tray Icon
    icon_image = create_image()
    menu = (
        pystray.MenuItem('Show Window', on_show_window_callback, default=True),
        pystray.MenuItem('Quit', on_quit_callback)
    )
    icon = pystray.Icon("DeskMixer", icon_image, "DeskMixer", menu)
    
    # Set the action for double-click on the tray icon
    icon.activate = on_show_window_callback

    # 3. Initialize the UI (passing the icon object)
    ui_app = VolumeControllerUI(root, tray_icon=icon)
    icon.ui_app = ui_app # Attach app instance to icon for callbacks

    # 4. Start the Tray Icon on a separate thread
    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()

    # 5. NEW: Respect the 'Start Hidden (in Tray)' setting from config
    # Access the start_in_tray from the serial_section
    if hasattr(ui_app.config_tab, 'serial_section') and ui_app.config_tab.serial_section:
        start_hidden = ui_app.config_tab.serial_section.start_in_tray.get()
    else:
        # Fallback to config manager if serial_section not available yet
        start_hidden = ui_app.config_manager.get_start_in_tray(default=True)
    
    if not start_hidden:
        # User wants the window visible on startup
        ui_app.root.after(100, ui_app.show_window)
    else:
        # User wants the window hidden in the tray on startup
        ui_app.root.after(100, ui_app.hide_window) 

    # Start the main UI loop
    root.mainloop()
    
    # NEW: Release the mutex when the app closes
    if mutex and HAS_WIN32_MUTEX:
        try:
            win32api.CloseHandle(mutex)
        except Exception as e:
            log_error(e, "Error releasing mutex on shutdown")


if __name__ == "__main__":
    try:
        # Setup global error handling first
        setup_error_handling() 
        run_app()
    except Exception as e:
        # A final fallback error handler
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)