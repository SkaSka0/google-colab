# @title 🚀 Upload Video to Youtube (Batch Supported)
# @markdown <br><center><img src='https://www.gstatic.com/youtube/img/branding/favicon/favicon_144x144.png' height="50" alt="YouTube-logo"/></center>
# @markdown <center><h2><font color=red><b>Upload Video to Youtube</b></h2></center><br>

# @markdown <h3>📝 <b>Video Details</b></h3>

#@markdown - pada `VIDEO_PATH` masukkan path folder untuk Batch Upload
VIDEO_PATH = ""  # @param {type:"string"}
TITLE = ""  # @param {type:"string"}

# @markdown <b>💡 Tips Deskripsi:</b><br>
# @markdown - Ketik <b>\n</b> untuk ganti baris.<br>
# @markdown - Deskripsi ini akan otomatis digabung dengan TEMPLATE di bawah.
DESCRIPTION_HEADER = ""  # @param {type:"string"}
DESCRIPTION_CHANNEL = "Drakor Asiap" #@param ["Snack Drama Indo", "Drakor Asiap"]

TAGS = "Drakor"  # @param {type:"string"}
CATEGORY_ID = "1 - Film & Animation"  # @param ["1 - Film & Animation", "2 - Autos & Vehicles", "10 - Music", "15 - Pets & Animals", "17 - Sports", "19 - Travel & Events", "20 - Gaming", "22 - People & Blogs", "23 - Comedy", "24 - Entertainment", "25 - News & Politics", "26 - Howto & Style", "27 - Education", "28 - Science & Technology"]

# @markdown <h3>⚙️ <b>Configuration</b></h3>
PRIVACY_STATUS = "private"  # @param ["private", "unlisted", "public"]
UPLOAD_DELAY = 5  # @param {type:"number"}

TOKEN_PATH = "/content/drive/MyDrive/CR/token_dsr02.pickle"  # @param {type:"string"}
CHUNK_SIZE_MB = 5  # @param {type:"slider", min:1, max:10, step:1}

# =====================================================================
# TEMPLATE DESCRIPTION
# =====================================================================
TEMPLATE_FOOTER = f"""
-------------------------------------------
Selamat datang di {DESCRIPTION_CHANNEL} 🎬 — ruang terbaik untuk menikmati drama singkat penuh aksi 💥, petualangan 🌍, dan cerita yang menggugah!
Di sini kamu akan menemukan rangkaian episode pendek dengan karakter kuat, alur penuh kejutan, dan momen intens yang bikin nagih.

Terima kasih sudah berkunjung!
Jangan lupa like, share, dan subscribe 🔔 agar kamu tidak ketinggalan update terbaru!

#Drama #FYP
"""

import json, re, sys, time, os, mimetypes

VIDEO_EXTENSIONS = (
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".flv", ".wmv", ".mpeg", ".mpg", ".3gp"
)

APPNAME = "YouTubeUploader"

def log(message, level="INFO"):
    print(f"{level}:{APPNAME}: {message}")

def load_timestamps(video_path):
    """
    Mencari file timestamp dengan nama yang sama:
    video.mp4 → video_timestamps.json
    """
    base = os.path.splitext(os.path.basename(video_path))[0]
    ts_path = os.path.join(
        os.path.dirname(video_path),
        f"{base}_timestamps.json"
    )

    if not os.path.exists(ts_path):
        return None, None

    try:
        with open(ts_path, "r") as f:
            return json.load(f), ts_path
    except Exception:
        return None, ts_path

def timestamps_to_description(timestamps):
    """
    Convert JSON timestamps to YouTube chapter format
    """
    lines = []
    for t in timestamps:
        lines.append(f"{t['timestamp']} {t['episode']}")
    return "\n".join(lines)

def is_valid_timestamp(ts):
    return re.match(r"^\d{2}:\d{2}:\d{2}$", ts)

def build_description(video_path):
    base_desc = process_description(DESCRIPTION_HEADER, TEMPLATE_FOOTER)
    timestamps, ts_path = load_timestamps(video_path)
    video_name = os.path.basename(video_path)

    # ❌ Tidak ada JSON
    if not timestamps:
        if ts_path:
            log(
                f"Timestamp file found but invalid → {os.path.basename(ts_path)} "
                f"(video: {video_name})",
                "ERROR"
            )
        else:
            log(
                f"No timestamp JSON for video: {video_name}",
                "WARNING"
            )
        return base_desc

    # ❌ Kurang dari 3 chapter
    if len(timestamps) < 3:
        log(
            f"Timestamp JSON ignored ({len(timestamps)} chapters) → "
            f"{os.path.basename(ts_path)} (video: {video_name})",
            "WARNING"
        )
        return base_desc

    # ❌ Format timestamp rusak
    for t in timestamps:
        if not is_valid_timestamp(t.get("timestamp", "")):
            log(
                f"Invalid timestamp format in "
                f"{os.path.basename(ts_path)} (video: {video_name})",
                "ERROR"
            )
            return base_desc

    # ✅ SUCCESS
    log(
        f"Video: {video_name} → using timestamp JSON: "
        f"{os.path.basename(ts_path)} ({len(timestamps)} chapters)",
        "SUCCESS"
    )

    chapter_text = timestamps_to_description(timestamps)
    return f"{base_desc}\nTimestamp:\n{chapter_text}"

# =====================================================================
# 📌 2. Drive Auto-Mount
# =====================================================================
def ensure_drive_mounted(path):
    if "/content/drive" in path:
        if not os.path.exists("/content/drive"):
            log("Google Drive detected but not mounted. Mounting...", "INFO")
            try:
                from google.colab import drive
                drive.mount("/content/drive")
                log("Drive mounted!", "SUCCESS")
            except Exception as e:
                log(f"Drive mount failed: {e}", "ERROR")
                return False
    return True

# =====================================================================
# 📌 3. Dependency Installer
# =====================================================================
import subprocess
def install_dependencies():
    required = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + required)
    except:
        pass

# =====================================================================
# 📌 4. Auth & API
# =====================================================================
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

def get_authenticated_service(token_path):
    log("Loading credentials...", "INFO")
    if not os.path.exists(token_path):
        log("Token not found!", "ERROR")
        return None

    with open(token_path, 'rb') as f:
        creds = pickle.load(f)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            log("Refreshing token...", "WARNING")
            creds.refresh(Request())
            with open(token_path, 'wb') as f:
                pickle.dump(creds, f)
        else:
            return None

    return build('youtube', 'v3', credentials=creds)

# =====================================================================
# 📌 5. Description Processor
# =====================================================================
def process_description(user_input, template):
    return user_input.replace("\\n", "\n") + "\n" + template

# =====================================================================
# 📌 6. TITLE Auto Formatter
# =====================================================================
def filename_to_title(filename):
    name = os.path.splitext(os.path.basename(filename))[0]
    parts = name.replace("_", " ").split()
    return " ".join(word.capitalize() for word in parts)

# =====================================================================
# 📌 7. Upload Logic
# =====================================================================
def upload_file(youtube, file_path, title, description, tags, category, privacy, chunk_size):
    log(f"Uploading file: {file_path}", "INFO")
    log(f"Title: {title}", "INFO")

    tags_list = [x.strip() for x in tags.split(",")]

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags_list,
            "categoryId": category
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    }

    # 🎯 MIME type auto-detection
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = "video/*"  # fallback aman

    media = MediaFileUpload(
        file_path,
        chunksize=chunk_size * 1024 * 1024,
        resumable=True,
        mimetype=mime_type
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    start = time.time()
    response = None

    try:
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"\rINFO:{APPNAME}: Uploading {int(status.progress() * 100)}%", end="")
        print()

        vid = response.get("id")
        log(f"Upload Success → https://youtu.be/{vid}", "SUCCESS")

        dur = int(time.time() - start)
        log(f"Upload Time: {dur//60}m {dur%60}s", "INFO")

    except HttpError as e:
        result = handle_http_error(e)
        if result == "STOP":
            raise SystemExit  # hentikan batch total
    except Exception as e:
        log(f"Upload ERROR: {e}", "ERROR")

# =====================================================================
# 📌 8. Batch / Single Handler
# =====================================================================
def get_video_list(path):
    if os.path.isfile(path):
        if path.lower().endswith(VIDEO_EXTENSIONS):
            return [path]
        else:
            return []

    if os.path.isdir(path):
        files = [
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.lower().endswith(VIDEO_EXTENSIONS)
        ]
        return sorted(files)

    return []

# =====================================================================
# 📌 9. Rate limit
# =====================================================================
def handle_http_error(e):
    """
    Handle specific YouTube API HttpError cases
    """
    try:
        error_content = []
        if hasattr(e, "error_details") and e.error_details:
            error_content = e.error_details
        elif hasattr(e, "content"):
            error_content = json.loads(e.content.decode()).get("error", {}).get("errors", [])
        for err in error_content:
            reason = err.get("reason")
            message = err.get("message")

            # 🚫 Upload limit exceeded
            if reason == "uploadLimitExceeded":
                log(
                    "Upload limit exceeded! "
                    "YouTube membatasi jumlah upload harian akun ini.",
                    "ERROR"
                )
                log("Batch upload dihentikan.", "ERROR")
                return "STOP"

            # ❌ Error lain dari YouTube
            log(f"YouTube API Error: {message} (reason: {reason})", "ERROR")

    except Exception:
        log(f"Unhandled HttpError: {e}", "ERROR")

    return "CONTINUE"

# =====================================================================
# 📌 10. Main
# =====================================================================
def main():
    log(f"Starting {APPNAME}...", "INIT")

    # 🔧 Environment setup
    install_dependencies()
    ensure_drive_mounted(TOKEN_PATH)

    # 🔐 Auth
    youtube = get_authenticated_service(TOKEN_PATH)
    if not youtube:
        log("Auth failed!", "ERROR")
        return

    # 📂 Collect files
    files = get_video_list(VIDEO_PATH)
    if not files:
        log("No video files found!", "ERROR")
        return

    category_id = CATEGORY_ID.split(" - ")[0]

    # 🚀 Upload loop
    for index, file_path in enumerate(files, start=1):
        log(f"Processing ({index}/{len(files)}): {file_path}", "INFO")

        # 🔥 BUILD DESCRIPTION PER VIDEO
        final_desc = build_description(file_path)

        # Auto title
        if os.path.isdir(VIDEO_PATH):
            title_to_use = filename_to_title(file_path)
        else:
            title_to_use = TITLE

        upload_file(
            youtube=youtube,
            file_path=file_path,
            title=title_to_use,
            description=final_desc,
            tags=TAGS,
            category=category_id,
            privacy=PRIVACY_STATUS,
            chunk_size=CHUNK_SIZE_MB
        )

        if index < len(files):
            log(f"Waiting {UPLOAD_DELAY} seconds before next upload...", "INFO")
            time.sleep(UPLOAD_DELAY)

    log("All uploads completed!", "SUCCESS")

# =====================================================================
# 📌 11. Execution
# =====================================================================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        log("Upload dihentikan oleh user (KeyboardInterrupt).", "WARNING")
    except SystemExit:
        log("Program dihentikan secara aman.", "INFO")
    except Exception as e:
        log(f"Fatal error: {e}", "ERROR")