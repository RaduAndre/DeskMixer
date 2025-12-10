"""Reusable styled combobox components"""
from tkinter import ttk


class StyledCombobox(ttk.Combobox):
    """Custom styled combobox with consistent appearance"""

    def __init__(self, parent, values=None, width=20, state="readonly", **kwargs):
        """
        Create a styled combobox

        Args:
            parent: Parent widget
            values: List of values for combobox
            width: Combobox width
            state: Combobox state ("readonly", "normal")
            **kwargs: Additional combobox options
        """
        default_options = {
            "font": ("Arial", 9),
            "width": width,
            "state": state
        }

        combobox_options = {**default_options, **kwargs}

        super().__init__(parent, **combobox_options)

        if values:
            self['values'] = values

        # Set default value if values provided
        if values and len(values) > 0:
            self.set(values[0])
