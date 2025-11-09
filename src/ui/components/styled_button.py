"""Reusable styled button components"""
import tkinter as tk


class StyledButton(tk.Button):
    """Custom styled button with consistent appearance"""

    def __init__(self, parent, text="", command=None, style="primary", **kwargs):
        """
        Create a styled button

        Args:
            parent: Parent widget
            text: Button text
            command: Button command callback
            style: Button style - "primary", "secondary", "danger", "success"
            **kwargs: Additional button options
        """
        # Style configurations
        styles = {
            "primary": {
                "bg": "#404040",
                "fg": "white",
                "activebackground": "#505050",
                "activeforeground": "white"
            },
            "secondary": {
                "bg": "#2d2d2d",
                "fg": "white",
                "activebackground": "#3d3d3d",
                "activeforeground": "white"
            },
            "danger": {
                "bg": "#cc0000",
                "fg": "white",
                "activebackground": "#dd1111",
                "activeforeground": "white"
            },
            "success": {
                "bg": "#00aa00",
                "fg": "white",
                "activebackground": "#00bb00",
                "activeforeground": "white"
            }
        }

        # Get style configuration
        style_config = styles.get(style, styles["primary"])

        # Default button options
        default_options = {
            "font": ("Arial", 9),
            "relief": "flat",
            "padx": 10,
            "pady": 5,
            "cursor": "hand2",
            "borderwidth": 0
        }

        # Merge style, defaults, and custom options
        button_options = {**default_options, **style_config, **kwargs}

        # Initialize button
        super().__init__(parent, text=text, command=command, **button_options)

        # Add hover effect
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        # Store original colors
        self._bg = button_options["bg"]
        self._active_bg = button_options["activebackground"]

    def _on_enter(self, event):
        """Handle mouse enter (hover)"""
        self.configure(bg=self._active_bg)

    def _on_leave(self, event):
        """Handle mouse leave"""
        self.configure(bg=self._bg)


class IconButton(StyledButton):
    """Button with icon (emoji or symbol)"""

    def __init__(self, parent, icon="", text="", command=None, style="primary", **kwargs):
        """
        Create an icon button

        Args:
            parent: Parent widget
            icon: Icon/emoji to display
            text: Optional text after icon
            command: Button command callback
            style: Button style
            **kwargs: Additional button options
        """
        button_text = f"{icon} {text}" if text else icon
        super().__init__(parent, text=button_text, command=command, style=style, **kwargs)
