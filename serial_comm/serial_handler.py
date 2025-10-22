import threading
import time
from utils.error_handler import log_error

try:
    import win32file
    import win32con
    import win32event
    import pywintypes

    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False


class SerialHandler:
    """Handle serial communication"""

    def __init__(self):
        self.serial_handle = None
        self.connected = False
        self.reading = False
        self.read_thread = None
        self.callbacks = []
        self.port = None

    def connect(self, port, baud_rate=9600):
        """Connect to serial port"""
        if not WINDOWS_AVAILABLE:
            log_error(Exception("pywin32 not available"), "Cannot connect without pywin32 or pyserial")
            return False

        try:
            # Format port name for Windows
            if not port.startswith('\\\\.\\'):
                port = f'\\\\.\\{port}'

            self.port = port

            # Open serial port using Windows API with overlapped I/O for non-blocking
            self.serial_handle = win32file.CreateFile(
                port,
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                0,  # exclusive access
                None,  # no security
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL | win32con.FILE_FLAG_OVERLAPPED,  # Enable overlapped I/O
                None
            )

            # Configure the serial port settings (DCB structure)
            # Get current DCB settings
            dcb = win32file.GetCommState(self.serial_handle)

            # Set baud rate and other parameters
            dcb.BaudRate = baud_rate
            dcb.ByteSize = 8
            dcb.Parity = 0  # No parity
            dcb.StopBits = 0  # 1 stop bit

            # Apply the settings
            win32file.SetCommState(self.serial_handle, dcb)

            # Set timeouts (in milliseconds)
            # Format: (ReadIntervalTimeout, ReadTotalTimeoutMultiplier, ReadTotalTimeoutConstant,
            #          WriteTotalTimeoutMultiplier, WriteTotalTimeoutConstant)
            timeouts = (50, 0, 1000, 0, 1000)  # 1 second read/write timeout
            win32file.SetCommTimeouts(self.serial_handle, timeouts)

            # Purge any existing data in buffers
            win32file.PurgeComm(self.serial_handle,
                                win32file.PURGE_RXCLEAR | win32file.PURGE_TXCLEAR)

            self.connected = True
            self.start_reading()
            return True

        except pywintypes.error as e:
            error_code = e.args[0]
            error_messages = {
                2: "The specified port does not exist",
                5: "Access denied - port may be in use by another application",
                121: "Device not responding or port already in use. Please check:\n"
                     "  - The device is properly connected\n"
                     "  - No other application is using this port\n"
                     "  - Try unplugging and replugging the device\n"
                     "  - Check Device Manager for driver issues",
            }

            detailed_message = error_messages.get(error_code, str(e))
            log_error(e, f"Failed to connect to {port}: {detailed_message}")
            self.connected = False
            return False

        except Exception as e:
            log_error(e, f"Failed to connect to {port}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from serial port"""
        try:
            self.reading = False
            if self.read_thread:
                self.read_thread.join(timeout=2)

            if self.serial_handle:
                win32file.CloseHandle(self.serial_handle)
                self.serial_handle = None

            self.connected = False
            return True

        except Exception as e:
            log_error(e, "Error disconnecting serial port")
            return False

    def is_connected(self):
        """Check if connected"""
        return self.connected and self.serial_handle is not None

    def start_reading(self):
        """Start reading from serial port"""
        if self.reading:
            return

        self.reading = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()

    def _read_loop(self):
        """Read data from serial port"""
        buffer = b""
        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)

        while self.reading and self.is_connected():
            try:
                # Try to read data with overlapped I/O
                hr, data = win32file.ReadFile(self.serial_handle, 1024, overlapped)

                # Wait for the read to complete or timeout
                if hr == 997:  # ERROR_IO_PENDING
                    bytes_read = win32file.GetOverlappedResult(self.serial_handle, overlapped, True)
                    if bytes_read > 0:
                        data = data[:bytes_read]

                if data:
                    buffer += data
                    # Process complete lines
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        line = line.decode('utf-8', errors='ignore').strip()
                        if line:
                            self._process_data(line)
                else:
                    time.sleep(0.01)

            except pywintypes.error as e:
                if e.args[0] == 995:  # Operation aborted (normal during disconnect)
                    break
                log_error(e, "Error reading from serial port")
                time.sleep(0.1)
            except Exception as e:
                log_error(e, "Error reading from serial port")
                time.sleep(0.1)

        win32file.CloseHandle(overlapped.hEvent)

    def _process_data(self, data):
        """Process received data"""
        try:
            # Clean up and validate data
            if not data:
                return
                
            clean_data = data.strip()
            
            # Handle button data immediately
            if clean_data.startswith('b'):
                parts = clean_data.split()
                if len(parts) == 2 and parts[1] in ('0', '1'):
                    # Notify callbacks immediately for button presses
                    for callback in self.callbacks:
                        callback(clean_data)
                return

            # Handle slider data (pipe-separated format)
            if '|' not in clean_data:
                return
                
            # Validate slider data format
            parts = clean_data.split('|')
            valid_data = True
            for part in parts:
                if not part.strip():
                    continue
                try:
                    key, value = part.strip().split()
                    if not key.startswith('s') or not value.isdigit():
                        valid_data = False
                        break
                except ValueError:
                    valid_data = False
                    break

            if valid_data:
                for callback in self.callbacks:
                    callback(clean_data)

        except Exception as e:
            log_error(e, "Error processing serial data")

    def add_callback(self, callback):
        """Add callback for received data"""
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def remove_callback(self, callback):
        """Remove callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def write(self, data):
        """Write data to serial port"""
        try:
            if self.is_connected():
                overlapped = pywintypes.OVERLAPPED()
                overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)

                hr, bytes_written = win32file.WriteFile(self.serial_handle, data.encode('utf-8'), overlapped)

                if hr == 997:  # ERROR_IO_PENDING
                    bytes_written = win32file.GetOverlappedResult(self.serial_handle, overlapped, True)

                win32file.CloseHandle(overlapped.hEvent)
                return True
        except Exception as e:
            log_error(e, "Error writing to serial port")

        return False