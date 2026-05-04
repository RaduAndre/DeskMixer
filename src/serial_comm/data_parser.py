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
    value: float  # Normalized 0.0 - 1.0  (board sends 0-1024, divided by 1024.0)

@dataclass
class SerialDataEvent:
    sliders: Dict[str, float]
    buttons: Dict[str, bool]

# ── Wire-protocol scale constant ─────────────────────────────────────────────
# The STM32 firmware maps its 12-bit ADC (0-4095) to 0-1024 via a right-shift
# (raw >> 2).  We divide by this to obtain a normalized float [0.0 .. 1.0].
# Matches SLIDER_MAX_VAL defined in sliders.h on the firmware side.
_SLIDER_SCALE = 1024.0

# Anything below 0.5% of full scale is snapped to 0.0 (physical zero-stop).
_ZERO_SNAP_THRESHOLD = 0.005

class SerialDataParser:
    """Parser for serial data returning structured events.

    The firmware transmits slider values in the range 0-1024 (= raw ADC >> 2).
    This parser divides by 1024.0 to produce a normalized float [0.0 .. 1.0]
    ready for the Windows audio API.

    Examples
    --------
    ``"Slider 1 768|Slider 2 512"``  →  s1=0.75, s2=0.50
    ``"Button 2 1"``                  →  b2=True
    """

    @staticmethod
    def parse_data(data_str: str) -> Optional[SerialDataEvent]:
        """
        Parse a serial data string into structured slider/button events.

        Handles:
          - Pipe-separated slider lines: ``"Slider 1 VAL|Slider 2 VAL|..."``
          - Single slider:              ``"Slider X VAL"``
          - Single button:              ``"Button X 1"``
          - Legacy short format:        ``"sX VAL"`` / ``"bX 1"``
        """
        try:
            if not data_str:
                return None

            if isinstance(data_str, bytes):
                data_str = data_str.decode('utf-8', errors='ignore')

            data_str = data_str.strip()
            sliders: Dict[str, float] = {}
            buttons: Dict[str, bool]  = {}

            # ── Pipe-separated line (primary firmware format) ─────────────
            if '|' in data_str:
                parts = data_str.split('|')
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    try:
                        sub = part.split()
                        if len(sub) == 3 and sub[0] == 'Slider':
                            _, slider_num, value = sub
                            key = f"s{slider_num}"
                            norm = float(value) / _SLIDER_SCALE
                            sliders[key] = 0.0 if norm < _ZERO_SNAP_THRESHOLD else norm
                        elif len(sub) == 2 and sub[0].startswith('s'):
                            # Legacy short format inside a pipe-separated packet
                            key, value = sub
                            if key[1:].isdigit():
                                norm = float(value) / _SLIDER_SCALE
                                sliders[key] = 0.0 if norm < _ZERO_SNAP_THRESHOLD else norm
                    except ValueError:
                        continue

            # ── Single "Slider X VAL" line ─────────────────────────────────
            elif data_str.startswith('Slider '):
                try:
                    parts = data_str.split()
                    if len(parts) == 3:
                        _, slider_num, value = parts
                        key = f"s{slider_num}"
                        norm = float(value) / _SLIDER_SCALE
                        sliders[key] = 0.0 if norm < _ZERO_SNAP_THRESHOLD else norm
                except ValueError:
                    pass

            # ── "Button X Y" line ──────────────────────────────────────────
            elif data_str.startswith('Button '):
                try:
                    parts = data_str.split()
                    if len(parts) == 3:
                        _, button_num, state = parts
                        buttons[f"b{button_num}"] = (state == '1')
                except ValueError:
                    pass

            # ── Legacy short formats ───────────────────────────────────────
            elif data_str.startswith('b'):
                try:
                    parts = data_str.split()
                    if len(parts) == 2:
                        key, value = parts
                        buttons[key] = (value == '1')
                except ValueError:
                    pass

            elif data_str.startswith('s'):
                try:
                    parts = data_str.split()
                    if len(parts) == 2:
                        key, value = parts
                        if key[1:].isdigit():
                            norm = float(value) / _SLIDER_SCALE
                            sliders[key] = 0.0 if norm < _ZERO_SNAP_THRESHOLD else norm
                except ValueError:
                    pass

            if not sliders and not buttons:
                return None

            return SerialDataEvent(sliders=sliders, buttons=buttons)

        except Exception as e:
            log_error(e, f"Error parsing serial data: {e}")
            return None