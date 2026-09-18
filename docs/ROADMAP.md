# Refactor Roadmap — Media Toolkit Scripts

> Scope: all standalone Colab scripts in this repo (excludes
> `Telegram-Leecher/` and `Telegram-Fetcher/`, which already have their
> own `ROADMAP.md` / `PROGRESS.md` / `TESTING.md`).
>
> Rules to follow for every item below: [`docs/INSTRUCTION.md`](./docs/INSTRUCTION.md).
> Checkbox tracking for this roadmap lives in a separate file:
> [`PROGRESS.md`](./PROGRESS.md).

## Ordering

Folders are processed in **alphabetical order**, and files within each
folder are processed in **alphabetical order**. This is an arbitrary
but predictable ordering — it does not imply that earlier files are
more broken or more important than later ones. If a file has a hard
dependency on another file's shared helper being extracted first, note
it explicitly in `PROGRESS.md` rather than reordering this roadmap.

```
1. audio_processing/
2. downloaders/
3. file_management/
4. metadata/
5. transcription/
6. uploaders/
7. video_processing/
```

## Workflow per file

Follow the Refactoring Workflow in [`docs/INSTRUCTION.md`](./docs/INSTRUCTION.md)
§15 (Understand → Preserve → Design → Refactor → Verify → Review) for
every file. On top of that, for this roadmap specifically:

- Note behavior that must not change directly in the PR description
  (output file naming, default values, log wording meaning,
  CLI-equivalent flags) — this is the "Preserve" step made concrete.
- Do not mix an English-translation pass with a structural refactor
  unless both are small enough to review together (INSTRUCTION.md §10, §15).
- End of session: tick the corresponding checkbox in `PROGRESS.md` and
  add a one-line note (date + what changed).

## Cross-cutting issues seen repeatedly across the repo

These aren't file-specific — flag them wherever they show up instead
of re-discovering them each time:

- **Mixed Indonesian/English** in logs, comments, and print statements
  across most files (INSTRUCTION.md §10 requires English-only for
  anything touched).
- **`#@param` globals used directly deep in logic** instead of being
  converted once into a config object at a clear boundary
  (INSTRUCTION.md §3, §4). A handful of files
  (`download_video_via_ytdlp_or_aria2c.py`,
  `mux_subtitle_into_video_enhanced.py`) already do this reasonably
  well and can serve as the reference pattern for the others.
- **Generic/inline `ffmpeg`/`ffprobe`/`yt-dlp` dependency-install
  checks duplicated per file** — each script re-implements "is ffmpeg
  installed, if not apt-get install" independently. Out of scope to
  unify into a shared module (scripts are meant to be standalone
  copy-paste cells per `README.md`), but each individual instance
  should still follow the idempotency rule in INSTRUCTION.md §4.
- **Bare `except Exception` / silent `pass`** in a few files — needs
  case-by-case review per INSTRUCTION.md §8.
- **Inconsistent success/failure return values** — some functions
  `return` a summary dict, some return `True/False`, some return
  nothing and rely on prints. Standardize per-file, not repo-wide
  (INSTRUCTION.md §11), since these files don't import each other.

## Folder-by-folder plan

### 1. `audio_processing/`

| # | File | Notable issues to address |
|---|------|----------------------------|
| 1 | `convert_audio_to_aac.py` | Mixed Indonesian/English logs; straightforward single-file flow, low risk — good first file to refactor to validate the workflow above. |
| 2 | `extract_audio_from_video.py` | Mixed language; codec→extension mapping and ffprobe codec detection could be split into a named helper. |
| 3 | `fix_mono_audio_channel.py` | Uses `!{cmd}` shell magic instead of `subprocess.run([...])` (INSTRUCTION.md §13, "avoid unsafe shell construction"); heavy Indonesian logging; audio-vs-video branch could be split into two named helpers. |
| 4 | `merge_audio_with_crossfade.py` | No `log()` abstraction (uses raw `print`); filter_complex string-building could be extracted into `_build_crossfade_filter()`; only `except subprocess.CalledProcessError` — check for missing `FileNotFoundError`/general error paths. |
| 5 | `separate_vocals_from_instrumental.py` | Fairly clean already; check thread/timer cleanup on exception paths; mixed language logs. |
| 6 | `split_audio_by_duration.py` | Bare `except Exception as e` in `get_duration()`; no dataclass grouping for the several related `#@param` fields; mixed language. |

### 2. `downloaders/`

| # | File | Notable issues to address |
|---|------|----------------------------|
| 1 | `download_file_via_requests_or_aria2c.py` | Two backends (`requests` vs `aria2c`) already reasonably separated — check against INSTRUCTION.md §5 (backend selection consistency) rather than restructure from scratch; some duplicated formatting helpers (`format_bytes`, progress bars) between the two engines. |
| 2 | `download_video_from_twitter.py` | Class-based already; mixed Indonesian/English within the same class; naming doesn't yet follow `_private_helper` convention for internal methods. |
| 3 | `download_video_refactored_podjav.py` | Already has type hints, docstrings, English logging — treat as a **verification pass** (confirm it matches INSTRUCTION.md §2–§4 fully) rather than a full rewrite. Uses Indonesian in some log message *contents* (not the code) — check if that's deliberate localized output per INSTRUCTION.md §10 exceptions or should be translated. |
| 4 | `download_video_via_ytdlp_or_aria2c.py` | Already uses dataclasses, `_private_helper` naming, and a `_create_download_config()` boundary — closest file in the repo to the target state. Use as the **reference example** when refactoring the others in this folder. Only remaining polish: a few functions still take many individual args instead of the grouped config (e.g. some `_analyze_downloaded_files` helpers take raw `output_dir` instead of config). |

### 3. `file_management/`

| # | File | Notable issues to address |
|---|------|----------------------------|
| 1 | `delete_files_by_filter.py` | `should_delete()` relies on several `#@param` globals directly instead of parameters (INSTRUCTION.md §4); `debug_mode` mixed into normal logging flow instead of using DEBUG level (INSTRUCTION.md §9). |
| 2 | `extract_or_compress_archive.py` | Best-organized file in this folder already — has `_`-prefixed helpers and clear extract/compress separation; still mixed Indonesian/English logs and docstrings throughout. |
| 3 | `move_or_copy_files_with_filter.py` | Long parameter list on `move_or_copy_path()` (10+ args) — good candidate for a config dataclass per INSTRUCTION.md §3; nested closures (`should_process`, `safe_operation`) make local reasoning harder, consider extracting. |
| 4 | `rename_files_sequentially.py` | Small and simple; mixed language; padding-digit logic (`if total_files >= 100... elif >= 10... else...`) has a redundant branch (`>=10` and `else` both return `2`) worth flagging in the PR rather than "fixing" silently (INSTRUCTION.md §1 — confirm intent first). |

### 4. `metadata/`

| # | File | Notable issues to address |
|---|------|----------------------------|
| 1 | `export_video_metadata_to_json.py` | Uses `!apt-get` shell magic; `pretty_print_json()` duplicated verbatim in `print_json_file_content.py` — flag duplication but do not silently unify across files without asking, since these are meant to stay standalone copy-paste cells. |
| 2 | `print_json_file_content.py` | Small, single-purpose; mostly cosmetic cleanup needed (ANSI color constants, naming). |

### 5. `transcription/`

| # | File | Notable issues to address |
|---|------|----------------------------|
| 1 | `fetch_assemblyai_transcript_result.py` | Reasonably clean already; several `save_*` functions duplicate the same open/write/log pattern — could extract a small shared writer, but weigh against INSTRUCTION.md §5 (avoid over-abstracting a 3-line pattern). |
| 2 | `parse_assemblyai_transcript_fields.py` | Uses Python's `logging` module directly instead of the project's simple `log()` convention used elsewhere — confirm with user whether to standardize or leave as-is (this is a deliberate deviation, not obviously a bug). |
| 3 | `transcribe_audio_via_assemblyai.py` | Longest/most complex file in this folder; heavy Indonesian logging; `main()` does upload + transcribe + poll + save + cleanup all inline — strong candidate for splitting into named stage functions per INSTRUCTION.md §5, but do this as more than one incremental PR. |

### 6. `uploaders/`

| # | File | Notable issues to address |
|---|------|----------------------------|
| 1 | `upload_video_to_facebook.py` | Largest file in the repo; imports scattered inside functions instead of at top of file (INSTRUCTION.md §12); scheduling logic (`get_batch_schedule_times`, `get_schedule_timestamp_iso_or_unix`) duplicates timezone/validation logic — consolidate carefully, this is the highest-risk file in the repo for accidental behavior change (real API side effects). Treat as **last** file overall, after the workflow has been validated on lower-risk files. |
| 2 | `upload_video_to_youtube.py` | `TEMPLATE_FOOTER` built from `#@param` values at module load time before `main()` runs — check against INSTRUCTION.md §4 (persistent runtime state / rebuild-per-run) since Colab re-runs can leave stale globals; mixed Indonesian/English. |

### 7. `video_processing/`

| # | File | Notable issues to address |
|---|------|----------------------------|
| 1 | `check_video_integrity_and_corruption.py` | Already has a structured custom logger (`log_debug/info/warn/error`) distinct from every other file's `log()` convention — decide whether to keep this file's own richer logging or align with the repo-wide simple convention; heavy Indonesian log *content* throughout (step messages). |
| 2 | `mux_audio_into_video.py` | Small and clean; `mode` param ("replace"/"add") is a good existing example of the INSTRUCTION.md §5 "validated string, not enum" pattern — keep as-is. |
| 3 | `mux_subtitle_into_video_basic.py` | Referenced in `README.md`'s folder structure but not available for review in this session — locate the file and add it to this table before starting this folder. |
| 4 | `mux_subtitle_into_video_enhanced.py` | Best-structured file in this folder — already does validation, verification-after-mux, and structured result dicts. Mostly needs the English-translation pass (INSTRUCTION.md §10) and a check that `mux_subtitle()`'s responsibilities (validate + build cmd + run + verify + cleanup) aren't too many for one function (INSTRUCTION.md §1). |
| 5 | `split_video_by_duration_or_size.py` | Uses `!apt-get`/shell magic; priority logic between `cut_by_size` and `cut_by_chunk_minutes` currently just prints a warning and proceeds — confirm this is intentional before changing; mixed language. |
| 6 | `trim_video_start.py` | Clean and small; good candidate for an early/easy file in this folder. |

## Explicitly out of scope for this roadmap

- `Telegram-Leecher/` and `Telegram-Fetcher/` — tracked by their own
  `ROADMAP.md` / `PROGRESS.md` / `TESTING.md` per `CONTRIBUTING.md`.
- Introducing a shared Python package/module across scripts — the
  repo is intentionally a collection of standalone Colab cells
  (`README.md`); do not propose consolidating shared helpers into an
  importable module without discussing it first.
- Any behavior change (default values, output formats, filename
  conventions) — refactors here are structure-only unless a specific
  PR explicitly calls out and justifies a behavior change.
