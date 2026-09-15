import os
import time
import asyncio
import json
import mimetypes

from tqdm import tqdm
from datetime import datetime 
from typing import Optional, Union
from humanize import naturalsize
from pyrogram import filters, Client
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pathlib import Path

from colab_fetcher import CONFIG_PATH
from colab_fetcher import load_credentials
from colab_fetcher.utils.client import app
from colab_fetcher.utils.logging import logger

# ==========================
# 📌 GLOBAL VARIABLE
# ==========================

completed_downloads = {}
active_downloads = {}

# Lock global untuk state management
state_lock = asyncio.Lock()
download_queue = asyncio.Queue()

# Tambahkan dictionary untuk menampung file sementara per user
batch_buffer = {}
batch_tasks = {}
BATCH_DELAY = 2  # detik

# State File
STATE_FILE = Path(__file__).resolve().parent.parent / "config/user_state.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Dictionary ekstensi file
EXTENSIONS = {
    # Video
    ".mp4": "video", ".avi": "video", ".mkv": "video", ".m2ts": "video",
    ".mov": "video", ".ts": "video", ".webm": "video", ".mpg": "video",
    # Audio
    ".mp3": "audio", ".wav": "audio", ".flac": "audio", ".aac": "audio",
    # Gambar
    ".jpg": "photo", ".jpeg": "photo", ".png": "photo", ".bmp": "photo",
    # Dokumen
    ".pdf": "pdf", ".doc": "document", ".docx": "document",
    # Archive
    ".zip": "archive", ".rar": "archive", ".7z": "archive",
    # Subtitle
    ".srt": "subtitle", ".ass": "subtitle"
}


# ==========================
# 📌 HANDLER FUNCTIONS
# ==========================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    user_id = message.from_user.id
    logger.info(f"/start command received from user {user_id}")
    await client.send_message(
        chat_id=message.chat.id,
        text=get_start_message(),
        reply_to_message_id=message.id
    )
    logger.info("Start message sent.")

@app.on_message(filters.command("help") & filters.private)
async def help_handler(client, message: Message):
    help_text = (
        "🛠️ <b>Telegram Fetcher Bot - Help</b>\n\n"
        "Berikut adalah daftar command yang tersedia:\n\n"
        "• <b>/start</b> - Memulai bot dan menampilkan pesan sambutan.\n"
        "• <b>/tgupload</b> - Mengunggah file dari Telegram ke Colab storage.\n"
        "• <b>/queue</b> - Menampilkan status antrian download, termasuk file aktif dan daftar file yang menunggu.\n"
        "• <b>/cancelall</b> - Membatalkan semua download aktif dan mengosongkan antrian.\n"
        "• <b>/help</b> - Menampilkan daftar command dan penjelasannya.\n\n"
        "📂 <b>Cara penggunaan:</b>\n"
        "1. Kirim file (document, video, audio, atau photo).\n"
        "2. Bot akan menambahkan file ke antrian download.\n"
        "3. Gunakan /queue untuk melihat status.\n"
        "4. Gunakan /cancelall untuk membatalkan semua proses.\n\n"
        "☁️ Pastikan Google Drive sudah di-mount jika ingin menyimpan ke Drive."
    )

    await client.send_message(
        chat_id=message.chat.id,
        text=help_text,
        reply_to_message_id=message.id,
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("tgupload"))
async def tgupload_command(client, message: Message):
    try:
        logger.info(f"Received /tgupload command from user {message.from_user.id}")

        await client.send_message(
            chat_id=message.chat.id,
            text=get_tgupload_message(),
            reply_to_message_id=message.id
        )

        await set_user_state(message.from_user.id, "waiting_for_file")
        logger.info(f"Set user {message.from_user.id} state to 'waiting_for_file'")
    except Exception as e:
        logger.exception("Error in /tgupload handler")
        await send_error(message, "processing_error", str(e))

@app.on_message(filters.private & (
    filters.document | filters.video | filters.audio |
    filters.photo | filters.voice | filters.sticker | filters.animation
))
async def handle_file_upload(client, message: Message):
    try:
        user_id = message.from_user.id

        # Validasi tipe file
        if not is_allowed_file(message):
            return await send_error(message, "invalid_type")

        output_dir = get_output_directory() 
        unique_name = get_unique_filename(output_dir, message)
        file_path = os.path.join(output_dir, unique_name)

        # Masukkan ke antrian download
        await download_queue.put((client, message, file_path, output_dir))
        await set_user_state(user_id, "queued")

        # ===== BATCHING MESSAGE =====
        filename = os.path.basename(file_path)

        # Inisialisasi buffer jika belum ada
        if user_id not in batch_buffer:
            batch_buffer[user_id] = []

        batch_buffer[user_id].append((message, filename))

        # Jika belum ada task batching, buat
        if user_id not in batch_tasks:
            batch_tasks[user_id] = asyncio.create_task(
                send_batch_message(client, message.chat.id, user_id)
            )

    except Exception as e:
        await send_error(message, "download_failed", str(e))
        logger.exception("Download error")

    finally:
        await clear_user_state(message.from_user.id)
        
@app.on_message(filters.command("queue"))
async def queue_command(client, message: Message):
    queue_text = "📊 <b>Status Antrian</b>\n\n"

    # Active download
    if active_downloads:
        queue_text += "📥 <b>Active Download:</b>\n"
        for msg_id, info in active_downloads.items():
            filename = info.get("filename", f"Pesan ID {msg_id}")
            # Link ke pesan progress
            queue_text += f"<a href='https://t.me/c/{info['chat_id']}/{msg_id}'>{filename}</a>\n"
    else:
        queue_text += "✅ Tidak ada download aktif.\n"

    # Queue size
    size = download_queue.qsize()
    queue_text += f"\n📂 <b>Total file dalam antrian:</b> {size}\n"

    # List file dalam queue
    if size > 0:
        queue_text += "\n📝 <b>Daftar file:</b>\n"
        for idx, item in enumerate(list(download_queue._queue), start=1):
            _, msg, file_path, _ = item
            filename = os.path.basename(file_path)
            short_name = smart_truncate_filename(filename)
            queue_text += f"{idx}. {short_name}\n"

        # Hitung total size
        total_size = 0
        for _, msg, _, _ in list(download_queue._queue):
            if msg.document:
                total_size += msg.document.file_size or 0
            elif msg.video:
                total_size += msg.video.file_size or 0
            elif msg.audio:
                total_size += msg.audio.file_size or 0
        if total_size > 0:
            from humanize import naturalsize
            queue_text += f"\n📦 <b>Total queue size:</b> {naturalsize(total_size)}\n"

    await message.reply_text(queue_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@app.on_callback_query(filters.regex(r"cancel_dl_(\d+)"))
async def handle_cancel(client, callback_query):
    message_id = int(callback_query.data.split("_")[-1])

    if message_id in active_downloads:
        active_downloads[message_id]["cancelled"] = True
        await callback_query.answer("Cancelling download...")
    else:
        await callback_query.answer("No active download to cancel", show_alert=True)

@app.on_message(filters.command("cancelall"))
async def cancel_all_command(client, message: Message):
    cancelled_count = 0

    # Batalkan semua download aktif
    if active_downloads:
        for msg_id in list(active_downloads.keys()):
            active_downloads[msg_id]["cancelled"] = True
            cancelled_count += 1

    # Kosongkan queue
    queue_size = download_queue.qsize()
    while not download_queue.empty():
        try:
            download_queue.get_nowait()
            download_queue.task_done()
        except asyncio.QueueEmpty:
            break

    # Buat pesan konfirmasi
    if cancelled_count > 0 or queue_size > 0:
        await message.reply_text(
            f"❌ Semua download dibatalkan.\n\n"
            f"📥 Active cancelled: {cancelled_count}\n"
            f"📂 Queue cleared: {queue_size}",
            parse_mode=ParseMode.HTML
        )
        logger.info(f"User {message.from_user.id} cancelled {cancelled_count} active downloads and cleared {queue_size} queued files.")
    else:
        await message.reply_text(
            "✅ Tidak ada download aktif atau file dalam antrian untuk dibatalkan.",
            parse_mode=ParseMode.HTML
        )

# ==========================
# 📌 WORKER & TASK FUNCTIONS
# ==========================

async def queue_worker():
    while True:
        client, message, file_path, output_dir = await download_queue.get()
        user_id = message.from_user.id
        logger.info(f"Start processing file {file_path} for user {user_id}")
        try:
            downloaded_path, elapsed_time = await download_with_progress(client, message, file_path, output_dir)
            if downloaded_path:
                # Simpan hasil ke completed_downloads
                if user_id not in completed_downloads:
                    completed_downloads[user_id] = []
                completed_downloads[user_id].append({
                    "filename": os.path.basename(file_path),
                    "size": os.path.getsize(downloaded_path),
                    "elapsed": elapsed_time
                })

                # Jika queue kosong, kirim ringkasan
                if download_queue.qsize() == 0:
                    summary_text = download_summary_message(user_id, output_dir)
                    await client.send_message(
                        chat_id=message.chat.id,
                        text=summary_text,
                        reply_to_message_id=message.id,
                        parse_mode=ParseMode.HTML
                    )
                    # Cleanup
                    completed_downloads.pop(user_id, None)

        except Exception as e:
            await send_error(message, "download_failed", str(e))
            logger.exception("Error in queue worker")
        finally:
            await clear_user_state(user_id)
            download_queue.task_done()
            logger.info(f"Finished processing file {file_path}")

async def send_batch_message(client, chat_id, user_id):
    await asyncio.sleep(BATCH_DELAY)

    items = batch_buffer.get(user_id, [])
    if not items:
        return

    total = len(items)
    filenames = [name for _, name in items]

    # Batasi tampilan max 10 file
    display_list = filenames[:10]
    more = total - len(display_list)

    text = (
        f"📥 <b>Total Files: {total}</b>\n\n"
        "📝 <b>Daftar file:</b>\n"
    )

    for name in display_list:
        short_name = smart_truncate_filename(name)
        text += f"» {short_name}\n"

    if more > 0:
        text += f"\n...dan {more} file lainnya"

    text += "\n✅ Ditambahkan ke antrian download"

    last_message = items[-1][0]

    await client.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=last_message.id,
        parse_mode=ParseMode.HTML
    )

    # Cleanup
    batch_buffer.pop(user_id, None)
    batch_tasks.pop(user_id, None)

async def download_with_progress(client, message: Message, file_path: str, output_dir: str):
    start_time = time.time()
    filename = os.path.basename(file_path)
    progress_msg = None
    is_cancelled = False
    last_progress_text = None
    last_update = 0

    # Cancel button
    cancel_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_dl_{message.id}")
    ]])

    active_downloads[message.id] = {
        "cancelled": False,
        "filename": filename,
        "chat_id": message.chat.id
    }

    async def progress(current, total):
        nonlocal progress_msg, is_cancelled, last_progress_text, last_update

        # Check cancel
        if active_downloads.get(message.id, {}).get("cancelled"):
            is_cancelled = True
            raise asyncio.CancelledError()

        elapsed = time.time() - start_time
        speed = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / speed if speed > 0 else 0

        progress_text = get_progress_text(
            filename, current, total, speed, elapsed, eta, output_dir
        )

        # Update setiap 5 detik atau jika isi berubah
        if time.time() - last_update >= 5:
            if progress_text != last_progress_text:
                try:
                    if progress_msg:
                        await progress_msg.edit_text(
                            progress_text,
                            reply_markup=cancel_markup,
                            parse_mode=ParseMode.HTML
                        )
                    else:
                        progress_msg = await message.reply_text(
                            progress_text,
                            reply_markup=cancel_markup,
                            parse_mode=ParseMode.HTML
                        )
                    last_progress_text = progress_text
                    last_update = time.time()
                except:
                    pass

    try:
        file_path = await message.download(
            file_name=file_path,
            progress=progress
        )

        if is_cancelled:
            if os.path.exists(file_path):
                os.remove(file_path)
            return None, None

        if progress_msg:
            try:
                await progress_msg.delete()
            except:
                pass

        elapsed = time.time() - start_time
        return file_path, elapsed

    except asyncio.TimeoutError:
        if progress_msg:
            try:
                await progress_msg.edit_text("⏳ Download timeout", reply_markup=None)
            except:
                pass
        await send_error(message, "timeout")
        logger.exception("Download timeout")
        return None, None

    except asyncio.CancelledError:
        if progress_msg:
            try:
                await progress_msg.edit_text("❌ Download cancelled by user", reply_markup=None)
            except:
                pass
        if os.path.exists(file_path):
            os.remove(file_path)
        await send_error(message, "cancelled")
        logger.info("Download cancelled by user")
        return None, None

    except PermissionError as e:
        await send_error(message, "permission_denied", str(e))
        logger.exception("Permission denied")
        return None, None

    except OSError as e:
        if "network" in str(e).lower():
            await send_error(message, "network_error", str(e))
        else:
            await send_error(message, "processing_error", str(e))
        logger.exception("OS error during download")
        return None, None

    except Exception as e:
        if progress_msg:
            try:
                await progress_msg.edit_text(f"⚠️ Download error: {str(e)}", reply_markup=None)
            except:
                pass
        return None, None

    finally:
        active_downloads.pop(message.id, None)

# ==========================
# 📌 HELPER FUNCTIONS
# ==========================

def format_duration(seconds: float) -> str:
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    parts = []
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)
    
def smart_truncate_filename(filename: str, max_length: int = 20) -> str:
    """Jika nama file terlalu panjang, langsung potong stringnya saja tanpa peduli ekstensi,

    aman dari segala jenis crash akibat format nama file.
    """
    if len(filename) > max_length:
        return f"{filename[:max_length]}..."
    return filename

def sanitize_filename(name: str) -> str:
    """Sanitize filename to remove unsupported characters."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '.', '_')).rstrip()

def get_file_extension(message: Message) -> str:
    """Mendapatkan ekstensi file dari nama file atau MIME metadata Telegram."""
    # Document
    if message.document:
        if message.document.file_name:
            ext = os.path.splitext(message.document.file_name)[1]
        else:
            ext = ext_from_mime(message.document.mime_type, ".bin")
        return ext.lower()

    # Video
    if message.video:
        if message.video.file_name:
            ext = os.path.splitext(message.video.file_name)[1]
        else:
            ext = ext_from_mime(message.video.mime_type, ".mp4")
        return ext.lower()

    # Audio
    if message.audio:
        if message.audio.file_name:
            ext = os.path.splitext(message.audio.file_name)[1]
        else:
            ext = ext_from_mime(message.audio.mime_type, ".mp3")
        return ext.lower()

    # Photo / voice / sticker / fallback
    if message.photo:
        return ".jpg"
    if message.voice:
        return ".ogg"
    if message.sticker:
        return ".webp"

    return ".bin"

def ext_from_mime(mime_type: str, default: str = ".bin") -> str:
    """Ambil ekstensi dari MIME type Telegram."""
    if not mime_type:
        return default

    ext = mimetypes.guess_extension(mime_type.lower())
    if ext == ".jpe":
        return ".jpg"
    return ext or default

def get_start_message() -> str:
    return (
        "👋 <b>Hello!</b> I’m your <b>Telegram Fetcher</b> bot.\n\n"
        "📤 Send me a file or command and I’ll handle it.\n"
        "💾 Files will be saved to <b>local Colab storage</b>.\n\n"
        "☁️ To upload to <b>Google Drive</b>, make sure you’ve <i>mounted</i> it first.\n"
        "📁 Use available commands to begin uploading!.\n"
        "ℹ️ Type <b>/help</b> to see all available commands and their descriptions."
    )

def get_tgupload_message() -> str:
    return (
        "📥 <b>Telegram File Upload</b>\n\n"
        "Please send the file you want to upload from Telegram.\n"
        "Make sure to send it as a <b>document</b> for best results.\n\n"
        "⏳ Waiting for your file..."
    )

def get_progress_text(filename, current, total, speed, elapsed, eta, output_dir):
    percent = current / total * 100
    filled = int(10 * percent / 100)
    bar = '▰' * filled + '▱' * (10 - filled)
    short_name = smart_truncate_filename(filename)
                        
    return (
        f"<b>📥 Downloading...</b>\n\n"
        f"<b>» {short_name}</b>\n\n"
        f"╭「 {bar} 」 {percent:.1f}%\n"
        f"├✅ <b>Downloaded:</b> {naturalsize(current)}\n"
        f"├📦 <b>Total Size:</b> {naturalsize(total)}\n"
        f"├⚡ <b>Speed:</b> {naturalsize(speed)}/s\n"
        f"├⏱️ <b>Elapsed:</b> {format_duration(elapsed)}\n"
        f"├⏳ <b>ETA:</b> {format_duration(eta)}\n"
        f"╰💾 <b>Saved To:</b> {output_dir}"
    )

def download_summary_message(user_id: int, output_dir: str) -> str:
    items = completed_downloads.get(user_id, [])
    total_files = len(items)
    total_size = sum(i["size"] for i in items)
    total_time = sum(i["elapsed"] for i in items)

    text = "✅ <b>Download Complete!</b>\n\n"
    text += "📂 <b>List File:</b>\n"
    for i in items:
        short_name = smart_truncate_filename(i["filename"])
        text += f"» {short_name}\n"

    text += (
        f"\n╭📂 <b>Total File »</b> {total_files}\n"
        f"├📁 <b>Total Size »</b> {naturalsize(total_size)}\n"
        f"├⏱️ <b>Saved Time »</b> {format_duration(total_time)}\n"
        f"╰💾 <b>Saved To »</b> {output_dir}"
    )
    return text

def get_unique_filename(directory: str, message: Message) -> str:
    """
    Generate unique filename dari:
    1. Nama file asli Telegram jika ada
    2. Caption jika file_name tidak ada
    3. Timestamp sebagai fallback
    Ekstensi diambil dari file_name atau MIME metadata Telegram.
    """
    os.makedirs(directory, exist_ok=True)
    ext = get_file_extension(message)

    # Ambil filename asli kalau ada
    original_filename = None
    if message.document and message.document.file_name:
        original_filename = message.document.file_name
    elif message.video and message.video.file_name:
        original_filename = message.video.file_name
    elif message.audio and message.audio.file_name:
        original_filename = message.audio.file_name

    if original_filename:
        base = sanitize_filename(os.path.splitext(original_filename)[0])
        final_name = f"{base}{ext}"
    elif message.caption:
        base = sanitize_filename(message.caption)[:50]
        final_name = f"{base}{ext}"
    else:
        final_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"

    # Handle duplikat nama
    counter = 1
    original_name = final_name
    while os.path.exists(os.path.join(directory, final_name)):
        name_part, ext_part = os.path.splitext(original_name)
        final_name = f"{name_part}_{counter}{ext_part}"
        counter += 1

    return final_name

async def send_error(message: Message, error_type: str, detail: str = None):
    """Mengirim pesan error yang user-friendly dengan detail tambahan"""
    error_messages = {
        "invalid_type": (
            "❌ <b>File type tidak didukung</b>\n"
            "Hanya menerima: Video, Audio, Gambar, PDF, atau Archive."
        ),
        "processing_error": (
            "⚠️ <b>Terjadi error saat memproses file</b>\n"
            "Silakan coba lagi atau kirim file lain."
        ),
        "download_failed": (
            "⏳ <b>Gagal mengunduh file</b>\n"
            "Pastikan koneksi stabil dan coba ulang."
        ),
        "drive_not_mounted": (
            "⚠️ <b>Google Drive belum ter-mount</b>\n"
            "Silakan mount terlebih dahulu sebelum upload."
        ),
        "file_too_large": (
            "❌ <b>File terlalu besar</b>\n"
            "Gunakan file dengan ukuran lebih kecil."
        ),
        "cancelled": "❌ <b>Download dibatalkan oleh user</b>",
        "timeout": "⏳ <b>Download timeout</b>\nCoba ulang dengan koneksi lebih cepat.",
        "permission_denied": "⚠️ <b>Tidak ada izin akses ke folder tujuan</b>",
        "unsupported_format": "❌ <b>Format file tidak didukung</b>",
        "network_error": "⚠️ <b>Koneksi terputus saat download</b>"
    }
    
    msg = error_messages.get(error_type, "Terjadi kesalahan tidak diketahui")
    if detail:
        msg += f"\n\n🔍 <b>Detail:</b> <code>{detail}</code>"
    await message.reply_text(msg, parse_mode=ParseMode.HTML)

def get_file_type(file_path: str) -> str:
    """Mendapatkan tipe file berdasarkan ekstensi"""
    _, ext = os.path.splitext(file_path)
    return EXTENSIONS.get(ext.lower(), "other")

def is_allowed_file(message: Message) -> bool:
    return True
    
def get_output_directory() -> str:
    # Baca konfigurasi dari credentials.json
    with open(CONFIG_PATH) as f:
        creds = json.load(f)

    download_path = creds.get("download_path", "/content/downloads")

    # Jika user memilih /content/drive, cek apakah sudah mount
    if download_path.startswith("/content/drive"):
        if not (os.path.exists("/content/drive") and os.path.ismount("/content/drive")):
            # Mount Google Drive jika belum
            from google.colab import drive
            drive.mount("/content/drive")
        os.makedirs(download_path, exist_ok=True)
    else:
        os.makedirs(download_path, exist_ok=True)

    return download_path

# ==========================
# 📌 USER STATE MANAGEMENT
# ==========================

async def load_user_state():
    async with state_lock:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        return {}

async def save_user_state(state):
    async with state_lock:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)

async def set_user_state(user_id, state):
    state_dict = await load_user_state()
    state_dict[str(user_id)] = state
    await save_user_state(state_dict)

async def get_user_state(user_id):
    state = await load_user_state()
    return state.get(str(user_id), None)

async def clear_user_state(user_id):
    state_dict = await load_user_state()
    if str(user_id) in state_dict:
        del state_dict[str(user_id)]
        await save_user_state(state_dict)

# ==========================
# 📌 MAIN ENTRY POINT
# ==========================

if __name__ == "__main__":
    logger.info("Starting the bot...")

    loop = asyncio.get_event_loop()
    worker_task = loop.create_task(queue_worker())

    try:
        app.run()
    finally:
        worker_task.cancel()
        try:
            loop.run_until_complete(worker_task)
        except asyncio.CancelledError:
            logger.info("Worker task cancelled cleanly.")

    logger.info("Bot stopped.")
