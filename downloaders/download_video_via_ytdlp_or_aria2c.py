#@title 🔽 Download Video (yt-dlp + aria2c)

import os
import subprocess
import time
import sys
import re
import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

#@markdown ⚙️ **INPUT CONFIGURATION**
filename = ""  #@param {type:"string"}
download_url = ""  #@param {type:"string"}
output_dir = "/content/media_toolkit/downloads/video"  #@param {type:"string"}
backend = "yt-dlp" #@param ["yt-dlp","aria2c"]
filename_suffix = "Diana Rider"  #@param {type:"string"}
use_suffix = False  #@param {type:"boolean"}

#@markdown ---
#@markdown 🔧 **ARIA2C CONFIGURATION**
aria2c_connections = 8 #@param {type:"integer", min:1, max:64}
aria2c_split = 8 #@param {type:"integer", min:1, max:64}
aria2c_segments = 8 #@param {type:"integer", min:1, max:64}
aria2c_min_split_size = "2M" #@param ["1M", "2M", "4M", "8M", "16M"] {type:"string"}
aria2c_file_allocation = "none" #@param ["none", "prealloc", "falloc", "trunc"] {type:"string"}
download_timeout = 1800  #@param {type:"integer", min:60, max:3600}

#@markdown ---
#@markdown 🔑 **COOKIES CONFIGURATION**
cookies_file = ""  #@param {type:"string"}
use_cookies = False  #@param {type:"boolean"}

#@markdown 🔑 **PO TOKEN CONFIGURATION**
po_token = ""  #@param {type:"string"}
use_po_token_provider = False  #@param {type:"boolean"}

#@markdown 🌐 **HTTP HEADERS CONFIGURATION**
referer_url = "https://javplayer.cc/"  #@param ["", "https://surrit.store/", "https://missav.ws/", "https://javplayer.cc/", "https://luluvdo.com/", "https://rou.video/", "https://www.pornhub.com/", "https://www.xvideos.com/"]
use_origin = True  #@param {type:"boolean"}
custom_user_agent = ""
use_custom_headers = True  #@param {type:"boolean"}

#@markdown 🕵️ **IMPERSONATION**
impersonate_browser = "chrome" #@param ["firefox","chrome","edge","safari"]

#@markdown 🐛 **DEBUG MODE**
DEBUG_RAW_OUTPUT = False  #@param {type:"boolean"}

@dataclass
class FilenameOptions:
    suffix: str = ""
    use_suffix: bool = False


@dataclass
class DownloaderConfig:
    backend: str = "yt-dlp"
    timeout: int = 1800


@dataclass
class Aria2Config:
    connections: int = 8
    split_count: int = 8
    segments: int = 8
    min_split_size: str = "2M"
    file_allocation: str = "none"


@dataclass
class AuthenticationConfig:
    cookies_file: str = ""
    use_cookies: bool = False
    po_token: str = ""
    use_po_token_provider: bool = False


@dataclass
class RequestConfig:
    referer_url: str = ""
    origin_url: str = ""
    custom_user_agent: str = ""
    use_custom_headers: bool = False
    impersonate_browser: str = ""


@dataclass
class DownloadConfig:
    filename_options: FilenameOptions
    output_dir: str
    downloader: DownloaderConfig
    aria2: Aria2Config
    authentication: AuthenticationConfig
    request: RequestConfig
    debug_raw_output: bool = False


def _create_download_config() -> DownloadConfig:
    """Create DownloadConfig from the Colab input values."""
    return DownloadConfig(
        filename_options=FilenameOptions(
            suffix=filename_suffix,
            use_suffix=use_suffix,
        ),
        output_dir=output_dir,
        downloader=DownloaderConfig(
            backend=backend,
            timeout=download_timeout,
        ),
        aria2=Aria2Config(
            connections=aria2c_connections,
            split_count=aria2c_split,
            segments=aria2c_segments,
            min_split_size=aria2c_min_split_size,
            file_allocation=aria2c_file_allocation,
        ),
        authentication=AuthenticationConfig(
            cookies_file=cookies_file,
            use_cookies=use_cookies,
            po_token=po_token,
            use_po_token_provider=use_po_token_provider,
        ),
        request=RequestConfig(
            referer_url=referer_url,
            origin_url=referer_url.rstrip("/") if use_origin else "",
            custom_user_agent=custom_user_agent,
            use_custom_headers=use_custom_headers,
            impersonate_browser=impersonate_browser,
        ),
        debug_raw_output=DEBUG_RAW_OUTPUT,
    )


def log(message: str, level: str = "INFO") -> None:
    print(f"{level}:VideoDownloader:{message}", flush=True)

# 📦 GENERIC INSTALLERS
def _ensure_python_package(pkg_name: str, import_name: str = None, upgrade: bool = False):
    """
    Ensure pip package is installed.
    - pkg_name: nama di pip
    - import_name: nama import (kalau beda)
    """
    import_name = import_name or pkg_name

    try:
        __import__(import_name)
        log(f"{pkg_name} already installed")

        if upgrade:
            log(f"Upgrading {pkg_name}...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "--upgrade", pkg_name],
                check=True
            )
            log(f"{pkg_name} upgraded successfully")

    except ImportError:
        log(f"Installing {pkg_name}...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", pkg_name],
            check=True
        )
        log(f"{pkg_name} installed successfully")

try:
    from packaging import version
except ImportError:
    _ensure_python_package("packaging")
    from packaging import version

def _ensure_system_binary(binary_name: str, install_cmd: list):
    """
    Ensure system binary tersedia (aria2c, ffmpeg, dll)
    """
    result = subprocess.run(["which", binary_name], capture_output=True, text=True)

    if result.returncode != 0:
        log(f"Installing {binary_name}...")
        subprocess.run(install_cmd, check=True)
        log(f"{binary_name} installed successfully")
    else:
        log(f"{binary_name} already installed")

# 🚀 MAIN DEPENDENCY MANAGER
def _install_dependencies(config: DownloadConfig) -> None:
    log("Starting dependency setup...")

    # 📦 CORE PYTHON DEPENDENCIES
    _ensure_python_package("yt-dlp", import_name="yt_dlp", upgrade=config.authentication.use_po_token_provider)

    # 🕵️ REQUIRED FOR --extractor-args "generic:impersonate"
    _ensure_python_package("curl_cffi")

    # 🔑 OPTIONAL: PO TOKEN PROVIDER
    if config.authentication.use_po_token_provider:
        _ensure_python_package("yt-dlp-get-pot")

    # ⚡ SYSTEM DEPENDENCIES
    if config.downloader.backend.lower() == "aria2c":
        result = subprocess.run(["which", "aria2c"], capture_output=True, text=True)
        if result.returncode != 0:
            log("Installing aria2c...")
            subprocess.run(["apt-get", "update"], check=True)
            subprocess.run(["apt-get", "install", "-y", "aria2"], check=True)
            log("aria2c installed successfully")
        else:
            log("aria2c already installed")

    _ensure_system_binary("ffprobe", ["apt-get", "install", "-y", "ffmpeg"])
    log("✅ All dependencies are ready!")

# 🧹 SANITIZE FILENAME FUNCTION
def _sanitize_filename(filename: str, max_length: int = 130) -> str:
    if not filename or not filename.strip():
        wib_tz = timezone(timedelta(hours=7))
        timestamp = datetime.now(wib_tz).strftime("%d-%m-%Y_%H%M%S")
        return timestamp

    sanitized = filename.lower().strip()
    sanitized = re.sub(r'[^\w\s-]', '_', sanitized)
    sanitized = re.sub(r'[\s-]+', '_', sanitized)
    sanitized = re.sub(r'_{2,}', '_', sanitized)
    sanitized = sanitized.strip('_')

    if not sanitized:
        wib_tz = timezone(timedelta(hours=7))
        timestamp = datetime.now(wib_tz).strftime("%d%m%Y_%H%M%S")
        return timestamp

    # ✂️ TRUNCATE per kata (split by underscore), bukan per karakter
    if max_length and len(sanitized) > max_length:
        words = sanitized.split('_')
        result_words = []
        current_length = 0

        for word in words:
            # +1 untuk underscore penyambung (kecuali kata pertama)
            extra = len(word) + (1 if result_words else 0)
            if current_length + extra > max_length:
                break
            result_words.append(word)
            current_length += extra

        # Fallback: kalau kata pertama saja sudah melebihi max_length,
        # potong kata itu secara karakter agar tidak menghasilkan string kosong
        if not result_words:
            sanitized = words[0][:max_length].rstrip('_')
        else:
            sanitized = '_'.join(result_words)

    return sanitized

# 🔍 VIDEO ANALYSIS FUNCTIONS
def _get_video_metadata(file_path: str) -> dict:
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        metadata = {
            'status': 'Unknown',
            'duration': '00:00:00',
            'resolution': 'N/A',
            'codec': 'N/A',
            'fps': 'N/A',
            'size': 0,
            'orientation': 'Unknown',
            'created': datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
        }

        file_size = os.path.getsize(file_path)
        metadata['size'] = file_size

        video_stream = None
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break

        if video_stream:
            duration_sec = float(video_stream.get('duration', data.get('format', {}).get('duration', 0)))
            if duration_sec > 0:
                hours = int(duration_sec // 3600)
                minutes = int((duration_sec % 3600) // 60)
                seconds = int(duration_sec % 60)
                metadata['duration'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            width = video_stream.get('width', 0)
            height = video_stream.get('height', 0)
            if width and height:
                metadata['resolution'] = f"{width}x{height}"
                metadata['orientation'] = 'Portrait' if height > width else 'Landscape'

            metadata['codec'] = video_stream.get('codec_name', 'N/A')
            fps_str = video_stream.get('r_frame_rate', '0/1')
            if '/' in fps_str:
                num, den = fps_str.split('/')
                if den != '0':
                    fps = float(num) / float(den)
                    metadata['fps'] = f"{fps:.1f}"

        if file_size > 1024:
            metadata['status'] = 'Completed'

        return metadata
    except Exception as e:
        return {'status': 'Error', 'error': str(e)}

def _analyze_downloaded_files(output_dir: str, original_files: set) -> dict:
    summary = {
        'total_files': 0,
        'new_files': 0,
        'new_filenames': [],
        'total_size_bytes': 0,
        'new_files_size_bytes': 0,
        'total_duration_seconds': 0,
        'files_metadata': [],
        'status_breakdown': {},
        'resolution_distribution': {}
    }

    if not os.path.exists(output_dir): return summary
    current_files = set(os.listdir(output_dir))
    new_files = current_files - original_files
    video_files = [f for f in current_files if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))]
    summary['total_files'] = len(video_files)
    summary['new_files'] = len([f for f in new_files if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))])

    for video_file in video_files:
        file_path = os.path.join(output_dir, video_file)
        metadata = _get_video_metadata(file_path)
        metadata['filename'] = video_file
        summary['files_metadata'].append(metadata)
        size = metadata.get('size', 0)
        summary['total_size_bytes'] += size

        if video_file in new_files:
            summary['new_files_size_bytes'] += size
            summary['new_filenames'].append(video_file)

        try:
            h, m, s = map(int, metadata.get('duration', '00:00:00').split(':'))
            summary['total_duration_seconds'] += h * 3600 + m * 60 + s
        except: pass

        status = metadata.get('status', 'Unknown')
        summary['status_breakdown'][status] = summary['status_breakdown'].get(status, 0) + 1
        resolution = metadata.get('resolution', 'Unknown')
        summary['resolution_distribution'][resolution] = summary['resolution_distribution'].get(resolution, 0) + 1

    return summary

def _print_download_summary(summary: dict, output_dir: str) -> None:
    total_size_mb = summary['total_size_bytes'] / (1024**2)
    new_size_mb = summary['new_files_size_bytes'] / (1024**2)
    success_rate = (summary['status_breakdown']['Completed']/summary['total_files']*100 if summary['total_files']>0 else 0)
    new_files_names = ", ".join(summary['new_filenames']) if summary['new_filenames'] else "None"

    print("📊 DOWNLOAD SUMMARY")
    print(f"├─ Output Directory         : {output_dir}")
    print(f"├─ New Files Name           : {new_files_names}")
    print(f"├─ Newly Downloaded Files   : {summary['new_files']}")
    print(f"├─ Newly Downloaded Size    : {new_size_mb:.2f} MB")
    print(f"├─ Total Files              : {summary['total_files']}")
    print(f"├─ Total Size               : {total_size_mb:.2f} MB")
    print(f"├─ Success Rate             : {success_rate:.1f}%")
    print("└─ FILE DETAILS:")
    for metadata in summary['files_metadata']:
        status_icon = "✔" if metadata.get('status') == 'Completed' else "✘"
        print(f"  {status_icon} [{metadata.get('size', 0)/1024/1024:.1f} MB] {metadata['filename']}")

# 🔧 COMMAND BUILDERS
def _build_ytdlp_command(download_url: str, output_dir: str, temp_dir: str, filename_template: str) -> list:
    return [
        sys.executable, "-m", "yt_dlp",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--console-title",
        # Menggunakan --paths untuk memisahkan folder home (final) dan temp (fragmen)
        "--paths", f"home:{output_dir}",
        "--paths", f"temp:{temp_dir}",
        "-o", filename_template,
        "--continue",
        # Hapus '--no-part' agar yt-dlp menggunakan ekstensi .part di folder temp sebelum selesai
        "--verbose",
        download_url
    ]

# 🔧 COMMAND BUILDERS
def _add_authentication_arguments(cmd: list, config: AuthenticationConfig) -> list:
    """Add cookie and manual PO-token arguments to the downloader command."""
    if config.use_cookies and config.cookies_file and config.cookies_file.strip():
        cmd.extend(["--cookies", config.cookies_file])
        log(f"🍪 Using cookies file: {config.cookies_file}")

    if config.po_token and config.po_token.strip():
        cmd.extend(["--extractor-args", f"youtube:po_token={config.po_token}"])
        log("🔑 Using manual PO Token")

    return cmd


def _add_po_token_provider_arguments(cmd: list, config: AuthenticationConfig) -> list:
    if not config.use_po_token_provider:
        return cmd

    try:
        version_str = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True,
            text=True
        ).stdout.strip()

        if version.parse(version_str) >= version.parse("2024.08.06"):
            check = subprocess.run(
                [sys.executable, "-m", "pip", "show", "yt-dlp-get-pot"],
                capture_output=True, text=True
            )

            if check.returncode == 0:
                cmd.extend(["--po-token-provider", "default"])
                log("🔌 PO Token Provider enabled")
            else:
                log("⚠️ yt-dlp-get-pot not installed, skipping...")
        else:
            log(f"⚠️ yt-dlp {version_str} not support PO Provider")

    except Exception as e:
        log(f"⚠️ PO Provider check failed: {e}")

    return cmd

def _add_browser_impersonation_arguments(cmd: list, browser: str) -> list:
    # Mengatasi error 403 Cloudflare anti-bot challenge pada extractor [generic]
    # dengan meniru fingerprint TLS browser (butuh curl_cffi terpasang).
    if browser:
        cmd.extend(["--impersonate", browser])
        log(f"🕵️ Using browser impersonation: {browser}")
    return cmd

def _add_http_header_arguments(cmd: list, config: RequestConfig) -> list:
    """Add configured Referer, Origin, and User-Agent arguments."""
    if not config.use_custom_headers:
        log("🌐 Custom headers disabled, skipping...")
        return cmd

    if config.referer_url and config.referer_url.strip():
        cmd.extend(["--referer", config.referer_url.strip()])
        log(f"🌐 Using referer: {config.referer_url.strip()}")

    if config.origin_url and config.origin_url.strip():
        cmd.extend(["--add-header", f"Origin: {config.origin_url.strip()}"])
        log(f"🌐 Using origin: {config.origin_url.strip()}")

    if config.custom_user_agent and config.custom_user_agent.strip():
        cmd.extend(["--user-agent", config.custom_user_agent.strip()])
        log("🧑‍💻 Using custom User-Agent")

    return cmd


def _add_downloader_backend_arguments(cmd: list, downloader: DownloaderConfig,
                                      aria2: Aria2Config) -> list:
    """Add backend-specific downloader arguments and fragment concurrency."""
    if downloader.backend == "aria2c":
        args = (
            f"aria2c:-x {aria2.connections} -j {aria2.split_count} "
            f"-s {aria2.segments} -k {aria2.min_split_size} "
            f"--file-allocation={aria2.file_allocation}"
        )
        cmd.extend([
            "--downloader", "aria2c",
            "--downloader", "dash,m3u8:aria2c",
            "--downloader-args", args,
        ])

    # fallback paralelisasi buat stream m3u8 terenkripsi yang tetap jatuh ke native
    cmd.extend(["--concurrent-fragments", str(aria2.split_count)])
    return cmd


def _truncate_filename_for_display(name: str, max_len: int = 15) -> str:
    """
    Memotong filename kalau terlalu panjang, ambil bagian awal saja
    dan tambahkan '...' di akhir.
    Hanya untuk tampilan saja. Tidak untuk menyimpan nama file.
    """
    if len(name) <= max_len:
        return name.ljust(max_len)

    return name[:max_len - 3] + "..."

def _create_progress_bar(percent: float, width: int = 10) -> str:
    """
    Membuat progress bar visual dari karakter blok.
    Contoh: [▰▰▰▰▰▱▱▱▱▱]
    """
    filled = int(width * percent / 100)
    return "▰" * filled + "▱" * (width - filled)


def _handle_download_progress_line(line: str, display_filename: str = "") -> bool:
    if "[download]" in line and "%" in line:
        match = re.search(
            r"(\d+\.?\d*)%\s+of\s+~?\s*([\d.]+\w+)\s+at\s+([\d.]+\w+/s)\s+ETA\s+(\S+)(?:\s+\(frag\s+(\d+)/(\d+)\))?",
            line
        )
        if match:
            percent, size, speed, eta, frag_cur, frag_total = match.groups()
            bar = _create_progress_bar(float(percent))
            fname = _truncate_filename_for_display(display_filename) if display_filename else "Downloads"
            frag_info = f"  |  Frag: {frag_cur}/{frag_total}" if frag_cur else ""
            print(
                f"\r{fname}: [{bar}]{percent}%  |  Size: {size}  |  Speed: {speed}  |  ETA: {eta}{frag_info}",
                end="", flush=True
            )
        else:
            print(f"\r{line[:150]}", end="", flush=True)
        return True

    if line.startswith("[#") and "%" in line:
        print(f"{line[:150]}", flush=True)
        return True

    return False

def _log_raw_output(line: str) -> None:
    """
    Mode debug: log SEMUA baris mentah dari subprocess apa adanya,
    tanpa filter, supaya bisa dilihat format asli dari yt-dlp, aria2c, ffmpeg, dll.
    """

    log(f"[RAW] {line}", "DEBUG")

# 🚀 RUNNER
def _start_download_process(cmd: list):
    """Start the downloader subprocess and return the running process."""
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )


def _is_fatal_download_error(line: str) -> bool:
    """Return True when a downloader output line indicates a fatal error."""
    fatal_errors = [
        "errorCode=24",
        "Authorization failed",
        "Download aborted"
    ]
    return any(error in line for error in fatal_errors)


def _log_download_output_line(line: str) -> None:
    """Log or print one non-progress downloader output line."""
    if "[info]" in line or "[generic]" in line:
        log(line)
    elif "ERROR" in line or "error" in line:
        log(line, "ERROR")
    else:
        print(line[:150], flush=True)


def _handle_download_output_line(line: str, process, last_was_progress: bool, debug_raw_output: bool, display_filename: str) -> bool:
    """Process one downloader output line and return its progress-display state."""
    if debug_raw_output:
        _log_raw_output(line)

    if _is_fatal_download_error(line):
        if last_was_progress:
            print()
        log(f"🚨 FATAL: {line}", "CRITICAL")
        process.kill()
        process.wait()
        return False

    if _handle_download_progress_line(line, display_filename):
        return True

    if last_was_progress:
        print()

    _log_download_output_line(line)
    return False


def _process_download_output(process, debug_raw_output: bool, display_filename: str) -> bool:
    """Read and process downloader output; return False when a fatal error occurs."""
    last_was_progress = False

    for line in process.stdout:
        line = line.strip()
        if _is_fatal_download_error(line):
            _handle_download_output_line(line, process, last_was_progress, debug_raw_output, display_filename)
            return False

        last_was_progress = _handle_download_output_line(
            line, process, last_was_progress, debug_raw_output, display_filename
        )

    if last_was_progress:
        print()

    return True


def _wait_for_download_process(process, timeout: int) -> bool:
    """Wait for the downloader process and return whether it exited successfully."""
    process.wait(timeout=timeout)
    if process.returncode == 0:
        return True

    log(f"❌ Return code {process.returncode}", "ERROR")
    return False


def _run_download_process(cmd: list, timeout: int, debug_raw_output: bool = False, display_filename: str = "") -> bool:
    """Run the downloader subprocess, handle its output, timeout, and final status."""
    start_time = time.time()
    process = None

    try:
        process = _start_download_process(cmd)
        if not _process_download_output(process, debug_raw_output, display_filename):
            return False

        success = _wait_for_download_process(process, timeout)
        if success:
            elapsed = time.time() - start_time
            log(f"✅ Completed in {elapsed:.2f}s", "SUCCESS")
        return success

    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
        log("⏰ Timeout reached", "ERROR")
        return False

    except Exception as e:
        log(f"🚨 Unexpected error: {e}", "ERROR")
        return False


# 🎬 MAIN ORCHESTRATOR
def _prepare_download_filename(filename: str, options: FilenameOptions) -> str:
    """Sanitize the requested filename and optionally append the configured suffix."""
    sanitized_filename = _sanitize_filename(filename)

    if options.use_suffix and options.suffix.strip():
        suffix = _sanitize_filename(options.suffix)
        sanitized_filename = f"{sanitized_filename}_{suffix}"

    log(f"🧹 Filename: '{sanitized_filename}'")
    return sanitized_filename


def _prepare_download_directories(output_dir: str):
    """Create the output and temporary directories and return their paths."""
    temp_dir = os.path.join(output_dir, "temp")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    return output_dir, temp_dir


def _snapshot_existing_files(output_dir: str) -> set:
    """Capture the filenames already present in the output directory."""
    return set(os.listdir(output_dir)) if os.path.exists(output_dir) else set()


def _build_download_filename_template(sanitized_filename: str) -> str:
    """Build the yt-dlp output filename template."""
    return f"{sanitized_filename}.%(ext)s"


def _build_download_command(download_url: str, filename_template: str,
                             output_dir: str, temp_dir: str,
                             config: DownloadConfig) -> list:
    """Build the complete yt-dlp command from the download configuration."""
    cmd = _build_ytdlp_command(download_url, output_dir, temp_dir, filename_template)
    cmd = _add_authentication_arguments(cmd, config.authentication)
    cmd = _add_po_token_provider_arguments(cmd, config.authentication)
    cmd = _add_browser_impersonation_arguments(cmd, config.request.impersonate_browser)
    cmd = _add_http_header_arguments(cmd, config.request)
    cmd = _add_downloader_backend_arguments(cmd, config.downloader, config.aria2)
    return cmd


def download_video(download_url: str, filename: str, config: DownloadConfig) -> bool:
    """Download one video using the supplied URL, filename, and configuration."""
    sanitized_filename = _prepare_download_filename(
        filename, config.filename_options
    )
    original_files = _snapshot_existing_files(config.output_dir)
    output_dir, temp_dir = _prepare_download_directories(config.output_dir)
    filename_template = _build_download_filename_template(sanitized_filename)

    cmd = _build_download_command(
        download_url,
        filename_template,
        output_dir,
        temp_dir,
        config,
    )

    log(f"🎬 Starting download with {config.downloader.backend.upper()}")
    success = _run_download_process(
        cmd,
        config.downloader.timeout,
        config.debug_raw_output,
        filename,
    )

    if success:
        summary = _analyze_downloaded_files(output_dir, original_files)
        _print_download_summary(summary, output_dir)

    return success


# ✅ EXECUTE
if __name__ == "__main__":
    config = _create_download_config()
    _install_dependencies(config)

    success = download_video(download_url, filename, config)

    if success:
        log("🎉 Download finished!", "SUCCESS")
    else:
        log("💥 Download failed/aborted!", "ERROR")
