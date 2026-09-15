# @title ✂️ Cut Start of Video (With Delete Option)
import os
import shutil
import subprocess
import sys

# Konfigurasi Logging Custom
APPNAME = "VideoCutter"

def log(message, level="INFO"):
    print(f"{level}:{APPNAME}:{message}")

def check_and_install_dependency():
    """Mengecek apakah FFmpeg terinstall, jika tidak maka install."""
    log("Mengecek dependency sistem...", "INFO")
    if shutil.which("ffmpeg") is None:
        log("FFmpeg tidak ditemukan. Menginstall FFmpeg...", "WARN")
        try:
            subprocess.run(["apt-get", "update", "-qq"], check=True)
            subprocess.run(["apt-get", "install", "-y", "ffmpeg", "-qq"], check=True)
            log("FFmpeg berhasil diinstall.", "INFO")
        except subprocess.CalledProcessError as e:
            log(f"Gagal menginstall FFmpeg: {e}", "ERROR")
            sys.exit(1)
    else:
        log("FFmpeg sudah terinstall.", "INFO")

def ensure_folder_exists(folder_path):
    """Memastikan folder output tersedia."""
    if not os.path.exists(folder_path):
        log(f"Folder output tidak ditemukan. Membuat folder: {folder_path}", "WARN")
        try:
            os.makedirs(folder_path, exist_ok=True)
            log(f"Folder berhasil dibuat.", "SUCCESS")
        except OSError as e:
            log(f"Gagal membuat folder: {e}", "ERROR")
            sys.exit(1)
    else:
        log(f"Folder output ditemukan: {folder_path}", "INFO")

def get_output_filepath(input_path, output_dir):
    """Membuat path output dengan suffix _cut."""
    filename = os.path.basename(input_path)
    name, ext = os.path.splitext(filename)
    new_name = f"{name}_cut{ext}"
    return os.path.join(output_dir, new_name)

# --- USER INPUT (Forms) ---
video_path = "/content/downloads/video/orang_bijak_tersembunyi_menantu_diremehkan_ternyata_penasehat_terbaik.mp4" # @param {type:"string"}
output_folder = "/content/media_toolkit/cut_start" # @param {type:"string"}
cut_start_seconds = 3 # @param {type:"number"}
delete_source = False # @param {type:"boolean"}

# --- MAIN PROCESS ---
def process_video(input_file, start_time, out_folder, delete_after):
    # 1. Validasi Input File
    if not os.path.exists(input_file):
        log(f"File input tidak ditemukan: {input_file}", "ERROR")
        return

    # 2. Cek Dependency
    check_and_install_dependency()

    # 3. Siapkan Folder Output
    ensure_folder_exists(out_folder)

    # 4. Tentukan Nama File Output
    output_file = get_output_filepath(input_file, out_folder)

    log(f"Memulai proses pemotongan...", "INFO")
    log(f"Input: {input_file}", "INFO")
    log(f"Membuang detik 0 sampai {start_time}", "INFO")
    log(f"Target Output: {output_file}", "INFO")

    # 5. Susun Command FFmpeg
    command = [
        "ffmpeg",
        "-y",                 # Overwrite output tanpa tanya
        "-ss", str(start_time), # Seek ke posisi start
        "-i", input_file,     # Input file
        "-c", "copy",         # Copy stream (No Re-encode)
        "-avoid_negative_ts", "1",
        "-hide_banner",
        "-loglevel", "error",
        output_file
    ]

    try:
        # Jalankan command
        log(f"Menjalankan FFmpeg...", "DEBUG")
        subprocess.run(command, check=True, capture_output=True, text=True)

        # 6. Validasi Output & Hapus Source (Opsional)
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            file_size = os.path.getsize(output_file) / (1024 * 1024) # MB
            log(f"Proses selesai! File tersimpan.", "SUCCESS")
            log(f"Lokasi Final: {output_file} ({file_size:.2f} MB)", "INFO")

            # --- LOGIKA HAPUS FILE SUMBER ---
            if delete_after:
                log("Opsi hapus sumber aktif. Menghapus file input...", "WARN")
                try:
                    os.remove(input_file)
                    log(f"File sumber berhasil dihapus: {input_file}", "SUCCESS")
                except OSError as e:
                    log(f"Gagal menghapus file sumber: {e}", "ERROR")
            # -------------------------------

        else:
            log("FFmpeg berjalan tapi file output kosong atau tidak ditemukan.", "ERROR")

    except subprocess.CalledProcessError as e:
        log(f"Terjadi kesalahan saat memproses video.", "ERROR")
        log(f"FFmpeg Error: {e.stderr}", "ERROR")

# Jalankan Fungsi Utama
if __name__ == "__main__":
    process_video(video_path, cut_start_seconds, output_folder, delete_source)