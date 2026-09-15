# @title 📝 Muxing Subtitle to Video (Softsub MKV - Enhanced)
import subprocess
import shutil
import os

# ✅ Unified Logging
def log(message: str, level: str = "INFO"):
    print(f"{level}:SubtitleMuxing:{message}")

# Check and install ffmpeg if not found
if not shutil.which("ffmpeg"):
    log("ffmpeg not found. Installing via apt...")
    subprocess.run(["apt-get", "update"])
    subprocess.run(["apt-get", "install", "-y", "ffmpeg"])
    if not shutil.which("ffmpeg"):
        log("ffmpeg installation failed.", "ERROR")
    else:
        log("ffmpeg installed successfully.")

#@markdown 📌 Input Paths
video_input = "/content/media_toolkit/downloads/videos"  # @param {type:"string"}
subtitle_input = "/content/media_toolkit/uploads"  # @param {type:"string"}
output_folder = "/content/media_toolkit/video"  # @param {type:"string"}
subtitle_lang = "ind"  # @param ["ind", "eng", "zho", "jpn", "kor"]

#@markdown 🛠 Pengaturan Subtitle Tanpa Ekstensi
tambahkan_ekstensi = True # @param {type:"boolean"}
format_subtitle = ".vtt" # @param [".srt", ".vtt", ".ass", ".ssa", ".sub", ".txt"]

#@markdown 🔽 Dropdown: aksi setelah mux selesai
cleanup_action = "delete_both"  # @param ["delete_video", "delete_subtitle", "delete_both", "keep_all"]

def is_file(path: str) -> bool:
    return os.path.isfile(path)

# 🔧 Mux a subtitle into a single video file
def mux_subtitle(video_path, subtitle_path, output_path, index=None, total=None):
    if not os.path.exists(video_path):
        log("Video file not found!", "ERROR")
        return
    if not os.path.exists(subtitle_path):
        log("Subtitle file not found!", "ERROR")
        return

    os.makedirs(output_path, exist_ok=True)
    progress = f"[{index+1}/{total}]" if index is not None else ""

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_file = os.path.join(output_path, f"{base_name}_sub.mkv")

    log(f"{progress} Processing: {os.path.basename(video_path)} with {os.path.basename(subtitle_path)}")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", subtitle_path,
        "-map", "0",
        "-map", "1:s:0",
        "-c", "copy",
        "-metadata:s:s:0", f"language={subtitle_lang}",
        output_file
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        log(f"{progress} Subtitle successfully muxed.", "SUCCESS")
        perform_cleanup(video_path, subtitle_path)
    else:
        log(f"{progress} Failed to mux subtitle.", "ERROR")
        print(result.stderr)

# 🧹 Cleanup function
def perform_cleanup(video_path, subtitle_path):
    if cleanup_action == "delete_video":
        if os.path.exists(video_path):
            os.remove(video_path)
            log(f"Deleted source video: {video_path}", "WARNING")
    elif cleanup_action == "delete_subtitle":
        if os.path.exists(subtitle_path):
            os.remove(subtitle_path)
            log(f"Deleted subtitle file: {subtitle_path}", "WARNING")
    elif cleanup_action == "delete_both":
        removed = []
        if os.path.exists(video_path):
            os.remove(video_path)
            removed.append("video")
        if os.path.exists(subtitle_path):
            os.remove(subtitle_path)
            removed.append("subtitle")
        if removed:
            log(f"Deleted source file(s): {', '.join(removed)}", "WARNING")
    else:
        log("No source files deleted (keep_all).")

# 🚀 Preview pairing sebelum muxing
# 🚀 Preview pairing sebelum muxing dengan nama yang di-truncate
def preview_pairs(video_files, subtitle_files, max_len=30):
    total = min(len(video_files), len(subtitle_files))
    log("Preview pairing video ↔ subtitle:")

    def truncate(text, length):
        if len(text) > length:
            return text[:length-3] + "..."
        return text

    for i in range(total):
        v = os.path.basename(video_files[i])
        s = os.path.basename(subtitle_files[i])

        # Terapkan truncate hanya untuk tampilan
        v_display = truncate(v, max_len)
        s_display = truncate(s, max_len)

        print(f"  [{i+1}] {v_display:<{max_len}} ↔ {s_display}")

    if len(video_files) != len(subtitle_files):
        log("⚠️ Jumlah video dan subtitle berbeda, hanya diproses hingga jumlah minimum.", "WARNING")

# 🚀 Batch process
def batch_mux_subtitles(video_input, subtitle_input, output_folder):
    video_files = [video_input] if is_file(video_input) else sorted([
        os.path.join(video_input, f) for f in os.listdir(video_input)
        if f.lower().endswith((".mp4", ".mkv", ".webm", ".mov"))
    ])

    subtitle_files = [subtitle_input] if is_file(subtitle_input) else sorted([
        os.path.join(subtitle_input, f) for f in os.listdir(subtitle_input)
    ])

    log(f"Video files found: {len(video_files)}")
    log(f"Subtitle files found: {len(subtitle_files)}")

    preview_pairs(video_files, subtitle_files)

    total = min(len(video_files), len(subtitle_files))

    for i in range(total):
        v_path = video_files[i]
        s_path = subtitle_files[i]

        # Logika tambahan ekstensi
        target_s_path = s_path
        created_temp_sub = False
        if tambahkan_ekstensi and not os.path.splitext(s_path)[1]:
            target_s_path = s_path + format_subtitle
            shutil.copy2(s_path, target_s_path)
            created_temp_sub = True

        mux_subtitle(v_path, target_s_path, output_folder, index=i, total=total)

        # Cleanup file temp jika dibuat
        if created_temp_sub and os.path.exists(target_s_path):
            os.remove(target_s_path)

    log("All files have been successfully processed.", "SUCCESS")

# 🚀 Run
batch_mux_subtitles(video_input, subtitle_input, output_folder)