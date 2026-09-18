# Instructions for AI Agents / Assistants

> This file is read automatically by many AI coding tools (Claude Code,
> Cursor, Copilot Workspace, etc.) before they start working in this
> repository. If you are an AI assistant reading this: follow the steps
> below **before** writing or modifying any code.

## 1. Read the project's coding rules first

Before making **any** change — refactor, bug fix, or new feature — read:

👉 [`docs/INSTRUCTION.md`](./docs/INSTRUCTION.md)

That document defines this project's rules for:

- preserving existing behavior,
- function naming (`_private_helper` vs `public_function`),
- configuration/dataclass structure,
- error handling and logging conventions,
- how much to change in a single step,
- when to ask before proceeding vs when it's safe to proceed.

Do not skip this even for a "small" change — the rules explain *why*
certain patterns exist in this codebase (e.g. persistent-runtime state
safety for Colab notebooks, idempotency for long-running downloads),
which is not always obvious from the code alone.

## 2. Check the relevant progress/roadmap docs before touching a file

This repo tracks planned/in-progress work in two places — check whichever
one applies to the file you're about to touch:

**Top-level script folders** (`audio_processing/`, `downloaders/`,
`file_management/`, `metadata/`, `transcription/`, `uploaders/`,
`video_processing/`) are tracked centrally in:

- [`docs/ROADMAP.md`](./docs/ROADMAP.md) — refactor priorities, ordering,
  and known issues per file
- [`docs/PROGRESS.md`](./docs/PROGRESS.md) — checklist of what's already
  refactored vs. still pending

**Sub-projects** (e.g. `Telegram-Leecher/`, `Telegram-Fetcher/`) keep
their own copies in their own folder instead:

- `ROADMAP.md` — priorities and reasoning behind planned changes
- `PROGRESS.md` — what's already fixed vs still pending
- `TESTING.md` — manual test results and known blockers

Do not re-implement or "fix" something that the relevant `ROADMAP.md` /
`PROGRESS.md` already tracks as in-progress or intentionally deferred,
without checking that context first.

## 3. When in doubt

- Prefer small, focused, reviewable changes over large rewrites.
- Do not change public behavior, defaults, or output formats unless
  explicitly requested.
- If a change would remove code that looks unused, or would reorder
  filesystem/state operations, ask first — see `docs/INSTRUCTION.md`
  §19 ("AI Refactoring Communication Protocol").

## 4. Summary at the end of a session

Per `docs/INSTRUCTION.md` §19, end each refactoring session with:

- the list of files/functions changed,
- any behavior intentionally changed, and why,
- anything intentionally left untouched because it was out of scope.
