import psutil
from utils.error_handler import log_error


class WindowMonitor:
    """Monitor focused window and active processes"""

    def __init__(self):
        self.last_focused = None
        self._check_win32()

    def _check_win32(self):
        """Check if win32 modules are available"""
        try:
            import win32gui
            import win32process
            self.has_win32 = True
        except ImportError:
            self.has_win32 = False
            log_error(
                ImportError("pywin32 not installed"),
                "Window monitoring requires pywin32"
            )

    def get_focused_app(self):
        """Get the currently focused application name"""
        if not self.has_win32:
            return None

        try:
            import win32gui
            import win32process

            hwnd = win32gui.GetForegroundWindow()

            # Skip if no valid window handle
            if not hwnd:
                return None

            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            # Validate PID before using it
            if pid <= 0 or pid > 2 ** 22:  # Max realistic PID on Windows
                return None

            # Check if process exists before creating Process object
            if not psutil.pid_exists(pid):
                return None

            process = psutil.Process(pid)
            return process.name()

        except psutil.NoSuchProcess:
            # Process terminated between checks
            return None
        except psutil.AccessDenied:
            # No permission to access this process
            return None
        except Exception as e:
            log_error(e, "Error getting focused window")
            return None

    def get_process_by_name(self, process_name):
        """Get process info by name"""
        try:
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'] == process_name:
                    return proc
        except Exception as e:
            log_error(e, f"Error finding process {process_name}")

        return None