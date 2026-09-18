#@title 🎧 Extract Original Audio
#@markdown - This script can extract audio from a **single video** or a **whole folder of videos** (batch).
#@markdown - No re-encoding → audio quality is kept identical to the source (codec copy).

import os
import shutil
import subprocess
import sys

APPNAME = "AudioExtraction"

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov")

CODEC_TO_EXTENSION = {
    "aac": "m4a",
    "mp3": "mp3",
    "opus": "opus",
    "vorbis": "ogg",
    "flac": "flac",
    "wav": "wav",
}
FALLBACK_EXTENSION = "m4a"


def log(message: str, level: str = "INFO") -> None:
    """Print a formatted log message."""
    print(f"{level}:{APPNAME}:{message}")


# ==============================
# DEPENDENCY CHECK
# ==============================
def _ensure_ffmpeg_installed() -> bool:
    """Check that ffmpeg is available, installing it via apt if not. Idempotent."""
    if shutil.which("ffmpeg"):
        return True

    log("ffmpeg not found. Installing via apt...")
    subprocess.run(["apt-get", "update"])
    subprocess.run(["apt-get", "install", "-y", "ffmpeg"])

    if not shutil.which("ffmpeg"):
        log("ffmpeg installation failed.", "ERROR")
        return False

    log("ffmpeg installed successfully.")
    return True


# ==============================
# HELPERS
# ==============================
def _detect_audio_codec(video_path: str) -> str:
    """Probe the first audio stream's codec name. Returns '' if undetectable."""
    probe_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name", "-of", "default=nokey=1:noprint_wrappers=1",
        video_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    return result.stdout.strip()


def _resolve_extension(codec: str, progress: str) -> tuple[str, str]:
    """Map a detected codec to its output extension. Returns (codec_label, extension)."""
    if not codec:
        log(f"{progress} ⚠️ Could not detect audio codec, using fallback extension '.{FALLBACK_EXTENSION}'", "WARNING")
        return "unknown", FALLBACK_EXTENSION
    return codec, CODEC_TO_EXTENSION.get(codec, FALLBACK_EXTENSION)


def _build_output_audio_path(video_path: str, output_folder: str, codec_label: str, extension: str) -> str:
    """Build the output audio file path, naming it after the extracted codec."""
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    return os.path.join(output_folder, f"{base_name}_{codec_label}.{extension}")


def _build_extract_command(video_path: str, audio_path: str) -> list[str]:
    """Build the ffmpeg command that copies the audio stream without re-encoding."""
    return [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",              # no video
        "-acodec", "copy",  # copy the original audio, no re-encode
        audio_path,
    ]


def _run_ffmpeg(cmd: list[str]) -> tuple[bool, str]:
    """Run the ffmpeg command. Returns (success, stderr)."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stderr


def _format_progress(index: int | None, total: int | None) -> str:
    """Build a '[n/total]' progress prefix, or an empty string outside batch mode."""
    if index is not None and total is not None:
        return f"[{index + 1}/{total}]"
    return ""


def _list_video_files(folder_path: str) -> list[str]:
    """List video files directly inside folder_path, sorted by name."""
    files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith(VIDEO_EXTENSIONS)
    ]
    return sorted(files)


# ==============================
# MAIN
# ==============================
def extract_audio(video_path: str, output_folder: str, index: int | None = None, total: int | None = None) -> bool:
    """Extract the original audio track from one video file, without re-encoding."""
    if not os.path.exists(video_path):
        log(f"File not found: {video_path}", "ERROR")
        return False

    os.makedirs(output_folder, exist_ok=True)
    progress = _format_progress(index, total)

    codec = _detect_audio_codec(video_path)
    codec_label, extension = _resolve_extension(codec, progress)
    audio_path = _build_output_audio_path(video_path, output_folder, codec_label, extension)

    log(f"{progress} Input Video: {video_path}")
    log(f"{progress} Detected Audio Codec: {codec_label}")
    log(f"{progress} Output Audio: {audio_path}")
    log(f"{progress} Extracting audio (no re-encode)...")

    cmd = _build_extract_command(video_path, audio_path)
    success, stderr = _run_ffmpeg(cmd)

    if not success:
        log(f"{progress} Failed to extract audio", "ERROR")
        print(stderr)
        return False

    log(f"{progress} Audio extracted successfully.", "SUCCESS")
    return True


def process_folder(folder_path: str, output_folder: str) -> None:
    """Extract audio from every video file directly inside folder_path."""
    video_files = _list_video_files(folder_path)

    log(f"Folder mode: processing {len(video_files)} video files in: {folder_path}")
    for idx, fpath in enumerate(video_files):
        extract_audio(fpath, output_folder, index=idx, total=len(video_files))
    log("All files in the folder have been processed.", "SUCCESS")


# ==============================
# INPUT FORM (Colab)
# ==============================
video_input_path = ""  # @param {type:"string"}
output_path = "/content/media_toolkit/audio_extract"  # @param {type:"string"}


# ==============================
# EXECUTION
# ==============================
if __name__ == "__main__":
    if not _ensure_ffmpeg_installed():
        sys.exit(1)

    if os.path.isdir(video_input_path):
        process_folder(video_input_path, output_path)
    elif os.path.isfile(video_input_path):
        extract_audio(video_input_path, output_path)
    else:
        log("Input path not found!", "ERROR")
