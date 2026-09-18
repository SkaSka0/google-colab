# Media Toolkit — Google Colab Scripts

> ⚠️ **Before doing any refactoring or contribution**, read [`docs/INSTRUCTION.md`](./docs/INSTRUCTION.md) and [`CONTRIBUTING.md`](./CONTRIBUTING.md) first. If you're using an AI assistant, also see [`AGENTS.md`](./AGENTS.md).

A collection of Python scripts for downloading, uploading, and
processing media (audio & video), designed specifically to run on
**Google Colab**. Each script is standalone — run as a single notebook
cell using `#@param` form inputs, not a Python package that imports
from other scripts.

## 🎯 About This Repo

This repo bundles various tools commonly used in a Colab video/audio
processing workflow — from downloading files from various sources,
splitting or merging audio, muxing subtitles, automatic transcription,
to uploading the final result to YouTube/Facebook. It also includes
two Telegram bot projects (`Telegram-Leecher` and `Telegram-Fetcher`)
that also run on top of Google Colab for file transfer via Telegram.

Because it's a collection of loose scripts (not one unified
application), each file can be used independently as needed — just
copy-paste it into a single Colab cell, fill in the form parameters,
and run it.

## 📁 Folder Structure

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
├── Telegram-Leecher/       # Telegram bot for transferring files to Telegram/Google Drive
├── Telegram-Fetcher/       # Telegram bot for pulling files from chat into Colab storage
│
└── docs/
    ├── INSTRUCTION.md      # General refactoring & coding style guide for this repo
    ├── ROADMAP.md          # Refactor priorities & reasoning for the folders above
    └── PROGRESS.md         # Per-file refactor status checklist
```

## ⚙️ How to Use

1. Open Google Colab, create a new notebook (or use an existing one).
2. Copy the contents of one script into a single cell.
3. Adjust the parameter values in the `#@param` section as needed
   (input/output paths, options, etc).
4. Run the cell — required dependencies (ffmpeg, aria2c, yt-dlp, etc.)
   are checked and installed automatically if not already available.

## 📝 Notes

- All scripts assume a **Google Colab** environment (they use
  `/content/...` paths, `google.colab.drive`, `google.colab.userdata`,
  etc.) and are not intended to be portable to other environments.
- `Telegram-Leecher` and `Telegram-Fetcher` are more structured bot
  projects (each has its own Python package) — see `ROADMAP.md`,
  `PROGRESS.md`, and `TESTING.md` in their respective folders for
  development status.
- For the standalone script folders above (`downloaders/`,
  `uploaders/`, `audio_processing/`, etc.), refactor status and
  priorities are tracked centrally in [`docs/ROADMAP.md`](./docs/ROADMAP.md)
  (reasoning & ordering) and [`docs/PROGRESS.md`](./docs/PROGRESS.md)
  (per-file checklist) — unlike the per-folder pattern used in
  `Telegram-Leecher`/`Telegram-Fetcher`.
- `docs/INSTRUCTION.md` contains the coding & refactoring style guide
  used as the reference when cleaning up the scripts in this repo.
