class SerialDataParser:
    """Parser for serial data.

    Supports two input formats:
      - Single-line pipe-separated: "s1 1023|s2 91|...|b1 0|b2 1"
      - Multi-line simple entries: "s1 296\ns1 308\ns2 341\n..."
    The parser returns the latest values seen for each slider/button:
      { 'sliders': {'p1': 0.289, ...}, 'buttons': {'b1': True, ...} }
    Slider values are normalized from 0-1023 -> 0.0-1.0.
    Button values are converted to booleans (1 -> True).
    """

    @staticmethod
    def parse_data(data_str):
        """Parse serial data string into slider/button dict"""
        try:
            if not data_str:
                return None

            if isinstance(data_str, bytes):
                data_str = data_str.decode('utf-8', errors='ignore')

            result = {'sliders': {}, 'buttons': {}}

            # Handle lines with pipe-separated values
            if '|' in data_str:
                # Process slider values
                parts = data_str.strip().split('|')
                for part in parts:
                    key, value = part.strip().split()
                    if key.startswith('s'):
                        try:
                            value = float(value) / 1023.0  # Normalize to 0-1
                            result['sliders'][key] = value
                        except ValueError:
                            continue
            # Handle single button values
            elif data_str.startswith('b'):
                key, value = data_str.strip().split()
                try:
                    result['buttons'][key] = (value == '1')
                except ValueError:
                    pass

            return result

        except Exception as e:
            log_error(e, f"Error parsing serial data: {e}")
            return None