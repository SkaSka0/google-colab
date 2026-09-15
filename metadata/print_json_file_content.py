# @title 📄 Tampilkan Isi File JSON

import json
import os

# ==============================
# 🔧 INPUT PARAMETER (COLAB)
# ==============================
json_file_path = "/content/media_toolkit/downloads/twitter/metadata/SNOS_154_SNOS_154_Sudden_bukkake_orgy_at_the_idol.json"  #@param {type:"string"}

# ==============================
# 🎨 PRETTY PRINT FUNCTION
# ==============================
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"

def pretty_print_json(data, indent=0, step=4):
    prefix = " " * indent
    icon = "📁"  # bisa diganti sesuai selera

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{prefix}{BOLD}{CYAN}{icon} {key}:{RESET}")
                pretty_print_json(value, indent + step, step)
            else:
                print(f"{prefix}{YELLOW}{icon} {key}{RESET} : {GREEN}{value}{RESET}")
    elif isinstance(data, list):
        for item in data:
            pretty_print_json(item, indent, step)

# ==============================
# 🚀 MAIN PROCESS
# ==============================
def show_json_content(file_path):
    if not os.path.exists(file_path):
        print(f"❌ File tidak ditemukan: {file_path}")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        print("✅ File JSON berhasil dibaca\n")
        pretty_print_json(data)  # gunakan fungsi pretty print

    except json.JSONDecodeError as e:
        print("❌ Gagal parsing JSON")
        print(e)

    except Exception as e:
        print("❌ Terjadi error")
        print(e)

# ==============================
# ▶️ EXECUTE
# ==============================
show_json_content(json_file_path)
