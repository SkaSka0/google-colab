# Telegram-Leecher — Development Roadmap

This roadmap outlines the recommended development direction for the codebase,
prioritized by **risk vs. effort**. Several existing issues can silently
corrupt or lose user data, so they take priority over new features or
cosmetic fixes.

---

## Phase 0 — Documentation Sync (Quick Win, ~1 day)

The README is currently **out of sync** with the actual code:

- The "Supported Links" section still marks `Mega.nz Link ❌ Coming Soon`
  and `GDTot, Sharer and Short Links ❌ Coming Soon`, even though `mega.py`
  and `terabox.py` are already implemented and routed from `manager.py`.
- Terabox is not mentioned anywhere in the README despite having its own
  module.

**Action items:**
- Update the "Supported Links" table — mark Mega.nz and Terabox as ✅.
- Re-check "Codebase Structure" whenever a new module is added, per the
  project's own README style guide.

This is low-cost but important — inaccurate documentation confuses new
contributors and users alike.

---

## Phase 1 — High-Priority Bug Fixes (Data & Reliability Risk)

This should be tackled **before any new feature work**, since these issues
can corrupt or silently drop download/upload results.

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | `open(file_name, "ab")` is used without deleting a pre-existing file first | `gdrive.py` → `gDownloadFile` | If a Google Drive task is retried with the same filename, old bytes accumulate on top of new ones → corrupted file |
| 2 | `cancelTask()` calls `BOT.TASK.cancel()` *before* deleting the status message and sending the failure notification | `handler.py` → `cancelTask` | Since `BOT.TASK` is almost always the very coroutine `cancelTask()` is running inside of (called deep in the leech call stack), cancelling it early injects a `CancelledError` at the next `await` checkpoint — aborting cleanup and the user-facing notification before they run. The failure is invisible until the Colab cell is manually interrupted, at which point an unrelated-looking `asyncio.exceptions.CancelledError` traceback surfaces. This blocks reliable testing of *any* other fix that relies on `cancelTask()` reporting failures to the user (e.g. Issue #3 below) |
| 3 | `token.pickle` is never refreshed when expired | `gdrive.py` → `build_service` | The bot fails completely with an unclear error once the token expires; the user must manually regenerate it. **Note:** verifying the failure-path behavior of this fix (expired file / revoked refresh token / missing file) depends on Issue #2 being fixed first, since those paths all report through `cancelTask()` |
| 4 | `ProcessPoolExecutor()` is instantiated but never used (dead code) | `manager.py` → `downloadManager` (Mega branch) | Minor resource leak; signals an unfinished Mega refactor |
| 5 | Google Docs/Sheets shortcuts inside a folder are not filtered out before calling `gDownloadFile` | `gdrive.py` → `gDownloadFolder` | A folder leech can silently fail mid-process with no clear message to the user |
| 6 | Many `except Exception: pass` / bare `logging.error` blocks with no propagation | `helper.py`, `handler.py`, etc. | A task can hang or "complete" while files are actually missing, with no notification to the user |

**Why this comes first:** these bugs undermine trust in the transfer
result itself — a silently corrupted or silently failed file is far more
costly to discover (and fix) after the fact than a UI bug. Fixing these
before anything else protects the core value proposition of the bot.

**Why Issue #2 was inserted ahead of Issue #3:** Issue #2 was discovered
while manually testing the Issue #3 fix (`token.pickle` refresh) — the
failure-path scenarios for #3 (expired token with an invalid refresh
token, an outdated token format, a missing token file) all route through
`cancelTask()`, so they couldn't be reliably confirmed until the
self-cancellation bug in `cancelTask()` itself was resolved. See
[`TESTING.md`](./TESTING.md) → Phase 1, Item 2 for the scenarios and
results that led to this discovery.

---

## Phase 2 — Structural Refactor (Medium, ~1–2 weeks)

Once critical bugs are resolved, move on to code quality:

1. **Global state management** (`variables.py` as class-based namespaces)
   currently limits the bot to handling **one task at a time**, and makes
   testing difficult since most functions depend on global state accessed
   via `global`. This isn't a bug per se — the bot is designed as
   single-owner — but it constrains future multi-task support. Only
   invest here if multi-task handling is actually on the roadmap.
2. **Split large functions** — per the project's own style guide, several
   functions violate single-responsibility:
   - `Leech()` in `handler.py` (100+ lines: handles conversion, size
     checking, splitting, uploading, and cleanup all at once)
   - `taskScheduler()` in `task_manager.py`
   - `YouTubeDL()` in `ytdl.py` (nested function + threading + hooks)
3. **Standardize error handling** — define a clear pattern for when to
   call `cancelTask()`, when to just log, and when to retry. Currently
   these are mixed with no consistent rule.
4. **Simplify `get_Aria2c_Name`** — it currently invokes `aria2c` twice
   (a dry run to get the filename, then a real run to download). This
   could be replaced with a direct HTTP `HEAD` request to resolve the
   filename, which is faster and avoids the duplicate process.

---

## Phase 3 — Reliability & Observability (Medium–Long Term)

- **Consistent retry mechanism** for network-dependent downloaders
  (Google Drive, Terabox, aria2) — each module currently has a different
  (or nonexistent) retry approach.
- **Basic test coverage**, starting with pure functions in `helper.py`
  (`sizeUnit`, `getTime`, `speedETA`, `getIDFromURL`) that don't require
  mocking Pyrogram or the Colab environment.
- **Structured logging** — the codebase currently mixes `print()` and
  `logging` calls; standardize on `logging` only (leftover `print()`
  calls remain in `handler.py` and `manager.py`).

---

## Phase 4 — New Features (After the Foundation Is Stable)

Only once the above phases are complete does it make sense to add:

- A GDTot/Sharer/short-link resolver (already listed as "Coming Soon" in
  the README, but no module exists yet).
- Automatic Google Drive token refresh (builds on the Phase 1 fix, but as
  a proper feature rather than a patch).
- More robust progress parsing for Mega — the current regex-based parsing
  in `mega.py` is fragile against changes in `megadl`'s output format.

---

## Summary of Priorities

**Recommended starting point: Phase 0 → Phase 1.**

The issues listed in Phase 1 are not "minor" — items #1 and #5 in
particular can silently corrupt or drop user data, which places them
above any new feature work. Item #2 (`cancelTask()` self-cancellation)
was elevated ahead of item #3 (`token.pickle` refresh) specifically
because #3's failure-path testing depends on #2 being fixed first —
sequencing matters here, not just severity. Phase 2 (refactoring) should
only begin once the core reliability issues are resolved, so structural
changes aren't built on top of a still-buggy foundation.
