# @title 🎧 Perbaikan Channel Audio (Mono L/R/Average) untuk Audio & Video

# ---- 1. Fungsi Log Custom ----
def log(msg, status="INFO"):
    print(f"{status.upper()}:AudioFixer:{msg}")

# ---- 2. Install Dependency jika belum ada ----
log("Memeriksa dependency...")
import shutil
if shutil.which("ffmpeg") is None:
    log("ffmpeg tidak ditemukan, menginstal...", "WARN")
    !apt-get update -qq
    !apt-get install -y ffmpeg
else:
    log("ffmpeg ditemukan")

# ---- 3. Parameter Input ----
input_path = "/content/media_toolkit/audio_extract/pemuda_terakhir_penjaga_suku_audio.m4a"  # @param {type:"string"}
output_folder = "/content/media_toolkit/audio_fixed"  # @param {type:"string"}
output_name = "pemuda_terakhir_penjaga_suku_audio"        # @param {type:"string"}
mono_mode = "left"                 # @param ["left", "right", "average"]

# Membuat folder jika belum ada
import os
os.makedirs(output_folder, exist_ok=True)

# Deteksi ekstensi file input
ext = os.path.splitext(input_path)[1].lower()
output_path = f"{output_folder}/{output_name}{ext}"

log(f"Input     : {input_path}")
log(f"Output    : {output_path}")
log(f"Mode mono : {mono_mode}")

# ---- 4. Tentukan filter audio mono ----
if mono_mode == "left":
    filter_cmd = "pan=mono|c0=FL"
elif mono_mode == "right":
    filter_cmd = "pan=mono|c0=FR"
else:  # average
    filter_cmd = "pan=mono|c0=0.5*FL+0.5*FR"

log(f"FFmpeg Audio Filter: {filter_cmd}")

# ---- 5. Proses Jika Input adalah AUDIO ----
audio_ext = [".m4a", ".mp3", ".aac", ".wav", ".flac", ".ogg"]

if ext in audio_ext:
    log("Mode: Input adalah Audio")

    cmd_audio = (
        f'ffmpeg -y -i "{input_path}" -af "{filter_cmd}" '
        f'-c:a aac -b:a 192k "{output_path}"'
    )

    log("Memproses audio...")
    !{cmd_audio}
    log("Selesai memperbaiki audio.")
    log(f"File disimpan di: {output_path}")

else:
    # ---- 6. Proses Jika Input adalah VIDEO ----
    log("Mode: Input adalah Video")

    temp_audio = "/content/temp_audio.m4a"
    temp_audio_fixed = "/content/temp_audio_fixed.m4a"

    # Ekstrak audio
    log("Ekstrak audio (copy, tanpa re-encode)...")
    extract_cmd = f'ffmpeg -y -i "{input_path}" -vn -acodec copy "{temp_audio}"'
    !{extract_cmd}
    log("Audio berhasil diekstrak.")

    # Convert ke mono
    log("Mengubah audio menjadi mono...")
    fix_cmd = (
        f'ffmpeg -y -i "{temp_audio}" -af "{filter_cmd}" '
        f'-c:a aac -b:a 192k "{temp_audio_fixed}"'
    )
    !{fix_cmd}
    log("Audio mono selesai dibuat.")

    # Remux video dengan audio baru
    log("Remux video + audio baru...")
    remux_cmd = (
        f'ffmpeg -y -i "{input_path}" -i "{temp_audio_fixed}" '
        f'-map 0:v -map 1:a -c:v copy -c:a copy "{output_path}"'
    )
    !{remux_cmd}

    log("Remux selesai.")
    log(f"Video final tersimpan: {output_path}")

    # Hapus temp
    os.remove(temp_audio)
    os.remove(temp_audio_fixed)
    log("Temporary audio dibersihkan.")