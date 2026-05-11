import json
import os
import shutil
import threading
import time
from datetime import datetime
from typing import Optional

from utils.error_handler import log_error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_app_data_folder():
    """Get the application data folder in user's Documents"""
    documents_path = os.path.join(os.path.expanduser('~'), 'Documents')
    app_folder = os.path.join(documents_path, 'DeskMixer')
    os.makedirs(app_folder, exist_ok=True)
    return app_folder


def _read_json_with_retry(path: str, retries: int = 5, delay: float = 0.15) -> dict:
    """
    Read and parse a JSON file, retrying on PermissionError / OSError so that
    transient locks (antivirus scan, Windows Defender, another process) do not
    cause permanent failures.

    Raises the last exception if every attempt fails.
    """
    last_exc = None
    for attempt in range(retries):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (PermissionError, OSError) as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))   # back-off: 0.15s, 0.30s, 0.45s …
        except json.JSONDecodeError:
            raise   # corrupt JSON – caller decides what to do
    raise last_exc


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class ConfigManager:
    """
    Manage configuration settings.
    Singleton pattern to ensure global access to the same state.

    Thread-safety guarantees
    ------------------------
    * A single ``threading.RLock`` (``_lock``) serialises every public method
      that touches ``self.config`` or the file-system.
    * ``save_config`` and ``save_config_if_changed`` are safe to call from any
      thread; they acquire the lock internally.
    * A *debounced / coalesced* save mechanism is built in:
      ``_schedule_save()`` arms a one-shot timer (default 300 ms).  Rapid back-
      to-back mutations share the same timer, so only one disk write happens
      after the burst settles.  Call ``save_config()`` directly whenever you
      need an immediate, synchronous flush.

    Corruption resistance
    ---------------------
    * Saves go through an atomic write-then-rename sequence using a ``.tmp``
      sibling file.  The final ``os.replace`` is the sole moment the live file
      is touched, so a crash mid-write leaves the old file intact.
    * The ``.tmp`` file is removed in a ``finally`` block whether or not the
      write succeeded.
    * ``load_config`` retries on ``PermissionError`` / ``OSError`` (back-off
      up to *retries × delay* seconds) before treating the file as corrupted.
    """

    _instance = None
    _initialized = False

    # Debounce window in seconds.  A pending save is coalesced into a single
    # disk write after this many seconds of inactivity.
    SAVE_DEBOUNCE_S: float = 0.30

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_file: str = "config.json"):
        if self._initialized:
            return

        self.config_file = config_file

        # Use Documents/DeskMixer folder for configuration
        self.config_dir = get_app_data_folder()
        self.config_path = os.path.join(self.config_dir, self.config_file)

        self.config: dict = {}
        self.has_changes: bool = False
        self.load_failed: bool = False

        # Thread-safety: a reentrant lock so methods can call each other safely
        self._lock = threading.RLock()

        # Debounced-save state
        self._save_timer: Optional[threading.Timer] = None

        # Ensure the config directory exists
        os.makedirs(self.config_dir, exist_ok=True)

        # Load configuration on initialization
        self.load_config()
        self._initialized = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _schedule_save(self):
        """
        Arm (or re-arm) the debounce timer.  Must be called while ``_lock``
        is already held.
        """
        if self._save_timer is not None:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(self.SAVE_DEBOUNCE_S, self._debounced_save)
        self._save_timer.daemon = True
        self._save_timer.start()

    def _debounced_save(self):
        """Callback fired by the debounce timer – runs on a background thread."""
        with self._lock:
            self._save_timer = None
            if self.has_changes:
                self._write_to_disk()

    def _write_to_disk(self) -> bool:
        """
        Perform the actual atomic write.  Must be called while ``_lock`` is
        already held.

        Returns True on success, False on failure.
        """
        temp_path = self.config_path + ".tmp"
        try:
            os.makedirs(self.config_dir, exist_ok=True)

            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, sort_keys=True)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    # fsync can fail on some file-systems (e.g. FAT32 over USB);
                    # a successful flush() is sufficient for our purposes.
                    pass

            # Atomic replacement – os.replace is guaranteed atomic on POSIX;
            # on Windows it is best-effort but far safer than delete+rename.
            os.replace(temp_path, self.config_path)
            self.has_changes = False
            return True

        except Exception as e:
            log_error(e, f"Error saving configuration to {self.config_path}")
            return False
        finally:
            # Always clean up the temp file so stale .tmp files cannot
            # accumulate and confuse future saves or reads.
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_config(self) -> dict:
        """
        Load configuration from disk.

        On ``PermissionError`` / ``OSError`` the read is retried with
        exponential back-off before the file is treated as corrupted.
        On ``json.JSONDecodeError`` (or after all retries are exhausted) a
        timestamped backup of the bad file is created and an empty config is
        returned so the application can continue.
        """
        with self._lock:
            self.load_failed = False
            if not os.path.exists(self.config_path):
                self.config = {}
                return self.config

            try:
                self.config = _read_json_with_retry(self.config_path)
            except Exception as e:
                log_error(e, f"Error loading configuration from {self.config_path}")
                self.load_failed = True
                self.config = {}

                # Back up the bad / locked file so the user can inspect it
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = f"{self.config_path}.corrupted_{timestamp}.bak"
                    shutil.copy2(self.config_path, backup_path)
                    print(f"[ConfigManager] Backed up problematic config to: {backup_path}")
                except Exception as backup_error:
                    log_error(backup_error, "Failed to backup problematic config file")

            return self.config

    def save_config(self, config=None) -> bool:
        """
        Synchronously flush the current config to disk right now.

        If *config* is supplied (a dict), it is merged into ``self.config``
        before writing.  This preserves the old calling convention used by
        ``button_section_handler`` which passes back the whole config dict
        it loaded earlier.

        Cancels any pending debounced save and writes immediately.
        Safe to call from any thread.
        """
        with self._lock:
            if config is not None and isinstance(config, dict):
                self.config.update(config)
                self.has_changes = True
            # Cancel any pending debounced save – we're doing it now
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None
            return self._write_to_disk()

    def save_config_if_changed(self) -> bool:
        """Save configuration only if there are pending changes."""
        with self._lock:
            if self.has_changes:
                return self.save_config()
            return False

    # ------------------------------------------------------------------
    # Bindings
    # ------------------------------------------------------------------

    def add_binding(self, var_name: str, app_names) -> bool:
        """Add or update a variable binding (supports single app or list of apps)"""
        try:
            if not var_name or not var_name.startswith('s'):
                return False

            with self._lock:
                if 'variable_bindings' not in self.config:
                    self.config['variable_bindings'] = {}

                # Normalise input to list
                if isinstance(app_names, str):
                    app_names = [app_names] if app_names else []
                elif not isinstance(app_names, list):
                    app_names = []

                # Resolve None / empty sentinel
                is_none = (
                    not app_names
                    or (len(app_names) == 1 and app_names[0] in (None, "None"))
                )

                if is_none:
                    app_names = [{"value": None, "argument": None}]
                else:
                    app_names = [app for app in app_names if app and app != "None"]
                    if not app_names:
                        app_names = [{"value": None, "argument": None}]

                current = self.config['variable_bindings'].get(var_name)

                # Normalise current for comparison
                if isinstance(current, dict):
                    current_apps = current.get('app_name', [])
                    if isinstance(current_apps, str):
                        current_apps = [current_apps]
                elif isinstance(current, list):
                    current_apps = current
                elif isinstance(current, str):
                    current_apps = [current]
                else:
                    current_apps = []

                # Compare (sets for strings/numbers, equality for dicts)
                changed = False
                try:
                    changed = set(current_apps) != set(app_names)
                except TypeError:
                    changed = current_apps != app_names

                if changed:
                    self.config['variable_bindings'][var_name] = app_names
                    self.has_changes = True
                    self._schedule_save()
                    return True

                return False

        except Exception as e:
            log_error(e, f"Error adding binding for {var_name}")
            return False

    def save_variable_binding(self, var_name: str, app_names) -> bool:
        """
        Alias for ``add_binding`` kept for backward compatibility.

        Called from ``BindingsSectionHandler.save_variable_binding`` and
        several UI legacy sections.
        """
        return self.add_binding(var_name, app_names)

    def remove_binding(self, var_name: str) -> bool:
        """Remove a variable binding"""
        try:
            with self._lock:
                if 'variable_bindings' in self.config and var_name in self.config['variable_bindings']:
                    del self.config['variable_bindings'][var_name]
                    self.has_changes = True
                    self._schedule_save()
                    return True
                return False
        except Exception as e:
            log_error(e, f"Error removing binding for {var_name}")
            return False

    def load_variable_binding(self, var_name: str):
        """Load a specific variable binding"""
        try:
            with self._lock:
                bindings = self.config.get('variable_bindings', {})
                binding = bindings.get(var_name)

                if binding:
                    if isinstance(binding, dict):
                        app_names = binding.get('app_name', [])
                        return [app_names] if isinstance(app_names, str) else app_names
                    elif isinstance(binding, list):
                        return binding
                    else:
                        return [binding] if binding else []
                return None

        except Exception as e:
            log_error(e, "Error loading variable binding")
            return None

    # ------------------------------------------------------------------
    # Button bindings
    # ------------------------------------------------------------------

    def add_button_binding(self, button_name: str, binding_data) -> bool:
        """Add or update a button binding"""
        try:
            if not button_name or not button_name.startswith('b'):
                return False

            with self._lock:
                if 'button_bindings' not in self.config:
                    self.config['button_bindings'] = {}

                if self.config['button_bindings'].get(button_name) != binding_data:
                    self.config['button_bindings'][button_name] = binding_data
                    self.has_changes = True
                    self._schedule_save()
                    return True

                return False

        except Exception as e:
            log_error(e, f"Error adding button binding for {button_name}")
            return False

    def remove_button_binding(self, button_name: str) -> bool:
        """Remove a button binding"""
        try:
            with self._lock:
                if 'button_bindings' in self.config and button_name in self.config['button_bindings']:
                    del self.config['button_bindings'][button_name]
                    self.has_changes = True
                    self._schedule_save()
                    return True
                return False
        except Exception as e:
            log_error(e, f"Error removing button binding for {button_name}")
            return False

    # ------------------------------------------------------------------
    # Misc setters / getters
    # ------------------------------------------------------------------

    def set_last_connected_port(self, port: str):
        """Set the last connected serial port (baud rate is fixed at 115200)"""
        with self._lock:
            if self.config.get('last_connected_port') != port:
                self.config['last_connected_port'] = port
                self.has_changes = True
                self._schedule_save()

    def set_slider_sampling(self, mode: str) -> bool:
        """Set the global volume control mode for all bindings"""
        valid_modes = {'instant', 'responsive', 'soft', 'normal', 'hard'}
        mode = (mode.lower() if mode else 'normal')
        if mode not in valid_modes:
            mode = 'normal'

        with self._lock:
            if self.config.get('slider_sampling') != mode:
                self.config['slider_sampling'] = mode
                self.has_changes = True
                self._schedule_save()
                return True
            return False

    def get_slider_sampling(self, default: str = 'normal') -> str:
        """Get the global volume control mode"""
        with self._lock:
            return self.config.get('slider_sampling', default)

    def get_app_list(self) -> list:
        """Get the list of user's preferred apps"""
        with self._lock:
            return self.config.get('app_list', [])

    def add_to_app_list(self, app_name: str) -> bool:
        """Add an app to the user's preferred app list"""
        try:
            if not app_name or app_name in ("None", "⌀ None"):
                return False

            with self._lock:
                if 'app_list' not in self.config:
                    self.config['app_list'] = []

                if app_name not in self.config['app_list']:
                    self.config['app_list'].append(app_name)
                    self.has_changes = True
                    self._schedule_save()
                    return True

                return False
        except Exception as e:
            log_error(e, f"Error adding {app_name} to app list")
            return False

    def remove_from_app_list(self, app_name: str) -> bool:
        """Remove an app from the user's preferred app list"""
        try:
            with self._lock:
                if 'app_list' in self.config and app_name in self.config['app_list']:
                    self.config['app_list'].remove(app_name)
                    self.has_changes = True
                    self._schedule_save()
                    return True
                return False
        except Exception as e:
            log_error(e, f"Error removing {app_name} from app list")
            return False

    def set_start_in_tray(self, value: bool):
        """Set the value for the start_in_tray config key."""
        with self._lock:
            new_value = bool(value)
            if self.config.get('start_in_tray') != new_value:
                self.config['start_in_tray'] = new_value
                self.has_changes = True
                self._schedule_save()

    def get_start_in_tray(self, default: bool = False) -> bool:
        """Get the value for the start_in_tray config key."""
        with self._lock:
            return self.config.get('start_in_tray', default)

    def set_screen_active(self, value) -> bool:
        """Set the screen_active state (0 or 1)."""
        with self._lock:
            new_value = int(value) if value in (0, 1) else 0
            if self.config.get('screen_active') != new_value:
                self.config['screen_active'] = new_value
                self.has_changes = True
                self._schedule_save()
                return True
            return False

    def get_screen_active(self, default: int = 0) -> int:
        """Get the screen_active state."""
        with self._lock:
            return self.config.get('screen_active', default)

    def get_config_value(self, key: str, default=None):
        """Get a configuration value"""
        with self._lock:
            return self.config.get(key, default)