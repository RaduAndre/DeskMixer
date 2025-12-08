"""
File utilities for UI2.
Handles file browsing and shortcut parsing.
"""

import os
from PySide6.QtWidgets import QFileDialog

def browse_app_file(parent_widget=None):
    """
    Open file dialog to select an application or shortcut.
    Returns tuple (app_path, app_name) or (None, None) if cancelled/error.
    """
    file_path = None
    try:
        # Try using Windows shell dialog that preserves .lnk files
        try:
            import win32gui
            import win32con

            # Use Windows file dialog with flag to not dereference links
            # We need a window handle. If parent_widget is QWidget, we can get winId()
            hwnd = 0
            if parent_widget:
                try:
                    hwnd = parent_widget.winId()
                except:
                    pass

            result = win32gui.GetOpenFileNameW(
                hwndOwner=hwnd,
                Filter='All Files\0*.*\0Shortcuts\0*.lnk\0Executables\0*.exe\0',
                Title='Select Application or Shortcut',
                Flags=win32con.OFN_FILEMUSTEXIST | win32con.OFN_PATHMUSTEXIST | 0x00100000  # OFN_NODEREFERENCELINKS
            )
            
            if result:
                 # result key maps to tuple, checking raw result
                 pass

            # win32gui.GetOpenFileNameW returns tuple (filename, customfilter, flags) or 0/None on cancel?
            # Actually PyWin32 returns the filename string directly on some versions? 
            # Or tuple (filename, customfilter, flags) 
            # Let's verify standard return. Usually (filename, customfilter, flags).
            # If cancel, raises error or returns something else?
            # It usually raises com_error or similar if cancelled on some wrappers, but PyWin32 win32gui wrapping is C-style.
            # GetOpenFileNameW returns tuple or raises exception on cancel?
            # Wait, looking at the user's code:
            # result = win32gui.GetOpenFileNameW(...)
            # if isinstance(result, (tuple, list)): file_path = result[0]
            
            if isinstance(result, (tuple, list)):
                file_path = result[0] if result else ""
            else:
                file_path = result

        except (ImportError, Exception) as e:
            print(f"Windows shell dialog failed: {e}, falling back to QFileDialog")
            # Fallback to QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(
                parent_widget,
                "Select Application or Shortcut",
                "",
                "All Files (*.*);;Shortcuts (*.lnk);;Executables (*.exe)"
            )

        if not file_path:
            return None, None

        # Process file
        app_path = file_path
        app_name = os.path.basename(file_path)

        # Check if it's a shortcut
        if file_path.lower().endswith('.lnk'):
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(file_path)
                
                target_path = shortcut.Targetpath
                arguments = shortcut.Arguments
                
                if target_path:
                    if arguments and arguments.strip():
                        app_path = f'"{target_path}" {arguments}'
                    else:
                        app_path = target_path
                
                # Name without .lnk
                app_name = os.path.basename(file_path)[:-4]
                
            except Exception as e:
                print(f"Error extracting shortcut info: {e}")
                # Fallback to path as-is
                app_name = os.path.basename(file_path)[:-4]
        
        return app_path, app_name

    except Exception as e:
        print(f"Error browsing app: {e}")
        return None, None
