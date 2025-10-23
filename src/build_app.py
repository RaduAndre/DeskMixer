import subprocess
import sys
import os

def run_pyinstaller_build():
    """
    Runs the PyInstaller command to build the DeskMix executable.
    """
    
    # --- Configuration ---
    APP_NAME = "DeskMixer"
    ICON_PATH = "icons/logo.png"  # Relative to src directory
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
        # Add the entire icons directory to maintain structure
        f"--add-data={ICON_PATH}{os.pathsep}icons",
        
        # --- FIX FOR SERIAL PORT AUTO-CONNECTION ---
        "--hidden-import=serial.tools.list_ports",
        "--hidden-import=serial", 
        "--hidden-import=serial.tools.list_ports_windows", 
        
        # --- Additional hidden imports for pystray and its dependencies ---
        "--hidden-import=pystray",
        "--hidden-import=pystray._win32", 
        
        MAIN_SCRIPT
    ]
    
    print("=" * 60)
    print(f"Starting PyInstaller build for {APP_NAME}...")
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
    # Ensure we're running from the src directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"Working directory: {os.getcwd()}")
    run_pyinstaller_build()