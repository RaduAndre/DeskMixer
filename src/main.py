# main.py

import tkinter as tk
import pystray
import threading
import sys

# Windows-specific imports for single instance check
try:
    import win32event
    import winerror
    import win32api
    import win32gui
    import win32con

    HAS_WIN32_MUTEX = True
except ImportError:
    HAS_WIN32_MUTEX = False

from ui.main_window import VolumeControllerUI
from utils.error_handler import setup_error_handling, log_error


# --- TRAY ICON CALLBACK FUNCTIONS ---

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


def bring_existing_instance_to_front():
    """Find and bring the existing DeskMixer window to the front."""
    if not HAS_WIN32_MUTEX:
        return False

    def enum_windows_callback(hwnd, windows):
        """Callback function for EnumWindows."""
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            if "DeskMixer" in window_title:
                windows.append(hwnd)
        return True

    try:
        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)

        if windows:
            hwnd = windows[0]
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            # Bring to front
            win32gui.SetForegroundWindow(hwnd)
            return True
    except Exception as e:
        log_error(e, "Error bringing existing instance to front")

    return False


def run_app():
    """Main application entry point"""

    # 0. Check for a single instance using a named Mutex (Windows only)
    mutex = None
    if HAS_WIN32_MUTEX:
        try:
            # Create a named mutex. If it already exists, win32api.GetLastError will be ERROR_ALREADY_EXISTS.
            mutex = win32event.CreateMutex(None, 1, SINGLE_INSTANCE_MUTEX_NAME)

            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                print("Another instance of DeskMixer is already running. Bringing it to focus.")
                win32api.CloseHandle(mutex)
                # Try to bring the existing instance to the front
                bring_existing_instance_to_front()
                sys.exit(0)
        except Exception as e:
            log_error(e, "Error during single instance check; proceeding without mutex protection.")

    # 1. Initialize Tkinter
    root = tk.Tk()
    root.withdraw()  # Start with the window hidden initially

    # 2. Initialize the UI first (without tray icon reference)
    ui_app = VolumeControllerUI(root, tray_icon=None)

    # 3. Create the System Tray Icon using the UI's create_tray_image method
    icon_image = ui_app.create_tray_image()
    menu = (
        pystray.MenuItem('Show Window', on_show_window_callback, default=True),
        pystray.MenuItem('Quit', on_quit_callback)
    )
    icon = pystray.Icon("DeskMixer", icon_image, "DeskMixer", menu)

    # Set the action for double-click on the tray icon
    icon.activate = on_show_window_callback

    # 4. Attach the tray icon to the UI app (now that it's created)
    ui_app.tray_icon = icon
    icon.ui_app = ui_app  # Attach app instance to icon for callbacks

    # 5. Start the Tray Icon on a separate thread
    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()

    # 6. Respect the 'Start Hidden (in Tray)' setting from config
    if hasattr(ui_app.config_tab, 'serial_section') and ui_app.config_tab.serial_section:
        start_hidden = ui_app.config_tab.serial_section.start_in_tray.get()
    else:
        # Fallback to config manager if serial_section not available yet
        start_hidden = ui_app.config_manager.get_start_in_tray(default=False)

    if not start_hidden:
        # User wants the window visible on startup
        ui_app.root.after(100, ui_app.show_window)
    else:
        # User wants the window hidden in the tray on startup
        ui_app.root.after(100, ui_app.hide_window)

        # 7. Start the main UI loop
    root.mainloop()

    # 8. Release the mutex when the app closes
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