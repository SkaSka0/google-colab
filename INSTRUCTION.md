# Project Refactoring & Coding Instructions

> **Purpose:** This document defines general-purpose coding, refactoring, naming,
> architecture, and quality rules to apply when refactoring any codebase.
>
> All future refactoring should follow these rules unless a specific exception is
> explicitly agreed upon.
>
> **Scope note:** Some sections describe patterns for specific situations (e.g.
> building external commands, long-running external operations, notebook-style
> runtimes). Apply the general principles in every project. Apply the
> situation-specific patterns only when they are relevant to the codebase being
> refactored — skip a section entirely if it does not apply.

---

## Quick Reference

```text
1. Do not change behavior/user-facing output unless explicitly requested.
2. Public function: no leading underscore. Private helper: prefix with `_`.
3. One function, one responsibility. Do not split code merely to shrink it.
4. Group related configuration into dataclasses, but avoid one giant "god object".
5. Persistent runtimes (notebooks, long-lived processes): never assume clean
   state between runs. Rebuild configuration each time.
6. Separate concerns: build → execute → parse output → summarize.
7. Retry only errors that are actually retryable (timeouts, rate limits).
8. No abstraction (enum/factory/wrapper) without a concrete, current need.
9. Small, reviewable refactors beat one large rewrite.
10. When in doubt: preserve existing behavior, don't improvise.
```

---

# 1. Core Principles

## 1.1 Preserve Existing Behavior

Refactoring must primarily improve the **internal structure of the code without changing its external behavior**.

Unless explicitly requested:

- Do not change the program's functionality.
- Do not remove existing features.
- Do not change user-facing behavior.
- Do not change default values.
- Do not change command-line/tool arguments.
- Do not change output formats unnecessarily.
- Do not introduce breaking changes.
- Do not "fix" behavior that may be intentional without discussing it first.

When behavior must change, clearly identify the change and explain why.

## 1.2 Single Responsibility Principle

Every function should have **one clear responsibility**.

A function should not simultaneously:

- validate input,
- modify configuration,
- build commands or payloads,
- start processes,
- parse output,
- handle errors,
- format UI output,
- and save results.

If a function is doing several independent jobs, consider extracting focused helper functions.

However:

> **Do not split functions merely to make them smaller.**

A helper should represent a meaningful responsibility, not just a few lines of code.

## 1.3 Clear and Descriptive Responsibilities

Function names must describe **what the function does**, not how the implementation happens to work.

Prefer:

```python
_build_request_payload()
_prepare_output_directories()
_snapshot_existing_state()
_analyze_results()
```

over vague names such as:

```python
_process()
_handle()
_do_task()
_helper()
```

A developer should be able to understand the function's purpose from its name without opening the implementation.

---

# 2. Function Naming

## 2.1 Public Functions

Public functions are the main functions intended to be called from outside the module.

They should **not** start with `_`.

Example:

```python
run_task()
```

## 2.2 Private/Internal Functions

Functions that exist only to support other functions should start with `_`.

Example:

```python
_build_command()
_add_authentication_arguments()
_process_output()
```

This convention makes the public API immediately visible.

### Rule

Use:

```python
public_function()
_private_helper()
```

Not:

```python
_private_main_function()
helper_function()
```

when the helper is intended to be internal.

## 2.3 Avoid Generic Function Names

Avoid names such as:

```python
process()
handle()
run()
execute()
do_work()
helper()
manager()
utils()
```

unless the scope and responsibility are genuinely obvious.

Prefer names that describe the operation:

```python
_run_task_process()
_handle_progress_line()
_log_output_line()
_build_command()
```

## 2.4 Boolean Names

Boolean variables should read naturally as conditions.

Prefer:

```python
use_cache
use_suffix
use_custom_headers
use_retry
```

over ambiguous names such as:

```python
cache
suffix
headers
retry
```

when the value represents an on/off choice.

---

# 3. Configuration Design

## 3.1 Avoid Long Parameter Lists

Functions should not receive a large number of closely related parameters.

Avoid:

```python
run_task(
    input_value,
    output_dir,
    backend,
    timeout,
    max_connections,
    split_count,
    min_split_size,
    allocation_mode,
    credentials_file,
    ...
)
```

Group related configuration into configuration objects.

Example:

```python
run_task(task_input, output_name, config)
```

## 3.2 Use Dataclasses for Structured Configuration

When several values belong to the same conceptual area, use a dataclass.

Example structure:

```text
AppConfig
├── io_options
├── output_dir
├── backend
├── retry
├── authentication
├── request
└── debug_raw_output
```

Example:

```python
@dataclass
class AppConfig:
    io_options: IOOptions
    output_dir: str
    backend: BackendConfig
    retry: RetryConfig
    authentication: AuthenticationConfig
    request: RequestConfig
    debug_raw_output: bool = False
```

## 3.3 Keep Operation Inputs Separate From Configuration

Values that represent the **operation being performed** should remain separate from general configuration.

For example:

```python
run_task(task_input, output_name, config)
```

Here:

- `task_input` = operation input
- `output_name` = operation input
- `config` = reusable configuration

Do not put every argument into one giant configuration object merely to reduce the parameter count.

## 3.4 Group by Responsibility

Configuration objects should represent meaningful domains.

Example structure:

```python
IOOptions
BackendConfig
RetryConfig
AuthenticationConfig
RequestConfig
AppConfig
```

Do not create a new configuration class for every one or two variables.

Avoid over-engineering.

## 3.5 Derived Values

If a value can be reliably derived from another configuration value, prefer deriving it at a clear boundary instead of storing duplicate state.

Example:

```python
normalized_path = raw_path.rstrip("/") if use_trailing_slash_removal else raw_path
```

The conversion from external/UI inputs into application configuration should happen in one place:

```python
_create_app_config()
```

This function acts as the boundary between UI/input variables and the internal application model.

## 3.6 Configuration Mutability

Do not use immutable/frozen configuration objects unless there is a concrete need.

For simple, single-process/interactive workflows, normal mutable dataclasses are preferred. Reach for immutability only when concurrency or shared state genuinely requires it.

---

# 4. Global Variables and State

## 4.1 Avoid Hidden Global Dependencies

Functions should not silently depend on global variables when the value logically belongs to their inputs.

Bad:

```python
def handle_progress_line(line):
    label = truncate_label(display_name)
```

Better:

```python
def _handle_progress_line(line, display_label):
    ...
```

The function's dependencies should be visible from its parameters.

## 4.2 Configuration Globals Should Have One Conversion Boundary

External inputs (CLI flags, environment variables, notebook form fields, config files) may remain as raw inputs, but application logic should not spread direct dependencies on those globals throughout the code.

Prefer:

```text
External inputs
    ↓
_create_app_config()
    ↓
AppConfig
    ↓
application logic
```

This makes future migration to another UI, CLI, or API easier.

## 4.3 Avoid Hidden Side Effects

A function should not unexpectedly modify unrelated global state.

Side effects should be obvious from the function's responsibility.

## 4.4 Persistent Runtime State Safety

Some environments keep running the same process or session across multiple
invocations — notebooks (Jupyter/Colab), long-lived servers, REPLs, background
workers. In these environments, global state can silently leak between runs,
which is a different risk profile than a fresh CLI invocation.

### Rules

- **Never assume clean state.** Every time the main entry point runs (whether
  triggered by a fresh process or a re-run within the same session), all
  configuration must be rebuilt from scratch.
- `_create_app_config()` (or its equivalent) **must always construct a new
  configuration object**, never mutate a previous instance in place.
- Do not store operation state (progress, collected results, etc.) in
  module-level globals that persist across runs. Keep it in function scope or
  in the object returned by the function.
- Dependency installation/setup routines must be idempotent — check whether a
  dependency is already available before installing it again, since setup
  code in these environments can run multiple times within the same session.
- If the code interacts with external resources that may already be
  initialized (mounted storage, open connections, cached clients), check
  their state before assuming they need to be (re)initialized.

---

# 5. Architecture

## 5.1 Prefer Clear Layers

The project should naturally separate into responsibilities such as:

```text
Input / Configuration
        ↓
Preparation
        ↓
Command / Payload Construction
        ↓
Execution
        ↓
Output Processing
        ↓
Analysis
        ↓
Summary / Presentation
```

Do not mix unrelated layers unless there is a practical reason.

## 5.2 Main Functions Should Orchestrate

A high-level public function should primarily coordinate the workflow.

Example:

```python
run_task(task_input, output_name, config)
```

Conceptually:

```text
prepare
  ↓
build
  ↓
run
  ↓
analyze
  ↓
summarize
```

The orchestration function should not contain the detailed implementation of every step.

## 5.3 Helpers Should Have Clear Boundaries

For example:

```text
_build_command()
    ├── _build_base_command()
    ├── _add_authentication_arguments()
    ├── _add_credential_provider_arguments()
    ├── _add_client_identity_arguments()
    ├── _add_header_arguments()
    └── _add_backend_arguments()
```

Each helper handles one logical concern.

## 5.4 Do Not Over-Abstract

Abstraction is useful when it:

- removes duplication,
- isolates a responsibility,
- makes code easier to understand,
- makes testing easier,
- or provides a stable boundary.

Do not create abstractions simply because they are theoretically possible.

Avoid unnecessary:

- factories,
- interfaces,
- base classes,
- enums,
- dependency injection frameworks,
- generic managers,
- wrapper classes,
- one-line helper functions.

> **Simple code is preferred over clever code.**

## 5.5 Strategy/Backend Selection Consistency

Some projects support more than one implementation of the same responsibility
(e.g. multiple storage backends, multiple HTTP clients, multiple rendering
engines). When that applies, keep the selection mechanism consistent and easy
to extend.

### Rules

- Select the strategy/backend through **one string (or otherwise simple)
  field** in the configuration (e.g. `backend.name`), not through many
  separate boolean flags.
- Validate the selected value **once**, at the configuration entry point
  (`_create_app_config()`), not scattered across multiple functions.
- Give each strategy/backend its own builder and runner functions with
  parallel naming:

```python
_build_backend_a_command() / _run_backend_a()
_build_backend_b_command() / _run_backend_b()
```

- The orchestrator (the public entry function) should only dispatch to the
  right implementation based on the configured value — it should not contain
  logic specific to any single strategy/backend.
- **An Enum or abstract base class is usually not necessary** for this — a
  validated string literal (`if backend not in ("a", "b")`) is often enough.
  This stays consistent with "avoid over-abstraction" in section 5.4. Reach
  for a stronger abstraction only once there are enough strategies, or
  enough shared structure between them, that a plain conditional becomes
  hard to follow.

---

# 6. Command / Payload Construction

When constructing external commands, requests, or structured payloads, build
them in understandable stages.

Prefer:

```python
payload = _build_base_command(...)
payload = _add_authentication_arguments(payload, ...)
payload = _add_credential_provider_arguments(payload, ...)
payload = _add_client_identity_arguments(payload, ...)
payload = _add_header_arguments(payload, ...)
payload = _add_backend_arguments(payload, ...)
```

over one large function containing all construction logic.

Each argument/field group should have an identifiable owner.

---

# 7. Process / Task Execution

External process or long-running task handling should be separated from
construction logic.

For example:

```text
_build_command()
        ↓
_start_process()
        ↓
_process_output()
        ↓
_wait_for_process()
```

The process runner should be responsible for process lifecycle and execution status.

Output parsing/formatting should not be unnecessarily mixed into process startup logic.

Fatal-error detection should be isolated where practical:

```python
_is_fatal_error()
```

## 7.1 Idempotency & Resume Safety for Long-Running Operations

Whenever an operation can fail partway through (network interruption, process
crash, runtime disconnect, timeout), that possibility must be handled
explicitly rather than ignored — this applies to downloads, batch jobs,
migrations, uploads, or any multi-step external operation.

### Rules

- The outcome of a long-running operation should be distinguishable into at
  least three categories: **fully succeeded**, **fully failed**, and
  **partial / resumable**.
- If the underlying mechanism supports resuming, do not automatically delete
  partial results unless explicitly requested.
- Any "snapshot of existing state" taken for comparison purposes (see section
  11.2) must be taken **before** the operation starts, and compared again
  after it finishes — including the case where the operation stops midway.
- Retry logic, if present, must be explicit and bounded (a maximum number of
  attempts), never unbounded.
- Distinguish errors that are **worth retrying** (network timeouts, rate
  limits) from errors that are **fatal and not worth retrying** (invalid
  input, authentication failure) — consistent with `_is_fatal_error()` above.

---

# 8. Error Handling

## 8.1 Handle Errors at the Appropriate Level

Do not wrap every line of code in:

```python
try:
    ...
except Exception:
    ...
```

Catch exceptions where there is enough context to handle them meaningfully.

## 8.2 Do Not Silently Ignore Errors

Avoid:

```python
except:
    pass
```

unless there is a deliberate reason and the ignored failure is genuinely harmless.

Prefer:

```python
except ValueError:
    ...
```

or another specific exception when possible.

## 8.3 Preserve Useful Error Information

Errors from external tools or services should retain enough context to diagnose failures.

Use the project's logging mechanism consistently:

```python
log("...", "ERROR")
log("...", "CRITICAL")
```

## 8.4 Distinguish Expected Failures From Unexpected Failures

Expected conditions should be handled explicitly.

Unexpected exceptions should not be disguised as successful execution.

---

# 9. Logging and Output

## 9.1 Use the Existing Logging Abstraction

Use:

```python
log(message)
```

for application-level log messages.

Do not duplicate the logging format throughout the code.

## 9.2 Keep User-Facing Output Separate From Diagnostic Logging

Progress displays and summaries are presentation concerns.

Raw subprocess or raw response output is diagnostic information.

For example:

```python
_log_raw_output()
_handle_progress_line()
_print_summary()
```

should have distinct responsibilities.

## 9.3 Debug Mode

Debug behavior should be controlled by configuration:

```python
debug_raw_output
```

Do not scatter independent debug flags throughout the code.

## 9.4 Logging Levels

Define logging levels explicitly so they are used consistently:

| Level      | When to use                                                          |
|------------|-----------------------------------------------------------------------|
| `DEBUG`    | Technical detail (raw commands, raw output) — only shown when `debug_raw_output=True` |
| `INFO`     | Normal progress relevant to the user (operation started, completed)   |
| `WARNING`  | Abnormal condition but the process still continues (retry, fallback)  |
| `ERROR`    | An operation failed but other work can still continue                 |
| `CRITICAL` | A failure that halts the overall process                              |

Avoid using `print()` directly outside `log()` for messages that carry one of
these levels — consistent with section 9.1.

---

# 10. Data and Return Values

## 10.1 Return Meaningful Values

Functions should return useful information instead of relying on side effects.

For example:

```python
return True
```

for success/failure is preferable to requiring callers to inspect hidden state.

## 10.2 Use Structured Data When Appropriate

When a function produces multiple related values, prefer a dictionary or dataclass over many separate return values.

Example:

```python
summary = {
    "total_items": ...,
    "new_items": ...,
    "total_size_bytes": ...,
}
```

If the structure becomes stable and complex enough, consider a dataclass.

## 10.3 Do Not Mutate Data Unexpectedly

If a helper receives a list/configuration object, avoid modifying it unless mutation is part of its explicit responsibility.

For builder-style functions, mutation is acceptable when it is part of the established builder pattern:

```python
items.extend(...)
return items
```

Keep that convention consistent.

---

# 11. File and Directory Handling

## 11.1 Make Directory Responsibilities Explicit

Directory creation should have its own responsibility when practical:

```python
_prepare_output_directories()
```

## 11.2 Preserve Existing State Detection Semantics

If the application needs to distinguish newly created/changed items from
pre-existing ones, take the snapshot at the appropriate point before the
operation changes the relevant state.

Do not casually change the order of filesystem or state operations during refactoring.

---

# 12. Naming Conventions

Use descriptive names consistently.

### Variables

Prefer:

```python
filename_template
output_dir
temp_dir
original_items
new_items
display_label
```

over:

```python
x
data
tmp
result
obj
item
```

unless the shorter name is genuinely obvious from a small local scope.

### Constants

Constants should use uppercase:

```python
DEBUG_RAW_OUTPUT
```

### Classes

Use `PascalCase`:

```python
AppConfig
IOOptions
BackendConfig
```

### Functions and variables

Use `snake_case`:

```python
run_task
_build_command
filename_template
```

---

# 13. Type Hints

Use type hints for:

- public functions,
- configuration classes,
- important helpers,
- non-obvious return values.

Examples:

```python
def run_task(
    task_input: str,
    output_name: str,
    config: AppConfig,
) -> bool:
    ...
```

```python
def _get_item_metadata(file_path: str) -> dict:
    ...
```

Do not add complicated typing solely for the sake of having more types.

Prefer readable types over overly elaborate generic type expressions.

---

# 14. Documentation and Comments

## 14.1 Comments Explain Why

Prefer comments that explain **why** something exists.

Good:

```python
# Keep temporary fragments separate from the final output directory.
```

Less useful:

```python
# Create temp directory.
os.makedirs(temp_dir)
```

The code already explains what it does.

## 14.2 Keep Comments Accurate

Outdated comments are worse than no comments.

Whenever behavior changes, update affected comments/docstrings.

## 14.3 Docstrings for Non-Obvious Functions

Use concise docstrings when a function's behavior, side effects, or constraints are not obvious.

Do not write documentation that merely repeats the function name.

---

# 15. Formatting and Style

Follow standard language conventions (e.g. PEP 8 for Python) unless a
project-specific convention has been deliberately established.

Prefer:

- readable line lengths,
- consistent indentation,
- consistent spacing,
- imports grouped logically,
- no unnecessary blank-line noise,
- no trailing debugging code.

Use automated formatters/linters when practical, but do not let tooling make the code less readable.

---

# 16. Imports

Keep imports:

1. standard library,
2. third-party libraries,
3. project-local modules.

Avoid unused imports.

If an import is only required after installing an optional dependency, handle that dependency intentionally rather than relying on accidental import order.

---

# 17. Dependency Management

Dependency installation should be explicit and centralized.

For example:

```python
_install_dependencies(config)
```

should own dependency setup.

Do not install packages unexpectedly inside unrelated functions.

Optional dependencies should only be installed when the relevant feature requires them.

Example:

```text
Optional feature X enabled
    → install the dependency that feature requires
```

```text
Backend Y selected
    → ensure the external tool/library Y needs is available
```

---

# 18. Refactoring Workflow

Every refactor should follow this order:

### Step 1 — Understand

Before changing code:

- identify current behavior,
- identify inputs and outputs,
- identify global dependencies,
- identify side effects,
- identify function responsibilities,
- identify important execution order.

### Step 2 — Preserve

Record behavior that must remain unchanged.

### Step 3 — Design

Decide:

- which responsibilities should be separated,
- which functions should be renamed,
- which values should be grouped,
- which helpers are actually necessary.

### Step 4 — Refactor

Make focused structural changes.

### Step 5 — Verify

At minimum:

- check syntax,
- check imports,
- inspect function call sites,
- check global-variable dependencies,
- check parameter names,
- check return values,
- check execution order,
- compare important behavior with the previous version.

### Step 6 — Review

Look specifically for:

- accidental behavior changes,
- unnecessary abstractions,
- duplicated logic,
- unclear names,
- hidden dependencies,
- dead code,
- unused imports,
- overly large functions.

---

# 19. Incremental Changes

Prefer small, understandable refactoring steps.

Do not combine unrelated changes such as:

- architecture refactoring,
- feature additions,
- UI redesign,
- dependency upgrades,
- behavior changes,
- performance optimization,

unless there is a clear reason.

A refactor should be easy to review and, if necessary, easy to revert.

---

# 20. Avoid Premature Optimization

Do not optimize code without evidence that optimization is needed.

Correctness and maintainability come first.

When performance matters:

1. identify the bottleneck,
2. measure it,
3. optimize the relevant part,
4. verify that behavior remains correct.

Do not sacrifice readability for negligible performance gains.

---

# 21. Avoid Dead Code

Remove:

- unused imports,
- unused variables,
- unused functions,
- obsolete comments,
- abandoned implementations,
- debugging statements.

However, do not remove apparently unused code if it may be part of an external/public API without first checking its usage.

---

# 22. Compatibility and Stability

When refactoring an existing stable version:

> **The stable version is the behavioral reference.**

Internal implementation may change, but important observable behavior should remain compatible unless explicitly approved.

When there is uncertainty, prefer:

```text
preserve existing behavior
```

over:

```text
make a speculative improvement
```

Discuss potentially breaking improvements before implementing them.

---

# 23. Security and Reliability

Even for a personal project, follow basic security practices.

### Never hard-code secrets

Do not commit:

- cookies,
- session strings,
- API tokens,
- passwords,
- private keys,
- personal access tokens.

### Avoid unsafe shell construction

Prefer argument lists:

```python
subprocess.run(["command", "--option", value])
```

over constructing shell commands as a single string whenever possible.

Avoid `shell=True` unless it is genuinely required.

### Validate external input

URLs, filenames, paths, and external tool/service output should not be blindly trusted.

---

# 24. External Tool and Service Boundaries

Treat external dependencies such as:

- third-party CLIs,
- package managers,
- external APIs and network services,
- system binaries,

as external boundaries.

Do not assume they always:

- exist,
- return valid output,
- return the same output format,
- complete successfully,
- or remain compatible forever.

Handle their failure modes where appropriate without making the code excessively defensive.

---

# 25. Testing and Verification

Tests are preferred whenever practical.

For functions that are easy to test independently, especially:

- input sanitization/validation,
- command or payload construction,
- configuration conversion,
- output/progress parsing,
- error detection,

consider adding focused tests.

If a full test suite is not practical, perform targeted verification.

At minimum for a refactor:

```text
Syntax check
    ↓
Import check
    ↓
Static/reference inspection
    ↓
Targeted function checks
    ↓
Real execution when possible
```

---

# 26. Git and Change Hygiene

Use Git commits that represent coherent changes.

Prefer commits such as:

```text
refactor: separate command builder responsibilities
refactor: group backend configuration
fix: preserve existing state-snapshot behavior
docs: update project instructions
```

Avoid large commits containing unrelated changes.

Do not commit:

- generated temporary files,
- build artifacts or large binary outputs,
- credentials,
- caches,
- local environment files,
- editor-specific temporary files,

unless explicitly required by the project.

---

# 27. Linux/Kernel-Inspired Principles That Apply Here

Most personal or small-team projects do **not** need Linux-kernel-level
complexity or process.

Only adopt the principles that are useful at the project's actual scale.

### 27.1 Explicit Is Better Than Clever

Code should be understandable during maintenance.

Avoid clever tricks when straightforward code communicates the intent better.

### 27.2 Minimize Unnecessary Complexity

Every abstraction has a maintenance cost.

Before introducing one, ask:

> "Does this make the code easier to understand or maintain?"

If not, do not add it.

### 27.3 Keep Interfaces Small

Functions should receive only what they reasonably need.

Configuration grouping is encouraged, but do not create giant "everything" objects.

### 27.4 Make Dependencies Visible

A function should make important dependencies clear through:

- parameters,
- configuration objects,
- return values.

Avoid hidden coupling.

### 27.5 Prefer Local Reasoning

A developer should be able to understand a function mostly by reading that function and its immediate collaborators.

Avoid requiring a developer to trace many unrelated globals or modules just to understand a small operation.

### 27.6 Don't Break Userspace

Adapted to any project:

> Existing user-facing behavior is a compatibility contract.

Internal improvements should not unexpectedly break the way the software is used.

### 27.7 Reviewability Matters

Code should be written so another developer can understand why a change was made.

A smaller, focused change is preferable to a massive rewrite when both achieve the same goal.

---

# 28. Decision Rules for Ambiguous Refactors

When multiple designs are possible, prioritize in this order:

1. **Correctness**
2. **Preserving existing behavior**
3. **Clarity**
4. **Maintainability**
5. **Simple architecture**
6. **Testability**
7. **Performance**
8. **Additional abstraction**

Do not choose a more sophisticated architecture merely because it looks more "professional."

Professional code is not code with the most abstractions.

Professional code is code whose structure matches the problem.

---

# 29. Refactoring Checklist

Before considering a refactor complete, verify:

- [ ] Existing behavior is preserved.
- [ ] Public functions are clearly identifiable.
- [ ] Private helpers use a leading `_`.
- [ ] Function names describe responsibilities clearly.
- [ ] Functions follow Single Responsibility Principle.
- [ ] Long parameter lists have been evaluated for grouping.
- [ ] Related configuration is grouped into dataclasses where appropriate.
- [ ] Operation inputs remain separate from configuration.
- [ ] Hidden global dependencies have been removed where practical.
- [ ] Derived values are created at a clear boundary.
- [ ] Command/payload construction is separated from execution.
- [ ] Error handling is explicit and meaningful.
- [ ] Logging responsibilities are clear.
- [ ] Unused code/imports have been removed.
- [ ] Comments explain intent rather than obvious syntax.
- [ ] Type hints are present where useful.
- [ ] No unnecessary abstraction has been introduced.
- [ ] No secrets or credentials are hard-coded.
- [ ] External process/service calls are handled safely.
- [ ] Syntax has been checked.
- [ ] Important call sites have been reviewed.
- [ ] Real execution has been tested when practical.
- [ ] The final diff is focused and reviewable.
- [ ] Persistent-runtime state assumptions have been checked, if applicable (section 4.4).
- [ ] Strategy/backend selection logic stays in one place, if applicable (section 5.5).
- [ ] Partial/failed long-running operations are handled explicitly, if applicable (section 7.1).

---

# 30. AI Refactoring Communication Protocol

Since refactoring is often done with the help of an AI assistant, add explicit
communication rules so the results can be reviewed easily.

### Rules

- **Limit the size of each change.** One refactoring step should touch one
  responsibility/section of this document at a time (e.g. only separate the
  command builder, without also changing error handling in the same step).
- **Ask before:**
  - removing a function/piece of code that looks unused but might be part of
    a public API,
  - changing the order of filesystem or state operations (snapshot, execute,
    cleanup),
  - changing a default value or output format,
  - adding a new dependency.
- **No need to ask before:**
  - renaming an internal helper that is clearly only used locally,
  - splitting a large function that clearly violates the Single
    Responsibility Principle (section 1.2), as long as behavior is
    unchanged.
- **Every refactoring session should end with a summary:**
  - the list of files/functions changed,
  - any behavior that was intentionally changed, and why,
  - anything intentionally left untouched because it was out of scope for
    that step.

---

# 31. Golden Rule

> **Refactor to make the code easier to understand, not merely different.**

If a refactor makes the architecture more complicated, introduces unnecessary abstractions, or makes a simple operation harder to follow, reconsider the refactor.

The goal is:

```text
Simple
    +
Clear
    +
Explicit
    +
Maintainable
    +
Behavior-compatible
```

—not maximum abstraction.