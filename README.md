# DeskMixer 🎚️

A physical volume mixer with programmable buttons for Windows, inspired by [Deej](https://github.com/omriharel/deej). DeskMixer provides a seamless experience for controlling application volumes and executing custom actions through physical sliders and buttons.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- **🎛️ Volume Control**: Control individual application volumes using physical sliders
- **⌨️ Custom Keybinds**: Bind custom keyboard shortcuts to physical buttons
- **🎮 Media Controls**: Quick access to media playback controls
- **🔇 Mute Controls**: Instant mute/unmute for specific applications
- **🪟 System Tray Integration**: Runs minimized in system tray with quick access
- **⚙️ Arduino-based**: Uses ESP32/Arduino for hardware control
- **🔌 Plug & Play**: Automatic serial port detection
- **💾 Persistent Configuration**: Saves your settings between sessions

## 🚀 Getting Started

### Prerequisites

- Python 3.13+ (for running from source)
- Arduino IDE (for uploading firmware)
- ESP32 board or compatible Arduino

### Hardware Requirements

- ESP32 microcontroller
- 4x 10kΩ linear potentiometers (sliders)
- 6x push buttons
- PCB or breadboard for connections
- USB cable for serial communication

> **Note**: 3D models and Gerber files for PCB manufacturing will be included in the following updates to the repository!

### Software Installation

#### Option 1: Pre-built Executable (Windows)
1. Releases will be uploaded on the [Releases](../../releases) page
2. For now you can build the code or download and run `DeskMixer.exe` from the `/dist/` folder

#### Option 2: Run from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/DeskMixer.git
   cd DeskMixer/src
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

### Arduino Setup

1. Open `arduino/DeskMixer/DeskMixer.ino` in Arduino IDE
2. Select your board (ESP32) and COM port
3. Upload the sketch to your Arduino
4. The firmware will automatically communicate with the DeskMixer application

**Pin Configuration (you can also configure it by your liking):**
- Sliders: GPIO 33, 32, 35, 34
- Buttons: GPIO 27, 25, 14, 26, 12, 13

## 🎮 Usage

### First Launch

1. Run DeskMixer
2. Go to the **Config** tab
3. Select your Arduino's COM port
4. Configure your sliders and button actions

### Configuring Sliders

In the **Volume** tab:
- Assign each slider to control specific applications or system audio
- You can assign multiple applications to the same slider
- Adjust volumes in real-time
- Changes are saved automatically

#### Available Slider Mappings:
- **🔊 Master**: Control the system master volume
- **🎤 Microphone**: Control your default microphone input level
- **🔔 System Sounds**: Control Windows system sounds
- **⭐ Current Application**: Control the currently active/focused application (cannot override allready binded applications)
- **🎵 Individual Applications**: Control specific running applications (e.g., Spotify, Discord, Chrome)
- **❔ Unbinded**: Slider is not assigned to any target (cannot override current application)
- **❌ None**: Slider is disabled

> **Note**: The application list updates automatically based on currently running audio applications

#### Available Button Actions:
- **⏯️ Play/Pause**: Toggle media playback
- **⏭️ Next Track**: Skip to next media track
- **⏮️ Previous Track**: Go to previous media track
- **⏩ Seek Forward**: Jump forward in current media
- **⏪ Seek Backward**: Jump backward in current media
- **🔊 Volume Up**: Increase system volume
- **🔉 Volume Down**: Decrease system volume
- **🔇 Mute**: Toggle mute for system, microphone or specific application
- **🔀 Switch Audio Output**: Switch between available audio output devices (this is a work in progress hope I can nail it)
- **⌨️ Keybind (Custom)**: Execute custom keyboard shortcuts (e.g., Ctrl+C, Alt+Tab)
- **🚀 Launch App**: Start or focus a specific application

> **Tip**: Combine button actions with specific application targets for advanced control. For example, bind a button to mute Discord specifically, or launch your favorite music player.


For keybind examples, see [KEYBIND_EXAMPLES.md](KEYBIND_EXAMPLES.md)

### System Tray

- **Double-click** tray icon to show/hide window
- **Right-click** for quick actions menu
- Enable "Start Hidden (in Tray)" in settings to start minimized

## 🛠️ Building from Source

To create your own executable:

```bash
cd src
python build_app.py
