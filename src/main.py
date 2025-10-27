import tkinter as tk
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

# Constants
SINGLE_INSTANCE_MUTEX_NAME = "Global\\DeskMixer_SingleInstanceMutex"


def run_app():
    """Main application entry point"""

    # Check for a single instance using a named Mutex (Windows only)
    mutex = None
    if HAS_WIN32_MUTEX:
        try:
            mutex = win32event.CreateMutex(None, 1, SINGLE_INSTANCE_MUTEX_NAME)

            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                print("Another instance of DeskMixer is already running. Bringing it to focus.")
                win32api.CloseHandle(mutex)
                # Try to notify the existing instance
                VolumeControllerUI.notify_existing_instance()
                sys.exit(0)
        except Exception as e:
            log_error(e, "Error during single instance check; proceeding without mutex protection.")

    # Initialize Tkinter
    root = tk.Tk()
    root.withdraw()  # Start with the window hidden initially

    # Initialize the UI (it will handle tray icon and IPC)
    ui_app = VolumeControllerUI(root)

    # Determine if we should start hidden based on config
    if hasattr(ui_app.config_tab, 'serial_section') and ui_app.config_tab.serial_section:
        start_hidden = ui_app.config_tab.serial_section.start_in_tray.get()
    else:
        start_hidden = ui_app.config_manager.get_start_in_tray(default=False)

    if not start_hidden:
        ui_app.root.after(100, ui_app.show_window)
    else:
        ui_app.root.after(100, ui_app.hide_window)

    # Start the main UI loop
    root.mainloop()

    # Release the mutex when the app closes
    if mutex and HAS_WIN32_MUTEX:
        try:
            win32api.CloseHandle(mutex)
        except Exception as e:
            log_error(e, "Error releasing mutex on shutdown")


if __name__ == "__main__":
    try:
        setup_error_handling()
        run_app()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)