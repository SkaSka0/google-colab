# Testing Log

Manual testing notes and progress, tracked separately from
[`PROGRESS.md`](./PROGRESS.md) (task checklist) and
[`ROADMAP.md`](./ROADMAP.md) (reasoning/context).

Use this file to record **what has been tested, what scenario, and the
result** for each item before its checkbox in `PROGRESS.md` is updated.
An item's checkbox may only move to `[TESTED & CONFIRMED]` once every
scenario below for that item is marked `Pass` and the user has
confirmed it.

## Status Legend

- `Not started` — no testing attempted yet
- `In progress` — some scenarios tested, others pending
- `Pass` — scenario behaved as expected, confirmed by user
- `Fail` — scenario did not behave as expected (see Notes)
- `Blocked` — cannot currently be tested (see Notes for reason)

## Testing Order

Test in this order — Phase 1, Item 2 (`cancelTask()`) must be retested
and confirmed **before** resuming Phase 1, Item 3 (`token.pickle`
refresh) Scenarios 3–5, since those scenarios' expected behavior is
reported entirely through `cancelTask()`.

1. Phase 1, Item 2 — `cancelTask()` self-cancellation fix
2. Phase 1, Item 3 — `token.pickle` refresh logic (Scenarios 3–5 retest)

---

## Phase 1, Item 2 — `cancelTask()` self-cancellation bug (`handler.py`)

**Overall status:** In progress — patch written, retest not yet performed.

**Background:** Found while testing Phase 1, Item 3 (`token.pickle`
refresh) Scenarios 3–5 below. `cancelTask()` called `BOT.TASK.cancel()`
before deleting the status message and sending the failure notification.
Since `BOT.TASK` is usually the same coroutine `cancelTask()` runs
inside of, this injected a `CancelledError` at the next `await`
checkpoint, silently aborting the cleanup/notification steps. The
failure was invisible until the Colab cell was manually interrupted,
at which point an unrelated-looking `asyncio.exceptions.CancelledError`
traceback surfaced. See `ROADMAP.md` → Phase 1, Issue #2 for full
reasoning.

**Fix:** moved `BOT.TASK.cancel()` to the last line of `cancelTask()`,
and wrapped the `MSG.status_msg.delete()` / `send_message()` calls in
their own try/except blocks so a failure in one doesn't block the
other.

| # | Scenario | Result | Notes |
|---|----------|--------|-------|
| 1 | Trigger `cancelTask()` via Google Drive refresh_token invalid (re-run Item 3, Scenario 3) | Not started | Confirms `#TASK_STOPPED` message reaches OWNER chat without manually interrupting the cell. |
| 2 | Trigger `cancelTask()` via Google Drive outdated token format (re-run Item 3, Scenario 4) | Not started | Same confirmation as above. |
| 3 | Trigger `cancelTask()` via missing `token.pickle` (re-run Item 3, Scenario 5) | Not started | Same confirmation as above. |
| 4	| Manual "Cancel ❌" button pressed mid-task	| Fail |	FileNotFoundError in Leech() at os.stat(new_path). Root cause is a separate race: cancelTask() runs in a different asyncio Task (the callback handler) than BOT.TASK, so Paths.WORK_PATH gets removed while Leech() is still mid-upload, before BOT.TASK.cancel() is delivered. See "Bugs Found During Testing" below. |
| 5 | Trigger `cancelTask()` from a non-Google-Drive source (e.g. broken Terabox or aria2 link) | Not started | Confirms the fix isn't accidentally scoped only to the Google Drive path. |
| 6 | Confirm `Paths.WORK_PATH` removal still happens in all of the above | Not started | Regression check on the `shutil.rmtree` cleanup step. |

---

## Phase 1, Item 3 — `token.pickle` refresh logic (`gdrive.py` → `build_service`)

**Overall status:** In progress — Scenarios 1–2 passed; Scenarios 3–5 failed
due to the `cancelTask()` bug above (now patched, pending its own retest
first — see Testing Order above).

| # | Scenario | Result | Notes |
|---|----------|--------|-------|
| 1 | Happy path — token valid, not expired | Pass | No refresh log line present, as expected. |
| 2 | Token expired, refresh_token valid | Pass | `"Google Drive token refreshed and saved."` logged; `token.pickle` re-written with new `expiry` confirmed. |
| 3 | Refresh_token revoked/invalid | Fail → Blocked | Expected `cancelTask()` message never reached Telegram; traceback only appeared after manually interrupting the cell. Root cause identified as Phase 1, Item 2 above. **Retest after Item 2 is confirmed.** |
| 4 | `token.pickle` in old (oauth2client) format | Fail → Blocked | Same root cause as Scenario 3. **Retest after Item 2 is confirmed.** |
| 5 | `token.pickle` file missing | Fail → Blocked | Same root cause as Scenario 3. **Retest after Item 2 is confirmed.** |

---

## Phase 1, Item 1 — `gDownloadFile` append bug (`gdrive.py`)

**Overall status:** Not started

_No scenarios logged yet. Suggested scenarios once testing begins:_

| # | Scenario | Result | Notes |
|---|----------|--------|-------|
| 1 | Fresh download, no pre-existing file | Not started | Verify file size / checksum matches source. |
| 2 | Retry with same filename after a partial/interrupted download | Not started | This is the scenario the original bug affected — confirm no byte accumulation (compare final file size/checksum against source, not just "it downloaded"). |

---

## Bugs Found During Testing, Not Yet Promoted

- Use this section as a holding area for bugs discovered while testing an item above but not yet given an official entry in `PROGRESS.md` / `ROADMAP.md`.
- _None currently pending — the `cancelTask()` self-cancellation bug found here was promoted to Phase 1, Item 2 in `PROGRESS.md` and `ROADMAP.md`._
- `Leech()` continues operating on files after `cancelTask()` has already run `shutil.rmtree(Paths.WORK_PATH)`, when `cancelTask()` is triggered from a different asyncio Task than BOT.TASK (e.g. the Cancel button handler). `BOT.TASK.cancel()` doesn't interrupt synchronously — there's a window where `Leech()` runs on deleted files. Candidate fix: explicit `BOT.State.task_going` guard checks at loop checkpoint boundaries in `Leech()` and `Do_Leech()`/`Do_Mirror()`/`Do_Local_Mirror()`. Not yet promoted to PROGRESS.md — pending confirmation the guard-check patch resolves it.
