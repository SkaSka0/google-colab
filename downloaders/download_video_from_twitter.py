# @title 🎞️ Download Twitter Video
# @markdown - Input tweet URL (single/multiple videos)
tweet_url = "https://x.com/TopAV/status/2062718045802594325?s=20"  # @param {type: "string"}
video_dir = "/content/media_toolkit/downloads/twitter"  # @param {type: "string"}
cookies_path = "/content/drive/MyDrive/Cookies/x_cookies.txt"  # @param {type: "string"}
# @markdown - Pilih strategi penamaan file
filename_strategy = "description"  # @param ["auto", "custom", "title", "description", "id"]
custom_filename = ""  # @param {type: "string"}

import os
import re
import json
import subprocess
import time
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

class VideoDownloader:
    """Optimized Twitter video downloader"""

    VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".mov", ".avi")

    def __init__(self, video_dir: str, cookies_path: str = ""):
        self.video_dir = Path(video_dir)
        self.metadata_dir = self.video_dir / "metadata"
        self.cookies_path = Path(cookies_path) if cookies_path else None
        self.setup_directories()

    def setup_directories(self):
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    @property
    def use_cookies(self) -> bool:
        return self.cookies_path and self.cookies_path.exists() and self.cookies_path.stat().st_size > 0

    @staticmethod
    def log(message: str, level: str = "INFO", end: str = "\n", prefix: str = ""):
        print(f"{prefix}{level}:TwitterDownloader:{message}", end=end, flush=True)

    @staticmethod
    def format_duration(seconds: float) -> str:
        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours:02}:{minutes:02}:{secs:02}"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def sanitize_filename(name: str, max_words: int = 40, max_chars: int = 40) -> str:
        """
        Sanitize filename:
        - Replace non-word characters with _
        - Collapse multiple _
        - Limit to max_words (Latin) or max_chars (CJK)
        - Ensure fallback if result empty
        """
        # Ganti semua karakter non-word (Unicode aware) dengan _
        name = re.sub(r'\W+', '_', name, flags=re.UNICODE)
        # Hilangkan underscore berlebih
        name = re.sub(r'_+', '_', name)
        # Hapus underscore di awal/akhir
        name = name.strip('_')

        # Jika kosong, fallback
        if not name:
            return "video_" + str(int(time.time()))

        # Deteksi apakah string mengandung CJK
        if re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', name):
            # Batasi jumlah karakter untuk CJK
            if len(name) > max_chars:
                name = name[:max_chars]
        else:
            # Batasi jumlah kata untuk Latin
            parts = name.split('_')
            if len(parts) > max_words:
                parts = parts[:max_words]
            name = "_".join(parts)

        return name

    @staticmethod
    def build_filename(meta: dict, custom_filename: str = "", strategy: str = "auto") -> str:
        """
        Build filename berdasarkan strategi:
        - custom: gunakan custom_filename
        - title: gunakan meta['title']
        - description: gunakan meta['description']
        - id: gunakan meta['id']
        - auto: fallback ke urutan default (custom -> title -> description -> id -> timestamp)
        """
        base = None

        if strategy == "custom" and custom_filename.strip():
            base = custom_filename.strip()
        elif strategy == "title" and meta.get("title"):
            base = meta["title"]
        elif strategy == "description" and meta.get("description"):
            base = meta["description"]
        elif strategy == "id" and meta.get("id"):
            base = meta["id"]
        elif strategy == "auto":
            # gunakan urutan default
            if custom_filename.strip():
                base = custom_filename.strip()
            elif meta.get("title"):
                base = meta["title"]
            elif meta.get("description"):
                base = meta["description"]
            elif meta.get("id"):
                base = meta["id"]
            else:
                base = str(int(time.time()))

        # fallback kalau base kosong
        if not base:
            base = str(int(time.time()))

        return VideoDownloader.sanitize_filename(base)

class TwitterVideoDownloader(VideoDownloader):
    """Twitter-specific video downloader"""

    def __init__(self, video_dir: str, cookies_path: str = ""):
        super().__init__(video_dir, cookies_path)
        self.install_dependencies()

    def install_dependencies(self):
        if not shutil.which("yt-dlp"):
            self.log("Installing yt-dlp...")
            subprocess.run(["pip", "install", "yt-dlp"], capture_output=True, check=True)
            self.log("yt-dlp installed successfully")

    def extract_tweet_id(self, url: str) -> str:
        match = re.search(r"/status/(\d+)", url)
        if not match:
            raise ValueError(f"Invalid tweet URL: {url}")
        return match.group(1)

    def build_ytdlp_command(self, tweet_url: str, output_template: str) -> List[str]:
        base_command = [
            "yt-dlp",
            "-f", "best[height<=1080]",
            "--write-info-json",
            "--no-warnings",
            "--console-title",
            "--progress",
            "-o", output_template,
        ]
        if self.use_cookies:
            base_command.extend(["--cookies", str(self.cookies_path)])
        base_command.extend(["--concurrent-fragments", "4"])
        base_command.append(tweet_url)
        return base_command

    def render_progress_bar(self, percent: float, bar_length: int = 10) -> str:
        """
        Render progress bar dengan ▰ (filled) dan ▱ (empty).
        percent: 0..100
        bar_length: panjang bar dalam karakter
        """
        try:
            # pastikan percent berada di rentang 0..100
            p = max(0.0, min(100.0, float(percent)))
            filled_length = int(round(bar_length * p / 100.0))
            bar = "▰" * filled_length + "▱" * (bar_length - filled_length)
            return bar
        except Exception:
            # fallback sederhana
            filled_length = int(bar_length * 0 / 100)
            return "▱" * bar_length

    def parse_progress(self, line: str) -> Optional[Dict[str, str]]:
        """
        Parse output dari yt-dlp untuk menampilkan progress bar custom.
        Menghasilkan string seperti:
        [download] [▰▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱] 100.0% of    1.82GiB in 00:00:29 at 63.44MiB/s
        """
        # Normalisasi line
        text = line.strip()

        # Tangani bar progress yang mengandung persen
        if "[download]" in text and "%" in text:
            try:
                # Ambil persen (mencari pola 0-100 dengan desimal opsional)
                percent_match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", text)
                if percent_match:
                    percent = float(percent_match.group(1))

                    # Render bar
                    bar = self.render_progress_bar(percent, bar_length=10)

                    # Ambil bagian setelah persen untuk menampilkan sisa info (of SIZE in TIME at SPEED)
                    # Kita cari posisi persen terakhir lalu ambil substring setelahnya
                    last_percent_pos = text.rfind("%")
                    rest = text[last_percent_pos + 1 :].strip()

                    # Jika rest kosong, coba ambil info lain dari line (mis. ukuran/eta ada sebelum persen)
                    # Kita juga coba ambil potongan yang mengandung "of" jika ada
                    if not rest:
                        # cari "of" dan ambil dari sana
                        of_match = re.search(r"\bof\b.*", text, flags=re.IGNORECASE)
                        if of_match:
                            rest = of_match.group(0).strip()
                        else:
                            # fallback: ambil seluruh line tanpa bagian [download]
                            rest = text.replace("[download]", "").strip()

                    formatted = f"[download] [{bar}] {percent:.1f}% {rest}"
                    return {"type": "progress", "data": formatted}
            except Exception:
                return None

        # Tangani Destination line
        if "[download]" in text and "Destination:" in text:
            return {"type": "destination", "data": text}

        # Tangani other download messages (mis. merging, has already)
        if "[download]" in text:
            return {"type": "info", "data": text}

        return None

    def download_video(self, tweet_url: str) -> List[Path]:
        tweet_id = self.extract_tweet_id(tweet_url)
        self.log(f"Starting download for tweet {tweet_id}")

        output_template = str(self.video_dir / "%(id)s.%(ext)s")
        command = self.build_ytdlp_command(tweet_url, output_template)

        start_time = time.time()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            for line in process.stdout:
                progress_data = self.parse_progress(line)
                if progress_data:
                    if progress_data["type"] == "progress":
                        # Tampilkan progress bar di satu baris
                        print(f"\r{progress_data['data']}", end="", flush=True)
                    elif progress_data["type"] == "destination":
                        # Tampilkan destination di bar baru
                        self.log(f"Downloading to: {progress_data['data'].split('Destination: ')[-1]}")
                    else:
                        # Info lain dari yt-dlp, tampilkan sebagai baris baru
                        print("\n" + progress_data["data"])
                else:
                    # Jika tidak ter-parse, tampilkan raw line (opsional: bisa dikomentari)
                    # print(line, end="")
                    pass
            process.wait()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command)
        except subprocess.CalledProcessError as e:
            self.log(f"Download failed: {e}", "ERROR", prefix="\n")
            raise

        elapsed = time.time() - start_time
        self.log(f"Download completed in {elapsed:.2f}s", prefix="\n")
        return self.get_downloaded_files()

    def get_downloaded_files(self) -> List[Path]:
        return [f for f in self.video_dir.iterdir() if f.is_file() and f.suffix.lower() in self.VIDEO_EXTS]

    def process_metadata(self, video_files: List[Path], custom_filename: str = "") -> List[Path]:
        def process_single_metadata(video_file: Path):
            video_id = video_file.stem
            info_file = self.video_dir / f"{video_id}.info.json"
            if not info_file.exists():
                return None
            try:
                meta = json.loads(info_file.read_text(encoding="utf-8"))
                filename_base = self.build_filename(meta, custom_filename, filename_strategy)
                new_name = f"{filename_base}{video_file.suffix}"
                new_path = self.video_dir / new_name

                video_file.rename(new_path)

                meta_save_path = self.metadata_dir / f"{filename_base}.json"
                meta_save_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                info_file.unlink()
                return new_path
            except Exception as e:
                self.log(f"Failed to process metadata for {video_id}: {e}", "WARNING")
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(process_single_metadata, video_files))
        new_files = [r for r in results if r]
        self.log(f"Processed {len(new_files)} metadata files")
        return new_files

    def get_video_info(self, video_file: Path) -> Dict[str, Any]:
        video_id = video_file.stem
        meta_path = self.metadata_dir / f"{video_id}.json"
        info = {
            "file": video_file,
            "size_mb": video_file.stat().st_size / (1024 * 1024),
            "metadata_available": False
        }
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                info.update({
                    "metadata_available": True,
                    "resolution": f"{meta.get('width', 'N/A')}x{meta.get('height', 'N/A')}",
                    "duration": self.format_duration(meta.get('duration')),
                    "title": meta.get('title', 'N/A')[:50] + "..." if meta.get('title') else 'N/A',
                    "uploader": meta.get('uploader', 'N/A')
                })
            except Exception as e:
                self.log(f"Error reading metadata for {video_id}: {e}", "WARNING")
        return info

    def generate_summary(self, tweet_url: str, video_files: List[Path], elapsed: float):
        """Generate comprehensive download summary"""
        tweet_id = self.extract_tweet_id(tweet_url)

        # Hitung total size
        total_size_mb = sum(f.stat().st_size for f in video_files) / (1024 * 1024)

        summary_lines = [
            "📊 Download Summary",
            f"├─📌 Tweet URL        : {tweet_url}",
            f"├─🆔 Tweet ID         : {tweet_id}",
            f"├─🔐 Cookies Used     : {'Yes' if self.use_cookies else 'No'}",
            f"├─📂 Target Folder    : {self.video_dir}",
            f"├─⏱️ Total Time       : {elapsed:.2f}s",
            f"├─📹 Total Videos     : {len(video_files)}",
            f"└─📜 File Details     :"
        ]

        # Get video info in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            video_info_list = list(executor.map(self.get_video_info, video_files))

        for i, info in enumerate(video_info_list, 1):
            summary_lines.append(f"   {i}. {info['file'].name}")
            summary_lines.append(f"      ├─💾 File Size  : {info['size_mb']:.2f} MB")

            if info["metadata_available"]:
                summary_lines.append(f"      ├─🎞️ Resolution : {info['resolution']}")
                summary_lines.append(f"      ├─⏱️ Duration   : {info['duration']}")
                summary_lines.append(f"      ├─📝 Title      : {info['title']}")
                summary_lines.append(f"      └─👤 Uploader   : {info['uploader']}")
            else:
                summary_lines.append(f"      └─⚠️ Metadata not available")

        return "\n".join(summary_lines)

def main():
    start_time = time.time()
    try:
        downloader = TwitterVideoDownloader(video_dir, cookies_path)

        # Download video
        downloaded_files = downloader.download_video(tweet_url)
        if not downloaded_files:
            downloader.log("No video files were downloaded", "ERROR")
            return

        # Process metadata dan dapatkan file baru
        downloaded_files = downloader.process_metadata(downloaded_files, custom_filename)

        # Generate summary dengan file baru
        elapsed = time.time() - start_time
        summary = downloader.generate_summary(tweet_url, downloaded_files, elapsed)
        print("\n" + summary)

    except Exception as e:
        VideoDownloader.log(f"Download failed: {e}", "ERROR")
        raise

if __name__ == "__main__":
    main()
