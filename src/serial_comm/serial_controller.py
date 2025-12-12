import threading
import time
from utils.error_handler import log_error
from audio.audio_utils import SliderSmoother
from serial_comm.data_parser import SerialDataParser
from utils.actions import ActionHandler

class SerialController:
    """
    Handles serial data processing, event dispatching, and action execution.
    Decouples serial logic from AudioManager.
    """

    def __init__(self, audio_manager, serial_handler, config_manager):
        self.audio_manager = audio_manager
        self.serial_handler = serial_handler
        self.config_manager = config_manager
        
        # Components
        self.slider_smoother = SliderSmoother()
        self.data_parser = SerialDataParser()
        self.action_handler = ActionHandler(audio_manager)
        
        # State tracking
        self.last_focused_app = None
        
        # Threshold tracking to prevent unnecessary volume calls
        self.last_applied_values = {}
        self.VOLUME_CHANGE_THRESHOLD = 0.01  # 1% threshold

    def start(self):
        """Start processing events and listening to serial"""
        if self.serial_handler:
            self.serial_handler.add_callback(self._handle_serial_data)
        print("SerialController started")

    def stop(self):
        """Stop processing and cleanup"""
        print("Stopping SerialController...")
        if self.serial_handler:
            self.serial_handler.remove_callback(self._handle_serial_data)


    def _handle_serial_data(self, data):
        """Handle incoming serial data"""
        try:
            # Parse data using the parser
            parsed_event = self.data_parser.parse_data(data)
            if not parsed_event:
                return

            # Handle Buttons - Execute Directly (no queue)
            if parsed_event.buttons:
                for btn_id, state in parsed_event.buttons.items():
                    if state: 
                        # Execute immediately in serial thread for lowest latency
                        self._handle_button_action(btn_id, state)

            # Handle Sliders - Direct Update
            if parsed_event.sliders and self.config_manager:
                # Use cached config - ConfigManager is singleton and updated by UI
                config = self.config_manager.config
                bindings = config.get('variable_bindings', {})
                slider_sampling = self.config_manager.get_slider_sampling()

                for slider_id, value in parsed_event.sliders.items():
                    # Apply smoothing
                    averaged_value = self.slider_smoother.apply_averaging(slider_id, value, slider_sampling)

                    # Skip threshold check in instant mode for zero latency
                    if slider_sampling == 'instant':
                        # Direct update - no threshold filtering
                        self.last_applied_values[slider_id] = averaged_value
                        binding = bindings.get(slider_id)
                        if binding:
                            self._apply_volume_change(binding, averaged_value)
                    else:
                        # Apply threshold to prevent excessive COM calls
                        last_value = self.last_applied_values.get(slider_id, -1)
                        if abs(averaged_value - last_value) >= self.VOLUME_CHANGE_THRESHOLD:
                            self.last_applied_values[slider_id] = averaged_value
                            
                            binding = bindings.get(slider_id)
                            if binding:
                                self._apply_volume_change(binding, averaged_value)

        except Exception as e:
            log_error(e, f"Error handling serial data: {data}")

    def _apply_volume_change(self, binding, value):
        """Apply volume change to targets"""
        if not self.audio_manager: return

        if isinstance(binding, dict):
            targets = binding.get('app_name', [])
        elif isinstance(binding, list):
            targets = binding
        else:
            targets = [binding] if binding else []

        if isinstance(targets, str):
            targets = [targets]

        for target in targets:
            # Handle new binding structure (list of dicts)
            if isinstance(target, dict):
                # Check for 'value' (new format) or 'app_name' (possible legacy/other format)
                target = target.get('value') or target.get('app_name')
            
            if not target:
                continue

            # Normalize target for case-insensitive comparison
            target_lower = target.lower()

            if target_lower == "master":
                self.audio_manager.set_master_volume(value)
            elif target_lower == "microphone":
                self.audio_manager.set_mic_volume(value)
            elif target_lower == "system sounds":
                self.audio_manager.set_system_sounds_volume(value)
            elif target_lower == "unbound":
                self.audio_manager.set_unbound_volumes(value)
            elif target_lower == "current application":
                self._handle_current_application_volume(value)
            elif target_lower == "none":
                pass
            else:
                # For specific apps, use original case
                self.audio_manager.set_app_volume(target, value)

    def _handle_current_application_volume(self, value):
        """Handle volume for currently focused application"""
        if not self.audio_manager or not self.audio_manager.driver: return
        
        # Get focused app from driver
        process_name = self.audio_manager.driver.get_focused_app()
        
        if process_name:
            self.last_focused_app = process_name
            
            # Check if bound to another slider
            bound_apps = self.audio_manager._get_bound_apps()
            
            if process_name not in bound_apps:
                 if self.audio_manager.driver.set_app_volume(process_name, value):
                     if hasattr(self.audio_manager, 'volume_tab') and self.audio_manager.volume_tab:
                         try:
                             self.audio_manager.volume_tab.update_focused_app(process_name)
                             self.audio_manager.volume_tab.update_volumes()
                         except Exception: pass

    def _handle_button_action(self, button_id, state):
        """Handle button press/release"""
        try:
            if not self.config_manager:
                return

            # Notify UI of button press (for visual feedback)
            if self.audio_manager:
                self.audio_manager.notify_button_press(button_id)

            # Use cached config
            config = self.config_manager.config
            binding = config.get('button_bindings', {}).get(button_id)

            if not binding:
                return

            # Extract new schema values
            value = binding.get('value')
            argument = binding.get('argument')
            argument2 = binding.get('argument2')
            
            # Legacy fallback (if 'value' doesn't exist, try 'action' from old schema)
            if not value:
                value = binding.get('action')

            if not value:
                return

            # Pass to ActionHandler
            # ActionHandler.execute_action now accepts action_name (which is 'value') 
            # and generic kwargs
            self.action_handler.execute_action(
                value, 
                argument=argument, 
                argument2=argument2,
                # Pass legacy keys just in case mixed config exists
                target=binding.get('target'),
                keys=binding.get('keybind'),
                app_path=binding.get('app_path')
            )

        except Exception as e:
            log_error(e, f"Error handling button {button_id}")
