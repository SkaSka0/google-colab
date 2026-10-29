#@title 🔎 Search & Download Subtitle (SubDL API v2)
#@markdown - Searches subtitles on **subdl.com** via the **API v2** and downloads the ones you pick.
#@markdown - Two search modes: by **title / IDs** (`subtitles/search`) or by **release filename** (`files/search`, ranked by `match_score`).
#@markdown - Default output folder matches `subtitle_input` in `mux_subtitle_into_video_enhanced.py`.
#@markdown
#@markdown ## 🔐 API Key from Colab Secrets
#@markdown 1. Open the left panel in Colab → 🔑 **Secrets**
#@markdown 2. Click **Add new secret**
#@markdown 3. Name: `SUBDL_API_KEY`
#@markdown 4. Value: your API key from your subdl.com account
#@markdown 5. Save and enable notebook access
#@markdown
#@markdown Free plan limits: 2,000 searches/day and **50 downloads/day**.

import io
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass

import requests
from google.colab import userdata

# ============================================================
# INPUT FORM (Colab)
# ============================================================

#@markdown ---
#@markdown ### 🔎 Search mode
search_mode = "title"  #@param ["title", "filename"]

#@markdown **Title mode** — fill ONE of: sd_id, imdb_id, tmdb_id, film_name
film_name = ""  #@param {type:"string"}
imdb_id = ""  #@param {type:"string"}
tmdb_id = ""  #@param {type:"string"}
sd_id = ""  #@param {type:"string"}
#@markdown `content_type` is required when using `tmdb_id`.
content_type = "any"  #@param ["any", "movie", "tv"]
season = ""  #@param {type:"string"}
episode = ""  #@param {type:"string"}
full_season = False  #@param {type:"boolean"}

#@markdown **Filename mode** — a release filename (a full path is fine, only the file name is used)
filename_query = ""  #@param {type:"string"}
#@markdown `local` is safe on every plan. `auto`/`ai` may use the AI parser (Pro, or 1 free match per month).
engine = "local"  #@param ["local", "auto", "ai"]
episode_scope = "exact"  #@param ["exact", "title"]
hi_filter = "any"  #@param ["any", "only", "exclude"]
subs_per_page = 10  #@param {type:"integer", min:1, max:30}

#@markdown **Both modes** — comma-separated language codes, e.g. `id` or `id,en`
languages = "id"  #@param {type:"string"}

#@markdown ---
#@markdown ### ⬇️ Download
mode = "search_only"  #@param ["search_only", "download"]
#@markdown Row numbers from the result table: `1`, `1,3`, `2-4`, or `all`
download_selection = "1"  #@param {type:"string"}
output_dir = "/content/media_toolkit/subtitle"  #@param {type:"string"}
#@markdown `file` = exact single subtitle file (falls back to zip if unavailable). `zip` = whole archive.
download_format = "file"  #@param ["file", "zip"]
#@markdown Only applies when the downloaded data is a zip archive.
extract_zip = True  #@param {type:"boolean"}
#@markdown Print the first 5 blocks of each saved subtitle file (.srt, .vtt, .ass, ...).
show_preview = True  #@param {type:"boolean"}

#@markdown ---
#@markdown Print the complete JSON returned by the search endpoint, before the result table.
show_full_json_response = False  #@param {type:"boolean"}
show_usage = True  #@param {type:"boolean"}
debug_raw_response = False  #@param {type:"boolean"}

# ============================================================
# CONSTANTS
# ============================================================

APPNAME = "SubdlClient"

API_BASE_URL = "https://api.subdl.com"
LEGACY_DOWNLOAD_BASE_URL = "https://dl.subdl.com"
API_KEY_SECRET_NAME = "SUBDL_API_KEY"

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5
# 429 = rate limited, 5xx = temporary server problem. Everything else is not retried.
RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)
# A daily quota will not recover within seconds, so retrying it is pointless.
NON_RETRYABLE_ERROR_CODES = ("quota_exceeded",)

SUBTITLE_EXTENSIONS = (".srt", ".vtt", ".ass", ".ssa", ".sub")
DEFAULT_SUBTITLE_EXTENSION = ".srt"
PREVIEW_BLOCK_COUNT = 5
PREVIEW_MAX_LINE_LENGTH = 100
ASS_OVERRIDE_TAG_PATTERN = re.compile(r"\{[^}]*\}")
N_ID_KEYS = ("n_id", "nId", "nid")
# Search entries carry no n_id field; the nId is the last segment of 'subtitlePage'
# (e.g. "/s/info/h50yy9xLhy"), matching the "/s/info/{n_id}" pattern in the v2 docs.
SUBTITLE_PAGE_PATTERN = re.compile(r"/s/info/([A-Za-z0-9_-]+)/?")
SUBDL_WEB_BASE_URL = "https://subdl.com"
MISSING_VALUE_TEXT = "?"
API_KEY_QUERY_PATTERN = re.compile(r"(api_key=)[^&\s\"']+")


# ============================================================
# CONFIGURATION (dataclasses)
# ============================================================

@dataclass
class SearchQuery:
    mode: str = "title"
    film_name: str = ""
    imdb_id: str = ""
    tmdb_id: str = ""
    sd_id: str = ""
    content_type: str = "any"
    season: str = ""
    episode: str = ""
    full_season: bool = False
    filename: str = ""
    engine: str = "local"
    episode_scope: str = "exact"
    hi_filter: str = "any"
    subs_per_page: int = 10
    languages: str = ""


@dataclass
class DownloadOptions:
    enabled: bool = False
    selection: str = "1"
    output_dir: str = ""
    format: str = "file"
    extract_zip: bool = True
    show_preview: bool = True


@dataclass
class AppConfig:
    query: SearchQuery
    download: DownloadOptions
    show_usage: bool = True
    show_full_json_response: bool = False
    debug_raw_response: bool = False


def _create_app_config() -> AppConfig:
    """Build a fresh AppConfig from the current Colab form values.

    Always constructs a new object because a Colab cell can be re-run
    inside the same kernel session.
    """
    return AppConfig(
        query=SearchQuery(
            mode=search_mode,
            film_name=film_name.strip(),
            imdb_id=imdb_id.strip(),
            tmdb_id=tmdb_id.strip(),
            sd_id=sd_id.strip(),
            content_type=content_type,
            season=season.strip(),
            episode=episode.strip(),
            full_season=full_season,
            filename=os.path.basename(filename_query.strip()),
            engine=engine,
            episode_scope=episode_scope,
            hi_filter=hi_filter,
            subs_per_page=subs_per_page,
            languages=languages.replace(" ", "").lower(),
        ),
        download=DownloadOptions(
            enabled=(mode == "download"),
            selection=download_selection.strip(),
            output_dir=output_dir,
            format=download_format,
            extract_zip=extract_zip,
            show_preview=show_preview,
        ),
        show_usage=show_usage,
        show_full_json_response=show_full_json_response,
        debug_raw_response=debug_raw_response,
    )


# ============================================================
# LOGGING
# ============================================================

def log(message: str, level: str = "INFO") -> None:
    """Print a formatted log message."""
    print(f"{level}:{APPNAME}:{message}", flush=True)


def _mask_api_keys(text: str) -> str:
    """Hide '?api_key=...' values. Search results embed the key in each download URL."""
    return API_KEY_QUERY_PATTERN.sub(r"\1***", text)


# ============================================================
# HTTP HELPERS
# ============================================================

def _get_api_key() -> str:
    """Read the SubDL API key from Colab Secrets. Returns '' if unavailable."""
    try:
        return userdata.get(API_KEY_SECRET_NAME) or ""
    except userdata.SecretNotFoundError:
        log(f"Secret '{API_KEY_SECRET_NAME}' not found in Colab Secrets!", "ERROR")
    except userdata.NotebookAccessError:
        log(f"Notebook access to secret '{API_KEY_SECRET_NAME}' is not enabled!", "ERROR")
    return ""


def _auth_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


def _parse_api_error(response: requests.Response) -> tuple[str, str]:
    """Extract (code, message) from the shared v2 error shape."""
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return "", response.text[:200]

    if isinstance(error, dict):
        return str(error.get("code", "")), str(error.get("message", ""))
    if isinstance(error, str):
        return "", error
    return "", response.text[:200]


def _request_with_retry(url: str, api_key: str, params: dict | None = None) -> requests.Response | None:
    """GET a URL with bounded retries on rate-limit/server errors only.

    Returns the response on success (HTTP 2xx), or None on a fatal or
    exhausted-retry failure. The caller decides what to do next.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                url, params=params, headers=_auth_headers(api_key), timeout=REQUEST_TIMEOUT
            )
        except (requests.Timeout, requests.ConnectionError) as e:
            log(f"Network error (attempt {attempt}/{MAX_RETRIES}): {e}", "WARNING")
        else:
            if response.ok:
                return response

            code, message = _parse_api_error(response)
            detail = f"HTTP {response.status_code} {code}: {message}".strip()

            if response.status_code == 402:
                log(f"{detail} (this feature requires SubDL Pro)", "ERROR")
                return None

            retryable = (
                response.status_code in RETRYABLE_STATUS_CODES
                and code not in NON_RETRYABLE_ERROR_CODES
            )
            if not retryable:
                log(detail, "ERROR")
                return None

            log(f"{detail} (attempt {attempt}/{MAX_RETRIES})", "WARNING")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_WAIT_SECONDS)

    log("Request failed after all retries.", "ERROR")
    return None


def _get_json(path: str, api_key: str, params: dict | None = None) -> dict | None:
    """GET an API v2 path and return parsed JSON, or None on failure."""
    response = _request_with_retry(f"{API_BASE_URL}{path}", api_key, params=params)
    if response is None:
        return None
    try:
        return response.json()
    except ValueError:
        log("Response is not valid JSON.", "ERROR")
        return None


# ============================================================
# ACCOUNT USAGE
# ============================================================

def _print_account_usage(api_key: str) -> None:
    """Print plan and quota counters. /me does not count against the search quota."""
    data = _get_json("/api/v2/me", api_key)
    if not data:
        return

    plan = (data.get("plan") or {}).get("name", "unknown")
    usage = data.get("usage") or {}
    parts = []
    for label in ("search", "downloads"):
        counter = usage.get(label) or {}
        if counter:
            parts.append(
                f"{label}: {counter.get('remaining', '?')}/{counter.get('limit', '?')} "
                f"left per {counter.get('period', '?')}"
            )
    log(f"Plan: {plan} | " + " | ".join(parts))


# ============================================================
# SEARCH
# ============================================================

def _pick_title_key(query: SearchQuery) -> tuple[str, str]:
    """Pick the single title key to send, in priority order. Returns ('', '') if none."""
    candidates = [
        ("sd_id", query.sd_id),
        ("imdb_id", query.imdb_id),
        ("tmdb_id", query.tmdb_id),
        ("film_name", query.film_name),
    ]
    filled = [(key, value) for key, value in candidates if value]
    if len(filled) > 1:
        log(f"Several title fields filled; using '{filled[0][0]}' only (API takes one).", "WARNING")
    return filled[0] if filled else ("", "")


def _build_title_search_params(query: SearchQuery) -> dict | None:
    """Build GET params for /subtitles/search. Returns None if the input is invalid."""
    key, value = _pick_title_key(query)
    if not key:
        log("Title mode: fill one of sd_id, imdb_id, tmdb_id, film_name.", "ERROR")
        return None

    if key == "tmdb_id" and query.content_type == "any":
        log("tmdb_id requires content_type = movie or tv.", "ERROR")
        return None

    params = {
        key: value,
        "type": "" if query.content_type == "any" else query.content_type,
        "languages": query.languages,
        "season": query.season,
        "episode": query.episode,
    }
    if query.full_season:
        params["full_season"] = 1

    return {k: v for k, v in params.items() if v not in ("", None)}


def _build_filename_search_params(query: SearchQuery) -> dict | None:
    """Build GET params for /files/search. Returns None if the input is invalid."""
    if not query.filename:
        log("Filename mode: fill filename_query.", "ERROR")
        return None

    params = {
        "filename": query.filename,
        "engine": query.engine,
        "episode_scope": query.episode_scope,
        "languages": query.languages,
        "type": "" if query.content_type == "any" else query.content_type,
        "subs_per_page": query.subs_per_page,
    }
    if query.hi_filter == "only":
        params["hi"] = 1
    elif query.hi_filter == "exclude":
        params["hi"] = 0

    return {k: v for k, v in params.items() if v not in ("", None)}


def search_subtitles(api_key: str, query: SearchQuery) -> dict | None:
    """Search SubDL v2. Returns the parsed JSON on success, None on failure."""
    if query.mode == "filename":
        path = "/api/v2/files/search"
        params = _build_filename_search_params(query)
    else:
        path = "/api/v2/subtitles/search"
        params = _build_title_search_params(query)

    if params is None:
        return None

    log(f"GET {path} {params}")
    data = _get_json(path, api_key, params=params)
    if data is None:
        return None

    if data.get("status") is False or (data.get("error") and not data.get("subtitles")):
        log(f"API error: {data.get('error', 'unknown error')}", "ERROR")
        return None

    return data


def _print_full_json_response(data: dict) -> None:
    """Pretty-print the complete search response JSON."""
    print("=" * 80)
    print("FULL SEARCH RESPONSE (JSON)")
    print("=" * 80)
    print(_mask_api_keys(json.dumps(data, ensure_ascii=False, indent=2)))
    print("=" * 80)


def _format_value(value: object) -> str:
    """Show '?' for values the API returned as null/empty."""
    if value is None or value == "":
        return MISSING_VALUE_TEXT
    return str(value)


def _two_digits(value: object) -> str:
    return f"{value:02d}" if isinstance(value, int) else str(value)


def _format_episode_label(sub: dict) -> str:
    """Build 'S01E05' / 'S01 FULL-SEASON' for TV entries ('' if nothing applies)."""
    label = ""
    if sub.get("season") is not None:
        label += f"S{_two_digits(sub['season'])}"
    if sub.get("episode") is not None:
        label += f"E{_two_digits(sub['episode'])}"
    if sub.get("full_season"):
        label = f"{label} FULL-SEASON".strip()
    return label


def _is_movie_result(data: dict) -> bool:
    """True when the matched title is a movie (season/full_season are noise there)."""
    match = data.get("match")
    if isinstance(match, dict) and match.get("type"):
        return match["type"] == "movie"
    results = data.get("results") or []
    return bool(results) and results[0].get("type") == "movie"


def _build_subtitle_page_url(sub: dict) -> str:
    """Web page of the subtitle on subdl.com ('' if the entry has none)."""
    page = str(sub.get("subtitlePage") or "")
    return f"{SUBDL_WEB_BASE_URL}{page}" if page else ""


def _format_match_line(match: dict) -> str:
    """Summarize the 'match' object returned by the search."""
    episode_text = ""
    if match.get("season") is not None:
        episode_text += f" S{_two_digits(match['season'])}"
    if match.get("episode") is not None:
        episode_text += f"E{_two_digits(match['episode'])}"
    return (
        f"Match: {match.get('title')} ({match.get('year')}){episode_text} "
        f"engine={match.get('engine')} confidence={match.get('confidence')}"
    )


def _print_search_results(data: dict) -> None:
    """Print matched titles, the match summary (if any), then a numbered subtitle table."""
    results = data.get("results") or []
    match = data.get("match")
    subtitles = data.get("subtitles") or []

    if results:
        log(f"Matched titles: {len(results)}")
        for item in results:
            log(
                f"  - {item.get('name')} ({item.get('year')}) [{item.get('type')}] "
                f"imdb={item.get('imdb_id')} tmdb={item.get('tmdb_id')} sd_id={item.get('sd_id')}"
            )

    if isinstance(match, dict):
        log(_format_match_line(match))

    if not subtitles:
        log("No subtitles found.", "WARNING")
        return

    is_movie = _is_movie_result(data)
    log(
        f"Subtitles found: {len(subtitles)} | page {data.get('currentPage', '?')}"
        f"/{data.get('totalPages', '?')}"
    )
    print("-" * 80)
    for index, sub in enumerate(subtitles, start=1):
        flags = []
        if sub.get("hi"):
            flags.append("HI")
        episode_label = "" if is_movie else _format_episode_label(sub)
        if episode_label:
            flags.append(episode_label)
        flag_text = f" [{', '.join(flags)}]" if flags else ""

        print(f"{index:>3}. [{_get_language_label(sub)}] {_get_release_label(sub)}{flag_text}")
        print(
            f"       file={_format_value(sub.get('name'))} | by {_format_value(sub.get('author'))} | "
            f"score={_format_value(sub.get('match_score'))} | fps={_format_value(sub.get('fps'))}"
        )
        page_url = _build_subtitle_page_url(sub)
        if page_url:
            print(f"       page: {page_url}")
    print("-" * 80)


# ============================================================
# SUBTITLE FIELD HELPERS
# The v2 docs do not show the subtitle entry shape for
# /subtitles/search, so every access is defensive.
# Enable debug_raw_response to see the real field names.
# ============================================================

def _get_language_label(sub: dict) -> str:
    return str(sub.get("lang") or sub.get("language") or "??")


def _get_release_label(sub: dict) -> str:
    return str(sub.get("release_name") or sub.get("name") or "unnamed")


def _resolve_n_id(sub: dict) -> str:
    """Return the subtitle nId used by /subtitles/{nId}/download, or '' if absent.

    Uses an explicit n_id field when present, otherwise derives it from
    'subtitlePage' ("/s/info/{nId}").
    """
    for key in N_ID_KEYS:
        value = sub.get(key)
        if value:
            return str(value)

    match = SUBTITLE_PAGE_PATTERN.fullmatch(str(sub.get("subtitlePage") or ""))
    return match.group(1) if match else ""


def _build_legacy_download_url(sub: dict) -> str:
    """Fallback: build a dl.subdl.com URL from the entry's relative 'url' field."""
    path = str(sub.get("url") or "")
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return f"{LEGACY_DOWNLOAD_BASE_URL}/{path.lstrip('/')}"


# ============================================================
# SELECTION
# ============================================================

def _parse_selection(selection: str, total: int) -> list[int]:
    """Convert '1,3', '2-4' or 'all' into sorted zero-based indices."""
    if selection.strip().lower() == "all":
        return list(range(total))

    indices = set()
    for part in selection.replace(" ", "").split(","):
        if not part:
            continue
        try:
            if "-" in part:
                start, end = (int(x) for x in part.split("-", 1))
                indices.update(range(start, end + 1))
            else:
                indices.add(int(part))
        except ValueError:
            log(f"Ignoring invalid selection token: '{part}'", "WARNING")

    return sorted(i - 1 for i in indices if 1 <= i <= total)


# ============================================================
# DOWNLOAD
# ============================================================

def _sanitize_filename(name: str, max_length: int = 120) -> str:
    """Make a filesystem-friendly lowercase name."""
    sanitized = name.lower().strip()
    sanitized = re.sub(r"[^\w\s-]", "_", sanitized)
    sanitized = re.sub(r"[\s-]+", "_", sanitized)
    sanitized = re.sub(r"_{2,}", "_", sanitized).strip("_")
    return sanitized[:max_length].rstrip("_") or "subtitle"


def _build_base_name(sub: dict) -> str:
    """Build '<release>_<lang>' used for output filenames."""
    release = _sanitize_filename(_get_release_label(sub))
    language = _sanitize_filename(_get_language_label(sub), max_length=20)
    return f"{release}_{language}"


def _guess_extension(response: requests.Response) -> str:
    """Take the subtitle extension from Content-Disposition, defaulting to .srt."""
    disposition = response.headers.get("content-disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition, flags=re.IGNORECASE)
    if match:
        extension = os.path.splitext(match.group(1))[1].lower()
        if extension in SUBTITLE_EXTENSIONS:
            return extension
    return DEFAULT_SUBTITLE_EXTENSION


def _fetch_download(url: str, api_key: str, params: dict | None = None) -> tuple[bytes, str] | None:
    """Download raw bytes. Returns (content, extension) or None on failure."""
    response = _request_with_retry(url, api_key, params=params)
    if response is None:
        return None

    if "application/json" in response.headers.get("content-type", "").lower():
        # A JSON body here is an error/info payload, not a subtitle file.
        log(f"Expected a file but got JSON: {response.text[:200]}", "ERROR")
        return None

    return response.content, _guess_extension(response)


def _write_file(content: bytes, target: str) -> str:
    if os.path.exists(target):
        log(f"Overwriting existing file: {target}", "WARNING")
    with open(target, "wb") as f:
        f.write(content)
    log(f"Saved: {target}", "SUCCESS")
    return target


def _extract_subtitle_files(content: bytes, out_dir: str, base_name: str) -> list[str]:
    """Extract subtitle files from ZIP bytes into out_dir.

    Output names are generated from base_name, never taken from the
    archive's member names (avoids path traversal from untrusted ZIPs).
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        log("Downloaded file is not a valid ZIP.", "ERROR")
        return []

    members = [name for name in archive.namelist() if name.lower().endswith(SUBTITLE_EXTENSIONS)]
    if not members:
        log("ZIP contains no subtitle files.", "WARNING")
        return []

    saved = []
    for number, member in enumerate(members, start=1):
        extension = os.path.splitext(member)[1].lower()
        suffix = "" if len(members) == 1 else f"_{number:02d}"
        target = os.path.join(out_dir, f"{base_name}{suffix}{extension}")
        saved.append(_write_file(archive.read(member), target))

    return saved


def _save_download(content: bytes, extension: str, out_dir: str, base_name: str, extract: bool) -> list[str]:
    """Save downloaded bytes: extract/keep a ZIP, or write a single subtitle file."""
    os.makedirs(out_dir, exist_ok=True)

    if zipfile.is_zipfile(io.BytesIO(content)):
        if extract:
            return _extract_subtitle_files(content, out_dir, base_name)
        return [_write_file(content, os.path.join(out_dir, f"{base_name}.zip"))]

    return [_write_file(content, os.path.join(out_dir, f"{base_name}{extension}"))]


def _download_by_n_id(n_id: str, api_key: str, preferred_format: str) -> tuple[bytes, str] | None:
    """Download via /subtitles/{nId}/download. 'file' falls back to 'zip' if it fails."""
    formats = ["file", "zip"] if preferred_format == "file" else ["zip"]

    for fmt in formats:
        log(f"Downloading nId={n_id} (format={fmt})")
        result = _fetch_download(
            f"{API_BASE_URL}/api/v2/subtitles/{n_id}/download", api_key, params={"format": fmt}
        )
        if result is not None:
            return result
        if fmt == "file":
            log("format=file failed, retrying as zip...", "WARNING")

    return None


def download_subtitle(sub: dict, api_key: str, options: DownloadOptions) -> list[str]:
    """Download one subtitle entry. Returns the list of saved file paths.

    Tries the documented v2 endpoint by nId first, then falls back to the
    legacy 'url' from the search result if that fails or no nId is known.
    """
    n_id = _resolve_n_id(sub)
    result = _download_by_n_id(n_id, api_key, options.format) if n_id else None

    if result is None:
        legacy_url = _build_legacy_download_url(sub)
        if not legacy_url:
            log(f"No usable nId or url in entry (keys: {sorted(sub.keys())}), skipping.", "ERROR")
            return []

        reason = "nId download failed" if n_id else "no nId in entry"
        log(f"{reason}, using legacy URL: {_mask_api_keys(legacy_url)}", "WARNING")
        result = _fetch_download(legacy_url, api_key)

    if result is None:
        return []

    content, extension = result
    return _save_download(content, extension, options.output_dir, _build_base_name(sub), options.extract_zip)


# ============================================================
# SUBTITLE PREVIEW
# ============================================================

def _decode_subtitle_bytes(raw: bytes) -> str:
    """Decode subtitle bytes: UTF-16 by BOM, then UTF-8, then Windows-1252 as a last resort."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _read_subtitle_text(path: str) -> str | None:
    """Read a subtitle file as text. Returns None (after a warning) if it cannot be read."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        log(f"Cannot read {path} for preview: {e}", "WARNING")
        return None
    return _decode_subtitle_bytes(raw)


def _extract_block_cues(text: str) -> list[str]:
    """Split SRT/VTT text into cue blocks, skipping headers and notes (blocks without '-->')."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = [block.strip("\n") for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    return [
        block for block in blocks
        if "-->" in block and not block.lstrip().upper().startswith("NOTE")
    ]


def _extract_ass_cues(text: str) -> list[str]:
    """Collect 'Dialogue:' lines of an ASS/SSA file as 'start --> end' + plain text blocks."""
    start_index, end_index, text_index, field_count = 1, 2, 9, 10  # default [Events] layout
    in_events = False
    cues = []

    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()

        if lowered == "[events]":
            in_events = True
            continue
        if stripped.startswith("["):
            in_events = False
            continue
        if not in_events:
            continue

        if lowered.startswith("format:"):
            fields = [name.strip().lower() for name in stripped.split(":", 1)[1].split(",")]
            if {"start", "end", "text"} <= set(fields):
                start_index = fields.index("start")
                end_index = fields.index("end")
                text_index = fields.index("text")
                field_count = len(fields)
            continue

        if lowered.startswith("dialogue:"):
            parts = stripped.split(":", 1)[1].lstrip().split(",", field_count - 1)
            if len(parts) < field_count:
                continue
            body = ASS_OVERRIDE_TAG_PATTERN.sub("", parts[text_index])
            body = body.replace("\\N", "\n").replace("\\n", "\n")
            cues.append(f"{parts[start_index].strip()} --> {parts[end_index].strip()}\n{body}")

    return cues


def _extract_cues(text: str, extension: str) -> list[str]:
    """Return the subtitle cues of a file, using the parser that matches its extension."""
    if extension in (".ass", ".ssa"):
        return _extract_ass_cues(text)
    if extension == ".sub":
        # MicroDVD: one cue per line, e.g. '{start}{end}text'.
        return [line for line in text.splitlines() if line.strip()]
    return _extract_block_cues(text)


def _shorten_line(line: str) -> str:
    if len(line) <= PREVIEW_MAX_LINE_LENGTH:
        return line
    return line[:PREVIEW_MAX_LINE_LENGTH - 3] + "..."


def _print_subtitle_preview(path: str, max_blocks: int = PREVIEW_BLOCK_COUNT) -> None:
    """Print the first subtitle blocks of a saved file. Skips non-subtitle extensions (e.g. .zip)."""
    extension = os.path.splitext(path)[1].lower()
    if extension not in SUBTITLE_EXTENSIONS:
        return

    text = _read_subtitle_text(path)
    if text is None:
        return

    name = os.path.basename(path)
    if extension == ".sub" and "\x00" in text:
        log(f"Preview skipped (binary subtitle): {name}", "WARNING")
        return

    cues = _extract_cues(text, extension)
    if not cues:
        # Typical for archives that only hold a README/notes file instead of real subtitles.
        log(f"No subtitle blocks found in {name}; it may not be a real subtitle file.", "WARNING")
        for line in [line for line in text.splitlines() if line.strip()][:3]:
            print(f"       {_shorten_line(line.strip())}")
        return

    shown = cues[:max_blocks]
    log(f"Preview of {name} (first {len(shown)} of {len(cues)} blocks):")
    print("-" * 80)
    print("\n\n".join(
        "\n".join(_shorten_line(line) for line in cue.splitlines())
        for cue in shown
    ))
    print("-" * 80)


def _download_selected(subtitles: list[dict], api_key: str, options: DownloadOptions) -> None:
    """Download every subtitle chosen by options.selection and print a summary."""
    indices = _parse_selection(options.selection, len(subtitles))
    if not indices:
        log(f"No valid rows in selection '{options.selection}'.", "ERROR")
        return

    all_saved = []
    failed = 0
    for position, index in enumerate(indices, start=1):
        log(f"--- [{position}/{len(indices)}] Row {index + 1} ---")
        saved = download_subtitle(subtitles[index], api_key, options)
        if saved:
            all_saved.extend(saved)
            if options.show_preview:
                for saved_path in saved:
                    _print_subtitle_preview(saved_path)
        else:
            failed += 1

    log(
        f"Done. Files saved: {len(all_saved)} | Failed rows: {failed}",
        "SUCCESS" if not failed else "WARNING",
    )
    log(f"Output folder: {options.output_dir}")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Application entry point."""
    config = _create_app_config()

    api_key = _get_api_key()
    if not api_key:
        return

    if config.show_usage:
        _print_account_usage(api_key)

    data = search_subtitles(api_key, config.query)
    if data is None:
        return

    subtitles = data.get("subtitles") or []

    if config.debug_raw_response:
        log(f"Response keys: {sorted(data.keys())}", "DEBUG")
        if subtitles:
            log(f"Raw first subtitle entry: {_mask_api_keys(str(subtitles[0]))}", "DEBUG")

    if config.show_full_json_response:
        _print_full_json_response(data)

    _print_search_results(data)

    if not config.download.enabled:
        log("mode = search_only. Set mode = 'download' to fetch files.")
        return

    if not subtitles:
        return

    _download_selected(subtitles, api_key, config.download)

    if config.show_usage:
        _print_account_usage(api_key)


if __name__ == "__main__":
    main()
