import platform
import warnings
from pycaw.constants import DEVICE_STATE, EDataFlow
from pycaw.pycaw import AudioUtilities
from pycaw.utils import AudioDevice


def get_audio_devices():
    """Get available audio output devices (Windows only)"""
    if platform.system() != "Windows":
        return None

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            devices = AudioUtilities.GetAllDevices(
                data_flow=EDataFlow.eRender.value,
                device_state=DEVICE_STATE.ACTIVE.value
            )
            return list(devices) if devices else None
    except Exception:
        return None


def get_current_device():
    """Get the currently active audio output device"""
    if platform.system() != "Windows":
        return None

    try:
        return AudioUtilities.GetSpeakers()
    except Exception:
        return None


def set_audio_device(device):
    """Set the default audio output device

    Args:
        device: AudioDevice object or device name (str)

    Returns:
        bool: True if successful, False otherwise
    """
    if platform.system() != "Windows":
        return False

    try:
        # If device is a string (name), find the matching AudioDevice
        if isinstance(device, str):
            devices = get_audio_devices()
            if not devices:
                return False

            device_obj = None
            for d in devices:
                if d.FriendlyName == device:
                    device_obj = d
                    break

            if not device_obj:
                return False

            device = device_obj

        # Set the device as default
        AudioUtilities.SetDefaultDevice(device.id)
        return True
    except Exception:
        return False


def cycle_audio_device():
    """Cycle to the next audio output device

    Returns:
        bool: True if successful, False otherwise
    """
    if platform.system() != "Windows":
        return False

    try:
        devices = get_audio_devices()
        if not devices or len(devices) < 2:
            return False

        current = get_current_device()
        if not current:
            return set_audio_device(devices[0])

        # Find current device index
        current_idx = -1
        for i, device in enumerate(devices):
            if device.id == current.id:
                current_idx = i
                break

        if current_idx == -1:
            return False

        # Get next device (wrap around)
        next_idx = (current_idx + 1) % len(devices)
        return set_audio_device(devices[next_idx])
    except Exception:
        return False


def get_device_names():
    """Get list of device names for UI display

    Returns:
        list: List of device names, or empty list if unavailable
    """
    devices = get_audio_devices()
    if not devices:
        return []

    return [device.FriendlyName for device in devices]