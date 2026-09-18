#@title 🔽 Download Video

# ============================================================
# IMPORTS
# ============================================================

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

import requests
from google.colab import userdata


# ============================================================
# ⚙️ CONFIGURATION — EDIT HERE
# ============================================================

# -------------------- General --------------------

filename = '/content/pending_subtitles.json'  #@param {type:"string"}
batch_processing = True  #@param {type:"boolean"}


# -------------------- Output ---------------------

output_dir = '/content/media_toolkit/downloads/video'  #@param {type:"string"}


# -------------------- Downloader -----------------

backend = 'yt-dlp'  #@param ["yt-dlp","aria2c"]
download_timeout = 1800  #@param {type:"integer", min:60, max:3600}


# -------------------- Aria2c ---------------------

aria2c_connections = 8  #@param {type:"integer", min:1, max:64}
aria2c_split = 8  #@param {type:"integer", min:1, max:64}
aria2c_segments = 8  #@param {type:"integer", min:1, max:64}
aria2c_min_split_size = '2M'  #@param ["1M","2M","4M","8M","16M"] {type:"string"}
aria2c_file_allocation = 'none'  #@param ["none","prealloc","falloc","trunc"] {type:"string"}


# -------------------- Batch ----------------------

BATCH_CHECKPOINT_SIZE = 5


# -------------------- Download URL ---------------

DOWNLOAD_URL_TEMPLATE = (
)


# -------------------- Title Sources ---------------

SOURCE_URL_TEMPLATES = [
]


# -------------------- Firecrawl -------------------

FIRECRAWL_API_URL = 'https://api.firecrawl.dev/v2/scrape'
FIRECRAWL_API_KEY_NAME = 'FIRECRAWL_API_KEY'
FIRECRAWL_TIMEOUT = 60

NOT_FOUND_KEYWORDS = [
    '404',
    'page not found',
    'not found',
    'video not found',
    "doesn't exist",
]


# ============================================================
# 🔧 UTILITY FUNCTIONS
# ============================================================

def log(message: str, level: str = 'INFO') -> None:
    """Print a formatted log message."""
    print(f'[{level}] {message}', flush=True)


def get_storage_info(path: str = '/content') -> str:
    """Return available and total storage in GB."""
    try:
        total, used, free = shutil.disk_usage(path)
        total_gb = total / 1024 ** 3
        free_gb = free / 1024 ** 3
        return f'{free_gb:.2f} GB / {total_gb:.2f} GB'
    except Exception:
        return 'Unknown'


def build_download_url(code: str) -> str:
    """Build the video download URL from the global template."""
    return DOWNLOAD_URL_TEMPLATE.format(code=code.upper())


def build_source_urls(code: str) -> list[str]:
    """Build all title-scraping source URLs from the global templates."""
    return [
        source.format(code=code.lower())
        for source in SOURCE_URL_TEMPLATES
    ]


# ============================================================
# 📦 DEPENDENCY MANAGEMENT
# ============================================================

def ensure_pip_package(
    pkg_name: str,
    import_name: str | None = None,
    upgrade: bool = False,
) -> None:
    """Install a Python package if it is not already available."""
    import_name = import_name or pkg_name

    try:
        __import__(import_name)
        log(f'{pkg_name} already installed')

        if upgrade:
            log(f'Upgrading {pkg_name}...')
            subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'pip',
                    'install',
                    '-q',
                    '--upgrade',
                    pkg_name,
                ],
                check=True,
            )
            log(f'{pkg_name} upgraded successfully')

    except ImportError:
        log(f'Installing {pkg_name}...')
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-q', pkg_name],
            check=True,
        )
        log(f'{pkg_name} installed successfully')


def ensure_binary(binary_name: str, install_cmd: list[str]) -> None:
    """Install a system binary if it is not available."""
    result = subprocess.run(
        ['which', binary_name],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        log(f'Installing {binary_name}...')
        subprocess.run(install_cmd, check=True)
        log(f'{binary_name} installed successfully')
    else:
        log(f'{binary_name} already installed')


def install_deps() -> None:
    """Install all dependencies required by the configured backend."""
    log('Starting dependency setup...')

    ensure_pip_package('requests')
    ensure_pip_package('beautifulsoup4', import_name='bs4')
    ensure_pip_package('yt-dlp', import_name='yt_dlp')

    if backend.lower() == 'aria2c':
        ensure_binary(
            'aria2c',
            ['apt-get', 'install', '-y', 'aria2'],
        )

    ensure_binary(
        'ffprobe',
        ['apt-get', 'install', '-y', 'ffmpeg'],
    )

    log('All dependencies are ready!')


# ============================================================
# 🔎 TITLE SCRAPING
# ============================================================

def extract_markdown_title(markdown: str) -> str:
    """Extract the first Markdown heading from scraped content."""
    for line in markdown.splitlines():
        line = line.strip()

        if line.startswith('#'):
            title = line.lstrip('#').strip()

            if title:
                return title

    return ''


def scrape_title(code: str) -> str:
    """Try each configured source until a valid title is found."""
    try:
        api_key = userdata.get(FIRECRAWL_API_KEY_NAME)

    except userdata.SecretNotFoundError:
        log(
            f"API Key '{FIRECRAWL_API_KEY_NAME}' tidak ditemukan "
            'di Colab Secrets!',
            'ERROR',
        )
        return ''

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    for target_url in build_source_urls(code):
        log(
            f'⏳ Meminta bantuan Firecrawl untuk menembus: '
            f'{target_url}'
        )

        payload = {
            'url': target_url,
            'formats': ['markdown'],
        }

        try:
            response = requests.post(
                FIRECRAWL_API_URL,
                headers=headers,
                json=payload,
                timeout=FIRECRAWL_TIMEOUT,
            )

            log(f'Status API Firecrawl: {response.status_code}')

            if response.status_code != 200:
                log(
                    f'API Firecrawl gagal ({response.status_code}). '
                    'Lanjut ke sumber berikutnya...',
                    'ERROR',
                )
                continue

            json_data = response.json()
            data = json_data.get('data', {})

            metadata = data.get('metadata', {})
            markdown = data.get('markdown', '')
            error = data.get('error')

            if error:
                log(f'Firecrawl Error: {error}', 'ERROR')
                continue

            target_status = (
                metadata.get('statusCode')
                or metadata.get('status_code')
                or metadata.get('status')
            )

            if target_status:
                log(f'Status Website Target: {target_status}')

                if int(target_status) != 200:
                    log(
                        f'Website mengembalikan HTTP {target_status}. '
                        'Lanjut ke sumber berikutnya...',
                        'ERROR',
                    )
                    continue

            scraped_title = (
                metadata.get('ogTitle')
                or metadata.get('og:title')
                or metadata.get('title')
            )

            if not scraped_title and markdown:
                scraped_title = extract_markdown_title(markdown)

            if not scraped_title:
                log(
                    'Metadata title tidak ditemukan. '
                    'Lanjut ke sumber berikutnya...',
                    'ERROR',
                )
                continue

            title_lower = scraped_title.lower()
            markdown_lower = markdown.lower()

            if any(
                keyword in title_lower
                for keyword in NOT_FOUND_KEYWORDS
            ):
                log('Halaman 404 terdeteksi dari judul.', 'ERROR')
                continue

            if any(
                keyword in markdown_lower
                for keyword in NOT_FOUND_KEYWORDS
            ):
                log('Halaman 404 terdeteksi dari isi halaman.', 'ERROR')
                continue

            log(f'Judul ditemukan: {scraped_title}', 'SUCCESS')
            return scraped_title

        except Exception as e:
            log(
                f'Terjadi error koneksi ke API: {e}. '
                'Lanjut ke sumber berikutnya...',
                'ERROR',
            )

    log(
        f"Gagal menemukan judul untuk kode '{code}' "
        'dari semua sumber.',
        'ERROR',
    )
    return ''


# ============================================================
# 📄 JSON / BATCH FILE MANAGEMENT
# ============================================================

def load_batch_json(json_path: str) -> list:
    """Load and validate the batch JSON file."""
    if not os.path.isfile(json_path):
        raise FileNotFoundError(
            f'File JSON tidak ditemukan: {json_path}'
        )

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError('Format JSON harus berupa array/list.')

    log(f'JSON berhasil dibaca: {len(data)} item')
    return data


def save_batch_json(json_path: str, data: list) -> bool:
    """Atomically save the batch JSON as a checkpoint."""
    json_path = os.path.abspath(json_path)
    directory = os.path.dirname(json_path)

    os.makedirs(directory, exist_ok=True)

    temp_path = f'{json_path}.tmp'

    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4,
            )
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, json_path)

        log(
            f'💾 Checkpoint JSON tersimpan: {json_path}',
            'SUCCESS',
        )
        return True

    except Exception as e:
        log(
            f'Gagal menyimpan checkpoint JSON: {e}',
            'ERROR',
        )

        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

        return False


# ============================================================
# 📝 FILENAME / VIDEO METADATA
# ============================================================

def sanitize_filename(filename: str) -> str:
    """Convert a title into a filesystem-friendly filename."""
    if not filename or not filename.strip():
        wib_tz = timezone(timedelta(hours=7))
        return datetime.now(wib_tz).strftime('%d-%m-%Y_%H%M%S')

    words = filename.split()
    limited_filename = ' '.join(words[:30])

    sanitized = limited_filename.lower().strip()
    sanitized = re.sub(r'[^\w\s-]', '_', sanitized)
    sanitized = re.sub(r'[\s-]+', '_', sanitized)
    sanitized = re.sub(r'_{2,}', '_', sanitized)
    sanitized = sanitized.strip('_')

    if not sanitized:
        wib_tz = timezone(timedelta(hours=7))
        return datetime.now(wib_tz).strftime('%d%m%Y_%H%M%S')

    return sanitized


def get_video_metadata(file_path: str) -> dict:
    """Read basic video metadata using ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v',
            'quiet',
            '-print_format',
            'json',
            '-show_format',
            '-show_streams',
            file_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)

        metadata = {
            'status': 'Unknown',
            'duration': '00:00:00',
            'resolution': 'N/A',
            'codec': 'N/A',
            'fps': 'N/A',
            'size': 0,
            'orientation': 'Unknown',
            'created': datetime.fromtimestamp(
                os.path.getctime(file_path)
            ).strftime('%Y-%m-%d %H:%M:%S'),
        }

        file_size = os.path.getsize(file_path)
        metadata['size'] = file_size

        video_stream = next(
            (
                stream
                for stream in data.get('streams', [])
                if stream.get('codec_type') == 'video'
            ),
            None,
        )

        if video_stream:
            duration_value = (
                video_stream.get('duration')
                or data.get('format', {}).get('duration')
                or 0
            )

            duration_sec = float(duration_value)

            if duration_sec > 0:
                hours = int(duration_sec // 3600)
                minutes = int(duration_sec % 3600 // 60)
                seconds = int(duration_sec % 60)

                metadata['duration'] = (
                    f'{hours:02d}:{minutes:02d}:{seconds:02d}'
                )

            width = video_stream.get('width', 0)
            height = video_stream.get('height', 0)

            if width and height:
                metadata['resolution'] = f'{width}x{height}'
                metadata['orientation'] = (
                    'Portrait'
                    if height > width
                    else 'Landscape'
                )

            metadata['codec'] = video_stream.get(
                'codec_name',
                'N/A',
            )

            fps_str = video_stream.get(
                'r_frame_rate',
                '0/1',
            )

            if '/' in fps_str:
                num, den = fps_str.split('/', 1)

                if den != '0':
                    fps = float(num) / float(den)
                    metadata['fps'] = f'{fps:.1f}'

        if file_size > 1024:
            metadata['status'] = 'Completed'

        return metadata

    except Exception as e:
        return {
            'status': 'Error',
            'error': str(e),
        }


def analyze_downloaded_files(
    original_files: set[str],
) -> dict:
    """Analyze video files in the configured output directory."""
    summary = {
        'total_files': 0,
        'new_files': 0,
        'new_filenames': [],
        'total_size_bytes': 0,
        'new_files_size_bytes': 0,
        'total_duration_seconds': 0,
        'files_metadata': [],
        'status_breakdown': {},
        'resolution_distribution': {},
    }

    if not os.path.exists(output_dir):
        return summary

    current_files = set(os.listdir(output_dir))
    new_files = current_files - original_files

    video_extensions = (
        '.mp4',
        '.mkv',
        '.avi',
        '.mov',
        '.webm',
    )

    video_files = [
        file_name
        for file_name in current_files
        if file_name.lower().endswith(video_extensions)
    ]

    summary['total_files'] = len(video_files)

    summary['new_files'] = len([
        file_name
        for file_name in new_files
        if file_name.lower().endswith(video_extensions)
    ])

    for video_file in video_files:
        file_path = os.path.join(output_dir, video_file)
        metadata = get_video_metadata(file_path)

        metadata['filename'] = video_file
        summary['files_metadata'].append(metadata)

        size = metadata.get('size', 0)
        summary['total_size_bytes'] += size

        if video_file in new_files:
            summary['new_files_size_bytes'] += size
            summary['new_filenames'].append(video_file)

        try:
            hours, minutes, seconds = map(
                int,
                metadata.get(
                    'duration',
                    '00:00:00',
                ).split(':'),
            )

            summary['total_duration_seconds'] += (
                hours * 3600
                + minutes * 60
                + seconds
            )

        except Exception:
            pass

        status = metadata.get('status', 'Unknown')

        summary['status_breakdown'][status] = (
            summary['status_breakdown'].get(status, 0) + 1
        )

        resolution = metadata.get(
            'resolution',
            'Unknown',
        )

        summary['resolution_distribution'][resolution] = (
            summary['resolution_distribution'].get(resolution, 0) + 1
        )

    return summary


def print_download_summary(summary: dict) -> None:
    """Print the download summary."""
    total_size_mb = summary['total_size_bytes'] / 1024 ** 2
    new_size_mb = summary['new_files_size_bytes'] / 1024 ** 2

    total_files = summary['total_files']

    success_rate = (
        summary['status_breakdown'].get('Completed', 0)
        / total_files
        * 100
        if total_files > 0
        else 0
    )

    new_files_names = (
        ', '.join(summary['new_filenames'])
        if summary['new_filenames']
        else 'None'
    )

    storage_info = get_storage_info()

    print('📊 DOWNLOAD SUMMARY')
    print(f'├─ Output Directory         : {output_dir}')
    print(f'├─ New Files Name           : {new_files_names}')
    print(f"├─ Newly Downloaded Files   : {summary['new_files']}")
    print(f'├─ Newly Downloaded Size    : {new_size_mb:.2f} MB')
    print(f"├─ Total Files              : {summary['total_files']}")
    print(f'├─ Total Size               : {total_size_mb:.2f} MB')
    print(f'├─ Success Rate             : {success_rate:.1f}%')
    print(f'├─ Colab Storage Available  : {storage_info}')
    print('└─ FILE DETAILS:')

    for metadata in summary['files_metadata']:
        status_icon = (
            '✔'
            if metadata.get('status') == 'Completed'
            else '✘'
        )

        size_mb = metadata.get('size', 0) / 1024 / 1024

        print(
            f"  {status_icon} "
            f"[{round(size_mb)} MB] "
            f"{metadata['filename']}"
        )


# ============================================================
# ⬇️ DOWNLOADER
# ============================================================

def build_base_command(
    download_url: str,
    filename_template: str,
) -> list[str]:
    """Build the base yt-dlp command."""
    temp_dir = os.path.join(output_dir, 'temp')

    return [
        sys.executable,
        '-m',
        'yt_dlp',
        '--merge-output-format',
        'mp4',
        '--no-playlist',
        '--console-title',
        '--paths',
        f'home:{output_dir}',
        '--paths',
        f'temp:{temp_dir}',
        '-o',
        filename_template,
        '--continue',
        '--verbose',
        download_url,
    ]


def inject_backend(cmd: list[str]) -> list[str]:
    """Add the configured downloader backend options."""
    if backend.lower() == 'aria2c':
        args = (
            f'aria2c:'
            f'-x {aria2c_connections} '
            f'-j {aria2c_split} '
            f'-s {aria2c_segments} '
            f'-k {aria2c_min_split_size} '
            f'--file-allocation={aria2c_file_allocation}'
        )

        cmd.extend([
            '--downloader',
            'aria2c',
            '--downloader-args',
            args,
        ])

        log('Aria2c backend active')

    return cmd


def truncate_filename(
    name: str,
    max_len: int = 10,
) -> str:
    """Shorten a filename for progress display."""
    if len(name) <= max_len:
        return name.ljust(max_len)

    return name[:max_len - 3] + '...'


def make_bar(
    percent: float,
    width: int = 10,
) -> str:
    """Create a simple text progress bar."""
    filled = int(width * percent / 100)

    return (
        '▰' * filled
        + '▱' * (width - filled)
    )


def handle_progress_line(
    line: str,
    display_name: str,
) -> bool:
    """Handle yt-dlp / aria2c progress output."""
    if '[download]' in line and '%' in line:
        match = re.search(
            r'(\d+\.?\d*)%\s+of\s+~?\s*'
            r'([\d.]+\w+)\s+at\s+'
            r'([\d.]+\w+/s)\s+ETA\s+(\S+)'
            r'(?:\s+\(frag\s+(\d+)/(\d+)\))?',
            line,
        )

        if match:
            (
                percent,
                size,
                speed,
                eta,
                frag_cur,
                frag_total,
            ) = match.groups()

            bar = make_bar(float(percent))
            fname = truncate_filename(
                display_name or 'Downloads'
            )

            frag_info = (
                f'  |  Frag: {frag_cur}/{frag_total}'
                if frag_cur
                else ''
            )

            print(
                f'\r{fname}: [{bar}]{percent}%  |  '
                f'Size: {size}  |  Speed: {speed}  |  '
                f'ETA: {eta}{frag_info}',
                end='',
                flush=True,
            )

        else:
            print(
                f'\r{line[:150]}',
                end='',
                flush=True,
            )

        return True

    if line.startswith('[#') and '%' in line:
        print(f'{line[:150]}', flush=True)
        return True

    return False


def run_downloader(
    cmd: list[str],
    display_name: str,
) -> bool:
    """Run the downloader process and handle its output."""
    fatal_errors = [
        'errorCode=24',
        'Authorization failed',
        'Download aborted',
    ]

    start_time = time.time()
    last_was_progress = False
    process = None

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in process.stdout:
            line = line.strip()

            if any(
                error in line
                for error in fatal_errors
            ):
                log(
                    f'FATAL: {line}',
                    'CRITICAL',
                )
                process.kill()
                process.wait()
                return False

            if handle_progress_line(
                line,
                display_name,
            ):
                last_was_progress = True
                continue

            if last_was_progress:
                print()
                last_was_progress = False

            if '[info]' in line or '[generic]' in line:
                log(line)

            elif 'ERROR' in line or 'error' in line:
                log(line, 'ERROR')

            else:
                print(
                    line[:150],
                    flush=True,
                )

        process.wait(timeout=download_timeout)

        if process.returncode == 0:
            elapsed = time.time() - start_time

            log(
                f'Completed in {elapsed:.2f}s',
                'SUCCESS',
            )
            return True

        log(
            f'Return code {process.returncode}',
            'ERROR',
        )
        return False

    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()

        log(
            'Timeout reached',
            'ERROR',
        )
        return False

    except Exception as e:
        log(
            f'Unexpected error: {e}',
            'ERROR',
        )
        return False


def download_video(
    download_url: str,
    filename: str,
    skip_scrape: bool = False,
) -> bool:
    """Download one video using the global configuration."""
    if skip_scrape:
        target_name = filename
        log(
            f"Batch mode → menggunakan title dari JSON: "
            f"'{target_name}'"
        )

    else:
        scraped_title = scrape_title(filename)

        log(f"Scrape Title: '{scraped_title}'")

        target_name = (
            scraped_title
            if scraped_title
            else filename
        )

    sanitized_filename = sanitize_filename(target_name)

    log(
        f"Filename: '{sanitized_filename}'"
    )

    storage_info = get_storage_info()

    log(
        f'Colab Storage Available: {storage_info}'
    )

    os.makedirs(output_dir, exist_ok=True)

    temp_dir = os.path.join(
        output_dir,
        'temp',
    )

    os.makedirs(
        temp_dir,
        exist_ok=True,
    )

    original_files = set(
        os.listdir(output_dir)
    )

    filename_template = (
        f'{sanitized_filename}.%(ext)s'
    )

    cmd = build_base_command(
        download_url,
        filename_template,
    )

    cmd = inject_backend(cmd)

    log(
        f'🎬 Starting download with '
        f'{backend.upper()}'
    )

    success = run_downloader(
        cmd,
        target_name,
    )

    if success:
        summary = analyze_downloaded_files(
            original_files
        )

        print_download_summary(summary)

    return success


# ============================================================
# 📦 BATCH PROCESSING
# ============================================================

def process_batch(json_path: str) -> None:
    """Process all pending items from the batch JSON."""
    batch_items = load_batch_json(json_path)
    total = len(batch_items)

    if total == 0:
        log(
            'Tidak ada item di dalam JSON.',
            'ERROR',
        )
        return

    success_count = 0
    failed_count = 0
    skipped_count = 0
    checkpoint_success_count = 0

    log('')
    log('=' * 60)
    log('🚀 BATCH PROCESSING')
    log('=' * 60)
    log(f'📄 JSON       : {json_path}')
    log(f'📦 Total item : {total}')
    log(
        f'💾 Checkpoint : setiap '
        f'{BATCH_CHECKPOINT_SIZE} file sukses'
    )
    log('=' * 60)

    for index, item in enumerate(
        batch_items,
        start=1,
    ):
        if not isinstance(item, dict):
            log(
                f'Item #{index} bukan object JSON. '
                'Dilewati.',
                'ERROR',
            )
            failed_count += 1
            continue

        code = str(
            item.get('nama_file', '')
        ).strip()

        title = str(
            item.get('title', '')
        ).strip()

        if not code:
            log(
                f"Item #{index} tidak memiliki "
                f"'nama_file'. Dilewati.",
                'ERROR',
            )
            failed_count += 1
            continue

        if not title:
            log(
                f"Item #{index} tidak memiliki "
                f"'title'. Dilewati.",
                'ERROR',
            )
            failed_count += 1
            continue

        if item.get('downloaded', False) is True:
            skipped_count += 1

            log(
                f'⏭️ [{index}/{total}] '
                'SKIP → sudah downloaded'
            )
            log(f'    Code  : {code}')
            log(f'    Title : {title}')

            continue

        log('')
        log('=' * 60)
        log(
            f'📦 BATCH ITEM {index}/{total}'
        )
        log(f'Code  : {code}')
        log(f'Title : {title}')
        log('=' * 60)

        download_url = build_download_url(code)

        log(f'🔗 URL: {download_url}')

        success = download_video(
            download_url=download_url,
            filename=title,
            skip_scrape=True,
        )

        if success:
            success_count += 1
            checkpoint_success_count += 1

            batch_items[index - 1]['downloaded'] = True

            log(
                f'✅ Download berhasil '
                f'({checkpoint_success_count}/'
                f'{BATCH_CHECKPOINT_SIZE} '
                'menuju checkpoint)'
            )

            if (
                checkpoint_success_count
                >= BATCH_CHECKPOINT_SIZE
            ):
                log('')
                log('💾 CHECKPOINT')
                log(
                    f'Menyimpan status '
                    f'{checkpoint_success_count} '
                    'download berhasil ke JSON...'
                )

                saved = save_batch_json(
                    json_path,
                    batch_items,
                )

                if saved:
                    log(
                        '✅ Checkpoint berhasil disimpan.',
                        'SUCCESS',
                    )
                    checkpoint_success_count = 0

                else:
                    log(
                        '⚠️ Checkpoint gagal disimpan!',
                        'ERROR',
                    )

        else:
            failed_count += 1

            log(
                f'❌ Download gagal: {code}',
                'ERROR',
            )

            batch_items[index - 1]['downloaded'] = False

    # ---------------- Final checkpoint ----------------

    if checkpoint_success_count > 0:
        log('')
        log('💾 FINAL CHECKPOINT')
        log(
            f'Menyimpan {checkpoint_success_count} '
            'file sukses yang tersisa...'
        )

        saved = save_batch_json(
            json_path,
            batch_items,
        )

        if saved:
            log(
                '✅ Final checkpoint berhasil disimpan.',
                'SUCCESS',
            )
        else:
            log(
                '❌ Final checkpoint gagal disimpan.',
                'ERROR',
            )

    # ---------------- Batch summary ------------------

    log('')
    log('=' * 60)
    log('📊 BATCH SUMMARY')
    log('=' * 60)
    log(f'Total       : {total}')
    log(f'Downloaded  : {success_count}')
    log(f'Skipped     : {skipped_count}')
    log(f'Failed      : {failed_count}')
    log(f'Checkpoint  : {json_path}')
    log('=' * 60)

    downloaded_total = sum(
        1
        for item in batch_items
        if (
            isinstance(item, dict)
            and item.get('downloaded', False) is True
        )
    )

    pending_total = total - downloaded_total

    log(
        f'📦 Total downloaded di JSON : '
        f'{downloaded_total}'
    )
    log(
        f'⏳ Pending                  : '
        f'{pending_total}'
    )
    log('=' * 60)


# ============================================================
# 🚀 MAIN
# ============================================================

def main() -> None:
    """Application entry point."""
    install_deps()

    if batch_processing:
        log('')
        log('🔄 Batch processing mode aktif')
        log(f'📄 Input JSON: {filename}')

        process_batch(filename)

    else:
        log('')
        log('🎯 Single file mode aktif')

        download_url = build_download_url(filename)

        success = download_video(
            download_url=download_url,
            filename=filename,
            skip_scrape=False,
        )

        if success:
            log(
                'Download finished!',
                'SUCCESS',
            )
        else:
            log(
                'Download failed/aborted!',
                'ERROR',
            )


if __name__ == '__main__':
    main()
