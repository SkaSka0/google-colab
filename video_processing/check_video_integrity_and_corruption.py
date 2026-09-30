#@title 🎬 Video Validity Checker (Black Screen, Audio, Duration, Truncation, Corrupt Detection) { display-mode: "form" }

#@markdown ### 📁 Folder & File Settings
folder_path = "/content/media_toolkit/downloads/video" #@param {type:"string"}
file_extensions = ".mp4, .mkv, .mov, .avi, .webm" #@param {type:"string"}
recursive_search = True #@param {type:"boolean"}

#@markdown ---
#@markdown ### ⏱️ Duration Mismatch (Truncated File) Check
#@markdown Compares the duration declared in metadata against the duration actually readable from the file.
#@markdown Reads every video packet without decoding, so it is much faster than a full decode.
enable_duration_mismatch_check = True #@param {type:"boolean"}
#@markdown Allowed gap as a fraction of declared duration (0.01 = 1%).
duration_tolerance_ratio = 0.01 #@param {type:"number"}
#@markdown Minimum allowed gap in seconds, so short videos don't trigger false alarms.
duration_tolerance_min_seconds = 5 #@param {type:"number"}

#@markdown ---
#@markdown ### 🔍 Decode / Corrupt Check
#@markdown Decodes the file to detect errors/corruption that ffprobe cannot see.
enable_decode_check = True #@param {type:"boolean"}
#@markdown Limit the decode check to the first N seconds to make it faster (0 = full file, slow for large files).
decode_check_seconds = 30 #@param {type:"integer"}

#@markdown ---
#@markdown ### ⬛ Black Screen Detection
enable_black_check = True #@param {type:"boolean"}
#@markdown Minimum duration (seconds) for a segment to be considered "black" by ffmpeg blackdetect.
black_min_duration = 1.0 #@param {type:"number"}
#@markdown Fraction of dark pixels in a frame for it to count as a "black frame" (0.0 - 1.0).
black_pic_threshold = 0.98 #@param {type:"slider", min:0, max:1, step:0.01}
#@markdown Pixel darkness threshold, 0 = pure black, 1 = white (0.0 - 1.0).
black_pix_threshold = 0.10 #@param {type:"slider", min:0, max:1, step:0.01}
#@markdown If the black-duration ratio is ≥ this value, the video is considered "fully black" (invalid).
black_total_ratio_threshold = 0.90 #@param {type:"slider", min:0, max:1, step:0.01}
#@markdown If the black-duration ratio is ≥ this value (but below the full-black threshold), it is reported as a warning only (not invalid).
black_warning_ratio_threshold = 0.30 #@param {type:"slider", min:0, max:1, step:0.01}

#@markdown ---
#@markdown ### ⚙️ Output Settings
show_only_invalid = False #@param {type:"boolean"}
print_summary_only = False #@param {type:"boolean"}

import subprocess
import json
import os
import re
from pathlib import Path


# ===================== CUSTOM LOGGER =====================

LOG_LEVEL_DEBUG = 0
LOG_LEVEL_INFO  = 1
LOG_LEVEL_WARN  = 2
LOG_LEVEL_ERROR = 3

# Change to LOG_LEVEL_DEBUG for more detailed output
CURRENT_LOG_LEVEL = LOG_LEVEL_INFO

_LEVEL_LABELS = {
    LOG_LEVEL_DEBUG : ("DEBUG", ""),
    LOG_LEVEL_INFO  : ("INFO ", ""),
    LOG_LEVEL_WARN  : ("WARN ", ""),
    LOG_LEVEL_ERROR : ("ERROR", ""),
}

def _log(level: int, step: str, message: str):
    """Core log function. Only prints if level >= CURRENT_LOG_LEVEL."""
    if level < CURRENT_LOG_LEVEL:
        return
    label, icon = _LEVEL_LABELS.get(level, ("?????", "❓"))
    print(f"[{label}] {icon}[{step}] {message}")

def log_debug(step: str, message: str):
    _log(LOG_LEVEL_DEBUG, step, message)

def log_info(step: str, message: str):
    _log(LOG_LEVEL_INFO, step, message)

def log_warn(step: str, message: str):
    _log(LOG_LEVEL_WARN, step, message)

def log_error(step: str, message: str):
    _log(LOG_LEVEL_ERROR, step, message)

def log_section(title: str):
    """Print a section separator to make the output easier to read."""
    print(f"{title}")

# =========================================================

# Matches ffmpeg's "-stats" progress output, e.g. "time=00:29:58.12"
_TIME_PATTERN = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")

# A full packet scan of a large file can take longer than run_cmd()'s 120s.
PACKET_SCAN_TIMEOUT_SECONDS = 900


class VideoCheckResult:
    def __init__(self, path):
        self.path = path
        self.is_valid = True
        self.issues = []
        self.info = {}

    def add_issue(self, msg):
        self.is_valid = False
        self.issues.append(msg)

    def __repr__(self):
        status = "✅ VALID" if self.is_valid else "❌ INVALID"
        lines = [f"{status} - {self.path}"]
        if self.info:
            lines.append(f"   duration : {self.info.get('duration', '?')}s")
            if "actual_duration" in self.info:
                lines.append(f"   actual   : {self.info['actual_duration']}s (readable)")
            lines.append(f"   size     : {self.info.get('size_mb', '?')} MB")
            lines.append(f"   video    : {self.info.get('video_codec', '-')} "
                          f"{self.info.get('resolution', '')}")
            lines.append(f"   audio    : {self.info.get('audio_codec', '-')}")
            if "black_ratio" in self.info:
                lines.append(f"   black    : {self.info['black_ratio']*100:.1f}% of duration")
        for issue in self.issues:
            lines.append(f"   ⚠ {issue}")
        return "\n".join(lines)


def run_cmd(cmd):
    log_debug("run_cmd", f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=120
    )
    log_debug("run_cmd", f"Return code: {result.returncode}")
    return result


def ffprobe_info(path):
    log_debug("ffprobe_info", f"Reading metadata: {path}")
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path
    ]
    result = run_cmd(cmd)
    if result.returncode != 0 or not result.stdout.strip():
        log_error("ffprobe_info", f"ffprobe failed or returned empty output for: {path}")
        return None
    try:
        data = json.loads(result.stdout)
        log_debug("ffprobe_info", "Metadata parsed as JSON successfully")
        return data
    except json.JSONDecodeError as e:
        log_error("ffprobe_info", f"Failed to parse JSON: {e}")
        return None


def check_basic(path, res: VideoCheckResult):
    step = "check_basic"
    log_info(step, f"Checking file existence and size: {os.path.basename(path)}")

    if not os.path.isfile(path):
        log_error(step, f"File not found: {path}")
        res.add_issue("File not found")
        return False

    size = os.path.getsize(path)
    size_mb = round(size / (1024 * 1024), 2)
    res.info["size_mb"] = size_mb
    log_debug(step, f"File size: {size_mb} MB ({size} bytes)")

    if size == 0:
        log_error(step, "File size is 0 bytes — empty file")
        res.add_issue("File size is 0 bytes")
        return False

    log_info(step, f"File found, size {size_mb} MB ✔")
    return True


def check_streams_and_duration(path, res: VideoCheckResult):
    step = "check_streams"
    log_info(step, "Reading streams and duration via ffprobe")

    data = ffprobe_info(path)
    if data is None:
        log_error(step, "ffprobe returned no data — file is likely corrupt")
        res.add_issue("ffprobe could not read the file (likely corrupt)")
        return None

    fmt = data.get("format", {})
    duration = float(fmt.get("duration", 0) or 0)
    res.info["duration"] = round(duration, 2)
    log_info(step, f"Detected duration: {round(duration, 2)}s")

    if duration <= 0.5:
        log_warn(step, f"Duration is too short or invalid: {duration}s")
        res.add_issue("Video duration is invalid or too short (≤0.5s)")

    streams = data.get("streams", [])
    log_debug(step, f"Total streams found: {len(streams)}")

    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    all_video_streams = [s for s in streams if s.get("codec_type") == "video"]
    real_video_streams = [
        s for s in all_video_streams
        if not s.get("disposition", {}).get("attached_pic", 0)
    ]
    thumbnail_streams = [
        s for s in all_video_streams
        if s.get("disposition", {}).get("attached_pic", 0)
    ]

    log_debug(step, f"Video streams: {len(all_video_streams)} total "
                    f"({len(real_video_streams)} real, {len(thumbnail_streams)} thumbnail)")
    log_debug(step, f"Audio streams: {len(audio_streams)}")

    if not all_video_streams:
        log_error(step, "No video stream at all")
        res.add_issue("No video stream")
    elif not real_video_streams:
        t = thumbnail_streams[0]
        msg = (f"No real video stream (only a thumbnail/cover art was detected, "
               f"{t.get('codec_name','?')} {t.get('width','?')}x{t.get('height','?')})")
        log_warn(step, msg)
        res.add_issue(msg)
        res.info["video_codec"] = "-"
        res.info["resolution"] = "-"
    else:
        v = real_video_streams[0]
        res.info["video_codec"] = v.get("codec_name", "?")
        res.info["resolution"] = f"{v.get('width','?')}x{v.get('height','?')}"
        log_info(step, f"Video stream: {res.info['video_codec']} @ {res.info['resolution']} ✔")
        if not v.get("width") or not v.get("height"):
            log_warn(step, "Resolution could not be read from metadata")
            res.add_issue("Video resolution could not be read")

    if not audio_streams:
        log_warn(step, "No audio stream found")
        res.add_issue("No audio stream")
    else:
        a = audio_streams[0]
        res.info["audio_codec"] = a.get("codec_name", "?")
        log_info(step, f"Audio stream: {res.info['audio_codec']} ✔")

    return duration if real_video_streams else None


def _measure_actual_duration(path: str) -> float | None:
    """Read every video packet without decoding and return the last timestamp reached.

    Returns None if the timestamp could not be determined.
    Raises subprocess.TimeoutExpired if the scan exceeds PACKET_SCAN_TIMEOUT_SECONDS.
    """
    cmd = [
        "ffmpeg", "-v", "error", "-stats",
        "-i", path,
        "-map", "0:v:0", "-c", "copy",
        "-f", "null", "-",
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=PACKET_SCAN_TIMEOUT_SECONDS
    )
    matches = _TIME_PATTERN.findall(result.stderr)
    if not matches:
        return None
    h, m, s = matches[-1]
    return int(h) * 3600 + int(m) * 60 + float(s)


def check_duration_mismatch(path, declared_duration, res: VideoCheckResult,
                            tolerance_ratio, min_tolerance_seconds):
    step = "check_duration"
    log_info(step, "Scanning packets to measure the actual playable duration")

    try:
        actual = _measure_actual_duration(path)
    except subprocess.TimeoutExpired:
        log_warn(step, f"Packet scan exceeded {PACKET_SCAN_TIMEOUT_SECONDS}s, skipping this check")
        return

    if actual is None:
        log_warn(step, "Could not measure actual duration, skipping this check")
        return

    res.info["actual_duration"] = round(actual, 2)
    gap = declared_duration - actual
    allowed_gap = max(min_tolerance_seconds, declared_duration * tolerance_ratio)

    if gap > allowed_gap:
        log_error(step, f"Truncated file: declared {declared_duration:.0f}s, "
                        f"actual {actual:.0f}s (missing {gap:.0f}s)")
        res.add_issue(
            f"File is truncated: metadata says {declared_duration:.0f}s "
            f"but only {actual:.0f}s is actually readable (missing {gap:.0f}s)"
        )
    else:
        log_info(step, f"Declared {declared_duration:.0f}s vs actual {actual:.0f}s ✔")


def check_decode_errors(path, res: VideoCheckResult, max_seconds=None):
    step = "check_decode"
    if max_seconds:
        log_info(step, f"Decoding the first {max_seconds} seconds to detect errors")
    else:
        log_info(step, "Decoding the full file to detect errors (may be slow)")

    cmd = ["ffmpeg", "-v", "error"]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
    cmd += ["-i", path, "-f", "null", "-"]

    result = run_cmd(cmd)
    stderr = result.stderr.strip()

    if stderr:
        line_count = len(stderr.splitlines())
        log_warn(step, f"Found {line_count} error/warning lines during decode")
        snippet = "; ".join(stderr.splitlines()[:3])
        res.add_issue(f"Decode error: {snippet}")
    else:
        log_info(step, "No decode errors found ✔")


def check_black_video(path, duration, res: VideoCheckResult,
                       black_min_duration, pic_th, pix_th,
                       total_ratio_th, warning_ratio_th,
                       max_seconds=60):
    step = "check_black"
    log_info(step, (f"Running blackdetect "
                    f"(d={black_min_duration}, pic_th={pic_th}, pix_th={pix_th})"))

    if not duration or duration <= 0:
        log_warn(step, "Invalid duration, skipping black screen check")
        return

    filter_str = (
        f"blackdetect=d={black_min_duration}:"
        f"pic_th={pic_th}:pix_th={pix_th}"
    )
    cmd = ["ffmpeg", "-v", "info"]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
        log_info(step, f"Analyzing only the first {max_seconds} seconds")
    cmd += ["-i", path, "-vf", filter_str, "-an", "-f", "null", "-"]

    result = run_cmd(cmd)
    stderr = result.stderr

    black_segments = re.findall(
        r"black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)",
        stderr
    )
    log_debug(step, f"Black segments found: {len(black_segments)}")

    if not black_segments:
        log_info(step, "No black screen segments detected ✔")
        return

    total_black = sum(float(d) for _, _, d in black_segments)
    ratio = total_black / duration
    res.info["black_ratio"] = round(ratio, 3)

    log_info(step, f"Total black duration: {total_black:.2f}s of {duration:.2f}s "
                   f"({ratio*100:.1f}%)")

    if ratio >= total_ratio_th:
        log_error(step, f"Video considered fully black: {ratio*100:.1f}% ≥ "
                        f"threshold {total_ratio_th*100:.0f}%")
        res.add_issue(
            f"Video is likely fully black ({ratio*100:.1f}% of duration detected as black)"
        )
    elif ratio >= warning_ratio_th:
        log_warn(step, f"Significant black segments: {ratio*100:.1f}% ≥ "
                       f"warning threshold {warning_ratio_th*100:.0f}%")
        res.add_issue(
            f"Video has significant black segments ({ratio*100:.1f}% of duration)"
        )
    else:
        log_info(step, f"Black ratio {ratio*100:.1f}% is below the warning threshold ✔")


def validate_video(path):
    step = "validate_video"
    filename = os.path.basename(path)

    log_section(f"📹 Validating: {filename}")
    log_info(step, f"Full path: {path}")

    res = VideoCheckResult(path)

    # Step 1 — Basic file check
    log_info(step, "→ Step 1/5: Basic file check")
    if not check_basic(path, res):
        log_error(step, "Basic check failed, skipping the remaining steps")
        return res

    # Step 2 — Stream & duration
    log_info(step, "→ Step 2/5: Streams & duration")
    duration = check_streams_and_duration(path, res)

    # Step 3 — Duration mismatch (truncated file) check
    if enable_duration_mismatch_check and duration:
        log_info(step, "→ Step 3/5: Duration mismatch check")
        check_duration_mismatch(
            path, duration, res,
            tolerance_ratio=duration_tolerance_ratio,
            min_tolerance_seconds=duration_tolerance_min_seconds,
        )
    elif not enable_duration_mismatch_check:
        log_info(step, "→ Step 3/5: Duration mismatch check [SKIPPED — disabled]")
    else:
        log_info(step, "→ Step 3/5: Duration mismatch check [SKIPPED — invalid duration]")

    # Step 4 — Decode error check
    if enable_decode_check:
        log_info(step, "→ Step 4/5: Decode error check")
        max_s = decode_check_seconds if decode_check_seconds > 0 else None
        check_decode_errors(path, res, max_seconds=max_s)
    else:
        log_info(step, "→ Step 4/5: Decode error check [SKIPPED — disabled]")

    # Step 5 — Black screen check
    if enable_black_check and duration:
        log_info(step, "→ Step 5/5: Black screen check")
        check_black_video(
            path, duration, res,
            black_min_duration=black_min_duration,
            pic_th=black_pic_threshold,
            pix_th=black_pix_threshold,
            total_ratio_th=black_total_ratio_threshold,
            warning_ratio_th=black_warning_ratio_threshold,
            max_seconds=60,
        )
    elif not enable_black_check:
        log_info(step, "→ Step 5/5: Black screen check [SKIPPED — disabled]")
    else:
        log_info(step, "→ Step 5/5: Black screen check [SKIPPED — invalid duration]")

    status = "VALID ✅" if res.is_valid else f"INVALID ❌ ({len(res.issues)} issues)"
    log_info(step, f"Final result: {status}")

    return res


def validate_videos_in_folder(folder, extensions, recursive=True):
    step = "scan_folder"
    log_section("📁 Starting Folder Scan")
    log_info(step, f"Folder    : {folder}")
    log_info(step, f"Extensions: {', '.join(extensions)}")
    log_info(step, f"Recursive : {recursive}")

    results = []
    if not os.path.isdir(folder):
        log_error(step, f"Folder not found: {folder}")
        print(f"⚠ Folder not found: {folder}")
        return results

    iterator = Path(folder).rglob("*") if recursive else Path(folder).glob("*")
    all_files = sorted(iterator)
    matched = [f for f in all_files if f.suffix.lower() in extensions]

    log_info(step, f"Total files found: {len(all_files)}, "
                   f"matching extensions: {len(matched)}")

    for idx, f in enumerate(matched, 1):
        log_info(step, f"[{idx}/{len(matched)}] Processing: {f.name}")
        results.append(validate_video(str(f)))

    return results


# ===================== EXECUTION =====================
log_section("🚀 Video Validity Checker — Start")

extensions = tuple(
    ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
    for ext in file_extensions.split(",") if ext.strip()
)

log_info("init", f"Extensions to check: {extensions}")
log_info("init", f"Duration check: {'enabled, tolerance ' + str(duration_tolerance_ratio*100) + '% / min ' + str(duration_tolerance_min_seconds) + 's' if enable_duration_mismatch_check else 'disabled'}")
log_info("init", f"Decode check  : {'enabled, max ' + str(decode_check_seconds) + 's' if enable_decode_check else 'disabled'}")
log_info("init", f"Black check   : {'enabled' if enable_black_check else 'disabled'}")

results = validate_videos_in_folder(folder_path, extensions, recursive=recursive_search)

invalid = [r for r in results if not r.is_valid]
valid_count = len(results) - len(invalid)

log_section("📊 FINAL RESULT")
log_info("summary", f"Total processed : {len(results)}")
log_info("summary", f"Valid           : {valid_count}")
log_info("summary", f"Invalid         : {len(invalid)}")

print(f"\n📊 Total: {len(results)} | ✅ Valid: {valid_count} | ❌ Invalid: {len(invalid)}\n")

if not print_summary_only:
    display_list = invalid if show_only_invalid else results
    for r in display_list:
        print(r)
        print("-" * 50)
