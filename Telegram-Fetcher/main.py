# @title <font color=red> 🖥️ Telegram Fetcher
# @markdown <br><center><h2><font color=lime><strong>Fill all Credentials, Run The Cell and Start The Bot</strong></h2></center>
# @markdown <br><br>

# @markdown ---
# @markdown
# @markdown ⚠️ **Important Setup**
# @markdown
# @markdown This notebook now uses **Colab Secrets** instead of `#@param`.
# @markdown
# @markdown Before running this cell, add the following variables in the **🔑 Colab Secrets panel**:
# @markdown
# @markdown - `API_ID`
# @markdown - `API_HASH`
# @markdown - `BOT_TOKEN`
# @markdown
# @markdown 📍 You can open Secrets from the **left sidebar → 🔑 Secrets**
# @markdown
# @markdown After adding them, simply **run this cell to start the bot**.
# @markdown
# @markdown ---

from google.colab import userdata

API_ID = userdata.get("API_ID")
API_HASH = userdata.get("API_HASH")
BOT_TOKEN = userdata.get("BOT_TOKEN")
DOWNLOAD_PATH = "/content/media_toolkit/downloads" #@param {type:"string"}

required_vars = {
    "API_ID": API_ID,
    "API_HASH": API_HASH,
    "BOT_TOKEN": BOT_TOKEN
}

for key, value in required_vars.items():
    if value is None or value == "":
        raise ValueError(f"Missing secret: {key}")

API_ID = int(API_ID)

import subprocess, json, shutil, os
from pathlib import Path
from IPython.display import clear_output

# ===== CONSTANTS =====
REPO_URL = "https://github.com/lIlSkaSkaSkalIl/Telegram-Fetcher"
REPO_DIR = "/content/Telegram-Fetcher"
CONFIG_DIR = f"{REPO_DIR}/colab_fetcher/config"

APPNAME = "TelegramFetcher"

def log(message, level="INFO"):
    """Custom logger dengan format LEVEL:APPNAME:MESSAGE"""
    print(f"{level}:{APPNAME}:{message}")

# Remove default Colab sample data
def remove_sample_data():
    if os.path.exists("/content/sample_data"):
        log("Removing /content/sample_data")

        shutil.rmtree("/content/sample_data")

def validate_inputs():
    """Validasi input API_ID, API_HASH, dan BOT_TOKEN."""
    if not all([API_ID, API_HASH, BOT_TOKEN]):
        raise ValueError("Semua field (API_ID, API_HASH, BOT_TOKEN) harus diisi!")
    try:
        int(API_ID)
    except ValueError:
        raise ValueError("API_ID harus berupa angka integer!")

def setup_repo():
    """Clone repository dari GitHub."""
    if os.path.exists(REPO_DIR):
        log("Menghapus repository lama...")
        shutil.rmtree(REPO_DIR)

    log("Cloning repository...")
    try:
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, REPO_DIR], check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Gagal clone repo: {e}\nPastikan URL valid dan koneksi stabil.")

def install_deps():
    """Install dependencies dari requirements.txt."""
    req_path = f"{REPO_DIR}/requirements.txt"
    if not os.path.exists(req_path):
        raise FileNotFoundError(f"File {req_path} tidak ditemukan!")

    log("Menginstall dependencies...", level="INFO")
    process = subprocess.Popen(
        ["pip", "install", "-r", req_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Real-time output log
    for line in process.stdout:
        log(line.strip(), level="DEBUG")
    if process.wait() != 0:
        raise RuntimeError("Instalasi gagal. Cek requirements.txt!")

def save_credentials():
    """Simpan credentials ke config/credentials.json."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    credentials = {
        "api_id": int(API_ID),
        "api_hash": API_HASH,
        "bot_token": BOT_TOKEN,
        "download_path": DOWNLOAD_PATH
    }
    try:
        with open(f"{CONFIG_DIR}/credentials.json", "w") as f:
            json.dump(credentials, f, indent=4)
        log("Credentials disimpan!", level="INFO")
    except Exception as e:
        raise IOError(f"Gagal menyimpan credentials: {e}")

def run_bot():
    """Jalankan bot dari package colab_fetcher."""
    log("Memulai bot...", level="INFO")
    try:
        !cd /content/Telegram-Fetcher/ && python3 -m colab_fetcher
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Bot crash! Error: {e}")


try:
    remove_sample_data()
    # validate_inputs()
    setup_repo()
    install_deps()
    save_credentials()
    clear_output()
    run_bot()
except Exception as e:
    log(f"ERROR: {str(e)}", level="ERROR")
    raise
