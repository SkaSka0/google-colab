#@title 🔪 Split Audio FFmpeg
#@markdown Metode ini menggunakan FFmpeg langsung melalui terminal sistem.
#@markdown RAM Python tidak akan penuh meskipun file audio berdurasi berjam-jam.

import subprocess
import os
import json
import math

from google.colab import drive

# ======== AUTO MOUNT GOOGLE DRIVE JIKA DIPAKAI ========
def ensure_drive_mounted():
    """Mount Google Drive jika path mengandung /content/drive."""
    needs_mount = (
        input_file.startswith("/content/drive") or
        output_folder.startswith("/content/drive")
    )

    if not needs_mount:
        return  # Tidak perlu mount

    # Cek apakah sudah ada direktori MyDrive → indikator sudah ter-mount
    if not os.path.isdir("/content/drive/MyDrive"):
        print("🔌 Google Drive belum ter-mount… Memasang Google Drive...")
        drive.mount('/content/drive')
    else:
        print("🔌 Google Drive sudah ter-mount.")

# ======== INPUT USER ========
input_file = "/content/media_toolkit/audio/sistem_beranak_naik_level_bangun_klan_xiuxian_terkuat_audio.m4a" #@param {type:"string"}
output_folder = "/content/media_toolkit/audio_split" #@param {type:"string"}
chunk_duration = 1000 #@param {type:"number"} # detik
overlap = 2 #@param {type:"number"} # detik

# --- Dropdown Sample Rate ---
sample_rate = 16000  #@param ["16000", "22050"] {type:"raw"}

# ======== JALANKAN AUTO-MOUNT JIKA DIPERLUKAN ========
ensure_drive_mounted()

# ======== FUNGSI DURASI ========
def get_duration(file_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        output = subprocess.check_output(cmd).decode().strip()
        return float(output)
    except Exception as e:
        print(f"Error membaca durasi: {e}")
        return 0

# ======== SETUP ========
os.makedirs(output_folder, exist_ok=True)

if not os.path.exists(input_file):
    raise FileNotFoundError(f"Input file tidak ditemukan: {input_file}")

print("⏳ Menganalisis file...")
total_duration = get_duration(input_file)
print(f"Total Durasi: {total_duration:.2f} detik")

# Hitung jumlah potongan estimasi
step = chunk_duration - overlap
num_chunks = math.ceil(total_duration / step)

print(f"✂ Mulai memotong menjadi estimasi {num_chunks} bagian...")
print(f"🎧 Sample Rate: {sample_rate} Hz")
print("-" * 40)

# ======== PROSES SPLIT ========
current_start = 0
index = 1

while current_start < total_duration:
    filename = f"part_{index:03d}.wav"
    output_path = os.path.join(output_folder, filename)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(current_start),
        "-t", str(chunk_duration),
        "-i", input_file,
        "-ac", "1",
        "-ar", str(sample_rate),
        "-loglevel", "error",
        output_path
    ]

    try:
        subprocess.run(cmd, check=True)
        current_end = min(current_start + chunk_duration, total_duration)
        print(f"✔ Chunk {index:03d}: {current_start:.1f}s ➡ {current_end:.1f}s")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error pada chunk {index}: {e}")

    current_start += step
    index += 1

print("-" * 40)
print("✅ SELESAI!")
print(f"📂 Output folder: {output_folder}")