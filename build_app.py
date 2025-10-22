import subprocess
import sys
import os

def run_pyinstaller_build():
    """
    Runs the PyInstaller command to build the DeskMix executable.
    """
    
    # --- Configuration ---
    APP_NAME = "DeskMixer"
    ICON_PATH = "icons/logo.png"
    MAIN_SCRIPT = "main.py"
    
    # --- PyInstaller Execution Command (VENV/Standard FIX) ---
    PYTHON_EXEC = sys.executable 
    PYINSTALLER_COMMAND_BASE = [PYTHON_EXEC, "-m", "PyInstaller"]
    
    # PyInstaller arguments (split into a list for subprocess)
    COMMAND = PYINSTALLER_COMMAND_BASE + [
        "--onefile",
        "--noconsole",
        f"--name={APP_NAME}",
        f"--icon={ICON_PATH}",
        f"--add-data={ICON_PATH}:{os.path.dirname(ICON_PATH)}", 
        
        # --- FIX FOR SERIAL PORT AUTO-CONNECTION ---
        # 1. Keep the standard list_ports import.
        "--hidden-import=serial.tools.list_ports",
        # 2. Add the main 'serial' package for broader compatibility.
        "--hidden-import=serial", 
        # 3. CRITICAL: Add the platform-specific internal backend for list_ports. 
        #    This is what is often missed on Windows.
        "--hidden-import=serial.tools.list_ports_windows", 
        
        # --- Additional hidden imports for pystray and its dependencies ---
        "--hidden-import=pystray",
        "--hidden-import=pystray._win32", 
        # Uncomment if you face Pillow errors:
        # "--hidden-import=PIL", 
        
        MAIN_SCRIPT
    ]
    
    # Print the command (starting from the executable name)
    print_command_list = COMMAND[0:] 
        
    print("=" * 60)
    print(f"Starting PyInstaller build for {APP_NAME}...")
    print(f"Command: {' '.join(print_command_list)}")
    print("=" * 60)
    
    try:
        # Run the command
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
            print(f"Executable is located in the 'dist' directory.")
            print("=" * 60)
        else:
            print("=" * 60)
            print(f"FAILURE: PyInstaller failed with exit code {process.returncode}")
            print("Check the build logs above for details.")
            print("=" * 60)

    except FileNotFoundError:
        print("\nERROR: Could not find the Python executable.")
        print(f"Please verify that the current environment is active and PyInstaller is installed.")
    except Exception as e:
        print(f"\nAn unexpected error occurred during the build process: {e}")

if __name__ == "__main__":
    run_pyinstaller_build()