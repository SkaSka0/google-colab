#@title 🎵 Pemisahan Vokal & Instrumen (Support Batch/Folder)
#@markdown - Script ini mendukung input berupa **`File Tunggal`** maupun **`Satu Folder`** penuh.
#@markdown - Proses berjalan antrian (satu selesai, lanjut berikutnya).

import os
import sys
import time
import shutil
import datetime
import threading
import subprocess
from pathlib import Path
from collections import deque
import torch
from google.colab import drive

# ==========================================
# 0. KONFIGURASI GLOBAL & LOGGING
# ==========================================
APPNAME = "DemucsProBatch"

def get_timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S")

def log(msg: str, status: str = "INFO"):
    print(f"{status}:{APPNAME}: {msg}", flush=True)

def ensure_drive_mounted(path_str: str):
    if "/content/drive" not in path_str:
        return
    if not os.path.isdir("/content/drive/MyDrive"):
        log("Menghubungkan ke Google Drive...", "SETUP")
        drive.mount('/content/drive')
        log("Google Drive berhasil terhubung.", "SUCCESS")

def log_system_stats():
    if torch.cuda.is_available():
        free_mem, total_mem = torch.cuda.mem_get_info()
        log(f"GPU Memory: Bebas {free_mem/1024**3:.2f} GB / Total {total_mem/1024**3:.2f} GB", "SYSTEM")
    else:
        log("Menggunakan CPU (Waspada lambat/timeout)", "SYSTEM")

# ==========================================
# 1. FUNGSI UTAMA (CORE FUNCTIONS)
# ==========================================

def setup_environment():
    if shutil.which("demucs") is None:
        log("Demucs tidak ditemukan. Menginstal...", "SETUP")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-U", "demucs"],
                           check=True, stdout=subprocess.DEVNULL)
            log("Instalasi Demucs berhasil.", "SUCCESS")
        except subprocess.CalledProcessError:
            log("Gagal menginstal Demucs.", "ERROR")
            sys.exit(1)

def build_demucs_command(file_path: Path, output_dir: Path, model: str, fmt: str, vocals_only: bool):
    cmd = ["demucs", "-n", model, "-o", str(output_dir), "-j", "2", str(file_path)]
    if fmt == "mp3":
        cmd.extend(["--mp3", "--mp3-bitrate", "320"])
    elif fmt == "wav":
        cmd.append("--float32")
    if vocals_only:
        cmd.append("--two-stems=vocals")
    return cmd

def process_single_file(file_path: Path, output_dir: Path, model: str, fmt: str, vocals_only: bool):
    """Memproses satu file audio dengan Timer Real-time."""
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    log(f"Memproses: {file_path.name} ({file_size_mb:.2f} MB)", "PROCESS")

    cmd = build_demucs_command(file_path, output_dir, model, fmt, vocals_only)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

    error_buffer = deque(maxlen=20)

    # --- SETUP TIMER VARIABLES ---
    start_time = time.time()
    stop_timer = threading.Event()
    current_progress = ["Menunggu Demucs..."] # Menggunakan list agar mutable (bisa diubah dalam thread)

    # Fungsi Timer yang berjalan di background
    def timer_loop():
        while not stop_timer.is_set():
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            time_str = f"{mins:02d}:{secs:02d}"

            # Ambil status progress terakhir dari Demucs (jika ada)
            status_msg = current_progress[0]

            # Print dalam satu baris menggunakan \r (Carriage Return)
            # ljust(100) digunakan untuk membersihkan sisa karakter lama jika teks memendek
            sys.stdout.write(f"\rPROCESS:{APPNAME}: [ {time_str} ] {status_msg}".ljust(100))
            sys.stdout.flush()
            time.sleep(0.5) # Update setiap 0.5 detik

    try:
        process = subprocess.Popen(
            cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1
        )

        # Jalankan Timer Thread
        t = threading.Thread(target=timer_loop)
        t.start()

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                error_buffer.append(line)
                clean_line = line.strip()
                # Update variable progress jika ada angka persen atau kata Separated
                if "%" in clean_line or "Separated" in clean_line:
                    current_progress[0] = clean_line

        return_code = process.poll()

        # Matikan Timer
        stop_timer.set()
        t.join()

        print() # Cetak baris baru agar log "Berhasil" tidak menimpa timer terakhir

        if return_code == 0:
            log(f"Berhasil: {file_path.name}", "SUCCESS")
            return True
        else:
            log(f"Gagal memproses {file_path.name} (Code: {return_code})", "ERROR")
            print("="*20 + " CRASH REPORT " + "="*20)
            print("..." + "".join(error_buffer))
            return False

    except Exception as e:
        if 'stop_timer' in locals(): stop_timer.set()
        log(f"Exception pada file {file_path.name}: {e}", "CRITICAL")
        return False

def run_batch_processing(input_str: str, output_str: str, model: str, fmt: str, vocals_only: bool):
    """Mengatur logika Batch vs Single File."""

    # 1. Mount Drive & Cek Path
    ensure_drive_mounted(input_str)
    ensure_drive_mounted(output_str)

    input_path = Path(input_str)
    output_path = Path(output_str)
    output_path.mkdir(parents=True, exist_ok=True)

    log_system_stats()

    files_to_process = []

    # 2. Deteksi Folder vs File
    if input_path.is_dir():
        log(f"Mendeteksi Folder. Scanning file audio...", "BATCH")
        valid_ext = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma'}
        # Mengambil semua file yang ekstensinya valid
        files_to_process = [
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in valid_ext
        ]
        files_to_process.sort() # Urutkan nama file
        log(f"Ditemukan {len(files_to_process)} file audio dalam folder.", "BATCH")
    elif input_path.is_file():
        log(f"Mendeteksi Single File.", "SINGLE")
        files_to_process = [input_path]
    else:
        log(f"Input tidak ditemukan: {input_str}", "ERROR")
        return

    # 3. Eksekusi Loop
    success_count = 0
    total = len(files_to_process)

    print("-" * 60)
    for i, file_obj in enumerate(files_to_process, 1):
        log(f"Antrian [{i}/{total}]", "QUEUE")
        result = process_single_file(file_obj, output_path, model, fmt, vocals_only)

        if result:
            success_count += 1
            # Optional: Clear GPU memory after each file to prevent buildup
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        print("-" * 60)

    log(f"Selesai! Berhasil memproses {success_count} dari {total} file.", "FINISH")


# ==========================================
# 2. PARAMETER INPUT
# ==========================================
# BISA MASUKKAN PATH FILE .WAV ATAU PATH FOLDER
input_source = "/content/media_toolkit/audio_extract" # @param {type:"string"}
output_folder = "/content/media_toolkit" # @param {type:"string"}
model_name = "htdemucs" # @param ["htdemucs", "htdemucs_ft", "mdx_extra_q"]
pisahkan_vokal_saja = True # @param {type:"boolean"}
format_output = "mp3" # @param ["mp3", "wav"]

# ==========================================
# 3. RUNTIME EXECUTION
# ==========================================
if __name__ == "__main__":
    setup_environment()
    run_batch_processing(
        input_str=input_source,
        output_str=output_folder,
        model=model_name,
        fmt=format_output,
        vocals_only=pisahkan_vokal_saja
    )