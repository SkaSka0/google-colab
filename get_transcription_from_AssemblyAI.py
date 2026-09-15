#@title 📥 Ambil Hasil Transkripsi dari AssemblyAI (Function Only)

from google.colab import userdata

import os, requests, json, re
from time import sleep

#@markdown ## 🔐 API Key dari Colab Secrets
#@markdown Cara pakai:
#@markdown 1. Buka panel kiri Colab → 🔑 **Secrets**
#@markdown 2. Klik **Add new secret**
#@markdown 3. Name: `ASSEMBLYAI_API_KEY`
#@markdown 4. Value: isi API key AssemblyAI kamu
#@markdown 5. Simpan


#@markdown ---
# =========================
# 🔐 API KEY (Colab Secret)
# =========================
api_key = userdata.get("ASSEMBLYAI_API_KEY")

# Transcript ID
transcript_id = "8876461d-0d7c-40f7-80a0-0579226a17ec"  #@param {type:"string"}

# Output folder
output_folder = "/content/media_toolkit/transcripts"  #@param {type:"string"}

# Nama file output
custom_filename = ""  #@param {type:"string"}

# Format output
output_format = "srt"  #@param ["semua", "json", "txt", "srt", "vtt"]

# Polling config
max_retries = 50  #@param {type:"integer"}
delay = 10  #@param {type:"number"}

os.makedirs(output_folder, exist_ok=True)

base_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
headers = {"authorization": api_key}

# =========================
# 🧾 LOGGING
# =========================
def log(msg, status="INFO"):
    print(f"{status.upper()}:AssemblyAiClient:{msg}")

# =========================
# 🧼 FILE NAME SANITIZER
# =========================
def sanitize_filename(filename):
    if not filename:
        return transcript_id
    filename = filename.lower()
    filename = re.sub(r'[^a-z0-9_-]', '_', filename)
    filename = re.sub(r'_{2,}', '_', filename)
    return filename.strip('_') or transcript_id

# =========================
# 📡 FETCH TRANSCRIPT STATUS
# =========================
def get_transcript():
    res = requests.get(base_url, headers=headers)
    res.raise_for_status()
    return res.json()

# =========================
# ⏳ POLLING LOOP
# =========================
def wait_for_completion():
    log(f"Polling dimulai (max {max_retries}x, delay {delay}s)")

    last_data = None

    for i in range(max_retries):
        data = get_transcript()
        last_data = data

        status = data.get("status")

        if status == "completed":
            log(f"COMPLETED ✅ (percobaan {i+1})")
            return data

        if status in ["error", "failed"]:
            raise Exception(f"Transkripsi gagal: {data.get('error')}")

        log(f"Status: {status} ({i+1}/{max_retries})")
        sleep(delay)

    log("Timeout polling — return last state", "WARN")
    return last_data

# =========================
# 💾 SAVE FUNCTIONS
# =========================
def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"JSON disimpan: {path}")

def save_txt(data, path):
    if data.get("text"):
        with open(path, "w", encoding="utf-8") as f:
            f.write(data["text"])
        log(f"TXT disimpan: {path}")
    else:
        log("Text tidak tersedia", "WARN")

def save_srt(path):
    res = requests.get(f"{base_url}/srt", headers=headers)
    res.raise_for_status()
    with open(path, "w", encoding="utf-8") as f:
        f.write(res.text)
    log(f"SRT disimpan: {path}")

def save_vtt(path):
    res = requests.get(f"{base_url}/vtt", headers=headers)
    if res.status_code == 200:
        with open(path, "w", encoding="utf-8") as f:
            f.write(res.text)
        log(f"VTT disimpan: {path}")
    else:
        log("VTT tidak tersedia", "WARN")

# =========================
# 🚀 MAIN PIPELINE
# =========================
def main():
    if not api_key:
        raise ValueError("ASSEMBLYAI_API_KEY belum di-set di Colab Secrets!")

    base_filename = sanitize_filename(custom_filename)

    log(f"File: {base_filename}")
    log("Memulai polling...")

    data = wait_for_completion()

    json_path = os.path.join(output_folder, f"{base_filename}.json")
    txt_path  = os.path.join(output_folder, f"{base_filename}.txt")
    srt_path  = os.path.join(output_folder, f"{base_filename}.srt")
    vtt_path  = os.path.join(output_folder, f"{base_filename}.vtt")

    if output_format == "semua":
        save_json(data, json_path)
        save_txt(data, txt_path)
        save_srt(srt_path)
        save_vtt(vtt_path)

    elif output_format == "json":
        save_json(data, json_path)

    elif output_format == "txt":
        save_txt(data, txt_path)

    elif output_format == "srt":
        save_srt(srt_path)

    elif output_format == "vtt":
        save_vtt(vtt_path)

    log("📊 RINGKASAN")
    log(f"ID: {transcript_id}")
    log(f"Status: {data.get('status')}")
    log(f"Output: {output_format}")
    log(f"Folder: {output_folder}")

# =========================
# ▶ RUN
# =========================
main()