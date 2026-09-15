#@title 🎧 Extract Original Audio
#@markdown - Script ini dapat mengekstrak audio dari **`satu video`** atau **`satu folder video`** (batch).
#@markdown - Tidak ada re-encode → kualitas audio tetap asli (copy codec).

import os
import subprocess
import shutil
import sys

# ✅ Unified Logging
def log(message, level="INFO"):
    print(f"{level}:AudioExtraction:{message}")

# 🔧 Pastikan ffmpeg tersedia
if not shutil.which("ffmpeg"):
    log("ffmpeg not found. Installing via apt...")
    subprocess.run(["apt-get", "update"])
    subprocess.run(["apt-get", "install", "-y", "ffmpeg"])
    if not shutil.which("ffmpeg"):
        log("ffmpeg installation failed.", "ERROR")
        sys.exit()
    else:
        log("ffmpeg installed successfully.")

# 🔄 Extract audio tanpa re-encode
def extract_audio(video_path, output_path, index=None, total=None):
    if not os.path.exists(video_path):
        log(f"File not found: {video_path}", "ERROR")
        return

    os.makedirs(output_path, exist_ok=True)

    progress = f"[{index+1}/{total}]" if index is not None and total is not None else ""
    base_name = os.path.splitext(os.path.basename(video_path))[0]

    # 🔍 Deteksi codec audio bawaan
    probe_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name", "-of", "default=nokey=1:noprint_wrappers=1",
        video_path
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    codec = result.stdout.strip()

    # Tentukan ekstensi berdasarkan codec
    codec_to_ext = {
        "aac": "m4a",
        "mp3": "mp3",
        "opus": "opus",
        "vorbis": "ogg",
        "flac": "flac",
        "wav": "wav"
    }

    if codec:
        ext = codec_to_ext.get(codec, "m4a")
    else:
        codec = "unknown"
        ext = "m4a"
        log(f"{progress} ⚠️ Could not detect audio codec, using fallback extension '.m4a'", "WARNING")

    audio_name = f"{base_name}_audio.{ext}"
    audio_path = os.path.join(output_path, audio_name)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",             # no video
        "-acodec", "copy", # copy audio asli
        audio_path
    ]

    log(f"{progress} Input Video: {video_path}")
    log(f"{progress} Detected Audio Codec: {codec}")
    log(f"{progress} Output Audio: {audio_path}")
    log(f"{progress} Extracting audio (no re-encode)...")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        log(f"{progress} Audio extracted successfully.", "SUCCESS")
    else:
        log(f"{progress} Failed to extract audio", "ERROR")
        print(result.stderr)

# 📁 Batch process folder
def process_folder(folder_path, output_path):
    video_files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith(('.mp4', '.mkv', '.webm', '.mov'))
    ]

    log(f"Folder mode: processing {len(video_files)} video files in: {folder_path}")
    for idx, fpath in enumerate(sorted(video_files)):
        extract_audio(fpath, output_path, index=idx, total=len(video_files))
    log("All files in the folder have been processed.", "SUCCESS")

# 📌 Input Form (Colab)
video_input_path = ""  # @param {type:"string"}
output_path = "/content/media_toolkit/audio_extract"  # @param {type:"string"}

# 🚀 Execution
if os.path.isdir(video_input_path):
    process_folder(video_input_path, output_path)
elif os.path.isfile(video_input_path):
    extract_audio(video_input_path, output_path)
else:
    log("Input path not found!", "ERROR")