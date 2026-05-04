import sys
import time
sys.path.append(r"d:\diverse\Proiecte\DeskMixer\src")
from serial_comm.serial_handler import SerialHandler

def test_connection():
    handler = SerialHandler()
    print("Testing connection...")
    result = handler.auto_connect()
    print("Auto connect result:", result)
    time.sleep(2)
    handler.disconnect()

if __name__ == "__main__":
    test_connection()
