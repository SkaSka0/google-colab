#@title 🧹 Delete Files by Extension, Size, Index Pattern, or All
folder_path = "/content/media_toolkit"  #@param {type:"string"}
#@markdown ---
delete_by_extension = True  #@param {type:"boolean"}
delete_exts = ".zip"  #@param ["", ".mp4,.mkv", ".jpg,.png", ".txt"] {allow-input: true}
#@markdown ---
delete_by_size = False  #@param {type:"boolean"}
min_size_gb = 2  #@param {type:"number"}
size_mode = "smaller"  #@param ["larger", "smaller"]
#@markdown ---
delete_by_index = False  #@param {type:"boolean"}
index_pattern = "3-23"  #@param {type:"string"}
#@markdown ---
debug_mode = True  #@param {type:"boolean"}

recursive_mode = False  #@param {type:"boolean"}

import os
import shutil
import re

# ============================================================
# 📜 Custom Logging (Seragam)
# ============================================================
APPNAME = "FileCleaner"

def log(message, level="INFO"):
    print(f"{level}:{APPNAME}:{message}")

# ============================================================
# 📏 Helpers
# ============================================================
def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} PB"

def get_size_gb(filepath):
    return os.path.getsize(filepath) / (1024 ** 3)

def list_all_files(folder):
    """List file sesuai mode: flat atau recursive."""
    file_list = []

    if recursive_mode:
        for root, dirs, files in os.walk(folder):
            for file in sorted(files):
                file_list.append(os.path.join(root, file))
    else:
        # Flat-only: hanya file di folder root
        for file in sorted(os.listdir(folder)):
            full = os.path.join(folder, file)
            if os.path.isfile(full):
                file_list.append(full)

    return file_list

def print_folder_summary(folder):
    total_files = 0
    total_size = 0

    if recursive_mode:
        iterator = os.walk(folder)
    else:
        iterator = [(folder, [], [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))])]

    for root, dirs, files in iterator:
        for file in files:
            total_files += 1
            try:
                total_size += os.path.getsize(os.path.join(root, file))
            except:
                pass

    mode = "Recursive" if recursive_mode else "Flat"
    log(f"📁 Mode: {mode}")
    log(f"Folder path : {folder}")
    log(f"Total files : {total_files}")
    log(f"Total size  : {format_size(total_size)}")

# ============================================================
# 🧠 Filter Logic
# ============================================================
def should_delete(filepath, extensions, size_threshold_gb, mode):
    name_check = False
    size_check = False
    ext_info = ""
    size_info = ""

    ext = os.path.splitext(filepath)[1].lower()

    if delete_by_extension:
        if extensions:
            name_check = ext in extensions
        ext_info = "✅" if name_check else "❌"

    if delete_by_size:
        size_gb = get_size_gb(filepath)
        if mode == "larger":
            size_check = size_gb >= size_threshold_gb
        else:
            size_check = size_gb <= size_threshold_gb
        size_info = "✅" if size_check else "❌"

    if delete_by_extension and delete_by_size:
        decision = name_check and size_check
    elif delete_by_extension:
        decision = name_check
    elif delete_by_size:
        decision = size_check
    else:
        decision = False

    return decision, ext_info, size_info

# ============================================================
# 🔢 Parse Index Pattern
# ============================================================
def parse_index_pattern(pattern: str, total_files: int):
    indexes = set()
    tokens = [t.strip() for t in re.split(r'[,\s]+', pattern) if t.strip()]
    for token in tokens:
        if '-' in token:
            try:
                start, end = token.split('-', 1)
                start, end = int(start), int(end)
                if start > end:
                    start, end = end, start
                for i in range(start, end + 1):
                    if 1 <= i <= total_files:
                        indexes.add(i)
            except:
                continue
        else:
            try:
                i = int(token)
                if 1 <= i <= total_files:
                    indexes.add(i)
            except:
                continue
    return sorted(indexes)

# ============================================================
# 🗑️ Delete by Index Pattern
# ============================================================
def delete_files_by_index_pattern(folder, pattern):
    all_files = list_all_files(folder)
    if not all_files:
        log("⚠️ Tidak ada file di folder.", "WARNING")
        return

    targets = parse_index_pattern(pattern, len(all_files))
    if not targets:
        log(f"⚠️ Tidak ada index valid dari pola: {pattern}", "WARNING")
        return

    log(f"🗑️ Menghapus file berdasarkan pola: {pattern}")
    log(f"🎯 Target index: {targets}")

    deleted_size = 0
    for i in targets:
        filepath = all_files[i - 1]
        file = os.path.basename(filepath)
        try:
            size_gb = get_size_gb(filepath)
            os.remove(filepath)
            deleted_size += size_gb
            log(f"[{i}] Deleted: {file} ({size_gb:.2f} GB)")
        except Exception as e:
            log(f"[{i}] Gagal menghapus {file}: {e}", "ERROR")

    log(f"Total terhapus: {len(targets)} file ({deleted_size:.2f} GB)")

# ============================================================
# 🗑️ Delete by Ext/Size
# ============================================================
def delete_files(folder, extensions, size_threshold_gb, mode):
    deleted_count = 0
    deleted_size = 0
    skipped = []

    all_files = list_all_files(folder)
    for idx, filepath in enumerate(all_files, start=1):
        file = os.path.basename(filepath)
        size_gb = get_size_gb(filepath)
        decision, ext_info, size_info = should_delete(filepath, extensions, size_threshold_gb, mode)

        if debug_mode:
            log(f"[{idx}] 🔎 {file} | {size_gb:.2f} GB | Ext:{ext_info} | Size:{size_info} | Delete:{'✅' if decision else '❌'}")

        if decision:
            try:
                os.remove(filepath)
                deleted_count += 1
                deleted_size += size_gb
                log(f"🗑️ Deleted: {file} ({size_gb:.2f} GB)")
            except Exception as e:
                log(f"Gagal hapus {file}: {e}", "ERROR")
        else:
            skipped.append(file)

    log(f"Deleted {deleted_count} file(s) ({deleted_size:.2f} GB)")

# ============================================================
# 🧹 Delete Entire Folder (tetap recursive)
# ============================================================
def delete_entire_folder(folder):
    if not os.path.exists(folder):
        log(f"Folder not found: {folder}", "ERROR")
        return

    print_folder_summary(folder)
    log("Deleting entire folder...")

    try:
        shutil.rmtree(folder)
        log(f"Folder deleted: {folder}")
    except Exception as e:
        log(f"Failed to delete folder: {e}", "ERROR")

# ============================================================
# 🚀 Eksekusi utama
# ============================================================
extensions = [ext.strip().lower() for ext in delete_exts.split(",") if ext.strip()]
size_threshold_gb = float(min_size_gb)

if delete_by_index:
    delete_files_by_index_pattern(folder_path, index_pattern)

elif delete_by_extension or delete_by_size:
    if os.path.isdir(folder_path):
        print_folder_summary(folder_path)
        delete_files(folder_path, extensions, size_threshold_gb, size_mode)
    else:
        log("Folder tidak valid!", "ERROR")

else:
    delete_entire_folder(folder_path)