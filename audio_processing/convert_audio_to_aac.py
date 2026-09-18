# @title 🎧 Convert Audio to AAC
# @markdown This script converts an audio file to AAC format with structured logging.

import os
import shutil
import subprocess
import sys

# ==============================
# CONFIG
# ==============================
APPNAME = "AudioConverter"  # fixed typo (was "AudioCoverter")

AAC_CODEC = "aac"

# Bitrate presets — "low" targets voice/dialog content (smaller size,
# still clear); "best" targets music/scoring where quality matters most.
AAC_BITRATE_PRESETS = {
    "best": "320k",
    "standard": "192k",
    "low": "128k",
}
DEFAULT_QUALITY = "standard"


def log(message: str, level: str = "INFO") -> None:
    """Print a formatted log message."""
    print(f"{level}:{APPNAME}: {message}")


# ==============================
# INPUT PARAM (Colab form)
# ==============================
input_file = "/content/media_toolkit/audio_merge/hidup_kembali_dengan_3_istri.wav"  # @param {type:"string"}
output_folder = "/content/media_toolkit/audio_convert"  # @param {type:"string"}
audio_quality = "standard"  # @param ["best", "standard", "low"]


# ==============================
# DEPENDENCY CHECK
# ==============================
def _ensure_ffmpeg_installed() -> bool:
    """Check that ffmpeg is available, installing it via apt if not. Idempotent."""
    if shutil.which("ffmpeg"):
        return True

    log("ffmpeg not found. Installing via apt...", "WARNING")
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
def _validate_input_file(path: str) -> bool:
    """Return True if the input file exists, log an error otherwise."""
    if not os.path.isfile(path):
        log(f"Input file not found: {path}", "ERROR")
        return False
    return True


def _resolve_bitrate(quality: str) -> str:
    """Map a quality preset name to its ffmpeg bitrate value."""
    bitrate = AAC_BITRATE_PRESETS.get(quality)
    if bitrate is None:
        log(f"Unknown quality preset '{quality}', falling back to '{DEFAULT_QUALITY}'.", "WARNING")
        bitrate = AAC_BITRATE_PRESETS[DEFAULT_QUALITY]
    return bitrate


def _build_output_path(input_path: str, out_folder: str, bitrate: str) -> str:
    """Build the output file path, including codec and bitrate in the filename."""
    basename = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(out_folder, f"{basename}_aac_{bitrate}.m4a")


def _build_ffmpeg_command(input_path: str, output_path: str, bitrate: str) -> list[str]:
    """Build the ffmpeg command used to convert audio to AAC."""
    return [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vn",
        "-c:a", AAC_CODEC,
        "-b:a", bitrate,
        output_path,
    ]


def _run_ffmpeg(cmd: list[str]) -> tuple[bool, str]:
    """Run the ffmpeg command. Returns (success, stderr)."""
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode == 0, result.stderr


def _get_file_size_mb(path: str) -> float:
    """Return the file size in megabytes."""
    return os.path.getsize(path) / (1024 * 1024)


def _log_conversion_summary(input_path: str, output_path: str) -> None:
    """Log input/output file sizes after a successful conversion."""
    log(f"Input size  : {_get_file_size_mb(input_path):.2f} MB")
    log(f"Output size : {_get_file_size_mb(output_path):.2f} MB")


# ==============================
# MAIN
# ==============================
def convert_audio_to_aac(input_path: str, out_folder: str, quality: str) -> bool:
    """
    Convert one audio file to AAC (.m4a) format at the requested quality preset.

    Returns True on success, False otherwise. Does not raise on
    expected failure conditions (missing input, missing ffmpeg,
    ffmpeg error) — the caller decides how to react (see the
    __main__ guard below).
    """
    if not _ensure_ffmpeg_installed():
        return False

    if not _validate_input_file(input_path):
        return False

    os.makedirs(out_folder, exist_ok=True)
    log(f"Output folder ready: {out_folder}")

    bitrate = _resolve_bitrate(quality)
    output_path = _build_output_path(input_path, out_folder, bitrate)

    log(f"Input:   {input_path}")
    log(f"Output:  {output_path}")
    log(f"Quality: {quality} ({bitrate})")

    log("Converting audio to AAC...")
    cmd = _build_ffmpeg_command(input_path, output_path, bitrate)
    success, stderr = _run_ffmpeg(cmd)

    if not success:
        log("Conversion failed!", "ERROR")
        log(stderr, "ERROR")
        return False

    log("Conversion completed!")
    _log_conversion_summary(input_path, output_path)
    log("Process completed without errors.")
    return True


if __name__ == "__main__":
    if not convert_audio_to_aac(input_file, output_folder, audio_quality):
        sys.exit(1)
