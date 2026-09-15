# @title 🎧 Convert Audio ke AAC
# @markdown Script ini mengonversi audio ke format AAC dengan log terstruktur.

import os
import subprocess

# ==============================
# CONFIG
# ==============================
APPNAME = "AudioCoverter"

def log(message, level="INFO"):
    print(f"{level}:{APPNAME}: {message}")

# ==============================
# INPUT PARAM
# ==============================
input_file = "/content/media_toolkit/audio_merge/hidup_kembali_dengan_3_istri.wav"  # @param {type:"string"}
output_folder = "/content/media_toolkit/audio_convert"  # @param {type:"string"}

# ==============================
# MAIN PROCESS
# ==============================

# 1. Validasi input file
if not os.path.isfile(input_file):
    log(f"Input file tidak ditemukan: {input_file}", "ERROR")
    raise SystemExit()

# 2. Membuat folder output jika belum ada
os.makedirs(output_folder, exist_ok=True)
log(f"Output folder siap: {output_folder}")

# 3. Menyusun nama file output
basename = os.path.splitext(os.path.basename(input_file))[0]
output_path = os.path.join(output_folder, f"{basename}_aac.m4a")

log(f"Input:  {input_file}")
log(f"Output: {output_path}")

# 4. Hitung ukuran file input
input_size = os.path.getsize(input_file) / (1024 * 1024)

# 5. Proses konversi AAC
log("Mengonversi audio ke AAC...")
cmd = [
    "ffmpeg",
    "-y",
    "-i", input_file,
    "-vn",
    "-c:a", "aac",
    "-b:a", "192k",
    output_path
]

process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# 6. Cek apakah sukses
if process.returncode != 0:
    log("Konversi gagal!", "ERROR")
    log(process.stderr, "ERROR")
    raise SystemExit()

log("Konversi selesai!")

# 7. Hitung ukuran file output
output_size = os.path.getsize(output_path) / (1024 * 1024)

# 8. Tampilkan status akhir
log(f"Ukuran input  : {input_size:.2f} MB")
log(f"Ukuran output : {output_size:.2f} MB")
log("Proses selesai tanpa error.")