#@title 🎛️ Merge Audio dengan Crossfade (Updated: List Files)
import subprocess
import os
import glob
import json

# --- Konfigurasi ---
input_folder = "/content/media_toolkit/audio_vocals" #@param {type:"string"}
output_filename = "/content/media_toolkit/audio_merge/hidup_kembali_dengan_3_istri.wav" #@param {type:"string"}
#@markdown Durasi transisi (detik)
crossfade_duration = 2 #@param {type:"number"}

# --- Validasi ---
if not os.path.exists(input_folder):
    raise FileNotFoundError(f"Folder tidak ditemukan: {input_folder}")

# Buat folder output jika belum ada
output_dir = os.path.dirname(output_filename)
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 1. Ambil list file dan urutkan
files = sorted([
    os.path.join(input_folder, f)
    for f in os.listdir(input_folder)
    if f.lower().endswith(('.wav', '.mp3', '.m4a'))
])

if len(files) < 2:
    print("❌ Error: Butuh minimal 2 file audio untuk melakukan merge.")
else:
    print(f"📂 Ditemukan {len(files)} file audio:")

    # --- [TAMBAHAN BARU] Menampilkan List File ---
    for idx, fpath in enumerate(files, 1):
        filename = os.path.basename(fpath)
        print(f"   {idx}. {filename}")
    print("-" * 50)
    # ---------------------------------------------

    print(f"🔗 Menyiapkan perintah FFmpeg dengan crossfade {crossfade_duration}s...")

    # --- 2. Membangun Perintah FFmpeg ---
    cmd_input = []

    # Masukkan semua input file
    for f in files:
        cmd_input.extend(["-i", f])

    filter_complex = ""

    # Inisialisasi label input pertama (file ke-0)
    last_output_label = "[0]"

    # Loop mulai dari file kedua (index 1) sampai akhir
    for i in range(1, len(files)):
        current_input_label = f"[{i}]"
        new_output_label = f"[a{i:02d}]"

        # Tentukan separator (titik koma kecuali di akhir)
        separator = ";" if i < len(files) - 1 else ""

        # Rakit filter: Input Lama + Input Baru -> Output Baru
        filter_complex += f"{last_output_label}{current_input_label}acrossfade=d={crossfade_duration}:c1=tri:c2=tri{new_output_label}{separator}"

        # Update label output terakhir untuk iterasi berikutnya
        last_output_label = new_output_label

    # --- 3. Eksekusi FFmpeg ---
    cmd = [
        "ffmpeg", "-y",
        *cmd_input,
        "-filter_complex", filter_complex,
        "-map", last_output_label, # Map label terakhir yang dihasilkan loop
        output_filename
    ]

    try:
        print("🚀 Memproses merge (ini mungkin memakan waktu tergantung durasi)...")
        # Tambahkan capture_output=True dan text=True agar bisa menangkap pesan error
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ SUKSES! File tersimpan di: {output_filename}")

        # --- Tambahan: Status File Output ---
        print("\n📊 Mengambil metadata file dengan ffprobe...")

        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", output_filename
        ]

        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        metadata = json.loads(result.stdout)

        # --- Ambil metadata utama ---
        fmt = metadata.get("format", {})
        streams = metadata.get("streams", [])

        audio_stream = None
        for s in streams:
            if s.get("codec_type") == "audio":
                audio_stream = s
                break

        print("\n================= 📝 STATUS FILE OUTPUT =================")
        print(f"📁 Filename      : {os.path.basename(output_filename)}")
        print(f"💾 File Size     : {os.path.getsize(output_filename)/(1024*1024):.2f} MB")
        if fmt:
            print(f"⏱️ Duration      : {float(fmt.get('duration', 0)):.2f} seconds")
            print(f"🔊 Bitrate       : {int(fmt.get('bit_rate', 0))/1000:.0f} kbps")
        print("=========================================================\n")

    except subprocess.CalledProcessError as e:
        print("\n❌ Terjadi kesalahan CRITICAL pada FFmpeg.")
        print("🔍 PESAN ERROR ASLI (STDERR):")
        print("-" * 20)
        # Menampilkan 20 baris terakhir dari error log agar tidak terlalu panjang
        error_lines = e.stderr.splitlines()
        print("\n".join(error_lines[-20:]))
        print("-" * 20)