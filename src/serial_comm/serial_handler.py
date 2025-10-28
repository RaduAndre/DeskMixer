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
    """Handle serial communication with automatic connection and handshake"""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
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
        self.status_callbacks = []
        self.attempting_reconnect = False
        self.stop_reconnect = False
        self.handshake_timeout = 3  # seconds
        self.handshake_request = "DeskMixer controller request"
        self.handshake_response = "DeskMixer Controller Ready"
        self.handshake_received = False
        self.monitoring_active = False
        self.last_ports_check = 0
        self.ports_check_interval = 2  # seconds between port availability checks

    def auto_connect(self):
        """Automatically connect to device with handshake"""
        if not WINDOWS_AVAILABLE:
            log_error(Exception("pywin32 not available"), "Cannot connect without pywin32")
            self._notify_status("disconnected", "pywin32 not available")
            return False

        self._notify_status("connecting", "Searching for device...")

        # Try saved configuration first
        if self.config_manager:
            config = self.config_manager.load_config()
            saved_port = config.get('last_connected_port')
            saved_baud = config.get('last_connected_baud', '9600')

            if saved_port:
                print(f"Trying saved port: {saved_port} at {saved_baud} baud")
                if self._try_connect_with_handshake(saved_port, int(saved_baud)):
                    return True
                else:
                    print(f"Could not connect to saved port: {saved_port}")

        # Scan all available COM ports
        print("Scanning all COM ports for compatible device...")
        connection_result = self._scan_and_connect_all_ports()

        if connection_result:
            return True
        else:
            print("No compatible device found on any COM port")
            self._notify_status("disconnected", "Device not found - will connect automatically when available")
            self._start_continuous_monitoring()
            return False

    def _scan_and_connect_all_ports(self):
        """Scan all available ports and try to connect to each one"""
        if not serial_list_ports:
            return False

        available_ports = serial_list_ports.comports()
        port_count = len(available_ports)

        if port_count == 0:
            print("No COM ports available on system")
            return False

        print(f"Found {port_count} COM port(s), scanning for compatible device...")

        # Try previously connected port first if it exists and is available
        if self.port:
            previous_port = self.port.replace('\\\\.\\', '')
            current_port_names = [port.device for port in available_ports]
            if previous_port in current_port_names:
                print(f"Priority: Trying previously connected port: {previous_port}")
                if self._try_connect_with_handshake(previous_port, self.baud_rate):
                    return True
                else:
                    print(f"Previous port {previous_port} is not responding correctly")

        # Try all other ports
        for port_info in available_ports:
            port_name = port_info.device

            # Skip the previous port (we already tried it)
            if self.port and port_name == self.port.replace('\\\\.\\', ''):
                continue

            print(f"Trying port: {port_name}")
            if self._try_connect_with_handshake(port_name, self.baud_rate):
                return True

        print(f"No compatible device found on any of {port_count} available port(s)")
        return False

    def _try_connect_with_handshake(self, port, baud_rate):
        """Try to connect to a port and perform handshake"""
        try:
            # Attempt basic connection
            if not self._connect_port(port, baud_rate):
                return False

            # Wait a moment for device to be ready
            time.sleep(0.5)

            # Perform handshake
            if self._perform_handshake():
                print(f"✓ Connected successfully to {port}")
                self._notify_status("connected", f"Connected to {port}")

                # ✅ ADD THIS: Save successful connection to config
                if self.config_manager:
                    self.config_manager.set_last_connected_port(port, baud_rate)
                    self.config_manager.save_config()

                return True
            else:
                print(f"✗ Handshake failed on {port} - not a compatible device")
                self._disconnect_internal()
                return False

        except Exception as e:
            log_error(e, f"Error during connection attempt to {port}")
            self._disconnect_internal()
            return False

    def _connect_port(self, port, baud_rate):
        """Basic connection to serial port (internal method)"""
        try:
            # Format port name for Windows
            if not port.startswith('\\\\.\\'):
                port = f'\\\\.\\{port}'

            self.port = port
            self.baud_rate = baud_rate  # ✅ Ensure baud rate is set

            # Open serial port using Windows API with overlapped I/O
            self.serial_handle = win32file.CreateFile(
                port,
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                0,  # exclusive access
                None,  # no security
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL | win32con.FILE_FLAG_OVERLAPPED,
                None
            )

            # Configure the serial port settings (DCB structure)
            dcb = win32file.GetCommState(self.serial_handle)
            dcb.BaudRate = baud_rate
            dcb.ByteSize = 8
            dcb.Parity = 0  # No parity
            dcb.StopBits = 0  # 1 stop bit
            win32file.SetCommState(self.serial_handle, dcb)

            # Set timeouts (in milliseconds)
            timeouts = (50, 0, 1000, 0, 1000)
            win32file.SetCommTimeouts(self.serial_handle, timeouts)

            # Purge any existing data in buffers
            win32file.PurgeComm(self.serial_handle,
                                win32file.PURGE_RXCLEAR | win32file.PURGE_TXCLEAR)

            self.connected = True
            self.attempting_reconnect = False
            self.monitoring_active = False
            self.start_reading()
            return True

        except pywintypes.error as e:
            error_code = e.args[0]
            if error_code not in (2, 5, 121):  # Don't log common "port not available" errors during scanning
                log_error(e, f"Failed to open port {port}")
            self.connected = False
            return False

        except Exception as e:
            log_error(e, f"Failed to connect to {port}")
            self.connected = False
            return False

    def _perform_handshake(self):
        """Perform handshake with device - CRITICAL FOR SUCCESSFUL CONNECTION"""
        try:
            self.handshake_received = False

            # Wait for device to stabilize
            time.sleep(0.5)

            # Send handshake request
            if not self.write(self.handshake_request + "\n"):
                return False

            # Wait for response with timeout
            start_time = time.time()
            while time.time() - start_time < self.handshake_timeout:
                if self.handshake_received:
                    return True
                time.sleep(0.1)

            return False

        except Exception as e:
            log_error(e, "Error during handshake")
            return False

    def disconnect(self):
        """Disconnect from serial port (public method)"""
        try:
            # Stop reconnection attempts
            self.stop_reconnect = True
            self.attempting_reconnect = False
            self.monitoring_active = False

            # Stop reading thread
            self.reading = False
            if self.read_thread and self.read_thread != threading.current_thread():
                self.read_thread.join(timeout=2)

            # Stop reconnection thread
            if self.reconnect_thread and self.reconnect_thread.is_alive() and self.reconnect_thread != threading.current_thread():
                self.reconnect_thread.join(timeout=2)

            # Close serial handle
            if self.serial_handle:
                try:
                    win32file.CloseHandle(self.serial_handle)
                except:
                    pass
                self.serial_handle = None

            self.connected = False
            self._notify_status("disconnected", "Manually disconnected")
            return True

        except Exception as e:
            log_error(e, "Error disconnecting serial port")
            return False

    def _disconnect_internal(self):
        """Internal disconnect without joining threads (safe to call from any thread)"""
        try:
            # Stop reading
            self.reading = False

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
            log_error(e, "Error in internal disconnect")
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

                # Handle physical disconnection - including error 995
                if error_code in (5, 22, 995, 1167):
                    print("Device disconnected - starting automatic reconnection")
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
            self._notify_status("reconnecting", "Device disconnected - reconnecting...")
            for callback in self.disconnect_callbacks:
                try:
                    callback()
                except Exception as e:
                    log_error(e, "Error in disconnect callback")

            # Start reconnection attempts if not manually stopped
            if not self.stop_reconnect:
                self._start_continuous_monitoring()

        except Exception as e:
            log_error(e, "Error handling physical disconnect")

    def _start_continuous_monitoring(self):
        """Start continuous background monitoring for devices"""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.attempting_reconnect = True
        self.stop_reconnect = False

        print("Starting continuous background monitoring for devices...")
        self._notify_status("disconnected", "Monitoring for devices - connect your device to continue")

        self.reconnect_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.reconnect_thread.start()

    def _monitoring_loop(self):
        """Continuous monitoring loop that NEVER STOPS until connected or manually disabled"""
        last_port_count = 0
        consecutive_no_changes = 0

        print("Background monitor: Actively watching for device connection...")

        # This loop runs FOREVER until we're connected or manually stopped
        while self.monitoring_active and not self.stop_reconnect and not self.is_connected():
            try:
                current_ports = self._get_current_ports()
                current_port_count = len(current_ports)

                # Check if ports changed or it's time to scan anyway
                ports_changed = (current_port_count != last_port_count)
                time_for_scan = (time.time() - self.last_ports_check) >= self.ports_check_interval

                if ports_changed or time_for_scan:
                    self.last_ports_check = time.time()
                    last_port_count = current_port_count
                    consecutive_no_changes = 0

                    if current_ports:
                        print(f"Background monitor: Found {len(current_ports)} port(s) - scanning...")
                        if self._scan_and_connect_all_ports():
                            # Successfully connected - monitoring will stop naturally
                            print("✓ Connected to device - monitoring paused")
                            return
                    else:
                        if ports_changed:
                            print("Background monitor: No COM ports available")
                else:
                    consecutive_no_changes += 1

                # Dynamic sleep interval - longer when no changes, but NEVER stop monitoring
                sleep_interval = self._calculate_sleep_interval(consecutive_no_changes)
                time.sleep(sleep_interval)

            except Exception as e:
                log_error(e, "Error in monitoring loop")
                time.sleep(5)  # Wait longer on error but continue monitoring

        # Only get here if monitoring was manually stopped or we're connected
        if not self.is_connected() and not self.stop_reconnect:
            # This should never happen, but if monitoring stops unexpectedly, restart it
            print("Warning: Monitoring stopped unexpectedly, restarting...")
            time.sleep(2)
            self._start_continuous_monitoring()

    def _calculate_sleep_interval(self, consecutive_no_changes):
        """Calculate adaptive sleep interval - monitoring NEVER stops, just slows down"""
        if consecutive_no_changes < 5:
            return 2  # Fast polling for first 10 seconds
        elif consecutive_no_changes < 15:
            return 5  # Medium polling after 10-30 seconds
        elif consecutive_no_changes < 30:
            return 10  # Slow polling after 30-60 seconds
        else:
            return 15  # Very slow polling after 60+ seconds, but NEVER stop

    def _get_current_ports(self):
        """Get current list of available COM ports"""
        if not serial_list_ports:
            return []

        try:
            available_ports = serial_list_ports.comports()
            return [port_info.device for port_info in available_ports]
        except Exception as e:
            log_error(e, "Error getting port list")
            return []

    def _process_data(self, data):
        """Process received data - INCLUDES HANDSHAKE RESPONSE DETECTION"""
        try:
            # Clean up and validate data
            if not data:
                return

            clean_data = data.strip()

            # Check for handshake response - CRITICAL FOR CONNECTION SUCCESS
            if self.handshake_response in clean_data:
                self.handshake_received = True
                print(f"✓ Handshake confirmed: {clean_data}")
                return

            # Handle button data immediately
            if clean_data.startswith('b'):
                parts = clean_data.split()
                if len(parts) == 2 and parts[1] in ('0', '1'):
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

    def add_disconnect_callback(self, callback):
        """Add callback to be called when device disconnects"""
        if callback not in self.disconnect_callbacks:
            self.disconnect_callbacks.append(callback)

    def add_reconnect_callback(self, callback):
        """Add callback to be called when device reconnects"""
        if callback not in self.reconnect_callbacks:
            self.reconnect_callbacks.append(callback)

    def add_status_callback(self, callback):
        """Add callback to be called when connection status changes"""
        if callback not in self.status_callbacks:
            self.status_callbacks.append(callback)

    def _notify_status(self, status, message):
        """Notify all status callbacks of a status change"""
        for callback in self.status_callbacks:
            try:
                callback(status, message)
            except Exception as e:
                log_error(e, "Error in status callback")

    def write(self, data):
        """Write data to serial port"""
        try:
            if self.is_connected():
                overlapped = pywintypes.OVERLAPPED()
                overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)

                # Ensure data ends with newline if not present
                if not data.endswith('\n'):
                    data += '\n'

                hr, bytes_written = win32file.WriteFile(self.serial_handle, data.encode('utf-8'), overlapped)

                if hr == 997:  # ERROR_IO_PENDING
                    bytes_written = win32file.GetOverlappedResult(self.serial_handle, overlapped, True)

                win32file.CloseHandle(overlapped.hEvent)
                return True
        except Exception as e:
            log_error(e, "Error writing to serial port")

        return False