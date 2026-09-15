#@title 🎬 Video Validity Checker (Black Screen, Audio, Duration, Corrupt Detection) { display-mode: "form" }

#@markdown ### 📁 Folder & File Settings
folder_path = "/content/media_toolkit/downloads/video" #@param {type:"string"}
file_extensions = ".mp4, .mkv, .mov, .avi, .webm" #@param {type:"string"}
recursive_search = True #@param {type:"boolean"}

#@markdown ---
#@markdown ### 🔍 Decode / Corrupt Check
#@markdown Mendecode file untuk mendeteksi error/corrupt yang tidak terbaca ffprobe.
enable_decode_check = True #@param {type:"boolean"}
#@markdown Batasi decode check ke N detik pertama saja agar lebih cepat (0 = full file, lambat untuk file besar).
decode_check_seconds = 30 #@param {type:"integer"}

#@markdown ---
#@markdown ### ⬛ Black Screen Detection
enable_black_check = True #@param {type:"boolean"}
#@markdown Minimal durasi (detik) sebuah segmen dianggap "hitam" oleh ffmpeg blackdetect.
black_min_duration = 1.0 #@param {type:"number"}
#@markdown Persentase piksel gelap dalam 1 frame agar dianggap "frame hitam" (0.0 - 1.0).
black_pic_threshold = 0.98 #@param {type:"slider", min:0, max:1, step:0.01}
#@markdown Threshold kegelapan piksel, 0 = hitam total, 1 = putih (0.0 - 1.0).
black_pix_threshold = 0.10 #@param {type:"slider", min:0, max:1, step:0.01}
#@markdown Jika rasio durasi hitam ≥ nilai ini, video dianggap "hitam total" (invalid).
black_total_ratio_threshold = 0.90 #@param {type:"slider", min:0, max:1, step:0.01}
#@markdown Jika rasio durasi hitam ≥ nilai ini (tapi di bawah threshold total), dicatat sebagai peringatan saja (tidak invalid).
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

# Ubah ke LOG_LEVEL_DEBUG untuk output yang lebih detail
CURRENT_LOG_LEVEL = LOG_LEVEL_INFO

_LEVEL_LABELS = {
    LOG_LEVEL_DEBUG : ("DEBUG", ""),
    LOG_LEVEL_INFO  : ("INFO ", ""),
    LOG_LEVEL_WARN  : ("WARN ", ""),
    LOG_LEVEL_ERROR : ("ERROR", ""),
}

def _log(level: int, step: str, message: str):
    """Fungsi log inti. Hanya cetak jika level >= CURRENT_LOG_LEVEL."""
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
    """Cetak pemisah bagian agar output lebih mudah dibaca."""
    print(f"{title}")

# =========================================================


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
            lines.append(f"   size     : {self.info.get('size_mb', '?')} MB")
            lines.append(f"   video    : {self.info.get('video_codec', '-')} "
                          f"{self.info.get('resolution', '')}")
            lines.append(f"   audio    : {self.info.get('audio_codec', '-')}")
            if "black_ratio" in self.info:
                lines.append(f"   black    : {self.info['black_ratio']*100:.1f}% durasi")
        for issue in self.issues:
            lines.append(f"   ⚠ {issue}")
        return "\n".join(lines)


def run_cmd(cmd):
    log_debug("run_cmd", f"Menjalankan: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=120
    )
    log_debug("run_cmd", f"Return code: {result.returncode}")
    return result


def ffprobe_info(path):
    log_debug("ffprobe_info", f"Membaca metadata: {path}")
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path
    ]
    result = run_cmd(cmd)
    if result.returncode != 0 or not result.stdout.strip():
        log_error("ffprobe_info", f"ffprobe gagal atau output kosong untuk: {path}")
        return None
    try:
        data = json.loads(result.stdout)
        log_debug("ffprobe_info", "Metadata berhasil di-parse sebagai JSON")
        return data
    except json.JSONDecodeError as e:
        log_error("ffprobe_info", f"Gagal parse JSON: {e}")
        return None


def check_basic(path, res: VideoCheckResult):
    step = "check_basic"
    log_info(step, f"Memeriksa keberadaan dan ukuran file: {os.path.basename(path)}")

    if not os.path.isfile(path):
        log_error(step, f"File tidak ditemukan: {path}")
        res.add_issue("File tidak ditemukan")
        return False

    size = os.path.getsize(path)
    size_mb = round(size / (1024 * 1024), 2)
    res.info["size_mb"] = size_mb
    log_debug(step, f"Ukuran file: {size_mb} MB ({size} bytes)")

    if size == 0:
        log_error(step, "Ukuran file adalah 0 byte — file kosong")
        res.add_issue("Ukuran file 0 byte")
        return False

    log_info(step, f"File ditemukan dan berukuran {size_mb} MB ✔")
    return True


def check_streams_and_duration(path, res: VideoCheckResult):
    step = "check_streams"
    log_info(step, "Membaca stream dan durasi via ffprobe")

    data = ffprobe_info(path)
    if data is None:
        log_error(step, "ffprobe tidak mengembalikan data — kemungkinan file corrupt")
        res.add_issue("ffprobe gagal membaca file (kemungkinan corrupt)")
        return None

    fmt = data.get("format", {})
    duration = float(fmt.get("duration", 0) or 0)
    res.info["duration"] = round(duration, 2)
    log_info(step, f"Durasi terdeteksi: {round(duration, 2)}s")

    if duration <= 0.5:
        log_warn(step, f"Durasi terlalu pendek atau tidak valid: {duration}s")
        res.add_issue("Durasi video tidak valid atau terlalu pendek (≤0.5s)")

    streams = data.get("streams", [])
    log_debug(step, f"Total stream ditemukan: {len(streams)}")

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

    log_debug(step, f"Stream video: {len(all_video_streams)} total "
                    f"({len(real_video_streams)} asli, {len(thumbnail_streams)} thumbnail)")
    log_debug(step, f"Stream audio: {len(audio_streams)}")

    if not all_video_streams:
        log_error(step, "Tidak ada stream video sama sekali")
        res.add_issue("Tidak ada stream video")
    elif not real_video_streams:
        t = thumbnail_streams[0]
        msg = (f"Tidak ada stream video asli (hanya thumbnail/cover art terdeteksi, "
               f"{t.get('codec_name','?')} {t.get('width','?')}x{t.get('height','?')})")
        log_warn(step, msg)
        res.add_issue(msg)
        res.info["video_codec"] = "-"
        res.info["resolution"] = "-"
    else:
        v = real_video_streams[0]
        res.info["video_codec"] = v.get("codec_name", "?")
        res.info["resolution"] = f"{v.get('width','?')}x{v.get('height','?')}"
        log_info(step, f"Stream video: {res.info['video_codec']} @ {res.info['resolution']} ✔")
        if not v.get("width") or not v.get("height"):
            log_warn(step, "Resolusi tidak terbaca dari metadata")
            res.add_issue("Resolusi video tidak terbaca")

    if not audio_streams:
        log_warn(step, "Tidak ada stream audio ditemukan")
        res.add_issue("Tidak ada stream audio")
    else:
        a = audio_streams[0]
        res.info["audio_codec"] = a.get("codec_name", "?")
        log_info(step, f"Stream audio: {res.info['audio_codec']} ✔")

    return duration if real_video_streams else None


def check_decode_errors(path, res: VideoCheckResult, max_seconds=None):
    step = "check_decode"
    if max_seconds:
        log_info(step, f"Mendecode {max_seconds} detik pertama untuk deteksi error")
    else:
        log_info(step, "Mendecode file penuh untuk deteksi error (mungkin lambat)")

    cmd = ["ffmpeg", "-v", "error"]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
    cmd += ["-i", path, "-f", "null", "-"]

    result = run_cmd(cmd)
    stderr = result.stderr.strip()

    if stderr:
        line_count = len(stderr.splitlines())
        log_warn(step, f"Ditemukan {line_count} baris error/warning saat decode")
        snippet = "; ".join(stderr.splitlines()[:3])
        res.add_issue(f"Error saat decode: {snippet}")
    else:
        log_info(step, "Tidak ada error decode ditemukan ✔")


def check_black_video(path, duration, res: VideoCheckResult,
                       black_min_duration, pic_th, pix_th,
                       total_ratio_th, warning_ratio_th,
                       max_seconds=60):
    step = "check_black"
    log_info(step, (f"Menjalankan blackdetect "
                    f"(d={black_min_duration}, pic_th={pic_th}, pix_th={pix_th})"))

    if not duration or duration <= 0:
        log_warn(step, "Durasi tidak valid, melewati black screen check")
        return

    filter_str = (
        f"blackdetect=d={black_min_duration}:"
        f"pic_th={pic_th}:pix_th={pix_th}"
    )
    cmd = ["ffmpeg", "-v", "info"]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
        log_info(step, f"Hanya menganalisis {max_seconds} detik pertama")
    cmd += ["-i", path, "-vf", filter_str, "-an", "-f", "null", "-"]

    result = run_cmd(cmd)
    stderr = result.stderr

    black_segments = re.findall(
        r"black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)",
        stderr
    )
    log_debug(step, f"Segmen hitam ditemukan: {len(black_segments)}")

    if not black_segments:
        log_info(step, "Tidak ada segmen black screen terdeteksi ✔")
        return

    total_black = sum(float(d) for _, _, d in black_segments)
    ratio = total_black / duration
    res.info["black_ratio"] = round(ratio, 3)

    log_info(step, f"Total durasi hitam: {total_black:.2f}s dari {duration:.2f}s "
                   f"({ratio*100:.1f}%)")

    if ratio >= total_ratio_th:
        log_error(step, f"Video dianggap hitam total: {ratio*100:.1f}% ≥ "
                        f"threshold {total_ratio_th*100:.0f}%")
        res.add_issue(
            f"Video diduga hitam total ({ratio*100:.1f}% durasi terdeteksi black)"
        )
    elif ratio >= warning_ratio_th:
        log_warn(step, f"Segmen hitam signifikan: {ratio*100:.1f}% ≥ "
                       f"warning threshold {warning_ratio_th*100:.0f}%")
        res.add_issue(
            f"Video punya segmen hitam signifikan ({ratio*100:.1f}% durasi)"
        )
    else:
        log_info(step, f"Rasio hitam {ratio*100:.1f}% masih di bawah threshold warning ✔")


def validate_video(path):
    step = "validate_video"
    filename = os.path.basename(path)

    log_section(f"📹 Memvalidasi: {filename}")
    log_info(step, f"Path lengkap: {path}")

    res = VideoCheckResult(path)

    # Step 1 — Basic file check
    log_info(step, "→ Step 1/4: Basic file check")
    if not check_basic(path, res):
        log_error(step, "Basic check gagal, melewati step selanjutnya")
        return res

    # Step 2 — Stream & duration
    log_info(step, "→ Step 2/4: Stream & durasi")
    duration = check_streams_and_duration(path, res)

    # Step 3 — Decode error check
    if enable_decode_check:
        log_info(step, "→ Step 3/4: Decode error check")
        max_s = decode_check_seconds if decode_check_seconds > 0 else None
        check_decode_errors(path, res, max_seconds=max_s)
    else:
        log_info(step, "→ Step 3/4: Decode error check [DILEWATI — dinonaktifkan]")

    # Step 4 — Black screen check
    if enable_black_check and duration:
        log_info(step, "→ Step 4/4: Black screen check")
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
        log_info(step, "→ Step 4/4: Black screen check [DILEWATI — dinonaktifkan]")
    else:
        log_info(step, "→ Step 4/4: Black screen check [DILEWATI — durasi tidak valid]")

    status = "VALID ✅" if res.is_valid else f"INVALID ❌ ({len(res.issues)} masalah)"
    log_info(step, f"Hasil akhir: {status}")

    return res


def validate_videos_in_folder(folder, extensions, recursive=True):
    step = "scan_folder"
    log_section("📁 Mulai Scan Folder")
    log_info(step, f"Folder  : {folder}")
    log_info(step, f"Ekstensi: {', '.join(extensions)}")
    log_info(step, f"Rekursif: {recursive}")

    results = []
    if not os.path.isdir(folder):
        log_error(step, f"Folder tidak ditemukan: {folder}")
        print(f"⚠ Folder tidak ditemukan: {folder}")
        return results

    iterator = Path(folder).rglob("*") if recursive else Path(folder).glob("*")
    all_files = sorted(iterator)
    matched = [f for f in all_files if f.suffix.lower() in extensions]

    log_info(step, f"Total file ditemukan: {len(all_files)}, "
                   f"cocok ekstensi: {len(matched)}")

    for idx, f in enumerate(matched, 1):
        log_info(step, f"[{idx}/{len(matched)}] Memproses: {f.name}")
        results.append(validate_video(str(f)))

    return results


# ===================== EKSEKUSI =====================
log_section("🚀 Video Validity Checker — Mulai")

extensions = tuple(
    ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
    for ext in file_extensions.split(",") if ext.strip()
)

log_info("init", f"Ekstensi yang akan diperiksa: {extensions}")
log_info("init", f"Decode check  : {'aktif, maks ' + str(decode_check_seconds) + 's' if enable_decode_check else 'nonaktif'}")
log_info("init", f"Black check   : {'aktif' if enable_black_check else 'nonaktif'}")

results = validate_videos_in_folder(folder_path, extensions, recursive=recursive_search)

invalid = [r for r in results if not r.is_valid]
valid_count = len(results) - len(invalid)

log_section("📊 HASIL AKHIR")
log_info("summary", f"Total diproses : {len(results)}")
log_info("summary", f"Valid          : {valid_count}")
log_info("summary", f"Invalid        : {len(invalid)}")

print(f"\n📊 Total: {len(results)} | ✅ Valid: {valid_count} | ❌ Invalid: {len(invalid)}\n")

if not print_summary_only:
    display_list = invalid if show_only_invalid else results
    for r in display_list:
        print(r)
        print("-" * 50)