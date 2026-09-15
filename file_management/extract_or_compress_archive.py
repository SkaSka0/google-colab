#@title 📦 Super Archive Tool (Extract & Compress)
import os
import re
import glob
import subprocess

try:
    from tqdm.notebook import tqdm
except ImportError:
    from tqdm.auto import tqdm

APPNAME = "SuperArchiveTool"
PERCENT_REGEX = re.compile(r"(\d{1,3})%")

# =====================================================================
# 🔧 KONFIGURASI
# =====================================================================

#@markdown ### ⚙️ Mode Operasi
mode = "extract" #@param ["extract", "compress"]

#@markdown ### 📥 Path
input_dir = "/content/media_toolkit" #@param {type:"string"}
output_dir = "/content/media_toolkit/video" #@param {type:"string"}

#@markdown ### 🗜️ Konfigurasi Kompresi (hanya dipakai jika mode = "compress")
compress_format = "zip" #@param ["zip", "rar"]
#@markdown Jika dicentang, semua isi `input_dir` digabung jadi 1 arsip.
#@markdown Jika tidak, tiap item (file/folder) di dalam `input_dir` dikompres jadi arsip terpisah.
compress_as_single_archive = False #@param {type:"boolean"}
single_archive_name = "archive" #@param {type:"string"}

# Ekstensi yang dianggap "arsip utama / part pertama" saat ekstraksi
VALID_SUFFIXES = (
    ".zip", ".rar", ".7z",
    ".zip.001", ".rar.001",
    ".part1.rar", ".part01.rar", ".part001.rar",
)

# Ekstensi yang dianggap "part lanjutan" → di-skip saat ekstraksi
SKIP_SUFFIXES = (
    ".zip.002", ".zip.003", ".zip.004", ".zip.005",
    ".zip.006", ".zip.007", ".zip.008", ".zip.009",
    ".z02", ".z03", ".z04", ".z05",
    ".part2.rar",  ".part02.rar",  ".part002.rar",
    ".part3.rar",  ".part03.rar",  ".part003.rar",
    ".part4.rar",  ".part04.rar",  ".part004.rar",
    ".part5.rar",  ".part05.rar",  ".part005.rar",
    ".rar.002", ".rar.003", ".rar.004", ".rar.005",
)


# =====================================================================
# 🪵 LOGGING
# =====================================================================

def log(message: str, level: str = "INFO") -> None:
    """Cetak satu baris log dengan format seragam."""
    print(f"{level}:{APPNAME}:{message}", flush=True)


# =====================================================================
# 🔍 FILTER / DETEKSI FILE (khusus ekstraksi)
# =====================================================================

def is_skip_part(filename_lower: str) -> bool:
    """True jika file adalah part lanjutan (bukan part pertama)."""
    return any(filename_lower.endswith(s) for s in SKIP_SUFFIXES)


def is_valid_archive(filename_lower: str) -> bool:
    """True jika file adalah arsip utama / part pertama yang valid."""
    return any(filename_lower.endswith(s) for s in VALID_SUFFIXES)


def find_extract_targets(folder: str) -> list:
    """Cari semua file arsip utama/part pertama di dalam sebuah folder."""
    all_files = glob.glob(os.path.join(folder, "*"))
    targets = []
    for f in all_files:
        f_lower = f.lower()
        if is_skip_part(f_lower):
            continue
        if is_valid_archive(f_lower):
            targets.append(f)
    return targets


# =====================================================================
# 🏃 EKSEKUSI SUBPROCESS (dipakai bareng oleh extract & compress)
# =====================================================================

def check_stdbuf_available() -> bool:
    """Cek apakah 'stdbuf' tersedia (dipakai untuk memaksa output child process tidak di-buffer)."""
    success, _ = run_command(["which", "stdbuf"])
    return success


def unbuffer_command(cmd: list) -> list:
    """
    Bungkus command dengan 'stdbuf -o0 -e0'. Tanpa ini, saat stdout diarahkan ke
    pipe (bukan terminal), 7z/rar biasanya beralih ke mode fully-buffered —
    output progress ditahan di buffer internal dan baru muncul di akhir proses,
    walaupun file arsip di disk sudah bertambah besar. 'stdbuf' memaksa child
    process langsung flush setiap ada output baru.
    """
    if check_stdbuf_available():
        return ["stdbuf", "-o0", "-e0"] + cmd
    log("'stdbuf' tidak ditemukan — progress bar mungkin tidak real-time.", "WARNING")
    return cmd


def run_command(cmd: list) -> tuple:
    """Jalankan command, return (sukses: bool, stderr: str)."""
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode == 0, result.stderr


def run_command_with_progress(cmd: list, on_percent) -> tuple:
    """
    Jalankan command sambil membaca output SECARA REAL-TIME, byte demi byte
    (bukan text-mode) supaya update yang dikirim lewat '\\r' tidak tertahan
    oleh translasi newline Python. Command otomatis dibungkus 'stdbuf' agar
    child process tidak menahan outputnya di buffer internal.
    Panggil on_percent(int) tiap kali angka persentase baru ditemukan.
    Return (sukses, baris_terakhir).
    """
    cmd = unbuffer_command(cmd)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)

    buffer = b""
    last_line = ""
    while True:
        chunk = process.stdout.read(1)
        if not chunk:
            break
        if chunk in (b"\r", b"\n"):
            if buffer.strip():
                text = buffer.decode("utf-8", errors="ignore")
                last_line = text
                match = PERCENT_REGEX.search(text)
                if match:
                    on_percent(min(int(match.group(1)), 100))
            buffer = b""
        else:
            buffer += chunk

    process.wait()
    return process.returncode == 0, last_line


# =====================================================================
# 📤 EKSTRAKSI
# =====================================================================

def build_extract_command(archive: str, output_folder: str) -> list:
    """Susun command 7z untuk mengekstrak satu arsip."""
    return ["7z", "x", archive, f"-o{output_folder}", "-y"]


def extract_one(archive: str, output_folder: str) -> bool:
    """Ekstrak satu arsip ke output_folder. Return True jika sukses."""
    os.makedirs(output_folder, exist_ok=True)
    cmd = build_extract_command(archive, output_folder)
    success, stderr = run_command(cmd)
    if success:
        log(f"{os.path.basename(archive)}", "SUCCESS")
    else:
        log(f"{os.path.basename(archive)} {stderr}", "ERROR")
    return success


def make_extraction_subfolder(folder: str, archive_path: str) -> str:
    """Bentuk path subfolder tujuan ekstraksi berdasarkan nama arsip."""
    filename = os.path.basename(archive_path)
    archive_stem = filename.split(".")[0]
    return os.path.join(folder, f"_extracted_{archive_stem}")


def recursive_extract(folder: str, depth: int = 0) -> None:
    """
    Rekursif: cari arsip di folder, ekstrak, lalu cek hasil ekstraksi
    apakah ada arsip lagi di dalamnya. Ulangi sampai tidak ada lagi.
    """
    indent = "  " * depth
    targets = find_extract_targets(folder)

    if not targets:
        log(f"{indent}Tidak ada arsip di: {folder} — selesai di kedalaman ini.")
        return

    log(f"{indent}[Depth {depth}] Ditemukan {len(targets)} arsip di: {folder}")

    for index, archive in enumerate(targets, 1):
        filename = os.path.basename(archive)
        log(f"{indent}--- [{index}/{len(targets)}] Mengekstrak: {filename} ---")

        extract_target = make_extraction_subfolder(folder, archive)
        success = extract_one(archive, extract_target)

        if success:
            recursive_extract(extract_target, depth + 1)


def run_extraction_mode(input_dir: str, output_dir: str) -> None:
    """Orkestrasi penuh untuk mode ekstraksi."""
    os.makedirs(output_dir, exist_ok=True)
    targets = find_extract_targets(input_dir)

    if not targets:
        log(f"Tidak ditemukan file arsip yang valid di: {input_dir}", "WARNING")
        return

    log(f"Ditemukan {len(targets)} arsip utama untuk diproses.")
    for index, archive in enumerate(targets, 1):
        filename = os.path.basename(archive)
        log(f"--- [{index}/{len(targets)}] Mengekstrak: {filename} ---")
        success = extract_one(archive, output_dir)
        if success:
            recursive_extract(output_dir, depth=1)


# =====================================================================
# 📥 KOMPRESI
# =====================================================================

def check_rar_binary_available() -> bool:
    """Cek apakah binary 'rar' (bukan 'unrar') tersedia untuk membuat arsip .rar."""
    success, _ = run_command(["which", "rar"])
    return success


def build_compress_command(fmt: str, archive_path: str, source_path: str) -> list:
    """Susun command untuk mengompres source_path menjadi archive_path, sesuai format."""
    if fmt == "zip":
        # -bsp1 memaksa 7z mengirim info progress ke stdout walau tidak jalan di TTY
        return ["7z", "a", "-tzip", "-bsp1", archive_path, source_path]
    elif fmt == "rar":
        # rar menampilkan persentase progress secara default (tanpa -idp)
        return ["rar", "a", archive_path, source_path]
    else:
        raise ValueError(f"Format kompresi tidak didukung: {fmt}")


def compress_one(source_path: str, archive_path: str, fmt: str, show_progress: bool = True) -> bool:
    """Kompres satu item (file/folder) menjadi satu arsip, dengan progress bar. Return True jika sukses."""
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)
    cmd = build_compress_command(fmt, archive_path, source_path)
    label = os.path.basename(source_path)

    if not show_progress:
        success, tail = run_command_with_progress(cmd, lambda p: None)
    else:
        with tqdm(total=100, desc=label, unit="%", leave=False) as bar:
            def on_percent(p: int) -> None:
                bar.n = p
                bar.refresh()
            success, tail = run_command_with_progress(cmd, on_percent)
            bar.n = 100 if success else bar.n
            bar.refresh()

    if success:
        log(f"{label} → {os.path.basename(archive_path)}", "SUCCESS")
    else:
        log(f"{label} {tail}", "ERROR")
    return success


def find_compress_targets(folder: str) -> list:
    """Cari semua item (file atau folder) di dalam folder untuk dikompres satu per satu."""
    return glob.glob(os.path.join(folder, "*"))


def build_archive_path(output_dir: str, name: str, fmt: str) -> str:
    """Bentuk path lengkap arsip output berdasarkan nama dan format."""
    return os.path.join(output_dir, f"{name}.{fmt}")


def run_compress_single_archive(input_dir: str, output_dir: str, fmt: str, archive_name: str) -> None:
    """Gabungkan seluruh isi input_dir menjadi satu arsip."""
    archive_path = build_archive_path(output_dir, archive_name, fmt)
    source_glob = os.path.join(input_dir, "*")
    log(f"Mengompres seluruh isi '{input_dir}' menjadi satu arsip: {os.path.basename(archive_path)}")
    compress_one(source_glob, archive_path, fmt)


def run_compress_per_item(input_dir: str, output_dir: str, fmt: str) -> None:
    """Kompres tiap item di input_dir menjadi arsip terpisah."""
    targets = find_compress_targets(input_dir)

    if not targets:
        log(f"Tidak ditemukan item untuk dikompres di: {input_dir}", "WARNING")
        return

    log(f"Ditemukan {len(targets)} item untuk dikompres satu per satu.")
    with tqdm(total=len(targets), desc="Total progres", unit="item") as overall_bar:
        for index, item in enumerate(targets, 1):
            item_name = os.path.basename(item)
            item_stem = os.path.splitext(item_name)[0]
            archive_path = build_archive_path(output_dir, item_stem, fmt)
            log(f"--- [{index}/{len(targets)}] Mengompres: {item_name} ---")
            compress_one(item, archive_path, fmt)
            overall_bar.update(1)


def run_compression_mode(input_dir: str, output_dir: str, fmt: str,
                          as_single: bool, archive_name: str) -> None:
    """Orkestrasi penuh untuk mode kompresi."""
    os.makedirs(output_dir, exist_ok=True)

    if fmt == "rar" and not check_rar_binary_available():
        log("Binary 'rar' tidak ditemukan. Install dengan: apt-get install rar", "ERROR")
        log("Catatan: 'unrar' saja tidak cukup untuk MEMBUAT arsip .rar.", "ERROR")
        return

    if as_single:
        run_compress_single_archive(input_dir, output_dir, fmt, archive_name)
    else:
        run_compress_per_item(input_dir, output_dir, fmt)


# =====================================================================
# 🚀 MAIN
# =====================================================================

def main() -> None:
    log(f"=== Proses Dimulai (mode={mode}) ===")

    if mode == "extract":
        run_extraction_mode(input_dir, output_dir)
    elif mode == "compress":
        run_compression_mode(
            input_dir, output_dir, compress_format,
            compress_as_single_archive, single_archive_name,
        )
    else:
        log(f"Mode tidak dikenal: {mode}", "ERROR")

    log("=== Seluruh Proses Selesai ===")


if __name__ == "__main__":
    main()