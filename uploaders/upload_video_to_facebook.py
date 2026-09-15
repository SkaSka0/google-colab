#@title 🚀 Upload to Facebook
#@markdown <br><center><img src='https://www.facebook.com/images/fb_icon_325x325.png' height="50" alt="Facebook-logo"/></center>
#@markdown <center><h2><font color=lightblue><b>Upload Video to Facebook</b></h2></center><br>

#@markdown **Instructions**:
#@markdown 1. Masuk ke Graph API Explorer lalu kirim `/me/accounts`
#@markdown 2. Ganti `PAGE_TOKEN`
#@markdown 3. Ganti `PAGE_ID` bila perlu.
#@markdown 4. Ganti `VIDEO_PATH` ke file video di Colab
#@markdown 5. (Opsional) Aktifkan Scheduled Publish dan isi tanggal yang diinginkan.
#@markdown 6. Pilih CHUNK_MODE: "manual", "auto", atau "adaptive". Jika manual, set CHUNK_SIZE_MB (8-64).

#@markdown ---
#@markdown --- User Parameters ---
PAGE_ID = "875434668987591"  #@param {type:"string"}
PAGE_TOKEN = ""  #@param {type:"string"}

#@markdown ---
#@markdown --- Batch Upload Params ---
USE_BATCH = True  #@param {type:"boolean"}
BATCH_FOLDER = "/content/downloads/videos"  #@param {type:"string"}

#@markdown ---
#@markdown --- Single Upload Params ---
VIDEO_PATH = "/content/downloads/videos/tertawakan_aku_cinta_buta_sistem_bangkit_murid_jadi_kaisar_dewa_jadi_budak_mau_lihat_balas_dendam.mp4"  #@param {type:"string"}
TITLE = "tertawakan aku cinta buta sistem bangkit murid jadi kaisar dewa jadi budak mau lihat balas dendam"  # @param {type:"string"}
DESCRIPTION = "[Full Sub Indo] tertawakan aku cinta buta sistem bangkit murid jadi kaisar dewa jadi budak mau lihat balas dendam"  # @param {type:"string"}
HASHTAG_GENRE = "none"  # @param ["none", "romance", "fantasy", "comedy", "sad", "general"]
CHUNK_MODE = "manual"   #@param ["manual","auto","adaptive"]
CHUNK_SIZE_MB = 32        #@param {type:"number"}  # used only in manual mode
MIN_CHUNK_MB = 8
MAX_CHUNK_MB = 64

#@markdown ---
#@markdown --- Schedule Params ---
# Note:
# - If USE_SCHEDULE == False -> no scheduling (published immediately)
# - If USE_SCHEDULE == True and SCHEDULE_TODAY == True -> schedule uses today's date (local Asia/Jakarta) + CUSTOM_TIME
# - If USE_SCHEDULE == True and SCHEDULE_TODAY == False -> uses CUSTOM_DATE + CUSTOM_TIME
# - If CUSTOM_DATE < today (local) -> automatically set to today
# - If scheduled datetime <= now -> will be shifted to now + 2 minutes
USE_SCHEDULE = True        #@param {type:"boolean"}
SCHEDULE_TODAY = True       #@param {type:"boolean", label:"Gunakan tanggal hari ini?"}
CUSTOM_DATE = "2025-11-25"  #@param {type:"string", label:"Tanggal (YYYY-MM-DD)"}
CUSTOM_TIME = "16:00:00"    #@param {type:"string", label:"Waktu (HH-MM-SS, 24h)"}

#@markdown ---
#@markdown --- Other params ---
RETRY_COUNT = 5  #@param {type:"number"}
SLEEP_BETWEEN_CHUNKS = 0.5  #@param {type:"number"}
SHOW_PROGRESS = True  #@param {type:"boolean"}

import sys
import time
import os
import datetime
import importlib
import subprocess
import json

APPNAME = "FBUploader"

# -------------------------
def log(message, level="INFO"):
    print(f"{level}:{APPNAME}: {message}")

# -------------------------
def install_dependencies():
    log("Memeriksa dan menginstal dependensi...", "INIT")
    import importlib, subprocess, sys
    for pkg in ["requests", "pytz"]:
        try:
            importlib.import_module(pkg)
            # log(f"Paket '{pkg}' sudah terinstal.", "DEBUG")
        except Exception:
            log(f"Paket '{pkg}' tidak ditemukan. Menginstal...", "WARNING")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])
            log(f"Paket '{pkg}' berhasil diinstal.", "INIT")
    log("Semua dependensi siap.", "INIT")

# -------------------------
CORE_HASHTAGS = ["#shortdrama", "#dramachina", "#reelsindo"]

GENRE_HASHTAGS = {
    "romance": ["#romance", "#romantis", "#lovestory"],
    "fantasy": ["#fantasi", "#kultivasi", "#wuxia"],
    "comedy":  ["#komedi", "#lucu", "#funnyvideo"],
    "sad":     ["#sedih", "#melow"],
    "general": ["#viral", "#fyp"],
    "none": []
}

def sanitize_filename_to_title(filename):
    name = os.path.splitext(os.path.basename(filename))[0]
    name = name.replace("_", " ")
    name = " ".join(word.capitalize() for word in name.split())
    return name

def get_video_files_from_folder(folder):
    supported = (".mp4", ".mov", ".mkv", ".avi")
    files = [
        os.path.join(folder, f)
        for f in sorted(os.listdir(folder))
        if f.lower().endswith(supported)
    ]
    return files

def get_batch_schedule_times(
    total_videos,
    use_schedule,
    schedule_today,
    custom_date,
    custom_time
):
    import pytz, datetime

    tz = pytz.timezone("Asia/Jakarta")
    now = datetime.datetime.now(tz)

    # -------------------------
    # Tentukan base_time
    # -------------------------
    if use_schedule:
        # Tentukan tanggal
        if schedule_today:
            date_use = now.date()
        else:
            date_use = max(
                datetime.datetime.strptime(custom_date, "%Y-%m-%d").date(),
                now.date()
            )

        time_use = datetime.datetime.strptime(custom_time, "%H:%M:%S").time()
        base_time = tz.localize(datetime.datetime.combine(date_use, time_use))

        # Validasi agar tidak di masa lalu
        if base_time <= now:
            log(
                "Waktu batch schedule berada di masa lalu. "
                "Menggeser ke now + 2 menit.",
                "WARNING"
            )
            base_time = now + datetime.timedelta(minutes=2)

    else:
        # Perilaku lama (default)
        base_time = now + datetime.timedelta(hours=2)

    # -------------------------
    # Generate jadwal batch
    # -------------------------
    times = []
    for i in range(total_videos):
        dt = base_time + datetime.timedelta(hours=i)
        ts = str(int(dt.astimezone(pytz.utc).timestamp()))
        times.append((dt, ts))

    return times

def build_hashtags_by_dropdown(genre):
    log(f"Membangun hashtag untuk genre: {genre}", "DEBUG")
    tags = CORE_HASHTAGS + GENRE_HASHTAGS.get(genre, [])
    unique_tags = list(dict.fromkeys(tags))
    result = " ".join(unique_tags[:8])
    log(f"Hashtag terpilih: {result}", "DEBUG")
    return result

# -------------------------
def get_schedule_timestamp_iso_or_unix(use_schedule, schedule_today, custom_date, custom_time):
    if not use_schedule:
        log("Jadwal upload tidak diaktifkan. Video akan langsung terbit.", "INFO")
        return None

    log("Menghitung waktu jadwal tayang...", "DEBUG")
    import datetime, pytz
    tz = pytz.timezone("Asia/Jakarta")
    now = datetime.datetime.now(tz)

    date_use = now.date() if schedule_today else max(
        datetime.datetime.strptime(custom_date, "%Y-%m-%d").date(),
        now.date()
    )

    time_use = datetime.datetime.strptime(custom_time, "%H:%M:%S").time()
    dt = tz.localize(datetime.datetime.combine(date_use, time_use))

    # Validasi agar tidak di masa lalu
    if dt <= now:
        log("Waktu jadwal sudah lewat dari waktu sekarang. Menambahkan delay 2 menit.", "WARNING")
        dt = now + datetime.timedelta(minutes=2)

    final_ts = str(int(dt.astimezone(pytz.utc).timestamp()))
    log(f"Jadwal Final (UTC Timestamp): {final_ts} | Lokal: {dt}", "INFO")
    return final_ts

# -------------------------
def get_file_size(path):
    import os
    size = os.path.getsize(path)
    log(f"Ukuran file terdeteksi: {size} bytes ({size/1024/1024:.2f} MB)", "DEBUG")
    return size

def start_upload_session(page_id, token, file_size):
    log("Memulai sesi upload ke API Facebook...", "NET")
    import requests
    try:
        r = requests.post(
            f"https://graph-video.facebook.com/v20.0/{page_id}/videos",
            data={
                "upload_phase": "start",
                "file_size": str(file_size),
                "access_token": token
            }
        )
        r.raise_for_status()
        j = r.json()
        log(f"Sesi Upload Dibuat. ID Sesi: {j['upload_session_id']}", "SUCCESS")
        log(f"Offset Awal: {j['start_offset']} | Offset Akhir: {j['end_offset']}", "DEBUG")
        return j["upload_session_id"], int(j["start_offset"]), int(j["end_offset"])
    except Exception as e:
        log(f"Gagal memulai sesi upload: {e}", "ERROR")
        if 'r' in locals(): log(f"Respon API: {r.text}", "ERROR")
        raise

def validate_batch_folder(folder):
    if not os.path.isdir(folder):
        log(f"Folder batch tidak ditemukan: {folder}", "FATAL")
        return False
    return True

def run_batch_upload():
    log("MODE BATCH UPLOAD DIAKTIFKAN", "INIT")

    if not validate_batch_folder(BATCH_FOLDER):
        log("Batch upload dibatalkan.", "INFO")
        return

    videos = get_video_files_from_folder(BATCH_FOLDER)
    if not videos:
        log("Tidak ada video ditemukan untuk batch upload.", "FATAL")
        return

    schedules = get_batch_schedule_times(
        len(videos),
        USE_SCHEDULE,
        SCHEDULE_TODAY,
        CUSTOM_DATE,
        CUSTOM_TIME
    )

    for idx, video_path in enumerate(videos, start=1):
        title = sanitize_filename_to_title(video_path)
        description = f"[Full Sub Indo] {title}"

        log(f"[BATCH {idx}/{len(videos)}] Title       : {title}", "INFO")
        log(f"[BATCH {idx}/{len(videos)}] Description : {description}", "INFO")

        local_dt, schedule_ts = schedules[idx - 1]

        log(
            f"[BATCH {idx}/{len(videos)}] "
            f"Video akan publish pada: {local_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "INFO"
        )

        try:
            result = resumable_upload(
                PAGE_ID,
                PAGE_TOKEN,
                video_path,
                title,
                description,
                True,
                schedule_ts,
                batch_index=idx,
                batch_total=len(videos)
            )

            if result and "id" in result:
                log(
                    f"[BATCH {idx}/{len(videos)}] "
                    f"UPLOAD BERHASIL! Video ID: {result['id']}",
                    "SUCCESS"
                )

        except Exception as e:
            log(
                f"[BATCH {idx}/{len(videos)}] GAGAL upload: {e}",
                "ERROR"
            )
            # lanjut ke video berikutnya
            continue

def run_single_upload():
    log("MODE SINGLE UPLOAD DIAKTIFKAN", "INIT")

    AUTO_HASHTAGS = build_hashtags_by_dropdown(HASHTAG_GENRE)
    description_final = (
        DESCRIPTION if HASHTAG_GENRE == "none"
        else f"{DESCRIPTION}\n\n{AUTO_HASHTAGS}"
    )

    schedule_ts = get_schedule_timestamp_iso_or_unix(
        USE_SCHEDULE, SCHEDULE_TODAY, CUSTOM_DATE, CUSTOM_TIME
    )

    result = resumable_upload(
        PAGE_ID,
        PAGE_TOKEN,
        VIDEO_PATH,
        TITLE,
        description_final,
        USE_SCHEDULE,
        schedule_ts
    )

    if result and "id" in result:
        log(f"UPLOAD BERHASIL! Video ID: {result['id']}", "SUCCESS")

def transfer_chunk_raw(page_id, token, session_id, offset, chunk):
    import requests
    # log(f"Mengirim chunk... Offset: {offset}, Ukuran: {len(chunk)} bytes", "NET") # Verbose per chunk
    try:
        r = requests.post(
            f"https://graph-video.facebook.com/v20.0/{page_id}/videos",
            data={
                "upload_phase": "transfer",
                "start_offset": str(offset),
                "upload_session_id": session_id,
                "access_token": token
            },
            files={"video_file_chunk": ("chunk", chunk)},
            timeout=120
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"Gagal transfer chunk di offset {offset}: {e}", "ERROR")
        raise

def finish_upload(page_id, token, session_id, title, desc, schedule, schedule_time):
    log("Mengirim permintaan 'finish' ke Facebook...", "NET")
    import requests
    data = {
        "upload_phase": "finish",
        "upload_session_id": session_id,
        "title": title,
        "description": desc,
        "access_token": token,
        "published": 0 if schedule else 1
    }
    if schedule:
        data["scheduled_publish_time"] = schedule_time
        log(f"Menyertakan parameter jadwal tayang: {schedule_time}", "DEBUG")

    try:
        r = requests.post(f"https://graph-video.facebook.com/v20.0/{page_id}/videos", data=data)
        r.raise_for_status()
        j = r.json()
        log("Proses Upload Selesai (Phase Finish OK).", "SUCCESS")
        return j
    except Exception as e:
        log(f"Gagal melakukan finish upload: {e}", "ERROR")
        if 'r' in locals(): log(f"Respon API: {r.text}", "ERROR")
        raise

# -------------------------
def print_live_progress(uploaded, total, start_time, chunk_mb):
    import time, sys
    elapsed = time.time() - start_time
    speed = (uploaded / 1024 / 1024) / elapsed if elapsed > 0 else 0
    percent = (uploaded / total) * 100

    # Kita gunakan \r untuk update baris yang sama, tapi log() menggunakan print biasa (newline)
    # Agar log verbose tidak berantakan dengan progress bar, progress bar ini hanya visual tambahan
    line = (
        f"\rINFO:{APPNAME}:Uploading: "
        f"{uploaded/1024/1024:.2f} MB / {total/1024/1024:.2f} MB "
        f"({percent:.2f}%) | "
        f"Speed: {speed:.2f} MB/s | "
        f"Chunk: {chunk_mb}MB"
    )
    sys.stdout.write(line)
    sys.stdout.flush()

# -------------------------
def resumable_upload(page_id, token, path, title, desc, schedule, schedule_time,
                     batch_index=None, batch_total=None):
    import time

    install_dependencies()

    prefix = ""
    if batch_index is not None:
        prefix = f"[BATCH {batch_index}/{batch_total}] "

    log(f"{prefix}Mempersiapkan upload file: {path}", "INFO")

    if not os.path.exists(path):
        log(f"File tidak ditemukan: {path}", "ERROR")
        return None

    size = get_file_size(path)
    session, offset, _ = start_upload_session(page_id, token, size)

    chunk_mb = 32 if batch_index is not None else max(
        MIN_CHUNK_MB, min(CHUNK_SIZE_MB, MAX_CHUNK_MB)
    )
    chunk_size = chunk_mb * 1024 * 1024
    log(f"Konfigurasi Chunk: {chunk_mb} MB ({chunk_size} bytes)", "INFO")

    start_time = time.time()

    with open(path, "rb") as f:
        log(f"Membuka file dan mencari offset: {offset}", "DEBUG")
        f.seek(offset)
        uploaded = offset

        while uploaded < size:
            current_chunk_size = min(chunk_size, size - uploaded)
            # log(f"Membaca chunk dari file... (Offset: {uploaded}, Size: {current_chunk_size})", "DEBUG")
            chunk = f.read(current_chunk_size)

            for attempt in range(RETRY_COUNT):
                try:
                    r = transfer_chunk_raw(page_id, token, session, uploaded, chunk)

                    new_offset = int(r.get("start_offset", uploaded + len(chunk)))
                    uploaded = new_offset

                    if SHOW_PROGRESS:
                        print_live_progress(uploaded, size, start_time, chunk_mb)

                    break # Break retry loop
                except Exception as e:
                    log(f"Error pada chunk offset {uploaded}: {e}", "ERROR")
                    if attempt + 1 >= RETRY_COUNT:
                        log("Jumlah retry maksimum terlampaui. Menghentikan proses.", "FATAL")
                        raise
                    sleep_time = 2 ** attempt
                    log(f"Tidur {sleep_time} detik sebelum retry...", "WAIT")
                    time.sleep(sleep_time)

            # Opsional: Tidur antar chunk
            # time.sleep(SLEEP_BETWEEN_CHUNKS)

    print()
    log("Semua chunk berhasil dikirim. Memulai finalisasi...", "INFO")
    return finish_upload(page_id, token, session, title, desc, schedule, schedule_time)

def preview_uploads():
    import os

    log("=== PREVIEW UPLOAD ===", "INIT")

    # -------------------------
    # MODE BATCH
    # -------------------------
    if USE_BATCH:
        if not validate_batch_folder(BATCH_FOLDER):
            log("Preview dibatalkan (folder batch tidak valid).", "WARNING")
            return

        videos = get_video_files_from_folder(BATCH_FOLDER)
        total = len(videos)

        log(f"Total file terdeteksi: {total}", "INFO")

        if total == 0:
            return

        schedules = get_batch_schedule_times(
            total,
            USE_SCHEDULE,
            SCHEDULE_TODAY,
            CUSTOM_DATE,
            CUSTOM_TIME
        )

        for idx, video in enumerate(videos, start=1):
            size = os.path.getsize(video)
            size_mb = size / 1024 / 1024

            local_dt, _ = schedules[idx - 1]
            schedule_str = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")

            log(
                f"{idx}. {os.path.basename(video)} | "
                f"{size_mb:.2f} MB -> {schedule_str}",
                "INFO"
            )

    # -------------------------
    # MODE SINGLE
    # -------------------------
    else:
        if not os.path.exists(VIDEO_PATH):
            log("File single upload tidak ditemukan.", "ERROR")
            return

        size = os.path.getsize(VIDEO_PATH)
        size_mb = size / 1024 / 1024

        log("Total file terdeteksi: 1", "INFO")

        if USE_SCHEDULE:
            schedule_ts = get_schedule_timestamp_iso_or_unix(
                USE_SCHEDULE,
                SCHEDULE_TODAY,
                CUSTOM_DATE,
                CUSTOM_TIME
            )

            import pytz, datetime
            tz = pytz.timezone("Asia/Jakarta")
            local_dt = datetime.datetime.fromtimestamp(int(schedule_ts), tz)
            schedule_str = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        else:
            schedule_str = "Publish langsung"

        log(
            f"{os.path.basename(VIDEO_PATH)} | "
            f"{size_mb:.2f} MB -> {schedule_str}",
            "INFO"
        )

    log("=== END PREVIEW ===", "INIT")

# -------------------------
if __name__ == "__main__":
    log("Program dimulai...", "INIT")

    if not PAGE_TOKEN:
        log("PAGE_TOKEN kosong! Harap isi token akses.", "FATAL")
    else:
        install_dependencies()

        preview_uploads()

        if USE_BATCH:
            run_batch_upload()
        else:
            run_single_upload()

    log("Program selesai.", "INFO")