# @title 🧠 Extract Video Metadata to JSON

import subprocess
import json
import os
import shutil

def log(message, level="INFO"):
    print(f"[{level}] {message}")

# 📥 User input
video_path = "/content/media_toolkit/video/snos_228_the_beautiful_delinquent_girl_i_saved_fell_in_love_with_me_and_i_repaid_her_kindness_with_a_passionate_kiss_riri_nanatsumori_sub.mkv"  # @param {type:"string"}
output_folder = "/content/media_toolkit/metadata"  # @param {type:"string"}
save_json = False  # @param {type:"boolean"}
indent_size = 2  # @param {type:"integer"}

# ✅ Validasi indent_size
if indent_size < 2:
    log("⚠️ indent_size terlalu kecil, diatur ke minimum (2)", level="WARNING")
    indent_size = 2
elif indent_size > 8:
    log("⚠️ indent_size terlalu besar, diatur ke maksimum (8)", level="WARNING")
    indent_size = 8

# ✅ Check if ffmpeg is installed
if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
    log("ffmpeg not found. Installing...")
    !apt-get update -y && apt-get install -y ffmpeg
    log("ffmpeg installed successfully.")
else:
    log("ffmpeg and ffprobe are available.")

# 🎨 Warna pakai ANSI escape code (ringan)
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"

def pretty_print_json(data, indent=0, step=4):
    prefix = " " * indent
    icon = "📁"  # bisa diganti sesuai selera

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{prefix}{BOLD}{CYAN}{icon} {key}:{RESET}")
                pretty_print_json(value, indent + step, step)
            else:
                print(f"{prefix}{YELLOW}{icon} {key}{RESET} : {GREEN}{value}{RESET}")
    elif isinstance(data, list):
        for item in data:
            pretty_print_json(item, indent, step)

def extract_metadata_to_json(video_path: str, output_folder: str = "metadata", save_json: bool = False, step: int = 4):
    # 🔍 Validate video file
    if not os.path.exists(video_path):
        log(f"File not found: {video_path}", level="ERROR")
        return

    # 🗂️ Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        log(f"Output folder not found. Creating: {output_folder}")
        os.makedirs(output_folder, exist_ok=True)

    log(f"Starting metadata extraction for: {video_path}")

    # 📄 Create JSON file name based on video name
    video_filename = os.path.basename(video_path)
    json_filename = os.path.splitext(video_filename)[0] + ".json"
    output_json_path = os.path.join(output_folder, json_filename)

    command = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        video_path
    ]

    try:
        log("Running ffprobe...")
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            log("Failed to run ffprobe.", level="ERROR")
            log(result.stderr.strip(), level="WARNING")
            return

        metadata = json.loads(result.stdout)

        log(f"{video_filename} Metadata:\n")
        # 🎨 Pretty print metadata ke console
        pretty_print_json(metadata, step=step)

        # 💾 Simpan ke file JSON jika dipilih
        if save_json:
            with open(output_json_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            log(f"✅ Metadata saved to: {output_json_path}")

        # return metadata

    except Exception as e:
        log(f"An error occurred: {e}", level="ERROR")

# 🚀 Run the function
extract_metadata_to_json(video_path, output_folder, save_json, indent_size)