# Feature Specification: a fast check that names a per-worktree virtualenv runs in a fresh item worktree

**Feature Branch**: `520-checks-venv`
**Created**: 2026-10-05
**Status**: Draft
**Input**: GitHub issue #520: fix(checks): a fast check whose command names a per-worktree virtualenv runs in a fresh item worktree: the interpreter resolves from the repository's main worktree or [checks] python, and worktree add bootstraps or warns.

Owner's day, 2026-10-05: a fast check configured as `.venv/bin/python -m pytest -q` works in
the house worktrees and fails in every worktree WUWEI creates, because a fresh worktree made by
`wuwei worktree add` has no `.venv` until one is built. The first build in a new worktree ends
in an unmeasured or environment-parked check and a builder improvising a virtualenv. Part of the
autonomy push (#530): no new refusal under observe or guarded.

## Root cause

- `cli/wuwei/fast_checks.py:37-38` hands each configured command, unchanged, to the checks port
  with the item worktree as its directory: `runner.run(str(path), command, root=root)`.
- `adapters/checks/local.py:26` runs it as `/bin/sh -c <command>` with `cwd=path`. A command
  whose first word is a relative interpreter path (`.venv/bin/python`) therefore resolves only
  inside the item worktree. `git worktree add` checks out tracked files only, and `.venv` is
  untracked, so the shell exits 127 with `/bin/sh: .venv/bin/python: No such file or
  directory` (`not found` under dash). `_environment` (`adapters/checks/local.py:16-19`) does
  not classify it, since its program pattern `[\w.-]+` excludes `/`, so the check is an ordinary
  failure: `commands/build.py:353-386` feeds it back to the builder as fix feedback, and the
  builder improvises a virtualenv.
- Nothing reads the repository's main worktree (the `[[repos]] path` in config), which does
  have the interpreter, and nothing lets the owner name an interpreter or a per-worktree
  bootstrap: `cli/wuwei/workspace.py:53-240` (`SCHEMA`) has no `[checks]` table.
- `cli/wuwei/commands/worktree.py:33-39` creates the worktree and prints its JSON; it neither
  builds the environment nor says the check will fail. `commands/doctor.py:326-331` shows the
  fast-check commands with no interpreter resolution. The builder brief
  (`cli/wuwei/brief.py:373-378`) names no interpreter, so the builder improvises one.

## User Scenarios and Testing

### User Story 1: the first check in a fresh worktree runs with the main worktree's interpreter (Priority: P1)

**Independent Test**: a workspace whose repository's main worktree has `.venv/bin/python` (a
stub executable) and an item worktree without `.venv`; the fast check is
`.venv/bin/python -m pytest -q`; the real local checks adapter runs it.

**Acceptance Scenarios**:

1. **Given** a fast check `.venv/bin/python -m pytest -q`, a main worktree with `.venv` and a
   fresh item worktree without one, **When** `wuwei build check <item>` runs, **Then** the check
   runs with the main worktree's `.venv/bin/python`, exits 0, and its record in
   `fast_checks.<repo>.<command>` carries `interpreter` = the main worktree's absolute path.
2. **Given** the item worktree has its own `.venv/bin/python`, **When** the check runs, **Then**
   the worktree's interpreter is used and recorded (the command runs unchanged).
3. **Given** neither worktree has the interpreter and `[checks] python` is unset, **When** the
   check runs, **Then** it runs unchanged and fails as today, and the record carries
   `interpreter: null`.

### User Story 2: the owner names the interpreter once (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `[checks] python = "<path>"` (absolute, or relative to the repository's main
   worktree), **When** a check whose relative interpreter is a Python (`.venv/bin/python`,
   `venv/bin/python3`) runs in any worktree, including one that has its own `.venv`, **Then**
   the configured interpreter runs it and is recorded.
2. **Given** `[checks] python` set and a check `node_modules/.bin/jest`, **When** it runs,
   **Then** the setting does not apply and worktree-then-main resolution does.

### User Story 3: worktree add builds the environment, or says what it will use (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `[checks] bootstrap` set, **When** `wuwei worktree add <item>` creates the
   worktree, **Then** the bootstrap command runs once in the new worktree through the checks
   port, and a later check in that worktree runs with the new worktree's own interpreter.
2. **Given** `[checks] bootstrap` set and it exits non-zero or cannot run, **When**
   `worktree add` finishes, **Then** the worktree exists, the command exits 0, and stderr has
   one `wuwei worktree warning:` line naming the bootstrap's exit and reason.
3. **Given** no bootstrap, a fast check naming a relative interpreter the new worktree lacks
   and the main worktree has, **When** `worktree add` finishes, **Then** stderr has one
   `wuwei worktree warning:` line per such check naming the main worktree interpreter it will
   use and `[checks] bootstrap` as the way to build one per worktree; exit stays 0.
4. **Given** `wuwei doctor`, **When** a repository's fast check names a relative interpreter,
   **Then** a `<repo> check interpreter` row shows the resolution (`ok` with the path and its
   source, or `warn` when found nowhere, naming `[checks] python` and `[checks] bootstrap`).

### User Story 4: the builder brief names the interpreter (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a builder brief written with a worktree whose repository's fast check names a
   relative interpreter, **When** the brief is written, **Then** its header has a
   `Check interpreter:` line naming the command, the resolved path and its source.

### Edge Cases

- A command with no relative interpreter (`python3 -m pytest -q`, `ruff check .`): no rewrite,
  no `interpreter` key in the record, no doctor row, no brief line, no warning. Existing records
  and tests stay byte-identical.
- The item worktree is the main worktree (a house checkout): the worktree source wins, the
  command runs unchanged.
- A path with spaces: the rewritten first word is shell-quoted.
- A broken interpreter symlink in the worktree counts as absent.
- `adapters.checks = "none"`: bootstrap reports unmeasured as a warning; checks stay unmeasured
  as today.

## Requirements

### Functional Requirements

- **FR-001**: Config accepts a top-level `[checks]` table with `python` (string, default `""`)
  and `bootstrap` (string, default `""`). The config cache version is bumped.
- **FR-002**: One shared helper resolves a fast check's interpreter: when the command's first
  word starts with `.venv/`, `venv/` or `node_modules/.bin/`, it returns the path and source:
  `checks.python` (when set and the word's file name starts with `python`), else `worktree`
  when it exists in the item worktree, else `main worktree` when it exists in the repository's
  configured path, else `missing`. Any other command returns nothing.
- **FR-003**: `fast_checks.record` runs a check whose source is `checks.python` or
  `main worktree` with its first word replaced by the quoted resolved path, and writes
  `interpreter` (absolute path, or null when missing) into the check record only for commands
  that name a relative interpreter. The record stays keyed by the configured command.
- **FR-004**: `wuwei worktree add` runs `[checks] bootstrap` once in the new worktree through
  the checks port when set; a non-zero or unmeasured result is one warning line, never a
  refusal. Without a bootstrap it prints one warning line per check that resolves to
  `main worktree` in the new worktree.
- **FR-005**: `wuwei doctor` adds a `<repo> check interpreter` row per repository whose fast
  checks name a relative interpreter, resolved as in the main worktree.
- **FR-006**: A builder brief with a worktree adds one `Check interpreter:` header line per such
  check.
- **FR-007**: `docs/site/configuration.md` lists `[checks]` in the Sections table and documents
  `checks.python` and `checks.bootstrap`; the workspace template carries a commented example.

### Key Entities

- Check record (`state.fast_checks.<repo>.<command>`): gains optional `interpreter`.
- `[checks]` config table: `python`, `bootstrap`.

## Success Criteria

- **SC-001**: The three issue acceptance scenarios pass as tests with a real checks adapter
  and neutral fixtures.
- **SC-002**: No existing test changes its expectation for a command without a relative
  interpreter; the full suite passes.
- **SC-003**: No new refusal: every new outcome under any posture is exit 0 with a warning, a
  doctor row, or the existing check result.

## Assumptions

- `[checks]` is one workspace-wide table, as the issue writes it; a relative `python` resolves
  against each repository's configured path ("repository-relative"), so one setting serves
  several repositories with the same layout. Overturn: owners with different interpreters per
  repository; then move it under `[[repos]]`.
- `[checks] python` applies only to a relative interpreter whose file name starts with
  `python`; it never rewrites a bare `python3` or a `node_modules/.bin` tool. The issue says it
  "overrides both" resolutions, which exist only for relative interpreters.
- Only the command's first word is inspected. `cd sub && .venv/bin/python ...`, `env X=1 ...`
  or a relative interpreter after a pipe are not rewritten. Overturn: a configured check of that
  shape in a real workspace.
- The main worktree's interpreter is used as is. In a src-layout package installed editable in
  the main worktree's venv, imports may resolve to the main worktree's source; the record names
  the interpreter so a reviewer can see it, and `[checks] bootstrap` is the remedy. Not solved
  here.
- A failed bootstrap is a warning and `worktree add` still exits 0: the worktree exists and
  the next check measures the environment (and falls back to the main worktree's interpreter).
  Under strict too, since bootstrap is not a guard. Bootstrap runs through the existing checks
  port, so its 300-second cap applies; a longer install times out as a warning.
- The bootstrap warning prints the exit and the port's reason only, not the command output, so
  no install log lands in the terminal.
- No design spec amendment: this changes how a configured command is executed, not a rule,
  guard or state contract. `tests/test_invariants.py` does not exist on this base.

## Deferred

- Interpreter resolution for commands where the interpreter is not the first word.
- Per-repository `[checks]` tables.
