"""
Button Menu Component
Handles button configuration menu.
"""

from ui2.settings_manager import settings_manager

class ButtonMenu:
    def __init__(self, menu_builder):
        self.menu_builder = menu_builder

    def build_menu(self, target_button):
        """Build the button configuration menu content."""
        self.menu_builder.clear()
        
        def add_action_item(name, value, argument=None, level=0, is_default=False):
            # Check if this action is the active one
            current_var = target_button.get_variable()
            is_selected = False
            if current_var:
                if current_var['value'] == value and current_var['argument'] == argument:
                    is_selected = True
            elif value == "None":
                 is_selected = True

            item = self.menu_builder.add_item(name, level=level, selected=is_selected, is_default=is_default)
            item.clicked.connect(lambda: self._handle_button_select(item, target_button, value, argument))
            return item

        self.menu_builder.add_head("General", expandable=True, expanded=True)
        
        add_action_item("Play/Pause", "Play/Pause")
        add_action_item("Previous", "Previous")
        add_action_item("Next", "Next")
        add_action_item("Volume Up", "Volume Up")
        add_action_item("Volume Down", "Volume Down")
        add_action_item("Seek Backward", "Seek Backward")
        add_action_item("Seek Forward", "Seek Forward")

        self.menu_builder.add_head("Actions", expandable=True, expanded=True)
        
        # Mute
        mute_item = self.menu_builder.add_item("Mute", is_expandable=True)
        add_action_item("Master", "Mute", "Master", level=1, is_default=True)
        add_action_item("Microphone", "Mute", "Microphone", level=1)
        add_action_item("System Sounds", "Mute", "System Sounds", level=1)
        add_action_item("Current Application", "Mute", "Current Application", level=1)
        
        if self.menu_builder.audio_manager:
            try:
                active_apps = self.menu_builder.audio_manager.get_all_audio_apps()
                for app_name in active_apps:
                    if app_name not in ["Master", "System Sounds", "Microphone"]:
                        add_action_item(app_name, "Mute", app_name, level=1)
            except Exception as e:
                print(f"Error getting active audio apps: {e}")
        
        saved_apps = settings_manager.get_app_list()
        if saved_apps:
            for app_name in sorted(saved_apps):
                if app_name not in ["Master", "Microphone", "System Sounds", "Current Application"]:
                    add_action_item(app_name, "Mute", app_name, level=1)
        
        # Switch Audio Output
        switch_item = self.menu_builder.add_item("Switch Audio Output", is_expandable=True)
        add_action_item("Cycle Through", "Switch Audio Output", "Cycle Through", level=1, is_default=True)
        add_action_item("Speakers", "Switch Audio Output", "Speakers", level=1)
        add_action_item("Headphones", "Switch Audio Output", "Headphones", level=1)
        
        # Keybind
        keybind_item = self.menu_builder.add_item("Keybind", is_expandable=True)
        
        current_kb = ""
        current_var = target_button.get_variable()
        if current_var and current_var['value'] == "Keybind":
            current_kb = current_var.get('argument', "")
            keybind_item.set_selected(True)
            
        input_item = self.menu_builder.add_input_item("Write Keybind", initial_value=current_kb, level=1)
        
        if keybind_item.is_selected():
            keybind_item.set_has_active_child(True)
            input_item.set_active(True)

        def update_ui_for_keybind(active: bool):
            for item in self.menu_builder.menu_items:
                item.set_selected(False)
                if hasattr(item, 'set_has_active_child'):
                    item.set_has_active_child(False)
            
            if active:
                keybind_item.set_selected(True)
                keybind_item.set_has_active_child(True)
                input_item.set_active(True)

        def on_keybind_save(value):
            target_button.set_variable("Keybind", value)
            update_ui_for_keybind(True)
            
        def on_keybind_toggle():
            current_var = target_button.get_variable()
            is_active = False
            if current_var and current_var['value'] == "Keybind":
                is_active = True
                
            if is_active:
                target_button.set_variable("None")
                update_ui_for_keybind(False)
            else:
                val = input_item.get_value()
                target_button.set_variable("Keybind", val)
                update_ui_for_keybind(True)
            
        input_item.value_changed.connect(on_keybind_save)
        input_item.clicked.connect(on_keybind_toggle)
        
        # Launch App
        launch_item = self.menu_builder.add_item("Launch app", is_expandable=True)
        
        current_app = ""
        current_path = ""
        launch_var = target_button.get_variable()
        launch_active = False
        if launch_var and launch_var['value'] == "Launch app":
            current_app = launch_var.get('argument', "")
            current_path = launch_var.get('argument2', "")
            launch_active = True
            
        browse_item = self.menu_builder.add_browse_item(initial_value=current_app, level=1)
        if current_path:
            browse_item.current_path = current_path
        
        if launch_active:
            launch_item.set_selected(True)
            launch_item.set_has_active_child(True)
            browse_item.set_active(True)
            
        def update_ui_for_launch(active: bool):
            for item in self.menu_builder.menu_items:
                item.set_selected(False)
                if hasattr(item, 'set_has_active_child'):
                    item.set_has_active_child(False)
            
            if active:
                launch_item.set_selected(True)
                launch_item.set_has_active_child(True)
                browse_item.set_active(True)

        def on_launch_save(name, path):
            # Store in target button
            target_button.set_variable("Launch app", name, path)
            update_ui_for_launch(True)
            
        def on_launch_toggle():
            # Triggered when clicking parent (Launch app item)
            current_var = target_button.get_variable()
            is_active = False
            if current_var and current_var['value'] == "Launch app":
                is_active = True
            
            if is_active:
                target_button.set_variable("None")
                update_ui_for_launch(False)
            else:
                # If toggling on without browsing, use current values in browse item
                text = browse_item.current_text
                path = browse_item.current_path
                target_button.set_variable("Launch app", text, path)
                update_ui_for_launch(True)

        # Use app_selected signal (name, path)
        browse_item.app_selected.connect(on_launch_save)
        browse_item.clicked.connect(on_launch_toggle) # Connected to parent click via default
        
        # Manually register browse_item as default child of launch_item for toggle logic
        self.menu_builder.default_children[launch_item] = browse_item

    def _handle_button_select(self, item, button, value, argument):
        current_var = button.get_variable()
        is_active = False
        if current_var:
             if current_var['value'] == value and current_var['argument'] == argument:
                 is_active = True
        
        if is_active:
            button.set_variable("None")
            item.set_selected(False)
        else:
            button.set_variable(value, argument)
            # Deselect all others
            for other_item in self.menu_builder.menu_items:
                other_item.set_selected(False)
                # Reset inputs/browsers active state
                if hasattr(other_item, 'set_active'):
                    other_item.set_active(False)
                # Reset parent active child indicators
                if hasattr(other_item, 'set_has_active_child'):
                    other_item.set_has_active_child(False)
            
            item.set_selected(True)
            if item.level == 1 and item in self.menu_builder.parent_map:
                parent = self.menu_builder.parent_map[item]
                parent.set_selected(True)
                parent.set_has_active_child(True)
