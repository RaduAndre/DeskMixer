# ui/main_window.py

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import sys

from ui.volume_tab import VolumeTab
from ui.config_tab import ConfigTab
from ui.serial_monitor import SerialMonitor
from audio.audio_manager import AudioManager
from utils.error_handler import handle_error, log_error
from utils.window_monitor import WindowMonitor
from config.config_manager import ConfigManager


class VolumeControllerUI:
    """Main application window with tabbed interface"""

    def __init__(self, root, tray_icon=None):
        self.root = root
        self.tray_icon = tray_icon  # Accept the pystray icon object
        self.running = True
        
        # Initialize config manager early
        self.config_manager = ConfigManager()

        try:
            self._initialize_window()
            self._initialize_managers()
            self._create_ui()
            self._start_monitoring()

        except Exception as e:
            handle_error(e, "Failed to initialize application")
            raise

        # Change the protocol for close button to self.hide_window
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        # Bind the minimize event (iconify) to also hide the window
        # The <Unmap> event fires when the window is iconified (minimized)
        self.root.bind("<Unmap>", self.on_minimize)

    # Helper function to get the resource path for PyInstaller
    def get_resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and PyInstaller"""
        if getattr(sys, 'frozen', False):
            # When bundled, the icon file is available in the temp directory if added with --add-data
            base_path = sys._MEIPASS
        else:
            # Get the directory containing this script file
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        return os.path.join(base_path, relative_path)

    def _initialize_window(self):
        """Initialize the main window properties"""
        self.root.title("DeskMixer")
        self.root.geometry("900x700")
        self.root.configure(bg="#1e1e1e")
        
        # Load icon for the taskbar/window header
        try:
            # Use the PyInstaller compatible resource path
            icon_path = self.get_resource_path('icons/logo.png')
            self.icon_image = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, self.icon_image)
        except Exception as e:
            log_error(e, "Could not load window icon from'.")
            
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
            #self.notebook.add(self.volume_tab.frame, text="  Volume Control  ")
            self.notebook.add(self.serial_tab.frame, text="  Serial Monitor  ")

        except Exception as e:
            handle_error(e, "Failed to create UI")
            raise

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
        # Check if the window is being minimized
        if str(self.root.state()) == 'iconic':
            self.hide_window()

    def hide_window(self):
        """Hides the main window and shows the tray icon."""
        self.root.withdraw()  # Hides the window

    def show_window(self):
        """Shows the main window and brings it to the front."""
        self.root.deiconify()  # Shows the window
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.attributes('-topmost', False)  # Makes it not permanently topmost
            
    def on_close(self):
        """Clean up and close the application, including the tray icon."""
        try:
            # Check for unsaved changes (existing code)
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
                
            # Stop the tray icon's thread gracefully
            if self.tray_icon:
                self.tray_icon.stop()
                
            # Use quit() for proper tkinter thread exit
            self.root.quit()
            self.root.destroy()

        except Exception as e:
            handle_error(e, "Error during application shutdown")
            self.root.destroy()
