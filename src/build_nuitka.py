import subprocess
import sys
import os


def run_nuitka_build():
    """
    Runs the Nuitka command to build the DeskMixer executable.
    """

    # --- Configuration ---
    APP_NAME = "DeskMixer"
    ICON_PATH = "icons/logo.ico"  # Relative to src directory
    MAIN_SCRIPT = "main.py"

    # --- Nuitka Execution Command ---
    PYTHON_EXEC = sys.executable
    NUITKA_COMMAND_BASE = [PYTHON_EXEC, "-m", "nuitka"]

    # Nuitka arguments (split into a list for subprocess)
    COMMAND = NUITKA_COMMAND_BASE + [
        # Basic compilation options
        "--standalone",  # Create a standalone executable with all dependencies
        "--onefile",  # Create a single executable file
        "--msvc=latest",  # Instruct Nuitka to use the latest installed MSVC

        # Windows-specific options
        "--windows-disable-console",  # No console window (GUI app)
        f"--windows-icon-from-ico={ICON_PATH}",  # Application icon

        # Output naming
        f"--output-filename={APP_NAME}.exe",

        # Include data files
        f"--include-data-dir=icons=icons",  # Include entire icons directory

        # Python package inclusions (hidden imports)
        "--include-package=serial",
        "--include-package=serial.tools",
        "--include-module=serial.tools.list_ports",
        "--include-module=serial.tools.list_ports_windows",
        "--include-package=pystray",
        "--include-module=pystray._win32",

        # Windows-specific imports
        "--include-module=win32file",
        "--include-module=win32con",
        "--include-module=win32event",
        "--include-module=pywintypes",

        # Additional modules your app uses
        "--include-package=tkinter",
        "--include-module=PIL",

        # Performance optimizations
        "--lto=yes",  # Link Time Optimization for smaller/faster executable

        # Show progress
        "--show-progress",
        "--show-memory",

        # Enable warnings
        "--warn-implicit-exceptions",
        "--warn-unusual-code",

        # Job control (use multiple CPU cores)
        f"--jobs={os.cpu_count()}",

        # Main script
        MAIN_SCRIPT
    ]

    print("=" * 60)
    print(f"Starting Nuitka build for {APP_NAME}...")
    print(f"This may take several minutes on first build...")
    print(f"Command: {' '.join(COMMAND)}")
    print("=" * 60)

    try:
        # Run the command from the src directory
        process = subprocess.Popen(COMMAND, cwd=os.getcwd(),
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   universal_newlines=True)

        # Stream output to console in real-time
        for line in process.stdout:
            print(line, end='')

        process.wait()

        if process.returncode == 0:
            print("=" * 60)
            print(f"SUCCESS: {APP_NAME} build finished!")
            print(f"Executable is located in the current directory as '{APP_NAME}.exe'")
            print("=" * 60)
        else:
            print("=" * 60)
            print(f"FAILURE: Nuitka failed with exit code {process.returncode}")
            print("Check the build logs above for details.")
            print("=" * 60)

    except FileNotFoundError:
        print("\nERROR: Could not find Nuitka or Python executable.")
        print(f"Please ensure Nuitka is installed: pip install nuitka")
        print(f"You may also need a C compiler (like MinGW64 or MSVC).")
    except Exception as e:
        print(f"\nAn unexpected error occurred during the build process: {e}")


def check_nuitka_requirements():
    """Check if Nuitka and required tools are installed"""
    print("Checking Nuitka installation...")

    try:
        result = subprocess.run([sys.executable, "-m", "nuitka", "--version"],
                                capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Nuitka found: {result.stdout.strip()}")
        else:
            print("✗ Nuitka not found. Installing...")
            subprocess.run([sys.executable, "-m", "pip", "install", "nuitka"], check=True)
    except Exception as e:
        print(f"✗ Error checking Nuitka: {e}")
        print("\nTo install Nuitka, run: pip install nuitka")
        print("\nYou also need a C compiler:")
        print("  - Windows: Install Visual Studio Build Tools or MinGW64")
        print("  - Download from: https://visualstudio.microsoft.com/downloads/")
        return False

    return True


if __name__ == "__main__":
    # Ensure we're running from the src directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"Working directory: {os.getcwd()}")

    # Check requirements before building
    if check_nuitka_requirements():
        run_nuitka_build()
    else:
        print("\nPlease install required tools and try again.")