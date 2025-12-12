
import sys

# Windows-specific imports for single instance check
try:
    import win32event
    import winerror
    import win32api
    HAS_WIN32_MUTEX = True
except ImportError:
    HAS_WIN32_MUTEX = False

from core.core_controller import CoreController

from utils.error_handler import setup_error_handling, log_error

# Application Version - Single source of truth
VERSION = "2.2.0"

# Constants
SINGLE_INSTANCE_MUTEX_NAME = "Global\\DeskMixer_SingleInstanceMutex"


def run_app():
    """Main application entry point"""

    # Windows-specific imports for single instance check
    import win32gui
    import win32con
    import os
    
    # High DPI Scaling Fix
    # Use System DPI Aware (1) instead of Per Monitor (2) to prevent coordinate snapping/jumping
    # when dragging between screens with different scaling.
    if os.name == 'nt':
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1) 
        except Exception:
            pass

    # Check for a single instance using a named Mutex (Windows only)
    mutex = None
    if HAS_WIN32_MUTEX:
        try:
            mutex = win32event.CreateMutex(None, 1, SINGLE_INSTANCE_MUTEX_NAME)

            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                print("Another instance of DeskMixer is already running. Bringing it to focus.")
                
                # Find the existing window
                hwnd = win32gui.FindWindow(None, "DeskMixer")
                if hwnd:
                    # Restore if minimized
                    if win32gui.IsIconic(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    
                    # Bring to front
                    win32gui.SetForegroundWindow(hwnd)
                
                win32api.CloseHandle(mutex)
                sys.exit(0)
        except Exception as e:
            log_error(e, "Error during single instance check; proceeding without mutex protection.")

    # Initialize PySide6 Application
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    # Create QApplication before any widget
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # For tray icon to keep app running

    # Initialize Core Controller
    core = CoreController()
    core.start()

    # Import and Initialize the UI2 Main Window
    # Doing this after QApplication ensures Qt is ready
    from ui2.main_window import MainWindow
    
    # Pass audio_manager and version to MainWindow
    main_window = MainWindow(audio_manager=core.audio_manager, version=VERSION)

    # Bridge SerialHandler status updates to MainWindow
    def status_bridge(status, message):
        main_window.status_update_signal.emit(status, message)
    
    if core.serial_handler:
        core.serial_handler.add_status_callback(status_bridge)
        
    # Bridge AudioManager volume updates to MainWindow (Thread-safe via Signal)
    def volume_bridge(target, volume):
        main_window.volume_update_signal.emit(target, volume)
        
    if core.audio_manager:
        core.audio_manager.add_volume_callback(volume_bridge)
        
    # Bridge AudioManager button press to MainWindow (Thread-safe via Signal)
    def button_press_bridge(button_id):
        main_window.button_press_signal.emit(button_id)
        
    if core.audio_manager:
        core.audio_manager.add_button_press_callback(button_press_bridge)

    # Determine if we should start hidden based on config
    # Core uses ConfigManager, which is what we want.
    start_hidden = core.get_start_in_tray()

    if not start_hidden:
        main_window.show()
    else:
        # Just ensure tray is visible (MainWindow handles tray mostly in setup_tray_icon)
        # If start hidden, we just don't show the window.
        pass

    # Start the event loop
    exit_code = app.exec()
    
    # Core cleanup
    core.stop()

    # Release the mutex when the app closes
    if mutex and HAS_WIN32_MUTEX:
        try:
            win32api.CloseHandle(mutex)
        except Exception as e:
            log_error(e, "Error releasing mutex on shutdown")
            
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        setup_error_handling()
        run_app()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)