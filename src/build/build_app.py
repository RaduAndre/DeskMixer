"""
DeskMixer - PyInstaller Build Script (Optimized for AV Detection)
This script builds a single executable with proper metadata to reduce false positives.
Location: src/build/build_app.py
"""

import PyInstaller.__main__
import os
import sys
import re

# Get the directory where build_app.py is located (src/build directory)
script_dir = os.path.dirname(os.path.abspath(__file__))

# Get the src directory (parent of build directory)
src_dir = os.path.dirname(script_dir)

# Add src directory to Python path so PyInstaller can find local modules
sys.path.insert(0, src_dir)

# Define paths relative to src directory
main_py = os.path.join(src_dir, 'main.py')
manifest_xml = os.path.join(src_dir, 'manifest.xml')
icon_path = os.path.join(src_dir, 'icons', 'logo.ico')
VERSION_FILE = os.path.join(script_dir, "version_info.txt")

print(f"Script directory: {script_dir}")
print(f"Source directory: {src_dir}")
print(f"Main file: {main_py}")
print()

# Check if main.py exists
if not os.path.exists(main_py):
    print("ERROR: main.py not found!")
    print(f"Expected location: {main_py}")
    print("Please ensure your project structure is:")
    print("  src/")
    print("  ├── main.py")
    print("  ├── manifest.xml")
    print("  ├── icons/")
    print("  │   └── logo.ico")
    print("  └── build/")
    print("      ├── build_app.py")
    print("      └── version_info.txt")
    sys.exit(1)

# Check if version_info.txt exists
if not os.path.exists(VERSION_FILE):
    print("ERROR: version_info.txt not found!")
    print(f"Expected location: {VERSION_FILE}")
    sys.exit(1)

# Parse version information from version_info.txt
def parse_version_file():
    """Extract version and metadata from version_info.txt"""
    with open(VERSION_FILE, 'r', encoding='utf-8') as f:
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

# Parse version info
try:
    version_info = parse_version_file()
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

# Build directories (relative to script directory)
BUILD_DIR = os.path.join(script_dir, "build_files")
DIST_DIR = os.path.join(script_dir, "dist")  # dist goes directly in src/build/

print("=" * 60)
print("Building DeskMixer with PyInstaller")
print("=" * 60)
print(f"Version: {PRODUCT_VERSION}")
print(f"Product Name: {PRODUCT_NAME}")
print(f"Company: {COMPANY_NAME}")
print(f"Build files directory: {BUILD_DIR}")
print(f"Distribution directory: {DIST_DIR}")
print()

# Check for icon file
if os.path.exists(icon_path):
    print(f"✓ Found logo.ico")
else:
    icon_path = None
    print("⚠ Warning: logo.ico not found, building without icon")

# Check for manifest
if os.path.exists(manifest_xml):
    print(f"✓ Found manifest.xml")
else:
    manifest_xml = None
    print("⚠ Warning: manifest.xml not found")

# Create build and dist directories if they don't exist
os.makedirs(BUILD_DIR, exist_ok=True)
os.makedirs(DIST_DIR, exist_ok=True)

# Try to delete existing executable if it exists
exe_path = os.path.join(DIST_DIR, f'{PRODUCT_NAME}.exe')
if os.path.exists(exe_path):
    try:
        os.remove(exe_path)
        print(f"✓ Removed existing executable")
    except PermissionError:
        print()
        print("=" * 60)
        print(f"⚠ WARNING: Cannot delete existing {PRODUCT_NAME}.exe")
        print("=" * 60)
        print("The file might be:")
        print("  1. Currently running (check Task Manager)")
        print("  2. Locked by antivirus software")
        print("  3. Open in another program")
        print()
        print("Please:")
        print(f"  - Close any running {PRODUCT_NAME}.exe processes")
        print("  - Wait for antivirus scan to complete")
        print("  - Try again")
        print()
        sys.exit(1)

# Build PyInstaller arguments
pyinstaller_args = [
    main_py,  # Full path to main.py
    f'--name={PRODUCT_NAME}',
    '--onefile',
    '--windowed',  # No console window
    '--clean',
    '--noupx',  # Don't use UPX compression (triggers AVs)
    f'--distpath={DIST_DIR}',
    f'--workpath={BUILD_DIR}',
    f'--specpath={BUILD_DIR}',
    f'--version-file={VERSION_FILE}',
]

# Add icon if available
if icon_path:
    pyinstaller_args.append(f'--icon={os.path.abspath(icon_path)}')

# Add manifest if available
if manifest_xml:
    pyinstaller_args.append(f'--manifest={os.path.abspath(manifest_xml)}')

# Add data files (icons folder and other resources)
# Include the icons directory (contains UI icons, not just the .ico file)
icons_dir = os.path.join(src_dir, 'icons')
if os.path.exists(icons_dir):
    # PyInstaller uses semicolon (;) on Windows to separate source and destination
    pyinstaller_args.append(f'--add-data={os.path.abspath(icons_dir)};icons')
    print(f"✓ Found icons directory at: {icons_dir}")
else:
    print("⚠ Warning: icons directory not found")

# Check for other common resource directories
resource_dirs = {
    'images': os.path.join(src_dir, 'images'),
    'assets': os.path.join(src_dir, 'assets'),
    'config': os.path.join(src_dir, 'config'),
    'resources': os.path.join(src_dir, 'resources'),
}

for name, path in resource_dirs.items():
    if os.path.exists(path):
        pyinstaller_args.append(f'--add-data={os.path.abspath(path)};{name}')
        print(f"✓ Found {name} directory, will be included in build")

# Exclude unnecessary modules to reduce size (removed PIL since it's needed)
exclude_modules = [
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'sphinx',
]

for module in exclude_modules:
    pyinstaller_args.append(f'--exclude-module={module}')

# Hidden imports - Add modules that PyInstaller might miss
hidden_imports = [
    'PIL',
    'PIL._tkinter_finder',
    'pycaw',
    'pycaw.pycaw',
    'comtypes',
    'comtypes.client',
    'comtypes.stream',
    'pyserial',
    'serial',
    'serial.tools',
    'serial.tools.list_ports',
]

for module in hidden_imports:
    pyinstaller_args.append(f'--hidden-import={module}')

print()
print("Building with PyInstaller...")
print("Arguments:", ' '.join(pyinstaller_args))
print()

try:
    PyInstaller.__main__.run(pyinstaller_args)
    print()
    print("=" * 60)
    print("✓ Build completed successfully!")
    print("=" * 60)
    print(f"Executable location: {os.path.join(DIST_DIR, f'{PRODUCT_NAME}.exe')}")
    print(f"Build files location: {BUILD_DIR}")
    print()

except Exception as e:
    print()
    print("=" * 60)
    print("✗ Build failed!")
    print("=" * 60)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    print()
    sys.exit(1)