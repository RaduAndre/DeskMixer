"""
board_comm.py
─────────────
High-level communication layer between the DeskMixer Python host and the
STM32 board.

Responsibilities:
  • On connect  → send CONNECTED, request GET_PARAMS, compare with local
                  config, push SET_PARAMS if needed.
  • On disconnect → send DISCONNECTED before the serial port closes.
  • send_image()  → encode a PIL/numpy image (or raw bytes) as a hex
                    framebuffer and transmit IMG:<2048 hex>.
  • Responds to incoming PARAMS / PARAMS_NONE lines from the board.

Command Queue & ACK:
  All commands that the board acknowledges (SET_PARAMS, CONNECTED,
  DISCONNECTED, IMG) are routed through a FIFO queue.  A background
  worker sends one command at a time and waits up to ACK_TIMEOUT seconds
  for the board to reply "ACK".  If no ACK is received the command is
  retried up to MAX_RETRIES times, then dropped with a warning.

  Commands sent directly (handshake helper path):
    • COMM_Send callers such as GET_PARAMS / GET_CONFIG – these have their
      own dedicated reply frames and are NOT ACK'd by the board.

Usage (from SerialController or wherever the serial_handler is wired):

    board_comm = BoardComm(serial_handler, config_manager)
    serial_handler.add_reconnect_callback(board_comm.on_connected)
    serial_handler.add_disconnect_callback(board_comm.on_disconnected)
    # Parser should call board_comm.handle_board_line() for every line
    # that starts with "PARAMS".
"""

import queue
import threading
import time
from utils.error_handler import log_error

# Number of sliders / buttons must match firmware NUM_SLIDERS / NUM_BUTTONS
NUM_SLIDERS = 5
NUM_BUTTONS = 6
FLASH_NAME_LEN = 15   # max chars per name (firmware uses 16 incl. \0)

# OLED dimensions (must match firmware DISPLAY_WIDTH / DISPLAY_PAGES)
OLED_WIDTH  = 128
OLED_PAGES  = 8        # 8 pages × 8 pixels = 64 px tall
OLED_FB_LEN = OLED_WIDTH * OLED_PAGES   # 1024 bytes

# ── Queue / ACK tuning ────────────────────────────────────────────────────────
ACK_TIMEOUT  = 2.0   # seconds to wait for "ACK" from board
MAX_RETRIES  = 3     # how many times to retry before giving up
QUEUE_MAXLEN = 64    # maximum pending commands before new ones are dropped


class _Cmd:
    """Internal command envelope for the queue."""
    __slots__ = ("text", "retries_left", "enqueued_at")

    def __init__(self, text: str):
        self.text          = text
        self.retries_left  = MAX_RETRIES
        self.enqueued_at   = time.monotonic()


class BoardComm:
    """
    Manages board-level communication above the raw serial protocol.

    Parameters
    ----------
    serial_handler : SerialHandler
        The underlying serial handler (must support .write(str)).
    config_manager : ConfigManager | None
        Used to read slider/button name config from the host config file.
    """

    def __init__(self, serial_handler, config_manager=None):
        self.serial_handler  = serial_handler
        self.config_manager  = config_manager
        self._lock           = threading.Lock()
        self._flow_lock      = threading.Lock()  # prevents concurrent connected flows

        # Params received from the board
        self._board_params   = None
        self._params_event   = threading.Event()
        # Cache of the last params we confirmed the board holds.
        # Used by sync_params_if_changed to send only changed fields.
        self._last_sent_params = None

        # ── Command queue ──────────────────────────────────────────────
        self._cmd_queue: "queue.Queue[_Cmd]" = queue.Queue(maxsize=QUEUE_MAXLEN)
        self._ack_event  = threading.Event()
        self._worker     = threading.Thread(
            target=self._queue_worker, daemon=True, name="BoardComm-CmdQueue")
        self._worker.start()

    # ─────────────────────────────────────────────────────────────────
    # Connection lifecycle
    # ─────────────────────────────────────────────────────────────────

    def on_connected(self):
        """
        Call this when the board has been successfully connected.
        Uses a lock so only one flow runs at a time even if the callback
        fires multiple times in quick succession.
        """
        if not self._flow_lock.acquire(blocking=False):
            print("BoardComm: on_connected already running, skipping duplicate")
            return
        t = threading.Thread(target=self._connected_flow, daemon=True)
        t.start()

    def on_disconnected(self):
        """
        Call this just before the serial connection is closed.
        Sends DISCONNECTED only when the port is still physically open
        (clean/manual disconnect).  On a physical USB pull, the handle is
        already closed so queuing DISCONNECTED would just cause 3 failing
        retries that — if reconnection is fast — end up being sent to the
        newly connected board, corrupting its GET_CONFIG sequence.
        """
        with self._lock:
            self._board_params = None
        try:
            if self.serial_handler and self.serial_handler.is_connected():
                self._enqueue("DISCONNECTED")
        except Exception as e:
            log_error(e, "BoardComm: error queuing DISCONNECTED")
        finally:
            try:
                self._flow_lock.release()
            except RuntimeError:
                pass

    def _connected_flow(self):
        """Background flow executed once the board is connected."""
        try:
            time.sleep(0.3)
            self._enqueue("CONNECTED")

            # Wait until CONNECTED has been sent AND ACK'd before issuing
            # GET_PARAMS.  Use a timed loop instead of join() so that a board
            # that never ACKs (e.g. a USB hiccup right after connect) doesn't
            # block this thread – and the flow_lock – forever.
            deadline = time.monotonic() + (ACK_TIMEOUT * MAX_RETRIES) + 1.0
            while time.monotonic() < deadline:
                if self._cmd_queue.unfinished_tasks == 0:
                    break
                time.sleep(0.05)

            time.sleep(0.05)  # brief guard for board to finish processing ACK

            board_params = self._fetch_board_params(timeout=3.0)
            host_params  = self._get_host_params()
            if host_params is None:
                print("BoardComm: no local config – skipping param sync")
                return

            if board_params is None or self._params_differ(board_params, host_params):
                print("BoardComm: syncing params to board")
                self._send_set_params(host_params)
            else:
                print("BoardComm: board params match host config – no sync needed")

            # Cache the host state so future incremental syncs can diff against it.
            with self._lock:
                self._last_sent_params = host_params

        except Exception as e:
            log_error(e, "BoardComm: error in connected flow")
        finally:
            # Always release the lock when the flow finishes so the next
            # genuine reconnect can run its flow
            try:
                self._flow_lock.release()
            except RuntimeError:
                pass

    # ─────────────────────────────────────────────────────────────────
    # Incoming line handler (call from SerialController / data path)
    # ─────────────────────────────────────────────────────────────────

    def handle_board_line(self, line: str) -> bool:
        """
        Inspect a raw line received from the board.

        Returns True if the line was consumed here (caller should not
        forward it to the slider/button parser).
        """
        if line == "ACK":
            # Signal the queue worker that the last command was received
            self._ack_event.set()
            return True
            
        if line == "PING":
            return True

        if line.startswith("PARAMS_LIST:"):
            self._parse_params_list(line)
            return True

        if line.startswith("PARAMS:"):
            self._parse_params_line(line)
            return True

        if line == "PARAMS_NONE":
            with self._lock:
                self._board_params = None
            self._params_event.set()
            print("BoardComm: board has no stored params")
            return True

        return False

    # ─────────────────────────────────────────────────────────────────
    # Image transmission
    # ─────────────────────────────────────────────────────────────────

    def send_image(self, image_source):
        """
        Send an image to the OLED display.

        ``image_source`` can be:
          • ``bytes`` / ``bytearray`` of exactly 1024 bytes (raw SSD1306
            page-organised framebuffer, 8 pages × 128 columns).
          • A PIL ``Image`` object – it will be converted to 1-bit, resized
            to 128×64, and packed into the correct page format.

        The image is sent as: ``IMG:<2048 uppercase hex chars>\\n``
        """
        try:
            fb = self._to_framebuffer(image_source)
            if fb is None:
                print("BoardComm.send_image: could not convert image to framebuffer")
                return False

            hex_str = fb.hex().upper()          # 2048 chars
            self._enqueue(f"IMG:{hex_str}")
            return True

        except Exception as e:
            log_error(e, "BoardComm.send_image error")
            return False

    # ─────────────────────────────────────────────────────────────────
    # Command queue helpers
    # ─────────────────────────────────────────────────────────────────

    def _enqueue(self, text: str):
        """
        Push a command into the outgoing queue (thread-safe).
        Drops the command and logs a warning if the queue is full.
        """
        try:
            self._cmd_queue.put_nowait(_Cmd(text))
        except queue.Full:
            print(f"BoardComm: command queue full – dropping: {text[:40]}")

    def _queue_worker(self):
        """
        Background thread: dequeue one command at a time, send it, and
        wait for an ACK.  Retries up to MAX_RETRIES times on timeout.
        """
        while True:
            cmd: _Cmd = self._cmd_queue.get()   # blocks until a command arrives

            sent_ok = False

            for attempt in range(MAX_RETRIES):
                if not self._direct_write(cmd.text):
                    # Serial not connected – back off briefly and retry
                    print(f"BoardComm: not connected, backing off cmd: {cmd.text[:40]}")
                    time.sleep(0.1)   # reduced from 0.5 s – queue drains faster
                    continue

                self._ack_event.clear()
                got_ack = self._ack_event.wait(timeout=ACK_TIMEOUT)

                if got_ack:
                    sent_ok = True
                    break
                else:
                    remaining = MAX_RETRIES - attempt - 1
                    if remaining > 0:
                        print(
                            f"BoardComm: no ACK for '{cmd.text[:40]}' "
                            f"(attempt {attempt + 1}/{MAX_RETRIES}), retrying…"
                        )
                    # Drain any late ACK so it cannot bleed into the next
                    # attempt's wait and incorrectly satisfy it.
                    time.sleep(0.05)
                    self._ack_event.clear()

            if not sent_ok:
                print(
                    f"BoardComm: command DROPPED after {MAX_RETRIES} retries: "
                    f"{cmd.text[:60]}"
                )

            self._cmd_queue.task_done()

    # ─────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────

    def _direct_write(self, text: str) -> bool:
        """
        Send a line to the board immediately (no queue, no ACK wait).
        Returns True if the bytes were passed to the serial layer.
        """
        if self.serial_handler and self.serial_handler.is_connected():
            if not text.endswith('\n'):
                text += '\n'
            return self.serial_handler.write(text)
        return False

    # Keep a thin _write() alias so the fetch-params path (which bypasses
    # the queue intentionally) still works.
    def _write(self, text: str):
        """Send a line directly (used for GET_PARAMS which has its own reply)."""
        self._direct_write(text)

    def _fetch_board_params(self, timeout: float = 3.0) -> dict | None:
        """
        Send GET_PARAMS and wait for the board to reply.
        Returns parsed params dict or None on timeout / PARAMS_NONE.

        Note: GET_PARAMS is NOT ACK'd – the board replies with PARAMS: or
        PARAMS_NONE, so we bypass the ACK queue here.
        """
        with self._lock:
            if self._board_params is not None:
                return self._board_params
            self._board_params = None
        self._params_event.clear()

        self._write("GET_PARAMS")

        if self._params_event.wait(timeout):
            with self._lock:
                return self._board_params   # may be None for PARAMS_NONE
        else:
            print("BoardComm: GET_PARAMS timed out")
            return None

    def _parse_params_list(self, line: str):
        """
        Parse a PARAMS_LIST:... response into a dict.
        Format: PARAMS_LIST: "Slider 1":"Spotify"|"Slider 2":"Chrome"...
        """
        payload = line[len("PARAMS_LIST: "):].strip()
        tokens = payload.split('|')
        sliders = [""] * NUM_SLIDERS
        buttons = [""] * NUM_BUTTONS
        
        for token in tokens:
            if ":" not in token: continue
            k, v = token.split(':', 1)
            k = k.strip('"')
            v = v.strip('"')
            if k.startswith("Slider"):
                try: 
                    idx = int(k.split()[1]) - 1
                    if 0 <= idx < NUM_SLIDERS: sliders[idx] = v
                except: pass
            elif k.startswith("Button"):
                try: 
                    idx = int(k.split()[1]) - 1
                    if 0 <= idx < NUM_BUTTONS: buttons[idx] = v
                except: pass
                
        with self._lock:
            # retain LED parameters from any existing _board_params if they exist
            led = {}
            if self._board_params and "led" in self._board_params:
                led = self._board_params["led"]
            self._board_params = {"sliders": sliders, "buttons": buttons, "led": led}
        self._params_event.set()
        print(f"BoardComm: received params list from board → {self._board_params}")

    def _parse_params_line(self, line: str):
        """
        Parse a PARAMS:... response into a dict.
        Now also handles: BR (brightness), SS/BS (styles), SCN/BCN (colours).
        """
        sliders = [""] * NUM_SLIDERS
        buttons = [""] * NUM_BUTTONS
        led = {
            "brightness":    None,
            "slider_style":  None,
            "button_style":  None,
            "slider_fill":   None,
            "button_fill":   None,
            "anim_speed":    None,
            "slider_colors": [None] * NUM_SLIDERS,
            "button_colors": [None] * NUM_BUTTONS,
        }

        try:
            payload = line[len("PARAMS:"):]
            tokens  = payload.split("|")
            for token in tokens:
                token = token.strip()
                if len(token) < 3:
                    continue
                colon = token.find(":")
                if colon < 1:
                    continue
                key = token[:colon]   # e.g. "S1", "BR", "SC2", "BC3"
                val = token[colon+1:]

                # ── scalar LED fields ────────────────────────────────
                if key == "BR":
                    try:
                        led["brightness"] = int(val)
                    except ValueError:
                        pass
                    continue
                if key == "SF":
                    try:
                        led["slider_fill"] = int(val)
                    except ValueError:
                        pass
                    continue
                if key == "BF":
                    try:
                        led["button_fill"] = int(val)
                    except ValueError:
                        pass
                    continue
                if key == "SS":
                    try:
                        led["slider_style"] = int(val)
                    except ValueError:
                        pass
                    continue
                if key == "BS":
                    try:
                        led["button_style"] = int(val)
                    except ValueError:
                        pass
                    continue
                if key == "AS":
                    try:
                        led["anim_speed"] = int(val)
                    except ValueError:
                        pass
                    continue

                kind = key[0]  # 'S' or 'B'

                # ── colour fields SCN / BCN ──────────────────────────
                if len(key) >= 3 and key[1] == 'C':
                    try:
                        idx = int(key[2:]) - 1
                        r, g, b = (int(x) for x in val.split(","))
                        if kind == 'S' and 0 <= idx < NUM_SLIDERS:
                            led["slider_colors"][idx] = [r, g, b]
                        elif kind == 'B' and 0 <= idx < NUM_BUTTONS:
                            led["button_colors"][idx] = [r, g, b]
                    except (ValueError, AttributeError):
                        pass
                    continue

                # ── name fields SN / BN ──────────────────────────────
                try:
                    idx = int(key[1:]) - 1
                except ValueError:
                    continue
                if kind == 'S' and 0 <= idx < NUM_SLIDERS:
                    sliders[idx] = val
                elif kind == 'B' and 0 <= idx < NUM_BUTTONS:
                    buttons[idx] = val

        except Exception as e:
            log_error(e, "BoardComm: error parsing PARAMS line")

        with self._lock:
            self._board_params = {"sliders": sliders, "buttons": buttons, "led": led}
        self._params_event.set()
        print(f"BoardComm: received params from board → {self._board_params}")

    def _get_host_params(self) -> dict | None:
        """
        Derive slider/button names + LED settings from the live config.
        Returns a dict with 'sliders', 'buttons', and 'led' keys.
        """
        if not self.config_manager:
            return None

        try:
            cfg      = self.config_manager.config
            var_bindings = cfg.get("variable_bindings", {})
            btn_bindings = cfg.get("button_bindings",  {})

            # ── Slider names ─────────────────────────────────────────────
            sliders = []
            for i in range(NUM_SLIDERS):
                key     = f"s{i + 1}"
                binding = var_bindings.get(key)
                name    = self._binding_to_slider_name(binding, i)
                sliders.append(name[:FLASH_NAME_LEN])

            # ── Button names ──────────────────────────────────────────────
            buttons = []
            for i in range(NUM_BUTTONS):
                key     = f"b{i + 1}"
                binding = btn_bindings.get(key)
                name    = self._binding_to_button_name(binding, i)
                buttons.append(name[:FLASH_NAME_LEN])

            # ── LED settings ──────────────────────────────────────────────
            led = {
                "brightness":    cfg.get("led_brightness", 80),
                "slider_fill":   cfg.get("slider_led_fill", 1),
                "slider_style":  cfg.get("slider_led_style", 0),
                "slider_colors": cfg.get("slider_led_colors", [[0,61,61]]*5),
                "button_fill":   cfg.get("button_led_fill", 1),
                "button_style":  cfg.get("button_led_style", 0),
                "button_colors": cfg.get("button_led_colors", [[61,20,0]]*6),
                "anim_speed":    cfg.get("led_anim_speed", 5),
            }

            return {"sliders": sliders, "buttons": buttons, "led": led}

        except Exception as e:
            log_error(e, "BoardComm: error reading host params")
            return None

    # ── Name extraction helpers ───────────────────────────────────────────

    @staticmethod
    def _binding_to_slider_name(binding, index: int) -> str:
        """
        Extract a human-readable name from a slider binding entry.

        Binding formats supported:
          - None / missing              → "Slider N"
          - str                         → used directly
          - list of str                 → joined with "+"
          - list of dict {"value": ...} → values joined with "+"
          - dict {"app_name": ...}      → legacy format
        """
        default = f"Slider {index + 1}"

        if not binding:
            return default

        targets = []

        if isinstance(binding, str):
            targets = [binding]
        elif isinstance(binding, list):
            for item in binding:
                if isinstance(item, dict):
                    v = item.get("value") or item.get("app_name")
                    if v and v not in ("None", "none"):
                        targets.append(str(v))
                elif item and str(item) not in ("None", "none"):
                    targets.append(str(item))
        elif isinstance(binding, dict):
            # Legacy {"app_name": ...} or {"value": ...}
            app = binding.get("app_name") or binding.get("value")
            if isinstance(app, list):
                targets = [str(a) for a in app if a and str(a) not in ("None", "none")]
            elif app and str(app) not in ("None", "none"):
                targets = [str(app)]

        if not targets:
            return default

        return "+".join(targets)

    @staticmethod
    def _binding_to_button_name(binding, index: int) -> str:
        """
        Extract a human-readable name from a button binding entry.

        Binding format: dict {"value": "action_name", "argument": ...}
        """
        default = f"Button {index + 1}"

        if not binding:
            return default

        if isinstance(binding, dict):
            name = binding.get("value") or binding.get("action")
            if name and str(name) not in ("None", "none"):
                # Convert snake_case to Title Case for readability
                return str(name).replace("_", " ").title()

        return default

    def _params_differ(self, board: dict, host: dict) -> bool:
        """Return True if any name or LED param differs between board and host."""
        for i in range(NUM_SLIDERS):
            if board["sliders"][i].strip() != host["sliders"][i].strip():
                return True
        for i in range(NUM_BUTTONS):
            if board["buttons"][i].strip() != host["buttons"][i].strip():
                return True
        # LED params
        b_led = board.get("led", {})
        h_led = host.get("led", {})
        if b_led.get("brightness")   != h_led.get("brightness"):   return True
        if b_led.get("slider_fill")  != h_led.get("slider_fill"):  return True
        if b_led.get("slider_style") != h_led.get("slider_style"): return True
        if b_led.get("button_fill")  != h_led.get("button_fill"):  return True
        if b_led.get("button_style") != h_led.get("button_style"): return True
        if b_led.get("anim_speed")   != h_led.get("anim_speed"):   return True
        if b_led.get("slider_colors") != h_led.get("slider_colors"): return True
        if b_led.get("button_colors") != h_led.get("button_colors"): return True
        return False

    def _send_set_params(self, params: dict):
        """
        Build and send SET_PARAMS including names + LED config.
        Format: SET_PARAMS:S1:name|...|B1:name|...|BR:80|SS:0|BS:0|SC1:R,G,B|...
        """
        def _clamp(name: str) -> str:
            return str(name).strip()[:FLASH_NAME_LEN]

        parts = []
        for i, name in enumerate(params["sliders"]):
            cmd = f'Parameter_update: "Slider {i+1}", "{_clamp(name)}"'
            self._enqueue(cmd)
            print(f"BoardComm: queued {cmd}")
        for i, name in enumerate(params["buttons"]):
            cmd = f'Parameter_update: "Button {i+1}", "{_clamp(name)}"'
            self._enqueue(cmd)
            print(f"BoardComm: queued {cmd}")

        led = params.get("led", {})
        if led.get("brightness") is not None:
            parts.append(f"BR:{int(led['brightness'])}")
        if led.get("slider_fill") is not None:
            parts.append(f"SF:{int(led['slider_fill'])}")
        if led.get("slider_style") is not None:
            parts.append(f"SS:{int(led['slider_style'])}")
        if led.get("button_fill") is not None:
            parts.append(f"BF:{int(led['button_fill'])}")
        if led.get("button_style") is not None:
            parts.append(f"BS:{int(led['button_style'])}")
        if led.get("anim_speed") is not None:
            parts.append(f"AS:{int(led['anim_speed'])}")
        for i, rgb in enumerate(led.get("slider_colors") or []):
            if rgb:
                parts.append(f"SC{i+1}:{rgb[0]},{rgb[1]},{rgb[2]}")
        for i, rgb in enumerate(led.get("button_colors") or []):
            if rgb:
                parts.append(f"BC{i+1}:{rgb[0]},{rgb[1]},{rgb[2]}")

        if parts:
            cmd = "SET_PARAMS:" + "|".join(parts)
            self._enqueue(cmd)
            print(f"BoardComm: queued SET_PARAMS → {cmd[:120]}...")
            
        with self._lock:
            self._last_sent_params = params

    def _send_diff_params(self, old: dict, new: dict):
        """
        Build and enqueue a SET_PARAMS containing ONLY the fields that
        differ between *old* (last known board state) and *new* (current
        host config).  This avoids overwriting unchanged board values and
        keeps SPI flash writes to a minimum.
        """
        def _clamp(name: str) -> str:
            return str(name).strip()[:FLASH_NAME_LEN]

        parts = []

        # ── Slider names ─────────────────────────────────────────────
        for i in range(NUM_SLIDERS):
            o = ((old.get("sliders") or [""] * NUM_SLIDERS) + [""] * NUM_SLIDERS)[i]
            n = ((new.get("sliders") or [""] * NUM_SLIDERS) + [""] * NUM_SLIDERS)[i]
            if o.strip() != n.strip():
                name_val = _clamp(n)
                cmd = f'Parameter_update: "Slider {i+1}", "{name_val}"'
                self._enqueue(cmd)
                print(f"BoardComm: queued {cmd}")

        # ── Button names ─────────────────────────────────────────────
        for i in range(NUM_BUTTONS):
            o = ((old.get("buttons") or [""] * NUM_BUTTONS) + [""] * NUM_BUTTONS)[i]
            n = ((new.get("buttons") or [""] * NUM_BUTTONS) + [""] * NUM_BUTTONS)[i]
            if o.strip() != n.strip():
                name_val = _clamp(n)
                cmd = f'Parameter_update: "Button {i+1}", "{name_val}"'
                self._enqueue(cmd)
                print(f"BoardComm: queued {cmd}")

        # ── LED scalar fields ─────────────────────────────────────────
        o_led = old.get("led", {})
        n_led = new.get("led", {})
        for py_key, wire_token in [
            ("brightness",   "BR"),
            ("slider_fill",  "SF"),
            ("slider_style", "SS"),
            ("button_fill",  "BF"),
            ("button_style", "BS"),
            ("anim_speed",   "AS"),
        ]:
            n_val = n_led.get(py_key)
            if n_val is not None and o_led.get(py_key) != n_val:
                parts.append(f"{wire_token}:{int(n_val)}")

        # ── Slider colours ────────────────────────────────────────────
        o_sc = o_led.get("slider_colors") or []
        n_sc = n_led.get("slider_colors") or []
        for i, new_rgb in enumerate(n_sc):
            old_rgb = o_sc[i] if i < len(o_sc) else None
            if new_rgb and old_rgb != new_rgb:
                parts.append(f"SC{i+1}:{new_rgb[0]},{new_rgb[1]},{new_rgb[2]}")

        # ── Button colours ────────────────────────────────────────────
        o_bc = o_led.get("button_colors") or []
        n_bc = n_led.get("button_colors") or []
        for i, new_rgb in enumerate(n_bc):
            old_rgb = o_bc[i] if i < len(o_bc) else None
            if new_rgb and old_rgb != new_rgb:
                parts.append(f"BC{i+1}:{new_rgb[0]},{new_rgb[1]},{new_rgb[2]}")

        if parts:
            cmd = "SET_PARAMS:" + "|".join(parts)
            self._enqueue(cmd)
            print(f"BoardComm: queued partial SET_PARAMS ({len(parts)} field(s)) → {cmd[:120]}")
            with self._lock:
                self._last_sent_params = new
        else:
            print("BoardComm: no config changes detected – nothing sent")

    def sync_params_if_changed(self, host_params: dict | None = None):
        """
        Public entry-point for incremental config sync.

        Compares *host_params* against the last known board state and sends
        only the fields that differ.  If no cached state exists yet (e.g.
        first connection attempt failed) a full SET_PARAMS is sent instead.

        Parameters
        ----------
        host_params : dict | None
            Pre-fetched host params dict.  If None, fresh params are fetched
            from the config manager.
        """
        try:
            if host_params is None:
                host_params = self._get_host_params()
            if host_params is None:
                return

            if not (self.serial_handler and self.serial_handler.is_connected()):
                return

            with self._lock:
                last = self._last_sent_params

            if last is None:
                # No cached state – send everything so the board is in sync.
                print("BoardComm: no cached state – sending full SET_PARAMS")
                self._send_set_params(host_params)
            else:
                self._send_diff_params(last, host_params)

        except Exception as e:
            log_error(e, "BoardComm: error in sync_params_if_changed")


    def send_led_params(self, **kwargs):
        """
        Send a partial SET_PARAMS with only the changed LED fields.
        Supported keyword args:
          brightness   (int 0-100)
          slider_fill  (int 0-2)
          slider_style (int 0-4)
          button_fill  (int 0-2)
          button_style (int 0-4)
          anim_speed   (int 1-10)
          slider_colors (list of 5 [R,G,B])
          button_colors (list of 6 [R,G,B])
        """
        parts = []
        if "brightness" in kwargs:
            parts.append(f"BR:{int(kwargs['brightness'])}")
        if "slider_fill" in kwargs:
            parts.append(f"SF:{int(kwargs['slider_fill'])}")
        if "slider_style" in kwargs:
            parts.append(f"SS:{int(kwargs['slider_style'])}")
        if "button_fill" in kwargs:
            parts.append(f"BF:{int(kwargs['button_fill'])}")
        if "button_style" in kwargs:
            parts.append(f"BS:{int(kwargs['button_style'])}")
        if "anim_speed" in kwargs:
            parts.append(f"AS:{int(kwargs['anim_speed'])}")  
        for i, rgb in enumerate(kwargs.get("slider_colors") or []):
            if rgb:
                parts.append(f"SC{i+1}:{rgb[0]},{rgb[1]},{rgb[2]}")
        for i, rgb in enumerate(kwargs.get("button_colors") or []):
            if rgb:
                parts.append(f"BC{i+1}:{rgb[0]},{rgb[1]},{rgb[2]}")
        if parts:
            self._enqueue("SET_PARAMS:" + "|".join(parts))
            # Keep the cache in sync so the next incremental diff is accurate.
            with self._lock:
                if self._last_sent_params is not None:
                    led = self._last_sent_params.setdefault("led", {})
                    for kw_key, led_key in [
                        ("brightness",    "brightness"),
                        ("slider_fill",   "slider_fill"),
                        ("slider_style",  "slider_style"),
                        ("button_fill",   "button_fill"),
                        ("button_style",  "button_style"),
                        ("anim_speed",    "anim_speed"),
                    ]:
                        if kw_key in kwargs:
                            led[led_key] = kwargs[kw_key]
                    if "slider_colors" in kwargs:
                        led["slider_colors"] = list(kwargs["slider_colors"])
                    if "button_colors" in kwargs:
                        led["button_colors"] = list(kwargs["button_colors"])

    @staticmethod
    def _to_framebuffer(source) -> bytes | None:
        """
        Convert *source* to a 1024-byte SSD1306 framebuffer.

        Supported sources:
          - bytes / bytearray of length 1024 → used directly.
          - PIL Image → converted to 1-bit, resized, packed into pages.
        """
        # Raw bytes path
        if isinstance(source, (bytes, bytearray)):
            if len(source) == OLED_FB_LEN:
                return bytes(source)
            print(f"BoardComm: raw framebuffer must be {OLED_FB_LEN} bytes "
                  f"(got {len(source)})")
            return None

        # PIL Image path
        try:
            from PIL import Image as PILImage

            if not isinstance(source, PILImage.Image):
                print("BoardComm: send_image source must be bytes or PIL.Image")
                return None

            # Resize to 128×64 and convert to 1-bit
            img = source.convert("L")
            img = img.resize((OLED_WIDTH, OLED_PAGES * 8), PILImage.LANCZOS)
            img = img.convert("1")   # 1-bit black-and-white

            # Pack into SSD1306 page format:
            # page p, column c → byte at p*128+c, bit position = row within page
            fb = bytearray(OLED_FB_LEN)
            for page in range(OLED_PAGES):
                for col in range(OLED_WIDTH):
                    byte = 0
                    for bit in range(8):
                        row = page * 8 + bit
                        pixel = img.getpixel((col, row))
                        if pixel:
                            byte |= (1 << bit)
                    fb[page * OLED_WIDTH + col] = byte

            return bytes(fb)

        except ImportError:
            print("BoardComm: Pillow not installed – only raw bytes are supported")
            return None
        except Exception as e:
            log_error(e, "BoardComm: image conversion error")
            return None
