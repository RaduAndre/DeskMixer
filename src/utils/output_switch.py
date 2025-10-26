import platform
import subprocess
import json
import sys
import asyncio
import gc
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

# Windows-specific: Hide console windows
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    CREATE_NO_WINDOW = 0x08000000
else:
    startupinfo = None
    CREATE_NO_WINDOW = 0

# Thread pool for async operations
_executor = ThreadPoolExecutor(max_workers=3)


@contextmanager
def safe_com_operation():
    """Context manager for safe COM operations"""
    try:
        yield
    finally:
        # Force garbage collection after COM operations
        gc.collect()
        # Small delay to let COM cleanup
        time.sleep(0.05)


def _run_powershell_hidden(command, timeout=10):
    """Run PowerShell command with hidden window"""
    if platform.system() == "Windows":
        # Use multiple methods to ensure window is hidden in compiled exe
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE

        # FIXED: Properly combine creation flags
        creation_flags = CREATE_NO_WINDOW
        if hasattr(subprocess, 'CREATE_NO_WINDOW'):
            creation_flags |= subprocess.CREATE_NO_WINDOW

        return subprocess.run(
            ["powershell.exe", "-WindowStyle", "Hidden", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=si,
            creationflags=creation_flags,
            shell=False
        )
    else:
        return subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout
        )


async def get_audio_devices_async():
    """Get available audio output devices (async)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, get_audio_devices)


def get_audio_devices():
    """Get available audio output devices for the current OS"""
    with safe_com_operation():
        system = platform.system()

        if system == "Windows":
            return _get_windows_devices()
        elif system == "Darwin":
            return _get_macos_devices()
        elif system == "Linux":
            return _get_linux_devices()
        else:
            return None


async def set_audio_device_async(device_identifier):
    """Set the default audio output device (async)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, set_audio_device, device_identifier)


def set_audio_device(device_identifier):
    """Set the default audio output device

    Args:
        device_identifier: Device index (Windows), name (macOS/Linux), or device dict
    """
    with safe_com_operation():
        system = platform.system()

        if system == "Windows":
            if isinstance(device_identifier, dict):
                device_identifier = device_identifier.get('Index')
            result = _set_windows_default(device_identifier)
            # Add delay after device switch
            if result:
                time.sleep(0.1)
            return result
        elif system == "Darwin":
            if isinstance(device_identifier, dict):
                device_identifier = device_identifier.get('name')
            result = _set_macos_default(device_identifier)
            if result:
                time.sleep(0.1)
            return result
        elif system == "Linux":
            if isinstance(device_identifier, dict):
                device_identifier = device_identifier.get('name')
            result = _set_linux_default(device_identifier)
            if result:
                time.sleep(0.1)
            return result
        else:
            return False


async def get_current_device_async():
    """Get the currently active audio output device (async)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, get_current_device)


def get_current_device():
    """Get the currently active audio output device"""
    with safe_com_operation():
        system = platform.system()
        devices = get_audio_devices()

        if not devices:
            return None

        for device in devices:
            if device.get('default') or device.get('Default'):
                return device

        return None


async def cycle_audio_device_async():
    """Cycle to the next audio output device (async)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, cycle_audio_device)


def cycle_audio_device():
    """Cycle to the next audio output device"""
    with safe_com_operation():
        devices = get_audio_devices()

        if not devices or len(devices) < 2:
            return False

        current = get_current_device()

        if not current:
            # No current device, set to first
            return set_audio_device(devices[0])

        # Find current device index
        current_idx = -1
        system = platform.system()

        for i, device in enumerate(devices):
            if system == "Windows":
                if device.get('Index') == current.get('Index'):
                    current_idx = i
                    break
            else:
                if device.get('name') == current.get('name'):
                    current_idx = i
                    break

        if current_idx == -1:
            return False

        # Get next device (wrap around)
        next_idx = (current_idx + 1) % len(devices)
        return set_audio_device(devices[next_idx])


async def get_device_names_async():
    """Get list of device names for UI display (async)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, get_device_names)


def get_device_names():
    """Get list of device names for UI display"""
    with safe_com_operation():
        devices = get_audio_devices()

        if not devices:
            return []

        system = platform.system()
        names = []

        for device in devices:
            if system == "Windows":
                names.append(device.get('Name', ''))
            else:
                names.append(device.get('name', ''))

        return [name for name in names if name]


def _get_windows_devices():
    """Get audio devices on Windows using PowerShell"""
    try:
        ps_command = """
        Get-AudioDevice -List | Where-Object {$_.Type -eq "Playback"} | 
        Select-Object Index, Name, Default | 
        ConvertTo-Json
        """
        result = _run_powershell_hidden(ps_command, timeout=10)

        if result.returncode != 0:
            return None

        devices = json.loads(result.stdout)
        if not isinstance(devices, list):
            devices = [devices]
        return devices
    except Exception:
        return None


def _set_windows_default(index):
    """Set default audio device on Windows"""
    try:
        ps_command = f"Set-AudioDevice -Index {index}"
        result = _run_powershell_hidden(ps_command, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def _get_macos_devices():
    """Get audio devices on macOS using SwitchAudioSource"""
    try:
        result = subprocess.run(
            ["SwitchAudioSource", "-a", "-t", "output"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        devices = [{"name": line.strip()} for line in result.stdout.strip().split('\n') if line.strip()]

        current = subprocess.run(
            ["SwitchAudioSource", "-c", "-t", "output"],
            capture_output=True,
            text=True,
            timeout=10
        ).stdout.strip()

        for device in devices:
            device["default"] = (device["name"] == current)

        return devices
    except Exception:
        return None


def _set_macos_default(device_name):
    """Set default audio device on macOS"""
    try:
        result = subprocess.run(
            ["SwitchAudioSource", "-s", device_name, "-t", "output"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def _get_linux_devices():
    """Get audio devices on Linux using pactl"""
    try:
        result = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        devices = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                parts = line.split('\t')
                if len(parts) >= 2:
                    devices.append({
                        "id": parts[0],
                        "name": parts[1],
                        "description": parts[1]
                    })

        default_result = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True,
            text=True,
            timeout=10
        )
        default_sink = default_result.stdout.strip()

        for device in devices:
            device["default"] = (device["name"] == default_sink)

        return devices
    except Exception:
        return None


def _set_linux_default(device_name):
    """Set default audio device on Linux"""
    try:
        result = subprocess.run(
            ["pactl", "set-default-sink", device_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


# ADDED: Cleanup function to be called on application exit
def cleanup():
    """Clean up resources before exit"""
    try:
        _executor.shutdown(wait=False)
        gc.collect()
    except:
        pass