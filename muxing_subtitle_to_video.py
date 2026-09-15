# @title 📝 Muxing Subtitle to Video (Softsub MKV - Enhanced)
import subprocess
import shutil
import os
import json

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
video_input = "/content/media_toolkit/downloads/video"  # @param {type:"string"}
subtitle_input = "/content/media_toolkit/subtitle"  # @param {type:"string"}
output_folder = "/content/media_toolkit/video"  # @param {type:"string"}
subtitle_lang = "ind"  # @param ["ind", "eng", "zho", "jpn", "kor"]

#@markdown 🛠 Subtitle Settings Without Extension
add_extension = False # @param {type:"boolean"}
subtitle_format = ".vtt" # @param [".srt", ".vtt", ".ass", ".ssa", ".sub", ".txt"]

#@markdown 🔀 Existing Softsub (if the video already has a built-in subtitle)
existing_subtitle_action = "remove_existing"  # @param ["remove_existing", "keep_existing"]

#@markdown 🎥 Output Container Format
output_container_mode = "always_mkv"  # @param ["always_mkv", "keep_original_format"]

#@markdown 🔽 Dropdown: action to take after muxing is complete
cleanup_action = "delete_both"  # @param ["delete_video", "delete_subtitle", "delete_both", "keep_all"]

# 📋 Show a summary of the selected configuration
def print_selected_configuration():
    print("=" * 50)
    print("SELECTED CONFIGURATION")
    print("=" * 50)
    print(f"Video input          : {video_input}")
    print(f"Subtitle input       : {subtitle_input}")
    print(f"Output folder        : {output_folder}")
    print(f"Subtitle language    : {subtitle_lang}")
    print(f"Add extension        : {add_extension}"
        + (f" (format: {subtitle_format})" if add_extension else ""))
    print(f"Existing softsub     : {existing_subtitle_action}")
    print(f"Output container     : {output_container_mode}")
    print(f"Cleanup action       : {cleanup_action}")
    print("=" * 50)

print_selected_configuration()

# 🚫 Folders/files to ignore when listing
IGNORED_NAMES = {".ipynb_checkpoints", "__pycache__", ".DS_Store"}

def is_file(path: str) -> bool:
    return os.path.isfile(path)

def is_ignored(name: str) -> bool:
    """Ignore hidden files/folders (starting with a dot) or present in IGNORED_NAMES."""
    return name.startswith(".") or name in IGNORED_NAMES

def list_valid_files(folder: str, extensions=None):
    """List files in a folder, skipping hidden files/folders like .ipynb_checkpoints."""
    result = []
    for f in os.listdir(folder):
        full_path = os.path.join(folder, f)

        if is_ignored(f):
            continue
        if not os.path.isfile(full_path):
            continue
        if extensions and not f.lower().endswith(extensions):
            continue

        result.append(full_path)

    return sorted(result)

# 🔍 Count how many subtitle streams already exist in the video using ffprobe
def count_existing_subtitle_streams(video_path):
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "s",
        "-show_entries", "stream=index,codec_name",
        "-of", "json",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"Failed to read subtitle stream: {result.stderr.strip()}", "WARNING")
        return []

    try:
        data = json.loads(result.stdout)
        return data.get("streams", [])
    except json.JSONDecodeError:
        log("Failed to parse ffprobe output.", "WARNING")
        return []

# ✅ [Suggestion #1] Validate the subtitle file before it's used for muxing
def validate_subtitle_file(subtitle_path):
    """
    Returns (is_valid: bool, reason: str).
    Basic check: file size is not 0, and (if an extension exists) ffprobe can
    detect at least 1 subtitle stream inside it.
    """
    if not os.path.exists(subtitle_path):
        return False, "Subtitle file not found"

    if os.path.getsize(subtitle_path) == 0:
        return False, "Subtitle file is empty (0 bytes)"

    ext = os.path.splitext(subtitle_path)[1].lower()
    if not ext:
        # ffprobe needs an extension/format hint for raw subtitles,
        # so deep validation is skipped for files without an extension.
        return True, "No extension - deep validation skipped"

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "s",
        "-show_entries", "stream=index",
        "-of", "json",
        subtitle_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"ffprobe failed to read the file: {result.stderr.strip()[:200]}"

    try:
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not streams:
            return False, "No subtitle stream detected in this file"
    except json.JSONDecodeError:
        return False, "Failed to parse ffprobe result for the subtitle file"

    return True, "OK"

# 📦 Determine the output extension based on the mode and original video format
def get_output_extension(video_path, mode):
    ext = os.path.splitext(video_path)[1].lower()

    if mode == "always_mkv":
        return ".mkv"

    # mode == keep_original_format
    if ext in (".mp4", ".m4v"):
        return ".mp4"
    if ext == ".mov":
        return ".mov"
    if ext == ".mkv":
        return ".mkv"
    if ext == ".webm":
        log(f"WebM format has very limited softsub support "
            f"(WebVTT only). Output will still be remuxed to MKV.", "WARNING")
        return ".mkv"

    log(f"Format '{ext}' is not recognized for keep_original_format mode, "
        f"falling back to MKV.", "WARNING")
    return ".mkv"

# ✅ [Suggestion #11] Verify the number of subtitle streams in the output file after muxing
def verify_output_subtitles(output_file, expected_count):
    """
    Returns (is_verified: bool, actual_count: int).
    """
    if not os.path.exists(output_file):
        return False, 0

    streams = count_existing_subtitle_streams(output_file)
    actual_count = len(streams)
    return actual_count >= expected_count, actual_count

# 🔧 Mux a subtitle into a single video file
# Returns a dict: {"status": "success"/"failed", "reason": str}
def mux_subtitle(video_path, subtitle_path, output_path, index=None, total=None):
    if not os.path.exists(video_path):
        log("Video file not found!", "ERROR")
        return {"status": "failed", "reason": "Video file not found"}

    # ✅ [Suggestion #1] Validate the subtitle before it's processed by ffmpeg
    is_valid, reason = validate_subtitle_file(subtitle_path)
    if not is_valid:
        log(f"Invalid subtitle: {reason}", "ERROR")
        return {"status": "failed", "reason": f"Invalid subtitle - {reason}"}

    os.makedirs(output_path, exist_ok=True)
    progress = f"[{index+1}/{total}]" if index is not None else ""

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_ext = get_output_extension(video_path, output_container_mode)
    output_file = os.path.join(output_path, f"{base_name}_sub{output_ext}")

    log(f"{progress} Processing: {os.path.basename(video_path)} with {os.path.basename(subtitle_path)} "
        f"→ output format {output_ext}")

    existing_subs = count_existing_subtitle_streams(video_path)
    existing_count = len(existing_subs)

    if existing_count > 0:
        log(f"{progress} Video has {existing_count} existing softsub(s) "
            f"(codec: {[s.get('codec_name') for s in existing_subs]})", "INFO")

    # mov_text is only compatible with MP4/MOV containers, not MKV
    incompatible_with_mkv = {"mov_text"}
    has_incompatible = any(s.get("codec_name") in incompatible_with_mkv for s in existing_subs)

    if existing_subtitle_action == "keep_existing" and output_ext == ".mkv" and has_incompatible:
        log(f"{progress} ⚠️ The existing subtitle uses the mov_text codec, which is not supported by MKV. "
            f"The mux process may fail if it isn't transcoded.", "WARNING")

    # New subtitle codec: mov_text is required for MP4/MOV, copy for MKV
    new_sub_codec = "mov_text" if output_ext in (".mp4", ".mov") else "copy"

    if existing_subtitle_action == "keep_existing" and existing_count > 0:
        new_sub_index = existing_count
        expected_subtitle_count = existing_count + 1
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", subtitle_path,
            "-map", "0",
            "-map", "1:s:0",
            "-c", "copy",
            f"-c:s:{new_sub_index}", new_sub_codec,
            f"-metadata:s:s:{new_sub_index}", f"language={subtitle_lang}",
            output_file
        ]
    else:
        expected_subtitle_count = 1
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", subtitle_path,
            "-map", "0:v",
            "-map", "0:a",
            "-map", "1:s:0",
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", new_sub_codec,
            "-metadata:s:s:0", f"language={subtitle_lang}",
            output_file
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log(f"{progress} Failed to mux subtitle.", "ERROR")
        print(result.stderr)
        return {"status": "failed", "reason": f"ffmpeg error: {result.stderr.strip()[:300]}"}

    # ✅ [Suggestion #11] Verify the output before deleting the source
    verified, actual_count = verify_output_subtitles(output_file, expected_subtitle_count)
    if not verified:
        log(f"{progress} ⚠️ Verification failed: expected {expected_subtitle_count} subtitle stream(s), "
            f"detected {actual_count} in the output file. Source was NOT deleted.", "ERROR")
        return {
            "status": "failed",
            "reason": f"Output verification failed (expected {expected_subtitle_count}, got {actual_count})"
        }

    log(f"{progress} Subtitle successfully muxed and verified "
        f"({actual_count}/{expected_subtitle_count} subtitle stream(s)).", "SUCCESS")
    perform_cleanup(video_path, subtitle_path)
    return {"status": "success", "reason": "OK"}

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

# 🚀 Preview pairing before muxing with truncated names
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

        v_display = truncate(v, max_len)
        s_display = truncate(s, max_len)

        print(f"  [{i+1}] {v_display:<{max_len}} ↔ {s_display}")

    if len(video_files) != len(subtitle_files):
        log("⚠️ The number of videos and subtitles differ, only the minimum count will be processed.", "WARNING")

# ✅ [Suggestion #2] Print the final batch summary
def print_batch_summary(results):
    total = len(results)
    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]

    print("=" * 50)
    print("BATCH MUXING SUMMARY")
    print("=" * 50)
    print(f"Total processed : {total}")
    print(f"Succeeded       : {len(success)}")
    print(f"Failed          : {len(failed)}")

    if failed:
        print("-" * 50)
        print("Details of failed files:")
        for r in failed:
            print(f"  ❌ {r['video']}  ↔  {r['subtitle']}")
            print(f"     Reason: {r['reason']}")
    print("=" * 50)

# 🚀 Batch process
def batch_mux_subtitles(video_input, subtitle_input, output_folder):
    video_files = [video_input] if is_file(video_input) else list_valid_files(
        video_input, extensions=(".mp4", ".mkv", ".webm", ".mov")
    )

    subtitle_files = [subtitle_input] if is_file(subtitle_input) else list_valid_files(
        subtitle_input
    )

    log(f"Video files found: {len(video_files)}")
    log(f"Subtitle files found: {len(subtitle_files)}")

    preview_pairs(video_files, subtitle_files)

    total = min(len(video_files), len(subtitle_files))
    results = []

    for i in range(total):
        v_path = video_files[i]
        s_path = subtitle_files[i]

        target_s_path = s_path
        created_temp_sub = False
        if add_extension and not os.path.splitext(s_path)[1]:
            target_s_path = s_path + subtitle_format
            shutil.copy2(s_path, target_s_path)
            created_temp_sub = True

        outcome = mux_subtitle(v_path, target_s_path, output_folder, index=i, total=total)
        results.append({
            "video": os.path.basename(v_path),
            "subtitle": os.path.basename(s_path),
            "status": outcome["status"],
            "reason": outcome["reason"],
        })

        if created_temp_sub and os.path.exists(target_s_path):
            os.remove(target_s_path)

    log("All files have been processed.", "SUCCESS")
    print_batch_summary(results)

# 🚀 Run
batch_mux_subtitles(video_input, subtitle_input, output_folder)