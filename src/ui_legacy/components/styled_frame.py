"""Reusable styled frame components"""
import tkinter as tk
from tkinter import ttk


class StyledFrame(tk.Frame):
    """Custom styled frame with consistent appearance"""

    def __init__(self, parent, bg="#2d2d2d", **kwargs):
        """
        Create a styled frame

        Args:
            parent: Parent widget
            bg: Background color
            **kwargs: Additional frame options
        """
        super().__init__(parent, bg=bg, **kwargs)


class StyledLabelFrame(tk.LabelFrame):
    """Custom styled label frame with consistent appearance"""

    def __init__(self, parent, text="", **kwargs):
        """
        Create a styled label frame

        Args:
            parent: Parent widget
            text: Frame label text
            **kwargs: Additional frame options
        """
        default_options = {
            "bg": "#2d2d2d",
            "fg": "white",
            "font": ("Arial", 10, "bold"),
            "padx": 8,
            "pady": 8
        }

        frame_options = {**default_options, **kwargs}
        super().__init__(parent, text=text, **frame_options)


class ScrollableFrame(tk.Frame):
    """Scrollable frame with canvas and scrollbar"""

    def __init__(self, parent, bg="#2d2d2d", height=None, **kwargs):
        """
        Create a scrollable frame

        Args:
            parent: Parent widget
            bg: Background color
            height: Optional fixed height
            **kwargs: Additional frame options
        """
        super().__init__(parent, **kwargs)

        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)

        # Create container frame inside canvas
        self.container = tk.Frame(self.canvas, bg=bg)

        # Configure canvas scrolling
        self.container.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Create window in canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.container, anchor="nw")

        # Configure canvas scroll command
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Pack canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Set height if specified
        if height:
            self.canvas.configure(height=height)

        # Mouse wheel scrolling
        self._bind_mousewheel()

        # Bind canvas width to container width
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, event):
        """Update container width when canvas is resized"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _bind_mousewheel(self):
        """Bind mouse wheel scrolling"""
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def set_height(self, height):
        """Set canvas height"""
        self.canvas.configure(height=height)
