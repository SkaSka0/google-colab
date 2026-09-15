#@title 🚀 AssemblyAI Audio ke Teks (v2: Opsi Hapus Audio)
#@markdown ## 🔐 API Key dari Colab Secrets
#@markdown Cara pakai:
#@markdown 1. Buka panel kiri Colab → 🔑 **Secrets**
#@markdown 2. Klik **Add new secret**
#@markdown 3. Name: `ASSEMBLYAI_API_KEY`
#@markdown 4. Value: isi API key AssemblyAI kamu
#@markdown 5. Simpan

#@markdown ---

from google.colab import userdata

api_key = userdata.get("ASSEMBLYAI_API_KEY")

#@markdown **Input Path**
audio_path = ""  #@param {type:"string"}
output_folder = "/content/media_toolkit/metadata"  #@param {type:"string"}

#@markdown ---
#@markdown **Mode Operasi**
mode = "upload_only"  #@param ["upload_only", "full"]
polling_interval = 10  #@param {type:"integer"}
max_polling = 60      #@param {type:"integer"}

#@markdown ---
#@markdown **Advanced Settings**
language_code = "zh"  #@param ["id", "en", "es", "fr", "de", "it", "pt", "nl", "ja", "ko", "zh", "hi"] {type:"string"}
output_format = "json" #@param ["json", "txt", "srt", "vtt", "all"]
cost_per_hour_usd = 0.15 #@param {type:"number"}

#@markdown ---
#@markdown **Boolean**
delete_audio_on_success = False  #@param {type:"boolean"}
speaker_labels = True  #@param {type:"boolean"}
punctuate = True      #@param {type:"boolean"}
format_text = True      #@param {type:"boolean"}


import os, requests, json, time, subprocess, datetime, platform

UPLOAD_ENDPOINT = "https://api.assemblyai.com/v2/upload"
TRANSCRIPT_ENDPOINT = "https://api.assemblyai.com/v2/transcript"
TIMEOUT = 30
TIMEOUT_LARGE = 60


# 🟢 Fungsi tampilan metadata rapi
def pretty_print_metadata(info: dict):
    """Tampilkan metadata dengan format yang mudah dibaca di terminal Colab"""
    print("\n\033[92m=== 📄 METADATA AKHIR ===\033[0m")
    max_key_len = max(len(k) for k in info.keys())
    for key, value in info.items():
        print(f"\033[96m{key.ljust(max_key_len)}\033[0m : {value}")
    print("\033[92m==========================\033[0m\n")


class AssemblyAIUploader:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({"authorization": api_key})

    def log(self, msg: str, level: str = "INFO"):
        print(f"{level}:AssemblyAiClient:{msg}")

    def get_audio_duration(self, file_path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of",
                 "default=noprint_wrappers=1:nokey=1", file_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            return float(result.stdout.strip())
        except Exception as e:
            self.log(f"Gagal membaca durasi audio: {e}", "WARNING")
            return 0.0

    def upload_audio(self, file_path: str) -> str:
        self.log(f"Mengunggah audio: {file_path}")
        file_size = os.path.getsize(file_path)
        try:
            with open(file_path, "rb") as f:
                if file_size > 5_242_880:
                    self.log("File besar, menggunakan chunked upload...", "INFO")
                    response = self.session.post(UPLOAD_ENDPOINT, data=f, timeout=int(TIMEOUT_LARGE))
                else:
                    response = self.session.post(UPLOAD_ENDPOINT, files={"file": f}, timeout=int(TIMEOUT))
            response.raise_for_status()
            upload_url = response.json()["upload_url"]
            self.log("Upload selesai ✅")
            return upload_url
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Gagal upload audio: {e}")

    def request_transcription(self, audio_url: str, **kwargs) -> str:
        data = {
            "audio_url": audio_url,
            "language_code": kwargs.get("language_code", "id"),
            "speaker_labels": kwargs.get("speaker_labels", True),
            "punctuate": kwargs.get("punctuate", True),
            "format_text": kwargs.get("format_text", True),
            "speech_model": "universal"
        }
        try:
            response = self.session.post(TRANSCRIPT_ENDPOINT, json=data, timeout=int(TIMEOUT))
            response.raise_for_status()
            transcript_id = response.json()["id"]
            self.log("Permintaan transkripsi berhasil dibuat ✅")
            self.log(f"Transcription ID: {transcript_id}")
            return transcript_id
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Gagal membuat transkripsi: {e}")

    def poll_transcription(self, transcript_id: str, interval: int, max_attempts: int):
        self.log(f"Memulai polling status transkripsi (interval {interval}s, max {max_attempts} kali)...")
        url = f"{TRANSCRIPT_ENDPOINT}/{transcript_id}"

        for attempt in range(1, max_attempts + 1):
            try:
                resp = self.session.get(url, timeout=TIMEOUT)
                resp.raise_for_status()
                result = resp.json()
                status = result.get("status", "unknown")

                self.log(f"Polling [#{attempt}/{max_attempts}]: status = {status}")

                if status == "completed":
                    self.log("Transkripsi selesai ✅")
                    return result
                elif status == "error":
                    self.log(f"Transkripsi gagal ❌: {result.get('error')}", "ERROR")
                    return result

                time.sleep(interval)

            except requests.exceptions.RequestException as e:
                self.log(f"Gagal memeriksa status: {e}", "WARNING")
                time.sleep(interval)

        self.log("Polling berakhir sebelum transkripsi selesai.", "WARNING")
        return {"status": "timeout"}

    def download_transcript_json(self, transcript_id: str, save_path: str):
        self.log(f"Mengunduh hasil transkrip JSON...")
        url = f"{TRANSCRIPT_ENDPOINT}/{transcript_id}"
        try:
            response = self.session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(response.json(), f, ensure_ascii=False, indent=2)
            self.log(f"Transkrip JSON disimpan di: {save_path}")
            return save_path
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Gagal mengunduh hasil transkrip JSON: {e}")

    def download_transcript_export(self, transcript_id: str, format_type: str, save_path: str):
        """Unduh format transkrip (srt/vtt)"""
        self.log(f"Mengunduh format {format_type.upper()}...")
        url = f"{TRANSCRIPT_ENDPOINT}/{transcript_id}/{format_type}"
        try:
            response = self.session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            # Ini adalah respons teks biasa, bukan JSON
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            self.log(f"{format_type.upper()} disimpan di: {save_path}")
            return save_path
        except requests.exceptions.RequestException as e:
            self.log(f"Gagal mengunduh {format_type.upper()}: {e}", "ERROR")
            raise RuntimeError(f"Gagal mengunduh {format_type.upper()}: {e}")


def main():
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"File audio tidak ditemukan: {audio_path}")
    if not api_key:
        raise ValueError("ASSEMBLYAI_API_KEY belum di-set di Colab Secrets!")

    start_time = time.time()
    os.makedirs(output_folder, exist_ok=True)
    transcript_folder = os.path.join(output_folder, "transcript")
    os.makedirs(transcript_folder, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    output_json = os.path.join(output_folder, f"{base_name}_upload_info.json")

    uploader = AssemblyAIUploader(api_key)

    try:
        duration_sec = uploader.get_audio_duration(audio_path)
        duration_min = round(duration_sec / 60, 2)
        est_hours = round(duration_min / 60, 4)
        file_size_mb = round(os.path.getsize(audio_path) / (1024 * 1024), 2)
        estimated_cost_usd = round(est_hours * cost_per_hour_usd, 5)

        audio_url = uploader.upload_audio(audio_path)
        transcript_id = uploader.request_transcription(
            audio_url,
            language_code=language_code,
            speaker_labels=speaker_labels,
            punctuate=punctuate,
            format_text=format_text
        )

        info = {
            "file_name": os.path.basename(audio_path),
            "colab_session_path": audio_path,
            "file_size_mb": file_size_mb,
            "transcript_id": transcript_id,
            "audio_url": audio_url,
            "language_code": language_code,
            "model_used": "universal",
            "audio_duration_sec": round(duration_sec, 2),
            "audio_duration_min": duration_min,
            "estimated_cost_hours": est_hours,
            "cost_per_hour_usd": cost_per_hour_usd,
            "estimated_cost_usd": estimated_cost_usd,
            "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp_utc": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "local_timezone": time.tzname[0],
            "environment": "colab" if "COLAB_GPU" in os.environ else platform.system().lower(),
            "upload_status": "success",
            "mode": mode,
            "polling_attempts": 0,
            "polling_interval_sec": polling_interval,
            "transcription_status": "pending",
            "output_format_requested": output_format,
            "transcript_json_path": None, # Path ke JSON *lengkap*
            "generated_files": {}, # Path ke file yang diminta (txt, srt, vtt)
            "error_message": None,
            "audio_file_deleted": False, # --- TAMBAHAN BARU ---
            "total_processing_time_sec": None
        }

        # Mode polling penuh
        if mode == "full":
            polling_result = uploader.poll_transcription(transcript_id, polling_interval, max_polling)
            info["polling_attempts"] = max_polling # Perbarui jumlah percobaan
            info["transcription_status"] = polling_result.get("status", "unknown")

            if polling_result.get("status") == "completed":

                # Buat dictionary untuk menyimpan path file yang dihasilkan
                generated_files = {}

                # --- Helper untuk menyimpan file teks ---
                def save_text_file(content, extension):
                    file_path = os.path.join(transcript_folder, f"{base_name}_transcript.{extension}")
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        uploader.log(f"Transkrip {extension.upper()} disimpan di: {file_path}")
                        return file_path
                    except Exception as e:
                        uploader.log(f"Gagal menyimpan {extension.upper()}: {e}", "WARNING")
                        return None

                # --- Helper untuk mengunduh format ekspor (SRT/VTT) ---
                def download_export(format_ext):
                    file_path = os.path.join(transcript_folder, f"{base_name}_transcript.{format_ext}")
                    try:
                        # Gunakan metode download_transcript_export yang baru
                        return uploader.download_transcript_export(transcript_id, format_ext, file_path)
                    except Exception as e:
                        uploader.log(f"Gagal mengunduh {format_ext.upper()}: {e}", "WARNING")
                        return None

                # --- Logika untuk format output ---

                # 1. Handle JSON
                if output_format == "json" or output_format == "all":
                    json_path = os.path.join(transcript_folder, f"{base_name}_transcript.json")
                    try:
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(polling_result, f, ensure_ascii=False, indent=2)
                        uploader.log(f"Transkrip JSON disimpan di: {json_path}")
                        generated_files["json"] = json_path
                        # Set path json utama untuk metadata
                        info["transcript_json_path"] = json_path
                    except Exception as e:
                        uploader.log(f"Gagal menyimpan JSON: {e}", "WARNING")

                # 2. Handle TXT
                if output_format == "txt" or output_format == "all":
                    full_text = polling_result.get("text")
                    if full_text:
                        generated_files["txt"] = save_text_file(full_text, "txt")
                    else:
                        uploader.log("Key 'text' tidak ditemukan di hasil JSON, tidak bisa menyimpan TXT.", "WARNING")

                # 3. Handle SRT
                if output_format == "srt" or output_format == "all":
                    generated_files["srt"] = download_export("srt")

                # 4. Handle VTT
                if output_format == "vtt" or output_format == "all":
                    generated_files["vtt"] = download_export("vtt")

                # Simpan daftar file yang dibuat ke metadata
                info["generated_files"] = generated_files

                # Pastikan 'transcript_json_path' terisi jika user HANYA minta srt/vtt/txt
                # Kita tetap simpan JSON utamanya untuk referensi
                if not info["transcript_json_path"] and (output_format != "json"):
                     # Simpan JSON utama secara "diam-diam" untuk referensi lengkap
                    main_json_path = os.path.join(transcript_folder, f"{base_name}_transcript_full.json")
                    try:
                        with open(main_json_path, "w", encoding="utf-8") as f:
                            json.dump(polling_result, f, ensure_ascii=False, indent=2)
                        info["transcript_json_path"] = main_json_path # Path ke file JSON *lengkap*
                        uploader.log(f"JSON lengkap (referensi) disimpan di: {main_json_path}", "INFO")
                    except Exception as e:
                        uploader.log(f"Gagal menyimpan JSON lengkap (referensi): {e}", "WARNING")


            elif polling_result.get("status") == "error":
                info["error_message"] = polling_result.get("error", "Unknown error")

        info["total_processing_time_sec"] = round(time.time() - start_time, 2)

        # --- LOGIKA PENGHAPUSAN FILE ---
        if delete_audio_on_success:
            # Tentukan kondisi sukses berdasarkan mode
            is_upload_only_success = (mode == "upload_only" and info["upload_status"] == "success")
            is_full_mode_success = (mode == "full" and info["transcription_status"] == "completed")

            if is_upload_only_success or is_full_mode_success:
                try:
                    os.remove(audio_path)
                    uploader.log(f"File audio asli BERHASIL dihapus: {audio_path}", "INFO")
                    info["audio_file_deleted"] = True
                except OSError as e:
                    uploader.log(f"Gagal menghapus file audio: {e}", "WARNING")
                    info["audio_file_deleted"] = False
            else:
                # Ini terjadi jika mode="full" tapi statusnya "timeout" atau "error"
                uploader.log(f"Proses tidak 'completed' (status: {info['transcription_status']}), file audio TIDAK dihapus.", "WARNING")
                info["audio_file_deleted"] = False
        else:
            info["audio_file_deleted"] = False # Default (tidak dihapus)
        # --- END LOGIKA PENGHAPUSAN ---


        # Simpan metadata akhir (sekarang menyertakan info 'audio_file_deleted')
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        uploader.log(f"Informasi upload & transkrip tersimpan di: {output_json}", "INFO")
        uploader.log(f"Durasi audio: {duration_min} menit", "INFO")
        uploader.log(f"Estimasi biaya: ${estimated_cost_usd}", "INFO")

        # 🟢 Tampilkan metadata akhir di terminal
        pretty_print_metadata(info)

        return info

    except Exception as e:
        uploader.log(f"Terjadi kesalahan: {e}", "ERROR")
        # --- PENTING ---
        # Karena error terjadi, program melompat ke sini dan TIDAK akan
        # menjalankan logika penghapusan file, sesuai permintaan.
        raise


if __name__ == "__main__":
    main()