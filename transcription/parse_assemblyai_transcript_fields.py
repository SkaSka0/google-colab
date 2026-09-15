#@title Parsing JSON AssemblyAI
import json
import logging
import os
import sys

# --- KONFIGURASI CUSTOM LOGGING ---
def setup_custom_logger(name):
    logger = logging.getLogger(name)

    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

log = setup_custom_logger("AssemblyParser")

# --- PARAMETER INPUT/OUTPUT ---
json_file = "" #@param {type:"string"}
output_folder = "/content/media_toolkit/transcripts/parsed" #@param {type:"string"}

# Dropdown untuk memilih field yang ingin diambil (pisahkan dengan koma)
selected_fields = "speaker,text" #@param ["speaker","text","confidence","start","end","speaker,text","speaker,text,confidence","speaker,text,confidence,start,end"] {allow-input: true}

# Ubah string menjadi list field
fields_to_extract = [f.strip() for f in selected_fields.split(",")]

log.info(f"🚀 Memulai proses parsing file: {json_file}")

try:
    with open(json_file, 'r') as f:
        data = json.load(f)
    log.info("✅ File JSON berhasil dibaca.")
except Exception as e:
    log.error(f"❌ Gagal membaca file JSON: {e}")
    raise

# --- PROSES PARSING ---
utterances = data.get("utterances", [])
log.info(f"📊 Total utterances ditemukan: {len(utterances)}")

parsed = []
for utt in utterances:
    entry = {field: utt.get(field) for field in fields_to_extract}
    parsed.append(entry)

log.info("⚙️ Proses parsing selesai.")

# --- PENYIMPANAN FILE ---
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    log.info(f"📁 Folder output '{output_folder}' dibuat.")

base_name = os.path.splitext(os.path.basename(json_file))[0]
output_file = os.path.join(output_folder, f"{base_name}_parsed.json")

try:
    with open(output_file, 'w') as f:
        json.dump(parsed, f, indent=2)
    log.info(f"💾 Hasil disimpan ke: {output_file}")
except Exception as e:
    log.error(f"❌ Gagal menyimpan file: {e}")

log.info("✨ Selesai!")
