#@title File Downloader (Hybrid: requests + aria2c)

import requests
import os
import re
import sys
import time
import mimetypes
import subprocess
import shutil
import psutil
from urllib.parse import unquote, urlparse, parse_qs
from tqdm import tqdm
from google.colab import drive

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
SHOW_DOWNLOAD_SUMMARY = True #@param {type:"boolean"}
#@markdown *(Show a summary: filename, size, duration, avg speed after the download)*
SHOW_SYSTEM_STATS = True #@param {type:"boolean"}
#@markdown *(Show Colab RAM & storage usage after the download finishes)*

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
APP_NAME = "FileDownloader"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REFERER = "https://google.com"

def simple_log(message):
    print(f"[{APP_NAME}] {message}")

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def format_duration(seconds):
    """
    Converts a duration in seconds into a human-readable string (e.g. 1m 23s).
    """
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

def print_download_summary(engine, filename, filepath, elapsed_seconds, expected_size=None):
    """
    Prints a clean summary block after a download finishes: filename,
    engine used, elapsed time, final size, and average speed.
    """
    actual_size = None
    if filepath and os.path.exists(filepath):
        actual_size = os.path.getsize(filepath)

    size_for_speed = actual_size if actual_size is not None else expected_size
    avg_speed = (size_for_speed / elapsed_seconds) if (size_for_speed and elapsed_seconds > 0) else 0

    simple_log("📋 Download Summary")
    simple_log(f"   📄 File     : {filename or 'Unknown'}")
    simple_log(f"   🛠️ Engine   : {engine}")
    simple_log(f"   📦 Size     : {format_bytes(actual_size) if actual_size is not None else 'Unknown'}")
    simple_log(f"   ⏱️ Duration : {format_duration(elapsed_seconds)}")
    simple_log(f"   🚀 Avg Speed: {format_bytes(avg_speed)}/s" if avg_speed else "   🚀 Avg Speed: N/A")
    simple_log(f"   📁 Path     : {filepath or 'Unknown'}")

def format_bytes(num_bytes):
    """
    Converts raw bytes into a human-readable string (e.g. 1.23 GB).
    """
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < step:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.2f} PB"

def show_system_stats():
    """
    Prints current Colab RAM and disk usage, so you know how much
    room is left after a download.
    """
    simple_log("📊 System Stats:")

    # --- RAM ---
    try:
        mem = psutil.virtual_memory()
        simple_log(
            f"   🧠 RAM   : {format_bytes(mem.used)} / {format_bytes(mem.total)} "
            f"used ({mem.percent}%) | Free: {format_bytes(mem.available)}"
        )
    except Exception as e:
        simple_log(f"   🧠 RAM   : Unable to read RAM stats ({e})")

    # --- Local Disk (/content) ---
    try:
        disk = shutil.disk_usage("/content")
        simple_log(
            f"   💾 Disk  : {format_bytes(disk.used)} / {format_bytes(disk.total)} "
            f"used | Free: {format_bytes(disk.free)}"
        )
    except Exception as e:
        simple_log(f"   💾 Disk  : Unable to read disk stats ({e})")

    # --- Google Drive (only if mounted) ---
    if os.path.exists("/content/drive/MyDrive"):
        try:
            drive_usage = shutil.disk_usage("/content/drive/MyDrive")
            simple_log(
                f"   ☁️ Drive : {format_bytes(drive_usage.used)} / {format_bytes(drive_usage.total)} "
                f"used | Free: {format_bytes(drive_usage.free)}"
            )
        except Exception as e:
            simple_log(f"   ☁️ Drive : Unable to read Drive stats ({e})")

def ensure_folder_exists(folder_path):
    if "/content/drive" in folder_path:
        simple_log("Storage target detected as Google Drive.")
        if not os.path.exists('/content/drive'):
            simple_log("Google Drive is not mounted yet. Mounting now...")
            drive.mount('/content/drive')
        else:
            simple_log("Google Drive is already mounted. Ready to use.")
    else:
        simple_log("Local (temporary) storage target. Skipping Drive mount.")

    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
        except OSError as e:
            simple_log(f"ERROR: Failed to create folder. Check your path. {e}")
            return False
    return True

# ==========================================
# REQUESTS ENGINE
# ==========================================

def get_full_file_info(response_headers, original_url, final_url):
    # 1. Content-Disposition
    header_cd = response_headers.get("content-disposition")
    if header_cd:
        fname = re.findall('filename="?([^"]+)"?', header_cd)
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

def custom_bar(n, total, width=20):
    """
    Builds a custom visual progress bar using unicode characters
    """
    fill_char = "▰"
    empty_char = "▱"

    ratio = n / total if total > 0 else 0
    percent = int(ratio * 100)
    filled_len = int(ratio * width)
    empty_len = width - filled_len

    visual_bar = f"{fill_char * filled_len}{empty_char * empty_len}"
    return f"「{visual_bar}」{percent:>3}%"

def make_custom_tqdm(total_bytes, initial_bytes):
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

def download_with_requests():
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Referer": REFERER,
    })

    try:
        simple_log("🔗 Contacting server...")
        start_time = time.time()
        with session.get(LINK_URL, stream=True, timeout=30) as r_head:
            r_head.raise_for_status()

            if r_head.history:
                simple_log(f"🔄 Redirect: {LINK_URL} -> {r_head.url}")

            raw_name, source_info = get_full_file_info(r_head.headers, LINK_URL, r_head.url)
            clean_name = sanitize_filename(CUSTOM_FILENAME.strip() or raw_name)
            total_size = int(r_head.headers.get('content-length', 0))
            final_url = r_head.url

        full_path = os.path.join(DOWNLOAD_FOLDER, clean_name)

        # --- RESUME LOGIC ---
        file_mode = 'wb'
        downloaded_bytes = 0
        range_header = {}

        if RESUME_DOWNLOAD and os.path.exists(full_path):
            local_file_size = os.path.getsize(full_path)
            if total_size > 0 and local_file_size < total_size:
                simple_log(f"⏪ Resuming from {local_file_size/(1024*1024):.2f} MB")
                downloaded_bytes = local_file_size
                range_header = {'Range': f'bytes={downloaded_bytes}-'}
                file_mode = 'ab'
            elif total_size > 0 and local_file_size == total_size:
                simple_log(f"✅ File '{clean_name}' has already been fully downloaded.")
                if SHOW_DOWNLOAD_SUMMARY:
                    print_download_summary("requests", clean_name, full_path, 0, expected_size=total_size)
                return

        with session.get(final_url, stream=True, timeout=30, headers=range_header) as response:
            if response.status_code == 416:
                simple_log("⚠️ Range error (file may already be complete).")
                return
            elif response.status_code == 200 and downloaded_bytes > 0:
                simple_log("🔄 Server rejected resume. Restarting from the beginning.")
                downloaded_bytes = 0
                file_mode = 'wb'

            content_length = int(response.headers.get('content-length', 0))
            if total_size == 0:
                total_size = content_length + downloaded_bytes

            simple_log(f"📄 File: {clean_name} ({source_info})")
            if total_size:
                simple_log(f"📦 Size: {total_size / (1024*1024):.2f} MB")

            # --- DISPLAY NAME SETUP ---
            display_name = clean_name[:15] + "..." if len(clean_name) > 18 else clean_name
            display_prefix = f"[{APP_NAME}] 📄 {display_name}"

            block_size = 8192

            with open(full_path, file_mode) as file:
                pbar = make_custom_tqdm(total_size, downloaded_bytes)

                try:
                    for chunk in response.iter_content(block_size):
                        if chunk:
                            file.write(chunk)
                            pbar.update(len(chunk))

                            bar_visual = custom_bar(pbar.n, total_size)
                            pbar.set_description_str(f"{display_prefix}:{bar_visual}")

                finally:
                    pbar.close()

            simple_log("✅ Download complete!")

            if SHOW_DOWNLOAD_SUMMARY:
                elapsed_seconds = time.time() - start_time
                print_download_summary("requests", clean_name, full_path, elapsed_seconds, expected_size=total_size)

    except requests.exceptions.Timeout:
        simple_log("⏱️ ERROR: Timeout while contacting the server.")
    except requests.exceptions.ConnectionError:
        simple_log("🔌 ERROR: Failed to connect to the server.")
    except Exception as e:
        simple_log(f"❌ SYSTEM ERROR: {e}")

# ==========================================
# ARIA2C ENGINE
# ==========================================

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

def aria2_progress_bar(percent, width=20):
    """
    Builds a single-line unicode progress bar, matching the style
    used by the requests engine.
    """
    fill_char = "▰"
    empty_char = "▱"

    percent = max(0, min(100, percent))
    filled_len = int((percent / 100) * width)
    empty_len = width - filled_len

    return f"「{fill_char * filled_len}{empty_char * empty_len}」{percent:>3}%"

def parse_aria2_output(process, display_name_holder):
    """
    Reads aria2c's stdout line by line, extracts progress info via regex,
    and renders it as a single, continuously-updating progress line.
    Any non-progress lines (results, errors, warnings) are printed as-is.
    """
    last_was_progress = False

    for raw_line in process.stdout:
        line = raw_line.strip()

        if not line or ARIA2_NOISE_PATTERN.match(line):
            continue

        if line.startswith("FILE:"):
            display_name_holder["name"] = os.path.basename(line.replace("FILE:", "").strip())
            continue

        match = ARIA2_PROGRESS_PATTERN.search(line)
        if match:
            percent = int(match.group("percent") or 0)
            downloaded = match.group("downloaded")
            total = match.group("total")
            speed = match.group("speed")
            eta = match.group("eta") or "N/A"
            conn = match.group("conn")

            name = display_name_holder["name"]
            display_name = name[:15] + "..." if len(name) > 18 else name
            prefix = f"[{APP_NAME}] 📄 {display_name}" if name else f"[{APP_NAME}]"

            bar_visual = aria2_progress_bar(percent)
            status_line = (
                f"{prefix} {bar_visual} "
                f"[{downloaded}/{total}, CN:{conn}, {speed}/s, ETA:{eta}]"
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

def ensure_aria2c_installed():
    if shutil.which("aria2c") is None:
        simple_log("⚙️ aria2c is not installed. Installing now...")
        subprocess.run(["apt-get", "install", "-y", "aria2"], check=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        simple_log("✅ aria2c installed successfully.")
    else:
        simple_log("✅ aria2c is already available.")

def download_with_aria2c():
    ensure_aria2c_installed()

    cmd = [
        "aria2c",
        LINK_URL,
        "--dir", DOWNLOAD_FOLDER,
        "--max-connection-per-server", str(CONNECTIONS_PER_SERVER),
        "--split", str(SPLIT_PER_FILE),
        "--min-split-size", MIN_SPLIT_SIZE,
        "--max-download-limit", SPEED_LIMIT,
        "--max-tries", str(MAX_RETRIES),
        "--retry-wait", str(RETRY_WAIT_TIME),
        "--connect-timeout", str(CONNECT_TIMEOUT),
        "--continue=true" if RESUME_DOWNLOAD else "--continue=false",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        "--console-log-level", "warn",
        "--summary-interval", "1",
        "--user-agent", USER_AGENT,
        "--referer", REFERER,
    ]

    if CUSTOM_FILENAME.strip():
        cmd.extend(["--out", CUSTOM_FILENAME.strip()])

    simple_log("🔗 Starting download via aria2c...")
    simple_log(f"⚙️ Connections: {CONNECTIONS_PER_SERVER} | Split: {SPLIT_PER_FILE} | Resume: {RESUME_DOWNLOAD}")

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

        display_name_holder = {"name": ""}
        parse_aria2_output(process, display_name_holder)

        process.wait()

        if process.returncode == 0:
            simple_log("✅ Download complete!")

            if SHOW_DOWNLOAD_SUMMARY:
                elapsed_seconds = time.time() - start_time
                final_name = CUSTOM_FILENAME.strip() or display_name_holder["name"]
                final_path = os.path.join(DOWNLOAD_FOLDER, final_name) if final_name else None
                print_download_summary("aria2c", final_name, final_path, elapsed_seconds)
        else:
            simple_log(f"❌ aria2c exited with error code: {process.returncode}")

    except FileNotFoundError:
        simple_log("❌ ERROR: aria2c not found even after installation. Try re-running the cell.")
    except KeyboardInterrupt:
        simple_log("⛔ Process forcibly stopped by user.")
        if process:
            process.terminate()
    except Exception as e:
        simple_log(f"❌ SYSTEM ERROR: {e}")

# ==========================================
# MAIN PROGRAM
# ==========================================

def run_downloader_pro():
    if not LINK_URL:
        simple_log("ERROR: URL link is empty.")
        return

    if not ensure_folder_exists(DOWNLOAD_FOLDER):
        return

    simple_log(f"🚀 Selected engine: {DOWNLOAD_ENGINE}")

    if DOWNLOAD_ENGINE == "aria2c":
        download_with_aria2c()
    elif DOWNLOAD_ENGINE == "requests":
        download_with_requests()
    else:
        simple_log(f"❌ ERROR: Unknown engine '{DOWNLOAD_ENGINE}'.")

    if SHOW_SYSTEM_STATS:
        show_system_stats()

if __name__ == "__main__":
    try:
        run_downloader_pro()
    except KeyboardInterrupt:
        print(f"\n[{APP_NAME}] ⛔ Process forcibly stopped by user (Keyboard Interrupt).")
    except Exception as e:
        simple_log(f"❌ Fatal error in main loop: {e}")