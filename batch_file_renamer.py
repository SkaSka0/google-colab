#@title 📝 Batch File Renamer (Verbose + Preview)
import os
import sys

# ==============================
# 1. Logging Custom
# ==============================

APPNAME = "BatchFileRenamer"

def log(message: str, level: str = "INFO") -> None:
    print(f"{level}:{APPNAME}:{message}", flush=True)

# ==============================
# 2. Parameter Input (Colab UI)
# ==============================

#@markdown ### 🔧 Konfigurasi Rename
target_folder = "/content/media_toolkit/extracted/(Drakorasia) WYMM 720p"      #@param {type:"string"}
base_filename = "Would You Marry Me? 720p Eps"           #@param {type:"string"}
start_number = 1                      #@param {type:"integer"}
sort_files = False                     #@param {type:"boolean"}

# ==============================
# 3. Fungsi Rename
# ==============================

def batch_rename(folder: str, base_name: str, start_num: int = 1, sort_files: bool = True):
    log(f"Folder target: {folder}")
    log(f"Nama dasar: '{base_name}'")
    log(f"Nomor awal: {start_num}")
    log(f"Sorting file: {sort_files}")

    if not os.path.exists(folder):
        log("Folder tidak ditemukan!", "ERROR")
        return

    files = [
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    ]

    if not files:
        log("Tidak ada file untuk di-rename.", "WARNING")
        return

    if sort_files:
        files.sort()

    total_files = len(files)
    log(f"Total file terdeteksi: {total_files}")

    # Tentukan padding digit
    if total_files >= 100:
        padding = 3
    elif total_files >= 10:
        padding = 2
    else:
        padding = 2

    log(f"Padding nomor digunakan: {padding} digit")

    # ==============================
    # PREVIEW RENAME
    # ==============================
    rename_map = []

    for idx, filename in enumerate(files, start=start_num):
        name, ext = os.path.splitext(filename)
        new_name = f"{base_name} {str(idx).zfill(padding)}{ext}"
        rename_map.append((filename, new_name))
        # log(f"{filename}  →  {new_name}")

    # ==============================
    # PROSES RENAME
    # ==============================

    log("Memulai proses rename aktual...")

    for old_name, new_name in rename_map:
        old_path = os.path.join(folder, old_name)
        new_path = os.path.join(folder, new_name)

        try:
            os.rename(old_path, new_path)
            log(f"Renamed: {old_name} → {new_name}", "SUCCESS")
        except Exception as e:
            log(f"Gagal rename {old_name}: {str(e)}", "ERROR")

    log("Batch rename selesai.", "SUCCESS")

# ==============================
# 4. Eksekusi
# ==============================

if __name__ == "__main__":
    log("=== Proses batch rename dimulai ===")
    batch_rename(
        folder=target_folder,
        base_name=base_filename,
        start_num=start_number,
        sort_files=sort_files
    )
    log("=== Proses selesai ===")