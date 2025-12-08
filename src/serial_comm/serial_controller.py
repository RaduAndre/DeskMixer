import threading
import queue
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

        # Event Queue for Buttons
        self.button_event_queue = queue.Queue()
        self.event_processing_thread = None
        self.processing_events = False
        
        # State tracking
        self.last_focused_app = None

    def start(self):
        """Start processing events and listening to serial"""
        if self.serial_handler:
            self.serial_handler.add_callback(self._handle_serial_data)
        
        self.processing_events = True
        self.event_processing_thread = threading.Thread(target=self._process_button_events, daemon=True)
        self.event_processing_thread.start()
        print("SerialController started")

    def stop(self):
        """Stop processing and cleanup"""
        print("Stopping SerialController...")
        self.processing_events = False
        if self.serial_handler:
            self.serial_handler.remove_callback(self._handle_serial_data)
        
        # Wait for thread if needed, but it's daemon
        pass

    def _process_button_events(self):
        """Process button events from queue"""
        try:
            import comtypes
            comtypes.CoInitialize()
        except ImportError:
            pass
        except Exception as e:
            log_error(e, "Failed to initialize COM in button thread")

        while self.processing_events:
            try:
                # Blocking get with timeout to allow checking processing_events flag
                event = self.button_event_queue.get(timeout=1.0)
                if event:
                    self._handle_button_action(event['button_id'], event['state'])
                    self.button_event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                log_error(e, "Error processing button event")

    def _handle_serial_data(self, data):
        """Handle incoming serial data"""
        try:
            # Parse data using the parser
            parsed_event = self.data_parser.parse_data(data)
            if not parsed_event:
                return

            # Handle Buttons - Push to Queue
            if parsed_event.buttons:
                for btn_id, state in parsed_event.buttons.items():
                    # Only queue if state is True (Pressed) - or handle both if needed
                    # The original code only handled state '1' (Pressed)
                    if state: 
                        self.button_event_queue.put({'button_id': btn_id, 'state': state})

            # Handle Sliders - Direct Update
            if parsed_event.sliders and self.config_manager:
                # Use cached config - ConfigManager is singleton and updated by UI
                config = self.config_manager.config
                bindings = config.get('variable_bindings', {})
                slider_sampling = self.config_manager.get_slider_sampling()

                for slider_id, value in parsed_event.sliders.items():
                    # Apply smoothing
                    averaged_value = self.slider_smoother.apply_averaging(slider_id, value, slider_sampling)

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

            if target == "Master":
                self.audio_manager.set_master_volume(value)
            elif target == "Microphone":
                self.audio_manager.set_mic_volume(value)
            elif target == "System Sounds":
                self.audio_manager.set_system_sounds_volume(value)
            elif target == "Unbinded":
                self.audio_manager.set_unbinded_volumes(value)
            elif target == "Current Application":
                self._handle_current_application_volume(value)
            elif target == "None":
                pass
            else:
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

            # Use cached config
            config = self.config_manager.config
            binding = config.get('button_bindings', {}).get(button_id)

            if not binding:
                return

            action = binding.get('action')
            target = binding.get('target')
            keybind = binding.get('keybind')
            app_path = binding.get('app_path')
            output_mode = binding.get('output_mode')
            output_device = binding.get('output_device')
            
            # New generic structure
            value = binding.get('value')
            argument = binding.get('argument')

            # Use the action handler instance
            kwargs = {}
            if target: kwargs['target'] = target
            if keybind: kwargs['keys'] = keybind
            if app_path: kwargs['app_path'] = app_path
            if output_mode: kwargs['output_mode'] = output_mode
            if output_device: kwargs['device_name'] = output_device
            
            # Pass generic values
            if value: kwargs['value'] = value
            if argument: kwargs['argument'] = argument

            self.action_handler.execute_action(action, **kwargs)

        except Exception as e:
            log_error(e, f"Error handling button {button_id}")
