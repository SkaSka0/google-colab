#@title 🔎 Search & Download Subtitle (SubSource API)
#@markdown - Searches **subsource.net** in two steps: find the movie/series → list its subtitles → download the ones you pick.
#@markdown - Subtitles are always delivered as a ZIP, which is extracted into subtitle files.
#@markdown - Default output folder matches `subtitle_input` in `mux_subtitle_into_video_enhanced.py`.
#@markdown
#@markdown ## 🔐 API Key from Colab Secrets
#@markdown 1. Open the left panel in Colab → 🔑 **Secrets**
#@markdown 2. Click **Add new secret**
#@markdown 3. Name: `SUBSOURCE_API_KEY`
#@markdown 4. Value: the key from the API tab of your SubSource account dashboard
#@markdown 5. Save and enable notebook access
#@markdown
#@markdown Free plan limits: 60 requests/minute, 1,800/hour, 7,200/day.

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
#@markdown ### 🎬 Step 1 — Find the movie / series
#@markdown Already know the ID? Fill `movie_id` and the search below is skipped.
movie_id = ""  #@param {type:"string"}
search_type = "text"  #@param ["text", "imdb"]
#@markdown `text` search uses `query`; `imdb` search uses `imdb` (an ID like tt1234567, or a full IMDb URL).
query = ""  #@param {type:"string"}
imdb = ""  #@param {type:"string"}
year = ""  #@param {type:"string"}
content_type = "all"  #@param ["all", "movie", "series"]
#@markdown For series, each season has its own movie ID.
season = ""  #@param {type:"string"}
#@markdown Row number from the movie table to use for step 2.
movie_selection = 1  #@param {type:"integer", min:1}

#@markdown ---
#@markdown ### 📄 Step 2 — List subtitles
#@markdown SubSource uses full language **names**, not codes (e.g. `indonesian`, `english`).
language = "indonesian"  #@param ["english", "indonesian", "malay", "spanish", "arabic", "french", "german", "portuguese", "chinese", "japanese", "korean"] {allow-input: true}
sort = "popular"  #@param ["newest", "oldest", "popular", "rating"]
#@markdown Exact release info string, e.g. `BluRay 1080p`. Leave empty for no filter.
release_info = ""  #@param {type:"string"}
hearing_impaired = "any"  #@param ["any", "only", "exclude"]
limit = 20  #@param {type:"integer", min:1, max:100}
page = 1  #@param {type:"integer", min:1}

#@markdown ---
#@markdown ### ⬇️ Step 3 — Download
mode = "search_only"  #@param ["search_only", "download"]
#@markdown Row numbers from the subtitle table: `1`, `1,3`, `2-4`, or `all`
download_selection = "1"  #@param {type:"string"}
output_dir = "/content/media_toolkit/subtitle"  #@param {type:"string"}
extract_zip = True  #@param {type:"boolean"}
#@markdown Print the first 5 blocks of each saved subtitle file (.srt, .vtt, .ass, ...).
show_preview = True  #@param {type:"boolean"}

#@markdown ---
#@markdown Print the complete JSON returned by the movie and subtitle searches.
show_full_json_response = False  #@param {type:"boolean"}
debug_raw_response = False  #@param {type:"boolean"}

# ============================================================
# CONSTANTS
# ============================================================

APPNAME = "SubsourceClient"

API_BASE_URL = "https://api.subsource.net/api/v1"
API_KEY_SECRET_NAME = "SUBSOURCE_API_KEY"

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 15
MAX_RETRY_AFTER_SECONDS = 120
# 429 = rate limited, 5xx = temporary server problem. Everything else is not retried.
RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)
# Free plan allows 60 requests/minute, so pause briefly between downloads.
DOWNLOAD_DELAY_SECONDS = 1.1

SUBTITLE_EXTENSIONS = (".srt", ".vtt", ".ass", ".ssa", ".sub")
DEFAULT_SUBTITLE_EXTENSION = ".srt"
PREVIEW_BLOCK_COUNT = 5
PREVIEW_MAX_LINE_LENGTH = 100
ASS_OVERRIDE_TAG_PATTERN = re.compile(r"\{[^}]*\}")


# ============================================================
# CONFIGURATION (dataclasses)
# ============================================================

@dataclass
class MovieQuery:
    movie_id: str = ""
    search_type: str = "text"
    query: str = ""
    imdb: str = ""
    year: str = ""
    content_type: str = "all"
    season: str = ""
    selection: int = 1


@dataclass
class SubtitleQuery:
    language: str = ""
    sort: str = "popular"
    release_info: str = ""
    hearing_impaired: str = "any"
    limit: int = 20
    page: int = 1


@dataclass
class DownloadOptions:
    enabled: bool = False
    selection: str = "1"
    output_dir: str = ""
    extract_zip: bool = True
    show_preview: bool = True


@dataclass
class AppConfig:
    movie: MovieQuery
    subtitles: SubtitleQuery
    download: DownloadOptions
    show_full_json_response: bool = False
    debug_raw_response: bool = False


def _create_app_config() -> AppConfig:
    """Build a fresh AppConfig from the current Colab form values.

    Always constructs a new object because a Colab cell can be re-run
    inside the same kernel session.
    """
    return AppConfig(
        movie=MovieQuery(
            movie_id=movie_id.strip(),
            search_type=search_type,
            query=query.strip(),
            imdb=imdb.strip(),
            year=year.strip(),
            content_type=content_type,
            season=season.strip(),
            selection=movie_selection,
        ),
        subtitles=SubtitleQuery(
            language=language.strip().lower(),
            sort=sort,
            release_info=release_info.strip(),
            hearing_impaired=hearing_impaired,
            limit=limit,
            page=page,
        ),
        download=DownloadOptions(
            enabled=(mode == "download"),
            selection=download_selection.strip(),
            output_dir=output_dir,
            extract_zip=extract_zip,
            show_preview=show_preview,
        ),
        show_full_json_response=show_full_json_response,
        debug_raw_response=debug_raw_response,
    )


# ============================================================
# LOGGING
# ============================================================

def log(message: str, level: str = "INFO") -> None:
    """Print a formatted log message."""
    print(f"{level}:{APPNAME}:{message}", flush=True)


# ============================================================
# HTTP HELPERS
# ============================================================

def _get_api_key() -> str:
    """Read the SubSource API key from Colab Secrets. Returns '' if unavailable."""
    try:
        return userdata.get(API_KEY_SECRET_NAME) or ""
    except userdata.SecretNotFoundError:
        log(f"Secret '{API_KEY_SECRET_NAME}' not found in Colab Secrets!", "ERROR")
    except userdata.NotebookAccessError:
        log(f"Notebook access to secret '{API_KEY_SECRET_NAME}' is not enabled!", "ERROR")
    return ""


def _auth_headers(api_key: str) -> dict:
    return {"X-API-Key": api_key}


def _extract_error_message(response: requests.Response) -> str:
    """Best-effort error text. The docs do not define an error body shape."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]

    if isinstance(body, dict):
        error = body.get("error") or body.get("message")
        if error:
            return str(error)[:200]
    return response.text[:200]


def _describe_rate_limit(response: requests.Response) -> str:
    """Summarize rate-limit related headers (names are not documented exactly)."""
    parts = [
        f"{name}={value}"
        for name, value in response.headers.items()
        if name.lower().startswith("x-ratelimit") or name.lower() == "retry-after"
    ]
    return ", ".join(parts)


def _get_retry_wait_seconds(response: requests.Response) -> float:
    """Honor a numeric Retry-After header (capped), else use the default wait."""
    retry_after = response.headers.get("retry-after", "")
    if retry_after.isdigit():
        return min(int(retry_after), MAX_RETRY_AFTER_SECONDS)
    return RETRY_WAIT_SECONDS


def _request_with_retry(path: str, api_key: str, params: dict | None = None) -> requests.Response | None:
    """GET an API path with bounded retries on rate-limit/server errors only.

    Returns the response on success (HTTP 2xx), or None on a fatal or
    exhausted-retry failure. The caller decides what to do next.
    """
    url = f"{API_BASE_URL}{path}"

    for attempt in range(1, MAX_RETRIES + 1):
        wait_seconds = RETRY_WAIT_SECONDS
        try:
            response = requests.get(
                url, params=params, headers=_auth_headers(api_key), timeout=REQUEST_TIMEOUT
            )
        except (requests.Timeout, requests.ConnectionError) as e:
            log(f"Network error (attempt {attempt}/{MAX_RETRIES}): {e}", "WARNING")
        else:
            if response.ok:
                return response

            detail = f"HTTP {response.status_code}: {_extract_error_message(response)}"
            if response.status_code == 429:
                detail += f" [{_describe_rate_limit(response)}]"

            if response.status_code not in RETRYABLE_STATUS_CODES:
                log(detail, "ERROR")
                return None

            wait_seconds = _get_retry_wait_seconds(response)
            log(f"{detail} (attempt {attempt}/{MAX_RETRIES})", "WARNING")

        if attempt < MAX_RETRIES:
            log(f"Waiting {wait_seconds:.0f}s before retrying...", "WARNING")
            time.sleep(wait_seconds)

    log("Request failed after all retries.", "ERROR")
    return None


def _get_json(path: str, api_key: str, params: dict | None = None) -> dict | None:
    """GET an API path and return parsed JSON, or None on failure."""
    response = _request_with_retry(path, api_key, params=params)
    if response is None:
        return None

    try:
        data = response.json()
    except ValueError:
        log("Response is not valid JSON.", "ERROR")
        return None

    if isinstance(data, dict) and data.get("success") is False:
        log(f"API reported failure: {_extract_error_message(response)}", "ERROR")
        return None

    return data


def _print_full_json_response(title: str, data: dict) -> None:
    """Pretty-print a complete response JSON."""
    print("=" * 80)
    print(f"FULL RESPONSE: {title}")
    print("=" * 80)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("=" * 80)


# ============================================================
# STEP 1: FIND THE MOVIE / SERIES
# ============================================================

def _is_digits_or_empty(name: str, value: str) -> bool:
    """Validate that an optional numeric form field is empty or all digits."""
    if value and not value.isdigit():
        log(f"{name} must be a number, got '{value}'.", "ERROR")
        return False
    return True


def _build_movie_search_params(movie: MovieQuery) -> dict | None:
    """Build GET params for /movies/search. Returns None if the input is invalid."""
    if movie.search_type == "text" and not movie.query:
        log("Text search: fill 'query'.", "ERROR")
        return None
    if movie.search_type == "imdb" and not movie.imdb:
        log("IMDb search: fill 'imdb'.", "ERROR")
        return None
    if not (_is_digits_or_empty("year", movie.year) and _is_digits_or_empty("season", movie.season)):
        return None

    params = {
        "searchType": movie.search_type,
        "q": movie.query if movie.search_type == "text" else "",
        "imdb": movie.imdb if movie.search_type == "imdb" else "",
        "year": movie.year,
        "type": "" if movie.content_type == "all" else movie.content_type,
        "season": movie.season,
    }
    return {key: value for key, value in params.items() if value != ""}


def search_movies(api_key: str, movie: MovieQuery, show_full_json: bool) -> list[dict] | None:
    """Search movies/series. Returns the list of matches, or None on failure."""
    params = _build_movie_search_params(movie)
    if params is None:
        return None

    log(f"GET /movies/search {params}")
    data = _get_json("/movies/search", api_key, params=params)
    if data is None:
        return None

    if show_full_json:
        _print_full_json_response("/movies/search", data)

    return data.get("data") or []


def get_movie_by_id(api_key: str, movie_id: str, show_full_json: bool) -> dict | None:
    """Fetch one movie/series by ID. Returns its data dict, or None on failure."""
    log(f"GET /movies/{movie_id}")
    data = _get_json(f"/movies/{movie_id}", api_key)
    if data is None:
        return None

    if show_full_json:
        _print_full_json_response(f"/movies/{movie_id}", data)

    return data.get("data")


def _print_movie_table(movies: list[dict]) -> None:
    """Print a numbered table of matched movies/series."""
    log(f"Matched titles: {len(movies)}")
    print("-" * 80)
    for index, movie in enumerate(movies, start=1):
        season_text = f" S{movie['season']}" if movie.get("season") is not None else ""
        print(
            f"{index:>3}. {movie.get('title')}{season_text} ({movie.get('releaseYear')}) "
            f"[{movie.get('type')}] subs={movie.get('subtitleCount')} "
            f"movieId={movie.get('movieId')} imdb={movie.get('imdbId')}"
        )
    print("-" * 80)


def _resolve_movie(api_key: str, config: AppConfig) -> tuple[str, str] | None:
    """Resolve (movie_id, title) from a direct ID or via search. None if not resolvable."""
    movie = config.movie

    if movie.movie_id:
        if not _is_digits_or_empty("movie_id", movie.movie_id):
            return None
        details = get_movie_by_id(api_key, movie.movie_id, config.show_full_json_response)
        title = (details or {}).get("title") or f"movie_{movie.movie_id}"
        return movie.movie_id, str(title)

    movies = search_movies(api_key, movie, config.show_full_json_response)
    if movies is None:
        return None
    if not movies:
        log("No movies/series found.", "WARNING")
        return None

    _print_movie_table(movies)

    if not 1 <= movie.selection <= len(movies):
        log(f"movie_selection {movie.selection} is out of range (1-{len(movies)}).", "ERROR")
        return None

    chosen = movies[movie.selection - 1]
    log(f"Using row {movie.selection}: {chosen.get('title')} (movieId={chosen.get('movieId')})")
    return str(chosen.get("movieId")), str(chosen.get("title") or "")


# ============================================================
# STEP 2: LIST SUBTITLES
# ============================================================

def _build_subtitle_params(movie_id: str, query: SubtitleQuery) -> dict:
    """Build GET params for /subtitles, skipping empty optional fields."""
    params = {
        "movieId": movie_id,
        "language": query.language,
        "releaseInfo": query.release_info,
        "sort": query.sort,
        "limit": query.limit,
        "page": query.page,
    }
    if query.hearing_impaired == "only":
        params["hearingImpaired"] = "true"
    elif query.hearing_impaired == "exclude":
        params["hearingImpaired"] = "false"

    return {key: value for key, value in params.items() if value not in ("", None)}


def search_subtitles(api_key: str, movie_id: str, query: SubtitleQuery, show_full_json: bool) -> dict | None:
    """List subtitles for a movie. Returns the parsed JSON, or None on failure."""
    params = _build_subtitle_params(movie_id, query)

    log(f"GET /subtitles {params}")
    data = _get_json("/subtitles", api_key, params=params)
    if data is None:
        return None

    if show_full_json:
        _print_full_json_response("/subtitles", data)

    return data


def _get_release_label(sub: dict) -> str:
    release_info = sub.get("releaseInfo")
    if isinstance(release_info, list):
        return " ".join(str(item) for item in release_info) or "unnamed"
    return str(release_info or "unnamed")


MISSING_VALUE_TEXT = "?"
MAX_COMMENTARY_LENGTH = 150


def _format_value(value: object) -> str:
    """Show '?' for values the API returned as null/empty (common for old Subscene imports)."""
    if value is None or value == "":
        return MISSING_VALUE_TEXT
    return str(value)


def _format_size_kb(size_bytes: int | None) -> str:
    if size_bytes is None:
        return MISSING_VALUE_TEXT
    return f"{size_bytes / 1024:.0f}KB"


def _format_rating(rating: dict | None) -> str:
    if not rating:
        return MISSING_VALUE_TEXT
    return f"{rating.get('good', 0)}/{rating.get('total', 0)}"


def _format_uploaders(sub: dict) -> str:
    """Join contributor display names; the first one is normally the uploader."""
    names = [
        str(person.get("displayname"))
        for person in (sub.get("contributors") or [])
        if person.get("displayname")
    ]
    return ", ".join(names) if names else MISSING_VALUE_TEXT


def _format_date(created_at: str | None) -> str:
    """Keep only the YYYY-MM-DD part of an ISO timestamp."""
    return created_at[:10] if created_at else MISSING_VALUE_TEXT


def _clean_commentary(commentary: str | None) -> str:
    """Collapse whitespace/newlines and truncate the uploader's note. '' if none."""
    if not commentary:
        return ""
    text = " ".join(commentary.split())
    if len(text) > MAX_COMMENTARY_LENGTH:
        text = text[:MAX_COMMENTARY_LENGTH - 3].rstrip() + "..."
    return text


def _print_subtitle_table(data: dict) -> list[dict]:
    """Print the numbered subtitle table and return the subtitle list."""
    subtitles = data.get("data") or []
    pagination = data.get("pagination") or {}

    if not subtitles:
        log("No subtitles found. Try removing filters (release_info, hearing_impaired).", "WARNING")
        return []

    log(
        f"Subtitles on this page: {len(subtitles)} | page {pagination.get('page', '?')}"
        f"/{pagination.get('pages', '?')} | total {pagination.get('total', '?')}"
    )
    print("-" * 80)
    for index, sub in enumerate(subtitles, start=1):
        flags = []
        if sub.get("hearingImpaired"):
            flags.append("HI")
        if sub.get("foreignParts"):
            flags.append("FOREIGN-PARTS")
        flag_text = f" [{', '.join(flags)}]" if flags else ""

        print(f"{index:>3}. [{sub.get('language')}] {_get_release_label(sub)}{flag_text}")
        print(
            f"       id={sub.get('subtitleId')} | files={_format_value(sub.get('files'))} | "
            f"{_format_size_kb(sub.get('size'))} | downloads={_format_value(sub.get('downloads'))} | "
            f"rating={_format_rating(sub.get('rating'))} | comments={_format_value(sub.get('comments'))}"
        )
        print(
            f"       by {_format_uploaders(sub)} | {_format_date(sub.get('createdAt'))} | "
            f"type={_format_value(sub.get('productionType'))}/{_format_value(sub.get('releaseType'))} | "
            f"fps={_format_value(sub.get('framerate'))}"
        )

        note = _clean_commentary(sub.get("commentary"))
        if note:
            print(f"       note: {note}")
    print("-" * 80)

    return subtitles


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
# STEP 3: DOWNLOAD
# ============================================================

def _sanitize_filename(name: str, max_length: int = 100) -> str:
    """Make a filesystem-friendly lowercase name."""
    sanitized = name.lower().strip()
    sanitized = re.sub(r"[^\w\s-]", "_", sanitized)
    sanitized = re.sub(r"[\s-]+", "_", sanitized)
    sanitized = re.sub(r"_{2,}", "_", sanitized).strip("_")
    return sanitized[:max_length].rstrip("_") or "subtitle"


def _build_base_name(movie_title: str, sub: dict) -> str:
    """Build '<title>_<release>_<language>_<subtitleId>'; the ID keeps names unique."""
    readable = _sanitize_filename(f"{movie_title} {_get_release_label(sub)}")
    language = _sanitize_filename(str(sub.get("language") or "xx"), max_length=20)
    return f"{readable}_{language}_{sub.get('subtitleId')}"


def _guess_extension(response: requests.Response) -> str:
    """Take the subtitle extension from Content-Disposition, defaulting to .srt."""
    disposition = response.headers.get("content-disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition, flags=re.IGNORECASE)
    if match:
        extension = os.path.splitext(match.group(1))[1].lower()
        if extension in SUBTITLE_EXTENSIONS:
            return extension
    return DEFAULT_SUBTITLE_EXTENSION


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


def download_subtitle(api_key: str, movie_title: str, sub: dict, options: DownloadOptions) -> list[str]:
    """Download one subtitle. Returns the list of saved file paths."""
    subtitle_id = sub.get("subtitleId")
    if not subtitle_id:
        log(f"Entry has no subtitleId (keys: {sorted(sub.keys())}), skipping.", "ERROR")
        return []

    log(f"Downloading subtitleId={subtitle_id}")
    response = _request_with_retry(f"/subtitles/{subtitle_id}/download", api_key)
    if response is None:
        return []

    if "application/json" in response.headers.get("content-type", "").lower():
        # A JSON body here is an error/info payload, not the ZIP archive.
        log(f"Expected a ZIP but got JSON: {response.text[:200]}", "ERROR")
        return []

    base_name = _build_base_name(movie_title, sub)
    return _save_download(
        response.content, _guess_extension(response), options.output_dir, base_name, options.extract_zip
    )


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


def _download_selected(api_key: str, movie_title: str, subtitles: list[dict], options: DownloadOptions) -> None:
    """Download every subtitle chosen by options.selection and print a summary."""
    indices = _parse_selection(options.selection, len(subtitles))
    if not indices:
        log(f"No valid rows in selection '{options.selection}'.", "ERROR")
        return

    all_saved = []
    failed = 0
    for position, index in enumerate(indices, start=1):
        log(f"--- [{position}/{len(indices)}] Row {index + 1} ---")
        saved = download_subtitle(api_key, movie_title, subtitles[index], options)
        if saved:
            all_saved.extend(saved)
            if options.show_preview:
                for saved_path in saved:
                    _print_subtitle_preview(saved_path)
        else:
            failed += 1

        if position < len(indices):
            time.sleep(DOWNLOAD_DELAY_SECONDS)

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

    resolved = _resolve_movie(api_key, config)
    if resolved is None:
        return
    resolved_id, movie_title = resolved

    data = search_subtitles(api_key, resolved_id, config.subtitles, config.show_full_json_response)
    if data is None:
        return

    if config.debug_raw_response:
        log(f"Response keys: {sorted(data.keys())}", "DEBUG")
        log(f"Filters applied by API: {data.get('filters')}", "DEBUG")

    subtitles = _print_subtitle_table(data)

    if not config.download.enabled:
        log("mode = search_only. Set mode = 'download' to fetch files.")
        return

    if not subtitles:
        return

    _download_selected(api_key, movie_title, subtitles, config.download)


if __name__ == "__main__":
    main()
