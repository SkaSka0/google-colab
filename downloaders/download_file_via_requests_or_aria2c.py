#@title File Downloader (Hybrid: requests + aria2c)

import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

import psutil
import requests
from google.colab import drive
from tqdm import tqdm

# ==========================================
# BASIC CONFIGURATION
# ==========================================
LINK_URL = "" #@param {type:"string"}
DOWNLOAD_FOLDER = "/content/media_toolkit/downloads" #@param {type:"string"}
CUSTOM_FILENAME = "" #@param {type:"string"}
#@markdown *(Leave Filename empty to auto-detect from server)*

DOWNLOAD_ENGINE = "aria2c" #@param ["aria2c", "requests"]
#@markdown *(aria2c = faster, multi-connection, recommended for large files.*
#@markdown *requests = simple single-connection, uses a custom progress bar.)*

# ==========================================
# ARIA2C CONFIGURATION (used only if engine = aria2c)
# ==========================================
CONNECTIONS_PER_SERVER = 16 #@param {type:"slider", min:1, max:16, step:1}
SPLIT_PER_FILE = 16 #@param {type:"slider", min:1, max:16, step:1}
MIN_SPLIT_SIZE = "5M" #@param ["1M", "5M", "10M", "20M", "50M"]
SPEED_LIMIT = "0" #@param {type:"string"}
#@markdown *(Speed limit e.g. "1M" = 1MB/s, "0" = unlimited)*
MAX_RETRIES = 5 #@param {type:"slider", min:0, max:20, step:1}
RETRY_WAIT_TIME = 5 #@param {type:"slider", min:0, max:60, step:1}
CONNECT_TIMEOUT = 30 #@param {type:"integer"}

# ==========================================
# SHARED CONFIGURATION
# ==========================================
RESUME_DOWNLOAD = True #@param {type:"boolean"}
SHOW_FILE_INFO = True #@param {type:"boolean"}
#@markdown *(Show file name, size, type, resume support, etc. BEFORE the download starts)*
SHOW_DOWNLOAD_SUMMARY = True #@param {type:"boolean"}
#@markdown *(Show a summary: filename, size, duration, avg speed after the download)*
SHOW_SYSTEM_STATS = True #@param {type:"boolean"}
#@markdown *(Show Colab RAM & storage usage after the download finishes)*

# ==========================================
# CONSTANTS
# ==========================================
APP_NAME = "FileDownloader"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REFERER = "https://google.com"

SUPPORTED_ENGINES = ("aria2c", "requests")
REQUEST_TIMEOUT_SECONDS = 30
DOWNLOAD_BLOCK_SIZE = 8192

# Matches lines like:
# [#1b08b6 576KiB/262MiB(0%) CN:8 DL:1.2MiB ETA:3m24s]
ARIA2_PROGRESS_PATTERN = re.compile(
    r'\[#(?P<gid>\w+)\s+'
    r'(?P<downloaded>[\d.]+\S*?)/(?P<total>[\d.]+\S*?)'
    r'(?:\((?P<percent>\d+)%\))?\s+'
    r'CN:(?P<conn>\d+)\s+'
    r'DL:(?P<speed>[\d.]+\S*)'
    r'(?:\s+ETA:(?P<eta>\S+))?\]'
)

# Lines that are just decorative noise from the multi-line summary block
ARIA2_NOISE_PATTERN = re.compile(
    r'^(\*\*\*.*\*\*\*|=+|-+)$'
)


# ==========================================
# CONFIGURATION OBJECTS
# ==========================================
@dataclass
class DownloadInput:
    url: str
    folder: str
    custom_filename: str


@dataclass
class Aria2Config:
    connections: int
    split: int
    min_split_size: str
    speed_limit: str
    max_retries: int
    retry_wait: int
    connect_timeout: int


@dataclass
class RuntimeOptions:
    engine: str
    resume: bool
    show_file_info: bool
    show_summary: bool
    show_system_stats: bool


@dataclass
class AppConfig:
    source: DownloadInput
    aria2: Aria2Config
    options: RuntimeOptions


@dataclass
class RemoteFileInfo:
    """What the server tells us about the file before we download it."""
    final_url: str
    redirected: bool
    status_code: int
    probe_method: str            # "HEAD" or "GET"
    filename: str
    filename_source: str
    size_bytes: int              # 0 = unknown
    content_type: str            # "" = unknown
    supports_resume: Optional[bool]  # None = server did not say
    last_modified: str
    server: str


def _create_app_config() -> AppConfig:
    """Build a fresh AppConfig from the Colab form values.

    Called once per run: a Colab cell can be re-executed in the same
    kernel, so a previous instance must never be reused.
    """
    return AppConfig(
        source=DownloadInput(
            url=LINK_URL,
            folder=DOWNLOAD_FOLDER,
            custom_filename=CUSTOM_FILENAME,
        ),
        aria2=Aria2Config(
            connections=CONNECTIONS_PER_SERVER,
            split=SPLIT_PER_FILE,
            min_split_size=MIN_SPLIT_SIZE,
            speed_limit=SPEED_LIMIT,
            max_retries=MAX_RETRIES,
            retry_wait=RETRY_WAIT_TIME,
            connect_timeout=CONNECT_TIMEOUT,
        ),
        options=RuntimeOptions(
            engine=DOWNLOAD_ENGINE,
            resume=RESUME_DOWNLOAD,
            show_file_info=SHOW_FILE_INFO,
            show_summary=SHOW_DOWNLOAD_SUMMARY,
            show_system_stats=SHOW_SYSTEM_STATS,
        ),
    )


# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def log(message: str, level: str = "INFO") -> None:
    """Print a log line. INFO has no level tag; other levels are prefixed."""
    if level == "INFO":
        print(f"[{APP_NAME}] {message}")
    else:
        print(f"[{APP_NAME}] {level}: {message}")


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)


def _format_duration(seconds: float) -> str:
    """Convert a duration in seconds into a human-readable string (e.g. 1m 23s)."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _format_bytes(num_bytes: float) -> str:
    """Convert raw bytes into a human-readable string (e.g. 1.23 GB)."""
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < step:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.2f} PB"


def _truncate_display_name(name: str) -> str:
    """Shorten a filename for the one-line progress display only."""
    return name[:15] + "..." if len(name) > 18 else name


def _build_progress_bar(percent: float, width: int = 20) -> str:
    """Build a single-line unicode progress bar shared by both engines."""
    percent = max(0.0, min(100.0, percent))
    filled_len = int((percent / 100) * width)
    empty_len = width - filled_len
    return f"「{'▰' * filled_len}{'▱' * empty_len}」{int(percent):>3}%"


def _log_request_error(error: Exception) -> None:
    """Log a requests-related failure with a user-friendly message."""
    if isinstance(error, requests.exceptions.Timeout):
        log("⏱️ Timeout while contacting the server.", "ERROR")
    elif isinstance(error, requests.exceptions.ConnectionError):
        log("🔌 Failed to connect to the server.", "ERROR")
    else:
        log(f"❌ System error: {error}", "ERROR")


def _show_system_stats() -> None:
    """Print current Colab RAM and disk usage, so you know how much room is left."""
    log("📊 System Stats:")

    # --- RAM ---
    try:
        mem = psutil.virtual_memory()
        log(
            f"   🧠 RAM   : {_format_bytes(mem.used)} / {_format_bytes(mem.total)} "
            f"used ({mem.percent}%) | Free: {_format_bytes(mem.available)}"
        )
    except Exception as e:
        log(f"   🧠 RAM   : Unable to read RAM stats ({e})")

    # --- Local Disk (/content) ---
    try:
        disk = shutil.disk_usage("/content")
        log(
            f"   💾 Disk  : {_format_bytes(disk.used)} / {_format_bytes(disk.total)} "
            f"used | Free: {_format_bytes(disk.free)}"
        )
    except Exception as e:
        log(f"   💾 Disk  : Unable to read disk stats ({e})")

    # --- Google Drive (only if mounted) ---
    if os.path.exists("/content/drive/MyDrive"):
        try:
            drive_usage = shutil.disk_usage("/content/drive/MyDrive")
            log(
                f"   ☁️ Drive : {_format_bytes(drive_usage.used)} / {_format_bytes(drive_usage.total)} "
                f"used | Free: {_format_bytes(drive_usage.free)}"
            )
        except Exception as e:
            log(f"   ☁️ Drive : Unable to read Drive stats ({e})")


def _print_download_summary(engine: str, filename: str, filepath: Optional[str],
                            elapsed_seconds: float, expected_size: Optional[int] = None) -> None:
    """Print a summary block after a download: file, engine, time, size, avg speed."""
    actual_size = None
    if filepath and os.path.exists(filepath):
        actual_size = os.path.getsize(filepath)

    size_for_speed = actual_size if actual_size is not None else expected_size
    avg_speed = (size_for_speed / elapsed_seconds) if (size_for_speed and elapsed_seconds > 0) else 0

    log("📋 Download Summary")
    log(f"   📄 File     : {filename or 'Unknown'}")
    log(f"   🛠️ Engine   : {engine}")
    log(f"   📦 Size     : {_format_bytes(actual_size) if actual_size is not None else 'Unknown'}")
    log(f"   ⏱️ Duration : {_format_duration(elapsed_seconds)}")
    log(f"   🚀 Avg Speed: {_format_bytes(avg_speed)}/s" if avg_speed else "   🚀 Avg Speed: N/A")
    log(f"   📁 Path     : {filepath or 'Unknown'}")


def _ensure_folder_exists(folder_path: str) -> bool:
    if "/content/drive" in folder_path:
        log("Storage target detected as Google Drive.")
        if not os.path.exists('/content/drive'):
            log("Google Drive is not mounted yet. Mounting now...")
            drive.mount('/content/drive')
        else:
            log("Google Drive is already mounted. Ready to use.")
    else:
        log("Local (temporary) storage target. Skipping Drive mount.")

    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
        except OSError as e:
            log(f"Failed to create folder. Check your path. {e}", "ERROR")
            return False
    return True


# ==========================================
# REMOTE FILE INFO (pre-download)
# ==========================================
def _detect_filename(response_headers, final_url: str) -> tuple[str, str]:
    """Work out the file name from the response. Returns (name, how_it_was_found)."""
    # 1. Content-Disposition
    header_cd = response_headers.get("content-disposition")
    if header_cd:
        fname = re.findall(r'filename="?([^"]+)"?', header_cd)
        if len(fname) > 0:
            return unquote(fname[0]), "Header (Content-Disposition)"

    # 2. URL Path
    parsed_url = urlparse(final_url)
    path_filename = os.path.basename(parsed_url.path)
    if path_filename and '.' in path_filename:
        return unquote(path_filename), "URL Path"

    # 3. Query Parameters
    query_params = parse_qs(parsed_url.query)
    for key in ['filename', 'file', 'name']:
        if key in query_params:
            candidate = query_params[key][0]
            if '.' in candidate:
                return unquote(candidate), f"URL Query (?{key}=)"

    # 4. Guess extension
    content_type = response_headers.get("content-type", "").split(";")[0].strip()
    extension = mimetypes.guess_extension(content_type) or ".bin"
    base_name = path_filename if path_filename else "downloaded_file"

    return f"{base_name}{extension}", "Content-Type Guess"


def _parse_content_length(response_headers) -> int:
    try:
        return int(response_headers.get("content-length", 0) or 0)
    except ValueError:
        return 0


def _parse_resume_support(response_headers) -> Optional[bool]:
    accept_ranges = response_headers.get("accept-ranges", "").lower()
    if "bytes" in accept_ranges:
        return True
    if "none" in accept_ranges:
        return False
    return None


def _build_remote_file_info(response: requests.Response, method: str) -> RemoteFileInfo:
    headers = response.headers
    filename, source = _detect_filename(headers, response.url)
    return RemoteFileInfo(
        final_url=response.url,
        redirected=bool(response.history),
        status_code=response.status_code,
        probe_method=method,
        filename=filename,
        filename_source=source,
        size_bytes=_parse_content_length(headers),
        content_type=headers.get("content-type", "").split(";")[0].strip(),
        supports_resume=_parse_resume_support(headers),
        last_modified=headers.get("last-modified", ""),
        server=headers.get("server", ""),
    )


def _probe_remote_file(url: str) -> RemoteFileInfo:
    """Ask the server about the file without downloading it.

    Tries a cheap HEAD request first and falls back to a streamed GET
    (body is never read) when the server rejects or drops HEAD requests.
    Raises requests exceptions if the server cannot be reached at all.
    """
    headers = {"User-Agent": USER_AGENT, "Referer": REFERER}

    try:
        with requests.head(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS,
                           allow_redirects=True) as response:
            if response.status_code < 400:
                return _build_remote_file_info(response, "HEAD")
    except requests.exceptions.ConnectionError:
        pass  # some servers drop HEAD requests; retry once with GET below

    with requests.get(url, headers=headers, stream=True,
                      timeout=REQUEST_TIMEOUT_SECONDS) as response:
        response.raise_for_status()
        return _build_remote_file_info(response, "GET")


def _fetch_remote_info(config: AppConfig) -> Optional[RemoteFileInfo]:
    """Probe the server. Fatal for the requests engine, best-effort for aria2c."""
    log("🔗 Contacting server...")
    try:
        return _probe_remote_file(config.source.url)
    except Exception as e:
        if config.options.engine == "requests":
            _log_request_error(e)
        else:
            log(f"Could not fetch file info ({e}). Continuing without it.", "WARNING")
        return None


def _resolve_target_filename(info: RemoteFileInfo, custom_filename: str, engine: str) -> str:
    """The name the file will be saved as (aria2c may still pick its own if unset)."""
    raw_name = custom_filename.strip() or info.filename
    # The requests engine sanitizes the name; aria2c receives it as-is via --out.
    return _sanitize_filename(raw_name) if engine == "requests" else raw_name


def _get_free_space_bytes(folder: str) -> Optional[int]:
    try:
        return shutil.disk_usage(folder).free
    except OSError:
        return None


def _describe_local_state(path: str, remote_size: int, resume: bool) -> str:
    """Describe whether (part of) the file already exists in the target folder."""
    if not os.path.exists(path):
        return "Not found locally (fresh download)"

    local_size = os.path.getsize(path)
    if remote_size <= 0:
        return f"Exists locally ({_format_bytes(local_size)}), remote size unknown"
    if local_size < remote_size:
        percent = local_size / remote_size * 100
        action = "will resume" if resume else "will restart (resume disabled)"
        return f"Partial file: {_format_bytes(local_size)} ({percent:.1f}%), {action}"
    if local_size == remote_size:
        return "Already fully downloaded"
    return f"Local file is larger than remote ({_format_bytes(local_size)}), will be re-downloaded"


def _log_remote_file_info(info: RemoteFileInfo, config: AppConfig) -> None:
    """Show everything we know about the file before the progress bar starts."""
    source, options = config.source, config.options
    target_name = _resolve_target_filename(info, source.custom_filename, options.engine)
    target_path = os.path.join(source.folder, target_name)
    extension = os.path.splitext(target_name)[1] or "none"

    log("🔎 File Info (before download)")
    log(f"   📄 Name      : {target_name} ({info.filename_source})")
    log(f"   📦 Size      : {_format_bytes(info.size_bytes) if info.size_bytes else 'Unknown'}")
    log(f"   🧩 Type      : {info.content_type or 'Unknown'} (extension: {extension})")

    resume_text = {True: "Yes (server supports ranges)",
                   False: "No (server rejects ranges)",
                   None: "Unknown (server did not say)"}[info.supports_resume]
    log(f"   ⏯️ Resumable : {resume_text}")

    if info.last_modified:
        log(f"   🕒 Modified  : {info.last_modified}")
    if info.server:
        log(f"   🖥️ Server    : {info.server}")
    if info.redirected:
        log(f"   🔄 Final URL : {info.final_url}")

    log(f"   📁 Target    : {target_path}")
    log(f"   💽 Local     : {_describe_local_state(target_path, info.size_bytes, options.resume)}")

    free_bytes = _get_free_space_bytes(source.folder)
    if free_bytes is not None:
        log(f"   🆓 Free disk : {_format_bytes(free_bytes)}")
        already_have = os.path.getsize(target_path) if os.path.exists(target_path) else 0
        still_needed = info.size_bytes - min(already_have, info.size_bytes)
        if info.size_bytes and still_needed > free_bytes:
            log(f"Not enough free space: need ~{_format_bytes(still_needed)}, "
                f"have {_format_bytes(free_bytes)}.", "WARNING")


# ==========================================
# REQUESTS ENGINE
# ==========================================
def _make_tqdm(total_bytes: int, initial_bytes: int) -> tqdm:
    return tqdm(
        total=total_bytes,
        initial=initial_bytes,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
        dynamic_ncols=True,
        bar_format="{desc} [{n_fmt}/{total_fmt}, {elapsed}<{remaining}, {rate_fmt}]",
        desc="",
        postfix="",
    )


def _log_compact_file_info(info: RemoteFileInfo, clean_name: str, total_size: int) -> None:
    """One-line file info, only used when the full info block is turned off."""
    log(f"📄 File: {clean_name} ({info.filename_source})")
    if total_size:
        log(f"📦 Size: {total_size / (1024 * 1024):.2f} MB")


def _run_requests_download(config: AppConfig, info: Optional[RemoteFileInfo]) -> None:
    source, options = config.source, config.options

    if info is None:
        return  # the probe failure was already logged by _fetch_remote_info

    start_time = time.time()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": REFERER})

    try:
        if info.redirected and not options.show_file_info:
            log(f"🔄 Redirect: {source.url} -> {info.final_url}")

        clean_name = _resolve_target_filename(info, source.custom_filename, "requests")
        total_size = info.size_bytes
        full_path = os.path.join(source.folder, clean_name)

        # --- RESUME LOGIC ---
        file_mode = 'wb'
        downloaded_bytes = 0
        range_header = {}

        if options.resume and os.path.exists(full_path):
            local_file_size = os.path.getsize(full_path)
            if total_size > 0 and local_file_size < total_size:
                log(f"⏪ Resuming from {local_file_size/(1024*1024):.2f} MB")
                downloaded_bytes = local_file_size
                range_header = {'Range': f'bytes={downloaded_bytes}-'}
                file_mode = 'ab'
            elif total_size > 0 and local_file_size == total_size:
                log(f"✅ File '{clean_name}' has already been fully downloaded.")
                if options.show_summary:
                    _print_download_summary("requests", clean_name, full_path, 0, expected_size=total_size)
                return

        with session.get(info.final_url, stream=True, timeout=REQUEST_TIMEOUT_SECONDS,
                         headers=range_header) as response:
            if response.status_code == 416:
                log("⚠️ Range error (file may already be complete).", "WARNING")
                return
            elif response.status_code == 200 and downloaded_bytes > 0:
                log("🔄 Server rejected resume. Restarting from the beginning.")
                downloaded_bytes = 0
                file_mode = 'wb'

            content_length = int(response.headers.get('content-length', 0))
            if total_size == 0:
                total_size = content_length + downloaded_bytes

            if not options.show_file_info:
                _log_compact_file_info(info, clean_name, total_size)

            display_prefix = f"[{APP_NAME}] 📄 {_truncate_display_name(clean_name)}"

            with open(full_path, file_mode) as file:
                pbar = _make_tqdm(total_size, downloaded_bytes)

                try:
                    for chunk in response.iter_content(DOWNLOAD_BLOCK_SIZE):
                        if chunk:
                            file.write(chunk)
                            pbar.update(len(chunk))

                            percent = (pbar.n / total_size * 100) if total_size > 0 else 0
                            pbar.set_description_str(f"{display_prefix}:{_build_progress_bar(percent)}")
                finally:
                    pbar.close()

            log("✅ Download complete!")

            if options.show_summary:
                elapsed_seconds = time.time() - start_time
                _print_download_summary("requests", clean_name, full_path, elapsed_seconds,
                                        expected_size=total_size)

    except Exception as e:
        _log_request_error(e)


# ==========================================
# ARIA2C ENGINE
# ==========================================
def _ensure_aria2c_installed() -> None:
    if shutil.which("aria2c") is None:
        log("⚙️ aria2c is not installed. Installing now...")
        subprocess.run(["apt-get", "install", "-y", "aria2"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("✅ aria2c installed successfully.")
    else:
        log("✅ aria2c is already available.")


def _build_aria2c_command(source: DownloadInput, aria2: Aria2Config, resume: bool) -> list[str]:
    cmd = [
        "aria2c",
        source.url,
        "--dir", source.folder,
        "--max-connection-per-server", str(aria2.connections),
        "--split", str(aria2.split),
        "--min-split-size", aria2.min_split_size,
        "--max-download-limit", aria2.speed_limit,
        "--max-tries", str(aria2.max_retries),
        "--retry-wait", str(aria2.retry_wait),
        "--connect-timeout", str(aria2.connect_timeout),
        "--continue=true" if resume else "--continue=false",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        "--console-log-level", "warn",
        "--summary-interval", "1",
        "--user-agent", USER_AGENT,
        "--referer", REFERER,
    ]

    if source.custom_filename.strip():
        cmd.extend(["--out", source.custom_filename.strip()])

    return cmd


def _stream_aria2c_output(process: subprocess.Popen) -> str:
    """Render aria2c's output as one continuously-updating progress line.

    Non-progress lines (results, errors, warnings) are printed as-is.
    Returns the file name aria2c reported (empty string if none).
    """
    reported_name = ""
    last_was_progress = False

    for raw_line in process.stdout:
        line = raw_line.strip()

        if not line or ARIA2_NOISE_PATTERN.match(line):
            continue

        if line.startswith("FILE:"):
            reported_name = os.path.basename(line.replace("FILE:", "").strip())
            continue

        match = ARIA2_PROGRESS_PATTERN.search(line)
        if match:
            percent = int(match.group("percent") or 0)
            eta = match.group("eta") or "N/A"

            prefix = (f"[{APP_NAME}] 📄 {_truncate_display_name(reported_name)}"
                      if reported_name else f"[{APP_NAME}]")

            status_line = (
                f"{prefix} {_build_progress_bar(percent)} "
                f"[{match.group('downloaded')}/{match.group('total')}, "
                f"CN:{match.group('conn')}, {match.group('speed')}/s, ETA:{eta}]"
            )

            sys.stdout.write("\r" + status_line + " " * 5)
            sys.stdout.flush()
            last_was_progress = True
        else:
            if last_was_progress:
                sys.stdout.write("\n")
                last_was_progress = False
            print(line)

    if last_was_progress:
        sys.stdout.write("\n")
        sys.stdout.flush()

    return reported_name


def _run_aria2c_download(config: AppConfig, info: Optional[RemoteFileInfo]) -> None:
    source, aria2, options = config.source, config.aria2, config.options

    _ensure_aria2c_installed()
    cmd = _build_aria2c_command(source, aria2, options.resume)

    log("🔗 Starting download via aria2c...")
    log(f"⚙️ Connections: {aria2.connections} | Split: {aria2.split} | Resume: {options.resume}")

    process = None
    start_time = time.time()
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        reported_name = _stream_aria2c_output(process)
        process.wait()

        if process.returncode == 0:
            log("✅ Download complete!")

            if options.show_summary:
                elapsed_seconds = time.time() - start_time
                # Fall back to the probed name if aria2c did not report one.
                final_name = (source.custom_filename.strip() or reported_name
                              or (info.filename if info else ""))
                final_path = os.path.join(source.folder, final_name) if final_name else None
                _print_download_summary("aria2c", final_name, final_path, elapsed_seconds)
        else:
            log(f"❌ aria2c exited with error code: {process.returncode}", "ERROR")

    except FileNotFoundError:
        log("❌ aria2c not found even after installation. Try re-running the cell.", "ERROR")
    except KeyboardInterrupt:
        log("⛔ Process forcibly stopped by user.", "WARNING")
        if process:
            process.terminate()
    except Exception as e:
        log(f"❌ System error: {e}", "ERROR")


# ==========================================
# MAIN PROGRAM
# ==========================================
def run_downloader_pro() -> None:
    config = _create_app_config()
    source, options = config.source, config.options

    if not source.url:
        log("URL link is empty.", "ERROR")
        return

    if not _ensure_folder_exists(source.folder):
        return

    log(f"🚀 Selected engine: {options.engine}")

    if options.engine in SUPPORTED_ENGINES:
        # aria2c only needs the probe for the info block; requests always needs it.
        needs_probe = options.engine == "requests" or options.show_file_info
        remote_info = _fetch_remote_info(config) if needs_probe else None

        if options.show_file_info and remote_info is not None:
            _log_remote_file_info(remote_info, config)

        if options.engine == "aria2c":
            _run_aria2c_download(config, remote_info)
        else:
            _run_requests_download(config, remote_info)
    else:
        log(f"❌ Unknown engine '{options.engine}'.", "ERROR")

    if options.show_system_stats:
        _show_system_stats()


if __name__ == "__main__":
    try:
        run_downloader_pro()
    except KeyboardInterrupt:
        print(f"\n[{APP_NAME}] ⛔ Process forcibly stopped by user (Keyboard Interrupt).")
    except Exception as e:
        log(f"❌ Fatal error in main loop: {e}", "ERROR")
