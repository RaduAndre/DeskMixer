import os
import sys
import subprocess
import re

try:
    import openpyxl
except ImportError:
    print("Installing openpyxl...")
    subprocess.run([sys.executable, "-m", "pip", "install", "openpyxl"], check=True)
    import openpyxl


def get_symbol_name_for_part(kicad_sym_path, part_id):
    """Search the .kicad_sym file for a symbol whose keywords or name matches the part_id (C number)."""
    if not os.path.exists(kicad_sym_path):
        return None
    try:
        with open(kicad_sym_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Find all symbol names in the file (lines like: (symbol "NAME" ...)
        symbols = re.findall(r'\(symbol\s+"([^"]+)"', content)
        # Filter out sub-unit symbols (they contain a digit suffix after the base name)
        # and try to find one matching the part_id
        base_symbols = [s for s in symbols if not re.search(r'_\d+_\d+$', s)]
        # Try to find by part_id directly
        for sym in base_symbols:
            if part_id.upper() in sym.upper():
                return sym
        # Fallback: return the last added base symbol (most recently downloaded)
        return base_symbols[-1] if base_symbols else None
    except Exception as e:
        print(f"  Warning: could not parse symbol name: {e}")
        return None


def get_footprint_name_for_part(pretty_dir, existing_mods_before):
    """Find the newly added .kicad_mod file by comparing before/after sets."""
    if not os.path.exists(pretty_dir):
        return None
    current_mods = set(f for f in os.listdir(pretty_dir) if f.endswith(".kicad_mod"))
    new_mods = current_mods - existing_mods_before
    if new_mods:
        # Strip the .kicad_mod extension
        return os.path.splitext(list(new_mods)[0])[0]
    # Fallback: return the most recently modified file
    if current_mods:
        latest = max(
            current_mods,
            key=lambda f: os.path.getmtime(os.path.join(pretty_dir, f))
        )
        return os.path.splitext(latest)[0]
    return None


def append_to_excel(xlsx_path, c_number, symbol_name, footprint_name, note):
    """Append a row to piese.xlsx, creating it with headers if it doesn't exist."""
    if os.path.exists(xlsx_path):
        wb = openpyxl.load_workbook(xlsx_path)
        ws = wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Piese"
        ws.append(["C Number", "Symbol Name", "Footprint Name", "Note"])

    ws.append([c_number, symbol_name or "N/A", footprint_name or "N/A", note])
    wb.save(xlsx_path)
    print(f"  Saved to '{xlsx_path}': [{c_number}, {symbol_name}, {footprint_name}, {note}]")


def download_lcsc_parts():
    print("--- KiCad Footprint Downloader (EasyEDA2KiCad) ---")
    print("Type the LCSC part number (e.g., C2040) and press Enter.")
    print("Type 'done' to exit.\n")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "LCSC_Library")
    xlsx_path = os.path.join(script_dir, "piese.xlsx")
    pretty_dir = output_dir + ".pretty"
    kicad_sym_path = output_dir + ".kicad_sym"

    while True:
        part_id = input("Enter Part Number: ").strip()

        if part_id.lower() == 'done':
            print("Exiting...")
            break

        if not part_id.startswith('C'):
            print("Warning: LCSC part numbers usually start with 'C'.")

        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                print(f"Created output directory: {output_dir}")

            # Snapshot existing footprint files before download
            existing_mods_before = set()
            if os.path.exists(pretty_dir):
                existing_mods_before = set(
                    f for f in os.listdir(pretty_dir) if f.endswith(".kicad_mod")
                )

            print(f"Fetching {part_id}...")
            subprocess.run([
                sys.executable, "-m", "easyeda2kicad",
                "--full",
                f"--lcsc_id={part_id}",
                f"--output={output_dir}"
            ], check=True)
            print(f"Successfully downloaded {part_id} to '{output_dir}'.")

            # Extract symbol and footprint names
            symbol_name = get_symbol_name_for_part(kicad_sym_path, part_id)
            footprint_name = get_footprint_name_for_part(pretty_dir, existing_mods_before)

            print(f"  Symbol   : {symbol_name or 'N/A'}")
            print(f"  Footprint: {footprint_name or 'N/A'}")

            # Ask user for a note to put in the next cell
            note = input("  Enter a note for this part (or press Enter to skip): ").strip()

            # Append to Excel
            append_to_excel(xlsx_path, part_id, symbol_name, footprint_name, note)
            print()

        except subprocess.CalledProcessError:
            print(f"Error: Could not find or download part {part_id}. Check the ID and your internet.\n")
        except FileNotFoundError:
            print("Error: 'easyeda2kicad' not found. Did you run 'pip install easyeda2kicad'?\n")


if __name__ == "__main__":
    download_lcsc_parts()