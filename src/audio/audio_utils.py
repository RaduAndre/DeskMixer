from collections import defaultdict, deque
from utils.error_handler import log_error

class SliderSmoother:
    """Handles smoothing/averaging of slider values"""
    
    def __init__(self):
        self.slider_history = defaultdict(lambda: deque(maxlen=5))
        self.history_sizes = {'soft': 5, 'normal': 10, 'hard': 20}

    def apply_averaging(self, slider_id, value, mode='normal'):
        """Apply averaging to slider input based on mode"""
        try:
            # Update history size based on current mode
            history_size = self.history_sizes.get(mode, 5)
            
            # Resize the deque if needed
            if self.slider_history[slider_id].maxlen != history_size:
                old_history = list(self.slider_history[slider_id])
                self.slider_history[slider_id] = deque(old_history[-history_size:], maxlen=history_size)
            
            # Add current value to history
            self.slider_history[slider_id].append(value)

            # Calculate average of historical values
            if len(self.slider_history[slider_id]) > 0:
                average_value = sum(self.slider_history[slider_id]) / len(self.slider_history[slider_id])
                return average_value
            else:
                return value

        except Exception as e:
            log_error(e, f"Error applying slider averaging for {slider_id} in mode {mode}")
            return value

    def clear_history(self):
        self.slider_history.clear()
