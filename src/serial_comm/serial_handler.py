import threading
import time
from utils.error_handler import log_error

try:
    import win32file
    import win32con
    import win32event
    import pywintypes
    import serial.tools.list_ports as serial_list_ports

    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False
    serial_list_ports = None


class SerialHandler:
    """Handle serial communication"""

    def __init__(self):
        self.serial_handle = None
        self.connected = False
        self.reading = False
        self.read_thread = None
        self.reconnect_thread = None
        self.callbacks = []
        self.port = None
        self.baud_rate = 9600
        self.disconnect_callbacks = []
        self.reconnect_callbacks = []
        self.attempting_reconnect = False
        self.stop_reconnect = False

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
            self.baud_rate = baud_rate

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
            self.attempting_reconnect = False
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
            # Stop reconnection attempts
            self.stop_reconnect = True
            self.attempting_reconnect = False

            # Stop reading thread
            self.reading = False
            if self.read_thread:
                self.read_thread.join(timeout=2)

            # Stop reconnection thread
            if self.reconnect_thread and self.reconnect_thread.is_alive():
                self.reconnect_thread.join(timeout=2)

            # Close serial handle
            if self.serial_handle:
                try:
                    win32file.CloseHandle(self.serial_handle)
                except:
                    pass
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
                error_code = e.args[0]

                # Handle physical disconnection
                if error_code in (5, 22, 995,
                                  1167):  # Access denied, invalid function, operation aborted, device not connected
                    log_error(e, f"Device physically disconnected (error {error_code})")
                    self._handle_physical_disconnect()
                    break

                log_error(e, f"Error reading from serial port (error {error_code})")
                time.sleep(0.1)

            except Exception as e:
                log_error(e, "Error reading from serial port")
                time.sleep(0.1)

        try:
            win32file.CloseHandle(overlapped.hEvent)
        except:
            pass

    def _handle_physical_disconnect(self):
        """Handle physical device disconnection"""
        try:
            # Mark as disconnected
            self.connected = False
            self.reading = False

            # Clean up handle
            if self.serial_handle:
                try:
                    win32file.CloseHandle(self.serial_handle)
                except:
                    pass
                self.serial_handle = None

            # Notify disconnect callbacks (update UI)
            for callback in self.disconnect_callbacks:
                try:
                    callback()
                except Exception as e:
                    log_error(e, "Error in disconnect callback")

            # Start reconnection attempts if not manually stopped
            if not self.stop_reconnect and self.port and self.baud_rate:
                self._start_reconnection()

        except Exception as e:
            log_error(e, "Error handling physical disconnect")

    def _start_reconnection(self):
        """Start automatic reconnection attempts"""
        if self.attempting_reconnect:
            return

        self.attempting_reconnect = True
        self.stop_reconnect = False
        self.reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self.reconnect_thread.start()

    def _reconnect_loop(self):
        """Attempt to reconnect to the device"""
        reconnect_interval = 2  # seconds between attempts
        max_attempts = 30  # try for 1 minute
        attempt = 0

        log_error(Exception("Starting auto-reconnection"), f"Attempting to reconnect to {self.port}")

        while self.attempting_reconnect and not self.stop_reconnect and attempt < max_attempts:
            attempt += 1

            try:
                # Check if the port is available again
                if serial_list_ports:
                    available_ports = [p.device for p in serial_list_ports.comports()]
                    port_name = self.port.replace('\\\\.\\', '')

                    if port_name in available_ports:
                        log_error(Exception("Port detected"),
                                  f"Port {port_name} is available, attempting reconnection...")

                        # Try to reconnect
                        if self.connect(port_name, self.baud_rate):
                            log_error(Exception("Reconnection successful"), f"Successfully reconnected to {port_name}")

                            # Notify reconnect callbacks (update UI)
                            for callback in self.reconnect_callbacks:
                                try:
                                    callback()
                                except Exception as e:
                                    log_error(e, "Error in reconnect callback")

                            self.attempting_reconnect = False
                            return
                        else:
                            log_error(Exception("Reconnection failed"),
                                      f"Failed to reconnect (attempt {attempt}/{max_attempts})")

            except Exception as e:
                log_error(e, f"Error during reconnection attempt {attempt}")

            # Wait before next attempt
            time.sleep(reconnect_interval)

        self.attempting_reconnect = False
        if attempt >= max_attempts:
            log_error(Exception("Reconnection abandoned"), f"Failed to reconnect after {max_attempts} attempts")

    def add_disconnect_callback(self, callback):
        """Add callback to be called when device disconnects"""
        if callback not in self.disconnect_callbacks:
            self.disconnect_callbacks.append(callback)

    def add_reconnect_callback(self, callback):
        """Add callback to be called when device reconnects"""
        if callback not in self.reconnect_callbacks:
            self.reconnect_callbacks.append(callback)

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