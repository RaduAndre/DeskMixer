import sys
import traceback
from tkinter import messagebox
from datetime import datetime
import os


def setup_error_handling():
    """Setup global error handling"""
    sys.excepthook = global_exception_handler


def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions"""
    # Prevent the handler from catching KeyboardInterrupt (Ctrl+C)
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    
    # We call log_error with the full_trace for uncaught exceptions
    log_error(exc_value, "Uncaught exception", error_msg)

    messagebox.showerror(
        "Critical Error",
        f"An unexpected error occurred:\n\n{exc_value}\n\nCheck error.log for details."
    )


def handle_error(exception, context="Error occurred"):
    """Handle and display error to user"""
    error_msg = f"{context}: {str(exception)}"
    log_error(exception, context)
    messagebox.showerror("Error", error_msg)


def log_error(exception, context="", full_trace=""):
    """
    Log error to file and console. 
    The log file is created in the current working directory of the application.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # If full_trace is not provided, generate it now
    if not full_trace:
        # traceback.format_exc() is safe to call even if an exception is not currently being handled
        full_trace = traceback.format_exc()

    log_message = f"\n{'=' * 80}\n"
    log_message += f"[{timestamp}] {context}\n"
    log_message += f"Error: {str(exception)}\n"
    log_message += f"{full_trace}\n"

    # Print to console
    print(log_message)

    # --- LOG PATH MODIFICATION ---
    # Construct the path relative to the current working directory (where the EXE/main.py is)
    log_path = os.path.join(os.getcwd(), "error.log")
    
    # Write to log file
    try:
        # Use 'a' for append mode, 'utf-8' encoding for safety
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_message)
            print(log_message)
    except Exception as e:
        # If logging fails (e.g., permissions), print a note to the console but continue
        print(f"Failed to write to log file at {log_path}: {e}")
