# @title 📂 Move or Copy Files/Folder (Updated with Size Filter)

import os
import shutil
from google.colab import drive

source_path = "/content/drive/Shareddrives/deniskareggae20/colab upload/movies.zip"  # @param {type:"string"}
target_folder = "/content/media_toolkit"  # @param {type:"string"}
operation_type = "copy"  # @param ["move", "copy"] {allow-input: false}
move_mode = "recursive"  # @param ["flat", "recursive"] {allow-input: false}
file_ext = ""  # @param {type:"string"}

#@markdown ---
flatten_structure = False  # @param {type:"boolean"}
skip_hidden = True  # @param {type:"boolean"}

#@markdown ---
filter_by_size = False # @param {type:"boolean"}
size_in_gb = 1.9 # @param {type:"number"}
size_mode = "larger" # @param ["larger", "smaller"]

#@markdown ---
filter_by_index = False # @param {type:"boolean"}
index_range = "10" # @param {type:"string"}

# ============================================================
# 📜 Unified Logging
# ============================================================
APPNAME = "FsToolkit"

def log(message, level="INFO"):
    print(f"{level}:{APPNAME}:{message}")

# ============================================================
# 🔒 Google Drive Handling
# ============================================================
def ensure_drive_mounted():
    drive_path = "/content/drive"
    if not os.path.ismount(drive_path):
        log(f"Mounting Google Drive ke {drive_path}...")
        drive.mount(drive_path)

# ============================================================
# 🧩 Helper Utilities
# ============================================================
def parse_index_range(range_str):
    """Mengubah string '1, 4, 7-9' menjadi set {1, 4, 7, 8, 9}"""
    indices = set()
    for part in range_str.split(','):
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                indices.update(range(start, end + 1))
            except ValueError: continue
        elif part.isdigit():
            indices.add(int(part))
    return indices

def unique_target_path(dst_dir, file_name):
    base, ext = os.path.splitext(file_name)
    counter = 1
    new_name = file_name
    new_path = os.path.join(dst_dir, new_name)
    while os.path.exists(new_path):
        new_name = f"{base} ({counter:03d}){ext}"
        new_path = os.path.join(dst_dir, new_name)
        counter += 1
    return new_path

def is_hidden(path):
    name = os.path.basename(path)
    return name.startswith(".") or "/." in path or "\\." in path

def remove_empty_dirs(path):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in dirs:
            d = os.path.join(root, name)
            try:
                if not os.listdir(d): os.rmdir(d)
            except OSError: pass

# ============================================================
# 🚚 MAIN: Move or Copy Path
# ============================================================
def move_or_copy_path(src, dst, operation="move", mode="flat", ext_filter="", skip_hidden=True,
                      flatten=False, filter_by_size=False, size_in_gb=1, size_mode="larger",
                      filter_by_index=False, index_range=""):

    if "/content/drive" in src or "/content/drive" in dst:
        ensure_drive_mounted()

    if not os.path.exists(src):
        log(f"Source path tidak ditemukan: {src}", "ERROR")
        return

    ext_list = [e.lower().lstrip(".") for e in ext_filter.replace(";", ",").split(",") if e.strip()]
    target_indices = parse_index_range(index_range) if filter_by_index else None

    processed_count = 0
    current_index = 0

    def should_process(file_path, file_name, idx):
        # Filter Index
        if filter_by_index and idx not in target_indices:
            return False
        # Filter Ekstensi
        if ext_list and not any(file_name.lower().endswith(f".{e}") for e in ext_list):
            return False
        # Filter Ukuran
        if filter_by_size:
            try:
                file_size_bytes = os.path.getsize(file_path)
                target_size_bytes = size_in_gb * (1024 ** 3)
                if size_mode == "larger" and file_size_bytes <= target_size_bytes: return False
                elif size_mode == "smaller" and file_size_bytes >= target_size_bytes: return False
            except: return False
        return True

    def safe_operation(src_file, dst_dir):
        nonlocal processed_count
        file_name = os.path.basename(src_file)
        target_path = unique_target_path(dst_dir, file_name)
        try:
            os.makedirs(dst_dir, exist_ok=True)
            if operation == "move": shutil.move(src_file, target_path)
            else: shutil.copy2(src_file, target_path)
            log(f"Processed ({processed_count+1}): {file_name}")
            processed_count += 1
        except Exception as e: log(f"Gagal memproses {file_name} | {e}", "ERROR")

    # Mode Execution
    if os.path.isfile(src):
        if should_process(src, os.path.basename(src), 1):
            safe_operation(src, dst)
    elif os.path.isdir(src):
        # Kumpulkan file dan urutkan
        all_files = []
        if mode == "flat":
            for item in os.listdir(src):
                p = os.path.join(src, item)
                if os.path.isfile(p) and not (skip_hidden and is_hidden(p)): all_files.append((p, item, src))
        else:
            for root, dirs, files in os.walk(src):
                if skip_hidden: dirs[:] = [d for d in dirs if not is_hidden(os.path.join(root, d))]
                for f in files:
                    p = os.path.join(root, f)
                    if not (skip_hidden and is_hidden(p)): all_files.append((p, f, root))

        all_files.sort(key=lambda x: x[1]) # Sort by filename

        for file_path, file_name, root_dir in all_files:
            current_index += 1
            if should_process(file_path, file_name, current_index):
                target_subdir = dst if flatten else os.path.join(dst, os.path.relpath(root_dir, src))
                safe_operation(file_path, target_subdir)

        if operation == "move": remove_empty_dirs(src)

    log(f"Selesai. Memproses total {processed_count} file.", "SUCCESS")

# ============================================================
# 🚀 RUN
# ============================================================
move_or_copy_path(source_path, target_folder, operation_type, move_mode, file_ext,
                  skip_hidden, flatten_structure, filter_by_size, size_in_gb,
                  size_mode, filter_by_index, index_range)