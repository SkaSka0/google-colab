#@title 🎬 AUTO SPLIT VIDEO
import os
import subprocess
import shutil
import re
import math

# =============================================
# UTIL
# =============================================

def is_ffmpeg_installed():
    return shutil.which("ffmpeg") is not None

def install_ffmpeg():
    print("🔧 Install FFmpeg...")
    !apt-get update -qq && apt-get install -y ffmpeg > /dev/null 2>&1
    print("✅ FFmpeg siap")

def get_video_duration(input_path):
    """Ambil durasi video dalam detik"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())

def get_file_size_bytes(input_path):
    return os.path.getsize(input_path)

def seconds_to_hms(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# =============================================
# PROGRESS PARSER
# =============================================

def run_ffmpeg_with_progress(cmd, total_duration):
    process = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        text=True
    )

    time_pattern = re.compile(r"time=(\d+):(\d+):(\d+).(\d+)")

    while True:
        line = process.stderr.readline()
        if not line:
            break

        match = time_pattern.search(line)
        if match:
            h, m, s, ms = match.groups()
            current = int(h)*3600 + int(m)*60 + int(s)

            percent = (current / total_duration) * 100
            percent = min(percent, 100)
            bar_len = 10
            filled = int(round(bar_len * percent / 100))
            filled = min(max(filled, 0), bar_len)
            bar = "▰" * filled + "▱" * (bar_len - filled)

            print(f"\r📊 「{bar}」 {percent:5.1f}% ({seconds_to_hms(current)})", end="")

    process.wait()
    print()

# =============================================
# SPLIT FUNCTION
# =============================================

def split_video(input_path, output_dir, chunk_seconds, copy_streams=True):
    os.makedirs(output_dir, exist_ok=True)
    total_duration = get_video_duration(input_path)

    total_parts = math.ceil(total_duration / chunk_seconds)

    print(f"🎬 Durasi total: {seconds_to_hms(total_duration)}")
    print(f"✂️ Split durasi tiap part: {seconds_to_hms(chunk_seconds)}")
    print(f"📦 Total part (estimasi): {total_parts}")
    print("-" * 60)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    padding = len(str(total_parts))

    for i in range(total_parts):
        start = i * chunk_seconds
        duration = min(chunk_seconds, total_duration - start)

        if duration < 0.5: # Hindari file sisa yang terlalu kecil (micro-chunk)
            break

        output_path = os.path.join(
            output_dir,
            f"{base_name}_part_{i+1:0{padding}d}.mkv"
        )

        cmd = [
            "ffmpeg", "-y",
            "-ss", seconds_to_hms(start),
            "-i", input_path,
            "-t", str(duration),
            "-map", "0"
        ]

        if copy_streams:
            cmd.extend(["-c", "copy"])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-c:s", "copy"
            ])

        cmd.append(output_path)

        print(f"\n🚀 Proses Part {i+1}/{total_parts}")
        print(f"⏱️ {seconds_to_hms(start)} → {seconds_to_hms(start+duration)}")

        run_ffmpeg_with_progress(cmd, duration)
        print(f"✅ Selesai: {output_path}")

    print("\n🎉 Semua part selesai!")

# =============================================
# PARAM INPUT & VALIDATION
# =============================================

#@markdown ---
input_path = "/content/media_toolkit/cut_videos/waaa_422_if_you_can_withstand_suehiro_jun_s_amazing_technique_you_can_have_raw_creampie_sex_jun_suehiro_sub.mkv" #@param {type:"string"}
output_dir = "/content/media_toolkit/split_result" #@param {type:"string"}

#@markdown ### ⏱️ Mode Waktu
#@markdown > Masukkan Waktu dalam menit (contoh: 60=1 Jam)
cut_by_chunk_minutes = False #@param {type:"boolean"}
chunk_minutes = 60 #@param {type:"number"}

#@markdown ### 💾 Mode Ukuran File
#@markdown > Masukkan ukuran dalam MB (contoh: 500)
cut_by_size = False #@param {type:"boolean"}
target_size_mb = 1900 #@param {type:"number"}

#@markdown ---
copy_streams = True #@param {type:"boolean"}
#@markdown ---

print("🎬 AUTO SPLIT VIDEO\n")

if not os.path.isfile(input_path):
    print("❌ Error: File tidak ditemukan!")
    import sys
    sys.exit()

if not is_ffmpeg_installed():
    install_ffmpeg()
else:
    print("✅ FFmpeg ready")

print("-" * 60)

total_duration = get_video_duration(input_path)
chunk_seconds = 0

# LOGIKA PRIORITAS & VALIDASI
if cut_by_size and cut_by_chunk_minutes:
    print("⚠️ Anda mengaktifkan kedua mode. Mode UKURAN FILE akan diprioritaskan.")

if cut_by_size:
    if target_size_mb <= 0:
        print("❌ Error: Target ukuran tidak valid (harus lebih besar dari 0 MB).")
        import sys
        sys.exit()

    total_size_bytes = get_file_size_bytes(input_path)
    target_size_bytes = target_size_mb * 1024 * 1024

    if target_size_bytes >= total_size_bytes:
        print("⚠️ Peringatan: Target size melebihi ukuran file asli.")
        print("Mereset durasi potongan menjadi full durasi video.")
        chunk_seconds = total_duration
    else:
        # Hitung rasio ukuran file untuk estimasi durasi target (Bitrate konstan)
        size_ratio = target_size_bytes / total_size_bytes
        chunk_seconds = total_duration * size_ratio

        if chunk_seconds < 1:
            print(f"❌ Error: Target {target_size_mb} MB terlalu kecil! Menghasilkan durasi di bawah 1 detik.")
            import sys
            sys.exit()

elif cut_by_chunk_minutes:
    if chunk_minutes <= 0:
        print("⚠️ Durasi menit tidak valid, direset minimal ke 1 menit.")
        chunk_minutes = 1
    chunk_seconds = chunk_minutes * 60

else:
    print("❌ Error: Anda harus mencentang minimal salah satu mode (cut_by_chunk_minutes atau cut_by_size).")
    import sys
    sys.exit()

# EKSEKUSI
split_video(
    input_path=input_path,
    output_dir=output_dir,
    chunk_seconds=chunk_seconds,
    copy_streams=copy_streams
)