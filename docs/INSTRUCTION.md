# Project Refactoring & Coding Instructions

> Purpose: general-purpose coding, refactoring, naming, and architecture
> rules for this repo. Apply the general principles everywhere; apply the
> situation-specific patterns (external commands, long-running tasks,
> notebook-style runtimes) only where relevant.

## Quick Reference

```text
1. Do not change behavior/output unless explicitly requested.
2. Public function: no leading underscore. Private helper: prefix with `_`.
3. One function, one responsibility. Don't split code merely to shrink it.
4. Group related config into dataclasses; avoid one giant "god object".
5. Persistent runtimes (notebooks, long-lived processes): never assume
   clean state between runs — rebuild configuration each time.
6. Separate concerns: build → execute → parse output → summarize.
7. Retry only errors that are actually retryable (timeouts, rate limits).
8. No abstraction (enum/factory/wrapper) without a concrete, current need.
9. Small, reviewable refactors beat one large rewrite.
10. All code, comments, logs, commits, and docs are written in English.
11. When in doubt: preserve existing behavior, don't improvise.
```

---

## 1. Core Principles

- **Preserve behavior.** Unless explicitly requested, don't change
  functionality, remove features, change defaults/output formats/CLI
  args, or "fix" behavior that may be intentional without discussing it
  first. If behavior must change, call it out explicitly and explain why.
- **Single Responsibility.** A function shouldn't validate input, build
  payloads, run processes, parse output, format UI, *and* save results
  all at once. Extract helpers for meaningful responsibilities — not
  just to make a function shorter.
- **Descriptive names.** Prefer `_build_request_payload()` over
  `_process()`/`_handle()`. A reader should understand a function's
  purpose from its name alone.

## 2. Naming

- **Public** functions (called from outside the module): no leading `_`.
- **Private/internal** helpers: prefix with `_`.
- Avoid generic names (`process`, `handle`, `run`, `manager`, `utils`)
  unless the scope is genuinely obvious — prefer names that describe the
  operation (`_handle_progress_line`, `_build_command`).
- Booleans should read as conditions: `use_cache`, `use_retry`, not
  `cache`, `retry`.
- Constants: `UPPER_CASE`. Classes: `PascalCase`. Functions/vars: `snake_case`.

## 3. Configuration

- Avoid long parameter lists — group related config into dataclasses
  (e.g. `AppConfig` containing `IOOptions`, `BackendConfig`,
  `RetryConfig`, etc.), but don't create a class for every 1–2 vars.
- Keep the *operation's own inputs* (e.g. `task_input`, `output_name`)
  separate from reusable *configuration* objects.
- Convert raw external/UI inputs into the internal config object in
  **one place** (e.g. `_create_app_config()`) — that's the boundary
  between input and application logic.
- Derive values at a clear boundary instead of duplicating state.
- Don't use frozen/immutable config unless concurrency genuinely needs it.

## 4. Global Variables & State

- Don't let functions silently depend on globals when the value belongs
  in their parameters — dependencies should be visible in the signature.
- External inputs may stay as raw globals, but application logic should
  route through one conversion boundary, not depend on those globals
  directly and repeatedly.
- Avoid unexpected side effects on unrelated global state.

### Persistent Runtime Safety (notebooks, long-lived processes, REPLs)

- **Never assume clean state** between runs in the same session/process.
  Rebuild all configuration from scratch every time the entry point runs.
- Config-builder functions must always construct a **new** object, never
  mutate a previous instance.
- Don't store operation state (progress, results) in module-level
  globals that persist across runs.
- Setup/dependency-install routines must be **idempotent** — check
  before (re)installing or (re)initializing anything (mounted storage,
  open connections, cached clients).

## 5. Architecture

- Prefer clear layers: input/config → preparation → command/payload
  construction → execution → output processing → analysis → summary.
- High-level public functions should **orchestrate**, not contain every
  implementation detail.
- Give helpers clear, single-concern boundaries (e.g. `_build_command()`
  delegating to `_add_authentication_arguments()`, `_add_backend_arguments()`, etc).
- **Don't over-abstract.** No factories/interfaces/enums/wrapper classes
  without a concrete, current need. Simple code beats clever code.
- **Strategy/backend selection:** pick via one config field (e.g.
  `backend.name`), validate once at the config boundary, give each
  strategy parallel-named builder/runner functions
  (`_build_x_command()`/`_run_x()`). A validated string is usually
  enough — no enum/ABC needed unless complexity genuinely warrants it.

## 6–7. Commands & Process Execution

- Build external commands/payloads in named stages
  (`_build_base_command` → `_add_authentication_arguments` → ...) rather
  than one large function.
- Separate command construction from process lifecycle
  (`_build_command` → `_start_process` → `_process_output` →
  `_wait_for_process`). Isolate fatal-error detection (`_is_fatal_error()`).

### Idempotency & Resume Safety (long-running operations)

- Distinguish **fully succeeded / fully failed / partial-resumable**
  outcomes explicitly.
- Don't auto-delete partial/resumable results unless requested.
- Take "existing state" snapshots **before** the operation starts, and
  re-compare after — including when it stops midway.
- Retry logic must be explicit and **bounded**. Distinguish retryable
  errors (timeouts, rate limits) from fatal ones (bad input, auth failure).

## 8. Error Handling

- Catch exceptions where there's enough context to handle them
  meaningfully — don't wrap every line in `try/except`.
- Avoid bare `except: pass` unless deliberate and genuinely harmless;
  prefer specific exceptions.
- Preserve error context in logs (`log(..., "ERROR")`).
- Don't disguise unexpected exceptions as success.

## 9. Logging & Output

- Use the project's `log()` abstraction consistently; don't duplicate
  the format inline.
- Keep user-facing progress/summaries separate from diagnostic/raw output.
- Debug output goes through a `debug_raw_output`-style flag, not scattered ad hoc flags.
- Levels: `DEBUG` (raw detail, debug-only) · `INFO` (normal progress) ·
  `WARNING` (recovered abnormal condition) · `ERROR` (one operation
  failed, others continue) · `CRITICAL` (halts everything).
- All log/console text is English (see §10 below).

## 10. Language Consistency

- **All code, comments, docstrings, log/console messages, commit
  messages, and docs must be English** — even in files that currently
  mix English and another language.
- When a file is touched for any reason, bring its language in line as
  part of that same change (don't defer it) — but don't open otherwise-
  untouched files *just* to translate them; batch pure-translation work
  into its own focused change unless a project-wide pass was requested.
- Translation must be text-only (no behavior change); if literal
  translation would lose meaning, rewrite clearly and flag it.
- **Exceptions:** text that must match an external API/tool verbatim
  stays as-is (add an English comment nearby); deliberately localized
  user-facing copy (e.g. a bot's replies for a non-English audience) is
  a product decision — confirm with the user before changing it, even
  though surrounding code/comments/logs still follow English-only.

## 11. Data, Files, Types, Comments — quick rules

- Return meaningful values (success/failure, structured data) instead of
  relying on hidden side effects; use dicts/dataclasses for multi-value results.
- Don't mutate passed-in data unless mutation is the function's explicit
  job (builder-style `items.extend(...); return items` is fine).
- Give directory setup and "snapshot before operation" their own
  responsibility; don't casually reorder filesystem/state operations
  during a refactor.
- Type-hint public functions, config classes, and non-obvious helpers —
  don't over-engineer typing for its own sake.
- Comments explain **why**, not what the code already shows; keep them
  accurate when behavior changes; docstrings only where behavior isn't obvious.

## 12. Style, Imports, Dependencies

- Follow standard language conventions (PEP 8 for Python) unless the
  project already deviates deliberately.
- Import order: stdlib → third-party → local. No unused imports.
- Centralize dependency installation (e.g. `_install_dependencies()`);
  don't install packages inside unrelated functions; only install what
  the enabled feature/backend actually needs.

## 13. Security & External Boundaries

- Never hard-code secrets (tokens, cookies, passwords, keys).
- Prefer argument-list subprocess calls over shell strings; avoid
  `shell=True` unless truly required.
- Don't blindly trust external URLs/filenames/tool output — validate
  where it matters.
- Treat third-party CLIs/APIs/binaries as boundaries that can fail,
  return unexpected output, or become unavailable — handle failure
  modes without excessive defensiveness.

## 14. Testing & Verification

- Prefer focused tests for input validation, command/payload
  construction, config conversion, and output parsing when practical.
- Minimum verification for any refactor: syntax check → import check →
  call-site/reference check → targeted function checks → real execution
  when possible.

## 15. Refactoring Workflow

1. **Understand** — current behavior, inputs/outputs, global deps, side
   effects, execution order.
2. **Preserve** — record what must not change.
3. **Design** — decide responsibility splits, renames, groupings.
4. **Refactor** — small, focused changes.
5. **Verify** — per §14, plus compare against prior behavior.
6. **Review** — check for accidental behavior changes, unneeded
   abstraction, dead code, unclear names, hidden deps.

Keep changes **incremental**: don't mix architecture refactoring,
feature additions, and behavior changes in one step. A project-wide
translation pass is its own separate change unless small enough to
review alongside the refactor it's part of.

## 16. Git Hygiene

- Coherent commits (`refactor: ...`, `fix: ...`, `docs: ...`), in English.
- Don't commit secrets, build artifacts, caches, or editor temp files.

## 17. Guiding Principles (condensed)

- Explicit beats clever; minimize complexity that doesn't aid
  understanding; keep interfaces small; make dependencies visible via
  parameters/config, not hidden coupling; a function should be
  understandable mostly by reading it and its direct collaborators;
  existing user-facing behavior is a compatibility contract — don't
  break it incidentally; keep changes reviewable.
- When designs are ambiguous, prioritize in order: **correctness →
  preserving behavior → clarity → maintainability → simple architecture
  → testability → performance → additional abstraction.**

## 18. Refactoring Checklist

- [ ] Existing behavior preserved
- [ ] Public/private naming correct (`_` prefix for internal helpers)
- [ ] Functions follow Single Responsibility
- [ ] Related config grouped into dataclasses where it helps
- [ ] Operation inputs kept separate from reusable config
- [ ] Hidden global dependencies removed where practical
- [ ] Command/payload construction separated from execution
- [ ] Error handling explicit and meaningful
- [ ] Logging levels used consistently
- [ ] Unused code/imports removed; no unnecessary abstraction added
- [ ] No hard-coded secrets
- [ ] Syntax, imports, and call sites checked; real execution tested if possible
- [ ] Persistent-runtime state assumptions checked, if applicable
- [ ] Partial/failed long-running operations handled explicitly, if applicable
- [ ] Touched code/comments/logs/docs are in English

## 19. AI Refactoring Communication Protocol

- Limit each change to one responsibility/section at a time.
- **Ask first** before: removing code that looks unused but might be
  public API, reordering filesystem/state operations, changing a
  default/output format, or adding a new dependency.
- **No need to ask** before: renaming a clearly-local internal helper,
  splitting a function that clearly violates SRP (behavior unchanged),
  or translating non-English comments/logs in a file already being
  touched for another reason.
- End every refactoring session with a summary: files/functions
  changed, any intentional behavior change and why, anything
  intentionally left out of scope.

## Golden Rule

> Refactor to make the code easier to understand, not merely different.

```text
Simple + Clear + Explicit + Maintainable + Behavior-compatible + English
```
