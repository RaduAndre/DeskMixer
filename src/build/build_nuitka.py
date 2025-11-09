"""
DeskMixer - Nuitka Build Script (with Manifest and Version Info)
Location: src/build/build_nuitka.py
"""

import subprocess
import sys
import os
import re


def parse_version_file(version_file_path):
    """Extract version and metadata from version_info.txt"""
    with open(version_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract values using regex
    version_info = {}

    # Extract file version (e.g., filevers=(1, 0, 0, 0))
    filevers_match = re.search(r'filevers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', content)
    if filevers_match:
        version_info['VERSION'] = '.'.join(filevers_match.groups())

    # Extract metadata from StringStruct entries
    patterns = {
        'COMPANY_NAME': r"StringStruct\(u'CompanyName',\s*u'([^']+)'\)",
        'FILE_DESCRIPTION': r"StringStruct\(u'FileDescription',\s*u'([^']+)'\)",
        'PRODUCT_VERSION': r"StringStruct\(u'ProductVersion',\s*u'([^']+)'\)",
        'PRODUCT_NAME': r"StringStruct\(u'ProductName',\s*u'([^']+)'\)",
        'COPYRIGHT': r"StringStruct\(u'LegalCopyright',\s*u'([^']+)'\)",
        'INTERNAL_NAME': r"StringStruct\(u'InternalName',\s*u'([^']+)'\)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            version_info[key] = match.group(1)

    return version_info


def run_nuitka_build():
    """
    Runs the Nuitka command to build the DeskMixer executable.
    """

    # Get the directory where build_nuitka.py is located (src/build directory)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Get the src directory (parent of build directory)
    src_dir = os.path.dirname(script_dir)

    # Add src directory to Python path so Nuitka can find local modules
    sys.path.insert(0, src_dir)

    # --- File Paths ---
    MAIN_SCRIPT = os.path.join(src_dir, "main.py")
    VERSION_FILE = os.path.join(script_dir, "version_info.txt")
    MANIFEST_XML = os.path.join(src_dir, "manifest.xml")
    ICON_PATH = os.path.join(src_dir, "icons", "logo.ico")

    # Output directories
    DIST_DIR = os.path.join(script_dir, "dist")
    OUTPUT_DIR = DIST_DIR  # exe will be in src/build/dist/
    BUILD_CACHE_DIR = os.path.join(DIST_DIR, "build_files")  # build files in src/build/dist/build_files/

    print(f"Script directory: {script_dir}")
    print(f"Source directory: {src_dir}")
    print(f"Main script: {MAIN_SCRIPT}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Build cache directory: {BUILD_CACHE_DIR}")
    print()

    # Check if main.py exists
    if not os.path.exists(MAIN_SCRIPT):
        print("ERROR: main.py not found!")
        print(f"Expected location: {MAIN_SCRIPT}")
        sys.exit(1)

    # Check if version_info.txt exists
    if not os.path.exists(VERSION_FILE):
        print("ERROR: version_info.txt not found!")
        print(f"Expected location: {VERSION_FILE}")
        sys.exit(1)

    # Parse version information from version_info.txt
    try:
        version_info = parse_version_file(VERSION_FILE)
        VERSION = version_info.get('VERSION', '1.0.0.0')
        PRODUCT_VERSION = version_info.get('PRODUCT_VERSION', '1.0.0')
        COMPANY_NAME = version_info.get('COMPANY_NAME', 'DeskMixer Project')
        PRODUCT_NAME = version_info.get('PRODUCT_NAME', 'DeskMixer')
        FILE_DESCRIPTION = version_info.get('FILE_DESCRIPTION', 'Hardware Audio Mixer Controller')
        COPYRIGHT = version_info.get('COPYRIGHT', 'Copyright (c) 2025 DeskMixer Project')
        INTERNAL_NAME = version_info.get('INTERNAL_NAME', 'DeskMixer')

        print("✓ Parsed version_info.txt successfully")
    except Exception as e:
        print(f"ERROR: Failed to parse version_info.txt: {e}")
        sys.exit(1)

    # Check for manifest
    has_manifest = os.path.exists(MANIFEST_XML)
    if has_manifest:
        print(f"✓ Found manifest.xml")
    else:
        print("⚠ Warning: manifest.xml not found")

    # Check for icon
    has_icon = os.path.exists(ICON_PATH)
    if has_icon:
        print(f"✓ Found logo.ico")
    else:
        print("⚠ Warning: logo.ico not found")

    # Create output directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(BUILD_CACHE_DIR, exist_ok=True)

    print()
    print("=" * 60)
    print("Building DeskMixer with Nuitka")
    print("=" * 60)
    print(f"Version: {PRODUCT_VERSION}")
    print(f"Product Name: {PRODUCT_NAME}")
    print(f"Company: {COMPANY_NAME}")
    print(f"Description: {FILE_DESCRIPTION}")
    print(f"Copyright: {COPYRIGHT}")
    print()

    # --- Nuitka Execution Command ---
    PYTHON_EXEC = sys.executable
    NUITKA_COMMAND_BASE = [PYTHON_EXEC, "-m", "nuitka"]

    # Nuitka arguments (split into a list for subprocess)
    COMMAND = NUITKA_COMMAND_BASE + [
        # Basic compilation options
        "--onefile",
        "--msvc=latest",  # Instruct Nuitka to use the latest installed MSVC
        "--enable-plugin=tk-inter",

        # Windows-specific options
        "--windows-disable-console",  # No console window (GUI app)

        # Output naming and location
        f"--output-filename={PRODUCT_NAME}.exe",
        f"--output-dir={OUTPUT_DIR}",

        # Include data files (use absolute paths)
        f"--include-data-dir={os.path.join(src_dir, 'icons')}=icons",

        # Python package inclusions (hidden imports)
        "--include-package=serial",
        "--include-package=serial.tools",
        "--include-module=serial.tools.list_ports",
        "--include-module=serial.tools.list_ports_windows",
        "--include-package=pystray",
        "--include-module=pystray._win32",

        # Include config module explicitly
        "--include-package=config",
        "--include-module=config.config_manager",

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
    ]

    # Add Windows version information
    COMMAND.extend([
        f"--windows-company-name={COMPANY_NAME}",
        f"--windows-product-name={PRODUCT_NAME}",
        f"--windows-file-version={VERSION}",
        f"--windows-product-version={PRODUCT_VERSION}",
        f"--windows-file-description={FILE_DESCRIPTION}",
    ])

    # Add icon if available
    if has_icon:
        COMMAND.append(f"--windows-icon-from-ico={ICON_PATH}")

    # Add manifest if available
    if has_manifest:
        COMMAND.append(f"--windows-uac-admin=no")  # Ensure UAC is set properly
        COMMAND.append(f"--windows-manifest={MANIFEST_XML}")

    # Main script (must be last)
    COMMAND.append(MAIN_SCRIPT)

    print("=" * 60)
    print(f"Starting Nuitka build for {PRODUCT_NAME}...")
    print(f"This may take several minutes on first build...")
    print("=" * 60)

    try:
        # Run the command from the src directory
        process = subprocess.Popen(COMMAND, cwd=src_dir,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   universal_newlines=True)

        # Stream output to console in real-time
        for line in process.stdout:
            print(line, end='')

        process.wait()

        if process.returncode == 0:
            print("=" * 60)
            print(f"✓ SUCCESS: {PRODUCT_NAME} build finished!")
            print("=" * 60)
            print(f"Executable location: {os.path.join(OUTPUT_DIR, PRODUCT_NAME + '.exe')}")
            print(f"Build files location: {BUILD_CACHE_DIR}")
            print()
            print(f"Product Name: {PRODUCT_NAME}")
            print(f"Version: {PRODUCT_VERSION}")
            print(f"Company: {COMPANY_NAME}")
            print("=" * 60)
        else:
            print("=" * 60)
            print(f"✗ FAILURE: Nuitka failed with exit code {process.returncode}")
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
    # Get the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Working directory: {script_dir}")
    print()

    # Check requirements before building
    if check_nuitka_requirements():
        run_nuitka_build()
    else:
        print("\nPlease install required tools and try again.")