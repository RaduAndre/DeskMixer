import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image
import threading
import os
import sys
import socket
import pystray

from ui.volume_tab import VolumeTab
from ui.config_tab import ConfigTab
from ui.serial_monitor import SerialMonitor
from audio.audio_manager import AudioManager
from utils.error_handler import handle_error, log_error
from utils.window_monitor import WindowMonitor
from config.config_manager import ConfigManager

# IPC Constants
IPC_PORT = 48612  # Port for inter-process communication
IPC_MESSAGE = b"SHOW_WINDOW"


class VolumeControllerUI:
    """Main application window with tabbed interface"""

    def __init__(self, root):
        self.root = root
        self.tray_icon = None
        self.running = True
        self.ipc_server = None

        # Initialize config manager early
        self.config_manager = ConfigManager()

        try:
            self._initialize_window()
            self._initialize_managers()
            self._create_ui()
            self._start_monitoring()
            self._setup_tray_icon()
            self._start_ipc_listener()

        except Exception as e:
            handle_error(e, "Failed to initialize application")
            raise

        # Change the protocol for close button to terminate the app
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # Bind the minimize event (iconify) to hide the window to tray
        self.root.bind("<Unmap>", self.on_minimize)

    def get_resource_path(self, relative_path):
        """
        Get absolute path to resource, works for dev and PyInstaller.

        Args:
            relative_path: Path relative to src directory (e.g., 'icons/logo.png')

        Returns:
            Absolute path to the resource
        """
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = sys._MEIPASS
        else:
            # Running in development mode
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        return os.path.join(base_path, relative_path)

    def create_tray_image(self):
        """Create a PIL image object for the tray icon."""
        try:
            icon_path = self.get_resource_path('icons/logo.png')
            return Image.open(icon_path)
        except Exception as e:
            log_error(e, "Could not load tray icon. Using default icon.")
            return Image.new('RGB', (64, 64), color='darkgrey')

    def _initialize_window(self):
        """Initialize the main window properties"""
        self.root.title("DeskMixer")
        self.root.geometry("900x700")
        self.root.configure(bg="#1e1e1e")

        # Load icon for the taskbar/window header
        try:
            icon_path = self.get_resource_path('icons/logo.png')
            self.icon_image = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, self.icon_image)
        except Exception as e:
            log_error(e, "Could not load window icon.")

        self.root.minsize(800, 600)

    def _initialize_managers(self):
        """Initialize audio and window managers"""
        try:
            self.audio_manager = AudioManager()
            self.window_monitor = WindowMonitor()
        except Exception as e:
            handle_error(e, "Failed to initialize managers")
            raise

    def _create_ui(self):
        """Create the tabbed user interface"""
        try:
            # Configure style
            style = ttk.Style()
            style.theme_use('clam')

            # Configure notebook style for better visibility
            style.configure('TNotebook',
                            background='#1e1e1e',
                            borderwidth=2,
                            relief='solid')

            style.configure('TNotebook.Tab',
                            background='#2d2d2d',
                            foreground='white',
                            padding=[30, 12],
                            font=('Arial', 11, 'bold'),
                            borderwidth=2)

            style.map('TNotebook.Tab',
                      background=[('selected', '#404040'), ('active', '#353535')],
                      foreground=[('selected', '#00ff00'), ('active', 'white')],
                      expand=[('selected', [1, 1, 1, 0])])

            # Main frame to hold notebook
            main_frame = tk.Frame(self.root, bg="#1e1e1e")
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # Create notebook
            self.notebook = ttk.Notebook(main_frame)
            self.notebook.pack(fill="both", expand=True)

            # Create tabs
            self.volume_tab = VolumeTab(self.notebook, self.audio_manager, self.window_monitor)
            self.config_tab = ConfigTab(self.notebook, self.audio_manager)
            self.serial_tab = SerialMonitor(self.notebook, self.audio_manager.serial_handler)

            # Add tabs to notebook
            self.notebook.add(self.config_tab.frame, text="  Configuration  ")
            self.notebook.add(self.serial_tab.frame, text="  Serial Monitor  ")

        except Exception as e:
            handle_error(e, "Failed to create UI")
            raise

    def _setup_tray_icon(self):
        """Setup and start the system tray icon"""
        try:
            icon_image = self.create_tray_image()
            menu = (
                pystray.MenuItem('Show Window', self._on_show_window, default=True),
                pystray.MenuItem('Quit', self._on_quit)
            )
            self.tray_icon = pystray.Icon("DeskMixer", icon_image, "DeskMixer", menu)

            # Set the action for double-click on the tray icon
            self.tray_icon.activate = self._on_show_window

            # Start the tray icon on a separate thread
            tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            tray_thread.start()
        except Exception as e:
            log_error(e, "Failed to setup tray icon")

    def _on_show_window(self, icon=None, item=None):
        """Handles the Show Window menu item and double-click."""
        self.root.after(0, self.show_window)

    def _on_quit(self, icon=None, item=None):
        """Handles the Quit menu item."""
        self.root.after(0, self.on_close)

    def _start_ipc_listener(self):
        """Start a listener socket to receive show window commands from new instances."""

        def listen():
            try:
                self.ipc_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.ipc_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.ipc_server.bind(('127.0.0.1', IPC_PORT))
                self.ipc_server.listen(1)
                self.ipc_server.settimeout(1.0)  # Check periodically if app is still running

                while self.running:
                    try:
                        conn, _ = self.ipc_server.accept()
                        data = conn.recv(1024)
                        if data == IPC_MESSAGE:
                            # Show the window on the main thread
                            self.root.after(0, self.show_window)
                        conn.close()
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.running:  # Only log if we're still supposed to be running
                            log_error(e, "Error in IPC listener")

                self.ipc_server.close()
            except Exception as e:
                log_error(e, "Could not start IPC listener")

        thread = threading.Thread(target=listen, daemon=True)
        thread.start()

    @staticmethod
    def notify_existing_instance():
        """Send a message to the existing instance to show itself."""
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(2.0)
            client.connect(('127.0.0.1', IPC_PORT))
            client.send(IPC_MESSAGE)
            client.close()
            return True
        except Exception as e:
            log_error(e, "Could not notify existing instance via IPC")
            return False

    def _start_monitoring(self):
        """Start background monitoring threads"""
        try:
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True
            )
            self.monitor_thread.start()
        except Exception as e:
            log_error(e, "Failed to start monitoring thread")

    def _monitor_loop(self):
        """Main monitoring loop for applications"""
        import time
        while self.running:
            try:
                focused_app = self.window_monitor.get_focused_app()
                if focused_app:
                    self.volume_tab.update_focused_app(focused_app)
                time.sleep(0.3)
            except Exception as e:
                log_error(e, "Error in monitoring loop")
                time.sleep(1)

    def on_minimize(self, event):
        """Handle window minimization event to hide the window."""
        if str(self.root.state()) == 'iconic':
            self.hide_window()

    def hide_window(self):
        """Hides the main window and shows the tray icon."""
        self.root.withdraw()

    def show_window(self):
        """Shows the main window and brings it to the front."""
        self.root.deiconify()
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.attributes('-topmost', False)

    def on_close(self):
        """Clean up and close the application, including the tray icon."""
        try:
            # Check for unsaved changes
            if hasattr(self, 'config_tab') and self.config_tab.unsaved_changes:
                response = messagebox.askyesnocancel(
                    "Unsaved Changes",
                    "There are unsaved changes. Would you like to save them before closing?",
                    icon='warning'
                )

                if response is None:  # Cancel
                    return
                elif response:  # Yes
                    self.config_tab.save_config()

            # Save all config changes one last time
            self.config_manager.save_config_if_changed()

            # Cleanup and close
            self.running = False

            if hasattr(self, 'audio_manager'):
                self.audio_manager.cleanup()

            # Close IPC server
            if self.ipc_server:
                try:
                    self.ipc_server.close()
                except:
                    pass

            # Stop the tray icon's thread gracefully
            if self.tray_icon:
                self.tray_icon.stop()

            # Use quit() for proper tkinter thread exit
            self.root.quit()
            self.root.destroy()

        except Exception as e:
            handle_error(e, "Error during application shutdown")
            self.root.destroy()