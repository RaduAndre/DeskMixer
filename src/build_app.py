"""
DeskMixer - PyInstaller Build Script (Optimized for AV Detection)
This script builds a single executable with proper metadata to reduce false positives.
"""

import PyInstaller.__main__
import os
import sys

# Get the directory where build_app.py is located (src directory)
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define paths relative to script directory (all in src/)
main_py = os.path.join(script_dir, 'main.py')
manifest_xml = os.path.join(script_dir, 'manifest.xml')
icon_path = os.path.join(script_dir, 'icons', 'logo.ico')

print(f"Working directory: {script_dir}")
print(f"Main file: {main_py}")
print()

# Check if main.py exists
if not os.path.exists(main_py):
    print("ERROR: main.py not found!")
    print(f"Expected location: {main_py}")
    print("Please ensure your project structure is:")
    print("  src/")
    print("  ├── build_app.py")
    print("  ├── main.py")
    print("  ├── manifest.xml")
    print("  └── icons/")
    print("      └── logo.ico")
    sys.exit(1)

# Version information
VERSION = "1.0.0.0"
PRODUCT_VERSION = "1.0.0"
COMPANY_NAME = "DeskMixer Project"
PRODUCT_NAME = "DeskMixer"
FILE_DESCRIPTION = "Hardware Audio Mixer Controller"
COPYRIGHT = "Copyright (c) 2025 DeskMixer Project"
INTERNAL_NAME = "DeskMixer"

# Build directories (relative to script directory)
BUILD_DIR = os.path.join(script_dir, "build")
DIST_DIR = os.path.join(script_dir, "dist")
VERSION_FILE = os.path.join(script_dir, "version_info.txt")

print("=" * 60)
print("Building DeskMixer with PyInstaller")
print("=" * 60)
print(f"Version: {PRODUCT_VERSION}")
print(f"Build directory: {DIST_DIR}")
print()

# Create version file for Windows
def create_version_file():
    """Create version_info.txt for PyInstaller"""
    version_file_content = f"""# UTF-8
#
# For more details about fixed file info:
# See: https://docs.microsoft.com/en-us/windows/win32/api/verrsrc/ns-verrsrc-vs_fixedfileinfo

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({VERSION.replace('.', ', ')}),
    prodvers=({VERSION.replace('.', ', ')}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{COMPANY_NAME}'),
        StringStruct(u'FileDescription', u'{FILE_DESCRIPTION}'),
        StringStruct(u'FileVersion', u'{PRODUCT_VERSION}'),
        StringStruct(u'InternalName', u'{INTERNAL_NAME}'),
        StringStruct(u'LegalCopyright', u'{COPYRIGHT}'),
        StringStruct(u'OriginalFilename', u'{PRODUCT_NAME}.exe'),
        StringStruct(u'ProductName', u'{PRODUCT_NAME}'),
        StringStruct(u'ProductVersion', u'{PRODUCT_VERSION}')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        f.write(version_file_content)

    print(f"✓ Created version_info.txt")

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

# Create version file
create_version_file()

# Create build and dist directories if they don't exist
os.makedirs(BUILD_DIR, exist_ok=True)
os.makedirs(DIST_DIR, exist_ok=True)

# Try to delete existing executable if it exists
exe_path = os.path.join(DIST_DIR, 'DeskMixer.exe')
if os.path.exists(exe_path):
    try:
        os.remove(exe_path)
        print(f"✓ Removed existing executable")
    except PermissionError:
        print()
        print("=" * 60)
        print("⚠ WARNING: Cannot delete existing DeskMixer.exe")
        print("=" * 60)
        print("The file might be:")
        print("  1. Currently running (check Task Manager)")
        print("  2. Locked by antivirus software")
        print("  3. Open in another program")
        print()
        print("Please:")
        print("  - Close any running DeskMixer.exe processes")
        print("  - Wait for antivirus scan to complete")
        print("  - Try again")
        print()
        sys.exit(1)

# Build PyInstaller arguments
pyinstaller_args = [
    main_py,  # Full path to main.py
    '--name=DeskMixer',
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
icons_dir = os.path.join(script_dir, 'icons')
if os.path.exists(icons_dir):
    # PyInstaller uses semicolon (;) on Windows to separate source and destination
    pyinstaller_args.append(f'--add-data={os.path.abspath(icons_dir)};icons')
    print(f"✓ Found icons directory at: {icons_dir}")
else:
    print("⚠ Warning: icons directory not found")

# Check for other common resource directories
resource_dirs = {
    'images': os.path.join(script_dir, 'images'),
    'assets': os.path.join(script_dir, 'assets'),
    'config': os.path.join(script_dir, 'config'),
    'resources': os.path.join(script_dir, 'resources'),
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
    print(f"Executable location: {os.path.join(DIST_DIR, 'DeskMixer.exe')}")
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

finally:
    # Cleanup
    if os.path.exists(VERSION_FILE):
        try:
            os.remove(VERSION_FILE)
            print("✓ Cleaned up temporary files")
        except:
            pass