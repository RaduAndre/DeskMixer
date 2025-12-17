from dataclasses import dataclass
from typing import Dict, Optional, Union
from utils.error_handler import log_error

@dataclass
class ButtonEvent:
    button_id: str
    state: bool  # True for pressed (1), False for released (0)

@dataclass
class SliderEvent:
    slider_id: str
    value: float  # Normalized 0.0 - 1.0

@dataclass
class SerialDataEvent:
    sliders: Dict[str, float]
    buttons: Dict[str, bool]

class SerialDataParser:
    """Parser for serial data returning structured events"""

    @staticmethod
    def parse_data(data_str: str) -> Optional[SerialDataEvent]:
        """Parse serial data string into slider/button dict"""
        try:
            if not data_str:
                return None

            if isinstance(data_str, bytes):
                data_str = data_str.decode('utf-8', errors='ignore')
            
            data_str = data_str.strip()
            sliders = {}
            buttons = {}

            # Handle lines with pipe-separated values (e.g. "Slider 1 364|Slider 2 351")
            if '|' in data_str:
                parts = data_str.split('|')
                for part in parts:
                    part = part.strip()
                    if not part: continue
                    
                    try:
                        # Try parsing "Slider X Y" format
                        sub_parts = part.split()
                        if len(sub_parts) == 3 and sub_parts[0] == 'Slider':
                            _, slider_num, value = sub_parts
                            key = f"s{slider_num}"
                            normalized_value = float(value) / 1023.0
                            # Zero-snap: values below 1% become 0
                            if normalized_value < 0.01:
                                normalized_value = 0.0
                            sliders[key] = normalized_value
                        
                        # Try parsing legacy "sX Y" format
                        elif len(sub_parts) == 2:
                            key, value = sub_parts
                            if key.startswith('s'):
                                normalized_value = float(value) / 1023.0
                                # Zero-snap: values below 1% become 0
                                if normalized_value < 0.01:
                                    normalized_value = 0.0
                                sliders[key] = normalized_value
                    except ValueError:
                        continue
            
            # Handle raw "Slider X Y" format (e.g. "Slider 0 1023")
            elif data_str.startswith('Slider '):
                try:
                    parts = data_str.split()
                    if len(parts) == 3:
                        _, slider_num, value = parts
                        key = f"s{slider_num}"
                        normalized_value = float(value) / 1023.0
                        # Zero-snap: values below 1% become 0
                        if normalized_value < 0.01:
                            normalized_value = 0.0
                        sliders[key] = normalized_value
                except ValueError:
                    pass

            # Handle raw "Button X Y" format (e.g. "Button 1 1")
            elif data_str.startswith('Button '):
                try:
                    parts = data_str.split()
                    if len(parts) == 3:
                        _, button_num, state = parts
                        key = f"b{button_num}"
                        buttons[key] = (state == '1')
                except ValueError:
                    pass

            # Handle legacy/simple format "bX Y" (e.g. "b1 1")
            elif data_str.startswith('b'):
                try:
                    parts = data_str.split()
                    if len(parts) == 2:
                        key, value = parts
                        buttons[key] = (value == '1')
                except ValueError:
                    pass
            
            # Handle legacy/simple format "sX Y" (e.g. "s0 1023")
            elif data_str.startswith('s'):
                try:
                    parts = data_str.split()
                    if len(parts) == 2:
                        key, value = parts
                        if key[1:].isdigit(): # Ensure it's s0, s1 etc
                             normalized_value = float(value) / 1023.0
                             # Zero-snap: values below 1% become 0
                             if normalized_value < 0.01:
                                 normalized_value = 0.0
                             sliders[key] = normalized_value
                except ValueError:
                    pass

            if not sliders and not buttons:
                return None

            return SerialDataEvent(sliders=sliders, buttons=buttons)

        except Exception as e:
            log_error(e, f"Error parsing serial data: {e}")
            return None