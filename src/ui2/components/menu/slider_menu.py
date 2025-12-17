"""
Slider Menu Component
Handles slider configuration menu.
"""

import os
from PySide6.QtWidgets import QFileDialog, QMenu
from PySide6.QtGui import QAction
from ui2 import colors
from ui2.settings_manager import settings_manager

try:
    import win32com.client
except ImportError:
    win32com = None

class SliderMenu:
    def __init__(self, menu_builder):
        self.menu_builder = menu_builder

    def build_menu(self, target_slider):
        """Build the slider configuration menu content."""
        self.menu_builder.clear()
        
        # Helper to create toggleable item
        def add_toggle_item(name, value, argument=None, level=0, extra_margin=0, on_right_click=None, parent=None):
            is_selected = target_slider.has_variable(value, argument)
            item = self.menu_builder.add_item(name, level=level, selected=is_selected, extra_margin=extra_margin, on_right_click=on_right_click)
            # Custom click handler for toggle
            item.clicked.connect(lambda: self._handle_slider_toggle(item, target_slider, value, argument))
            return item

        self.menu_builder.add_head("General", expandable=True, expanded=True)
        
        add_toggle_item("Master", "Master")
        add_toggle_item("Microphone", "Microphone")
        add_toggle_item("System sounds", "System sounds")
        add_toggle_item("Focused application", "Focused application")
        add_toggle_item("Unbound", "Unbound")
        
        self.menu_builder.add_head("Active sounds", expandable=True, expanded=True)
        if self.menu_builder.audio_manager:
            try:
                 active_apps = self.menu_builder.audio_manager.get_all_audio_apps()
                 found_any = False
                 for app_name in active_apps:
                     if app_name in ["Master", "System Sounds", "Microphone"]:
                         continue 
                     add_toggle_item(app_name, app_name)
                     found_any = True
                     
                 if not found_any:
                     self.menu_builder.add_item("No active apps found", level=0)
            except Exception as e:
                print(f"Error fetching active apps: {e}")
                self.menu_builder.add_item("Error fetching apps", level=0)
        else:
             self.menu_builder.add_item("Audio Service Unavailable", level=0)
        
        self.menu_builder.add_head("Other applications", expandable=True, expanded=True)

        def on_new_app_text(text):
            if text and text.strip():
                clean_text = text.strip()
                settings_manager.add_app_to_list(clean_text)
                self.build_menu(target_slider)
                
        def on_browse_click():
            file_dialog = QFileDialog()
            file_name, _ = file_dialog.getOpenFileName(None, "Select Application", "", "Executables (*.exe);;Shortcuts (*.lnk);;All Files (*)")
            
            if file_name:
                app_name = ""
                _, ext = os.path.splitext(file_name)
                if ext.lower() == '.lnk':
                    if win32com:
                        try:
                            shell = win32com.client.Dispatch("WScript.Shell")
                            shortcut = shell.CreateShortCut(file_name)
                            target_path = shortcut.Targetpath
                            img_name = os.path.basename(target_path)
                            app_name = img_name
                        except Exception as e:
                            print(f"Error resolving shortcut: {e}")
                            app_name = os.path.basename(file_name)
                    else:
                        app_name = os.path.basename(file_name)
                elif ext.lower() == '.exe':
                    app_name = os.path.basename(file_name)
                else:
                    app_name = os.path.basename(file_name)
                
                if app_name:
                    settings_manager.add_app_to_list(app_name)
                    self.build_menu(target_slider)

        
        input_item = self.menu_builder.add_input_item("Select new application", initial_value="", level=0, show_icon=True, icon_name="search.svg", icon_callback=on_browse_click)
        input_item.value_changed.connect(on_new_app_text)
        
        saved_apps = settings_manager.get_app_list()
        if saved_apps:
            
            def create_delete_handler(app_name):
                 def on_right_click(pos):
                     parent_widget = self.menu_builder.content_layout.parentWidget()
                     menu = QMenu(parent_widget) 
                     delete_action = QAction(f"Delete '{app_name}'", menu)
                     delete_action.triggered.connect(lambda: delete_app(app_name))
                     menu.addAction(delete_action)
                     
                     menu.setStyleSheet(f"""
                        QMenu {{
                            background-color: {colors.BACKGROUND};
                            color: {colors.WHITE};
                            border: 1px solid {colors.BORDER};
                        }}
                        QMenu::item {{
                            padding: 5px 20px;
                        }}
                        QMenu::item:selected {{
                            background-color: {colors.BACKGROUND};
                        }}
                     """)
                     menu.exec(pos)
                 return on_right_click

            def delete_app(app_name):
                settings_manager.remove_app_from_list(app_name)
                self.build_menu(target_slider)
            
            for app_name in saved_apps:
                add_toggle_item(app_name, app_name, extra_margin=20, on_right_click=create_delete_handler(app_name))

    def _handle_slider_toggle(self, item, slider, value, argument):
        if not slider.has_variable(value, argument):
            if hasattr(self.menu_builder, 'variable_validator') and self.menu_builder.variable_validator:
                conflicting_slider = self.menu_builder.variable_validator(value, argument, slider)
                if conflicting_slider:
                    if hasattr(item, 'flash_error'):
                        item.flash_error()
                    if hasattr(conflicting_slider, 'flash_success'):
                        conflicting_slider.flash_success()
                    return

        slider.toggle_variable(value, argument)
        item.set_selected(slider.has_variable(value, argument))
