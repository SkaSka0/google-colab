# Media Toolkit — Google Colab Scripts

> ⚠️ **Sebelum melakukan refactor atau kontribusi apa pun**, baca [`docs/INSTRUCTION.md`](./docs/INSTRUCTION.md) dan [`CONTRIBUTING.md`](./CONTRIBUTING.md) terlebih dahulu. Jika menggunakan AI assistant, lihat juga [`AGENTS.md`](./AGENTS.md).

Kumpulan script Python untuk kebutuhan download, upload, dan pengolahan
media (audio & video), dirancang khusus untuk dijalankan di **Google
Colab**. Setiap script bersifat *standalone* — dijalankan sebagai satu
cell notebook tersendiri menggunakan form input `#@param`, bukan
package Python yang saling import satu sama lain.

## 🎯 Tentang Repo Ini

Repo ini adalah gabungan berbagai tools yang biasa dipakai dalam alur
kerja pemrosesan video/audio di Colab — mulai dari mengunduh file dari
berbagai sumber, memisahkan atau menggabungkan audio, muxing subtitle,
transkripsi otomatis, sampai upload hasil akhir ke YouTube/Facebook.
Selain itu ada juga proyek bot Telegram (`Telegram-Leecher` dan
`Telegram-Fetcher`) yang juga berjalan di atas Google Colab untuk
transfer file via Telegram.

Karena sifatnya kumpulan script lepas (bukan satu aplikasi terpadu),
setiap file bisa dipakai secara independen sesuai kebutuhan — cukup
copy-paste ke satu cell Colab, isi parameter di form, lalu jalankan.

## 📁 Struktur Folder

```
media_toolkit/
│
├── downloaders/
│   ├── download_file_via_requests_or_aria2c.py
│   ├── download_video_from_twitter.py
│   └── download_video_via_ytdlp_or_aria2c.py
│
├── uploaders/
│   ├── upload_video_to_youtube.py
│   └── upload_video_to_facebook.py
│
├── audio_processing/
│   ├── extract_audio_from_video.py
│   ├── fix_mono_audio_channel.py
│   ├── split_audio_by_duration.py
│   ├── merge_audio_with_crossfade.py
│   ├── convert_audio_to_aac.py
│   └── separate_vocals_from_instrumental.py
│
├── video_processing/
│   ├── mux_audio_into_video.py
│   ├── mux_subtitle_into_video_basic.py
│   ├── mux_subtitle_into_video_enhanced.py
│   ├── trim_video_start.py
│   ├── split_video_by_duration_or_size.py
│   └── check_video_integrity_and_corruption.py
│
├── transcription/
│   ├── transcribe_audio_via_assemblyai.py
│   ├── fetch_assemblyai_transcript_result.py
│   └── parse_assemblyai_transcript_fields.py
│
├── metadata/
│   ├── export_video_metadata_to_json.py
│   └── print_json_file_content.py
│
├── file_management/
│   ├── move_or_copy_files_with_filter.py
│   ├── delete_files_by_filter.py
│   ├── rename_files_sequentially.py
│   └── extract_or_compress_archive.py
│
├── Telegram-Leecher/       # Bot Telegram untuk transfer file ke Telegram/Google Drive
├── Telegram-Fetcher/       # Bot Telegram untuk menarik file dari chat ke penyimpanan Colab
│
└── docs/
    └── INSTRUCTION.md      # Panduan umum refactoring & coding style untuk repo ini
```

## ⚙️ Cara Pakai

1. Buka Google Colab, buat notebook baru (atau pakai notebook yang
   sudah tersedia).
2. Copy isi salah satu script ke satu cell.
3. Sesuaikan nilai parameter di bagian `#@param` sesuai kebutuhan
   (path input/output, opsi, dll).
4. Jalankan cell — dependency yang dibutuhkan (ffmpeg, aria2c, yt-dlp,
   dsb.) akan otomatis dicek dan diinstall jika belum tersedia.

## 📝 Catatan

- Semua script mengasumsikan environment **Google Colab** (memakai
  path `/content/...`, `google.colab.drive`, `google.colab.userdata`,
  dsb.) dan tidak ditujukan untuk portable ke environment lain.
- `Telegram-Leecher` dan `Telegram-Fetcher` adalah proyek bot yang
  lebih terstruktur (punya package Python sendiri) — lihat
  `ROADMAP.md`, `PROGRESS.md`, dan `TESTING.md` di masing-masing
  folder untuk status pengembangannya.
- `docs/INSTRUCTION.md` berisi panduan gaya coding & refactoring yang
  dipakai sebagai acuan saat merapikan script-script di repo ini.
