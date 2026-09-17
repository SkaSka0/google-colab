# Refactor Progress Tracker

> Companion to [`ROADMAP.md`](./ROADMAP.md). Same order: folders
> alphabetical, files alphabetical within each folder.
>
> Check a box only once the file has gone through the full workflow in
> `ROADMAP.md` (understand → preserve → design → refactor → verify →
> summarize), not just once it's been glanced at. Add a one-line note
> with the date and PR/commit reference when you tick a box.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

## 1. `audio_processing/`

- [ ] `convert_audio_to_aac.py` —
- [ ] `extract_audio_from_video.py` —
- [ ] `fix_mono_audio_channel.py` —
- [ ] `merge_audio_with_crossfade.py` —
- [ ] `separate_vocals_from_instrumental.py` —
- [ ] `split_audio_by_duration.py` —

## 2. `downloaders/`

- [ ] `download_file_via_requests_or_aria2c.py` —
- [ ] `download_video_from_twitter.py` —
- [ ] `download_video_refactored_podjav.py` — *(already close to compliant; verification pass only)*
- [ ] `download_video_via_ytdlp_or_aria2c.py` — *(reference-quality file; verification pass only)*

## 3. `file_management/`

- [ ] `delete_files_by_filter.py` —
- [ ] `extract_or_compress_archive.py` —
- [ ] `move_or_copy_files_with_filter.py` —
- [ ] `rename_files_sequentially.py` —

## 4. `metadata/`

- [ ] `export_video_metadata_to_json.py` —
- [ ] `print_json_file_content.py` —

## 5. `transcription/`

- [ ] `fetch_assemblyai_transcript_result.py` —
- [ ] `parse_assemblyai_transcript_fields.py` —
- [ ] `transcribe_audio_via_assemblyai.py` —

## 6. `uploaders/`

- [ ] `upload_video_to_facebook.py` — *(highest-risk file — do last)*
- [ ] `upload_video_to_youtube.py` —

## 7. `video_processing/`

- [ ] `check_video_integrity_and_corruption.py` —
- [ ] `mux_audio_into_video.py` —
- [ ] `mux_subtitle_into_video_basic.py` — *(file not located yet — find it before starting)*
- [ ] `mux_subtitle_into_video_enhanced.py` —
- [ ] `split_video_by_duration_or_size.py` —
- [ ] `trim_video_start.py` —

---

## Summary

- Total files tracked: **27** (26 located + 1 pending location)
- Done: **0**
- In progress: **0**
- Not started: **27**

Update the summary counts whenever a checkbox changes.
