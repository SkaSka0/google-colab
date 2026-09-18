# Contributing

Thanks for wanting to contribute! Please read this before opening a PR —
it applies equally to human contributors and AI coding assistants.

## Before you start

**Read [`docs/INSTRUCTION.md`](./docs/INSTRUCTION.md) first.** It defines
this project's rules for refactoring, naming, error handling, logging,
configuration structure, and how large a single change should be. Most
PR review feedback traces back to something already covered there.

If you're using an AI coding assistant, point it at
[`AGENTS.md`](./AGENTS.md) — it tells the assistant to read the same
document before making changes.

## Before touching a specific file

Check the relevant progress/roadmap doc first, so you don't duplicate
something already in progress or reintroduce something intentionally
deferred:

- **Top-level script folders** (`audio_processing/`, `downloaders/`,
  `file_management/`, `metadata/`, `transcription/`, `uploaders/`,
  `video_processing/`) are tracked centrally in
  [`docs/ROADMAP.md`](./docs/ROADMAP.md) (priorities and *why*) and
  [`docs/PROGRESS.md`](./docs/PROGRESS.md) (checklist of what's done).
- **Sub-projects** (e.g. `Telegram-Leecher/`, `Telegram-Fetcher/`) keep
  their own copies in their own folder instead:
  - `ROADMAP.md` — current priorities and *why* they're prioritized that way
  - `PROGRESS.md` — checklist of what's fixed vs. still pending
  - `TESTING.md` — manual test results and known blockers

## Making changes

- Keep PRs small and focused — one responsibility per PR, per
  `docs/INSTRUCTION.md` §15 ("Keep changes incremental...") and §19
  ("AI Refactoring Communication Protocol").
- Do not change existing behavior, defaults, or output formats unless
  it's the explicit point of the PR. If it is, say so clearly in the
  PR description.
- Follow the naming conventions in `docs/INSTRUCTION.md` §2
  (`_private_helper` vs `public_function`, etc).
- If your change removes code that looks unused, or reorders
  filesystem/state operations, explain why in the PR description.

## PR checklist

- [ ] I read `docs/INSTRUCTION.md` before making this change
- [ ] I checked the relevant `ROADMAP.md` / `PROGRESS.md` (top-level
      `docs/` or the sub-project's own), if any
- [ ] This PR does one focused thing (no unrelated changes mixed in)
- [ ] Existing behavior is preserved, or any change is explicitly called out
- [ ] I described what was tested / how to verify the change

## Questions

If something in `docs/INSTRUCTION.md` seems to conflict with what a PR
needs to do, please open a discussion/issue first rather than silently
deviating from it.
