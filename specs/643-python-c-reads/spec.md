# Feature Specification: a read-only python -c on state.json is a read, not a records write

**Feature Branch**: `643-python-c-reads`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #643 (owner, 2026-10-10): the records guard refused
`python3 -c "import json; print(json.load(open('.wuwei/state.json'))[...])"`, a read.
Deliver: a `python -c` snippet whose source opens workspace files only for reading (no
`'w'`, `'a'`, `'x'`, `'+'` modes, no `write_text`, `write_bytes`, `os.remove`, `rename`,
`replace`, `unlink`, `shutil`, `subprocess`, `os.system`, no redirect) is classified as a
reader by the shell classifier, the same as `cat` or `jq`. Anything else keeps today's
refusal, and the reason names the first write-like token found.

## Root cause

Reproduced in-process on `main` through the whole PreToolUse hook (`wuwei.commands.hook.run`)
in a temporary workspace with a day `state.json`, under `observe`, `guarded` and `strict`:

| Command | Today, every posture |
|---|---|
| `python3 -c "import json,sys; print(json.load(open('.wuwei/state.json'))['day'])"` | exit 2, `Opaque interpreter; use the wuwei CLI for state changes.` plus `posture: records = block (floor; no setting lowers it)` |
| the same read of `.wuwei/days/<day>/state.json` | exit 2, same reason |
| `python3 -c "open('.wuwei/days/<day>/state.json', 'w')"` | exit 2, same reason (no token named) |
| `python3 -c "from pathlib import Path; Path('.wuwei/days/<day>/state.json').write_text('x')"` | exit 2, same reason (no token named) |
| `python3 -c "import json; print(open('notes.txt').read())"` | exit 0, no output |

In the code:

- `cli/wuwei/guards/protect_state.py:616-622` (`check_bash`): any interpreter command whose
  words match `_STATE_MENTION` (`.wuwei`, `state.json`, `events.jsonl` and the rest) is refused
  with exit 2 unless `shell.reads(command.argv)` is true. The records area always blocks, so
  no posture lowers it.
- `cli/wuwei/shell.py:876-892` (`reads`): the one shared read predicate knows a single
  interpreter form, `python -m json.tool` (line 889). A `python -c <code>` call never reads, so
  a read-only snippet falls into the refusal above, and the refusal carries one fixed reason
  for reads and writes alike.
- The issue points at `_wuwei_action` and the readers list near line 208. `_wuwei_action`
  returns `None` for a `-c` call and is not involved; the readers list (`_owner_action`) and
  `_write_targets` (line 498) already route through the same `shell.reads`, so the fix there
  is the same one predicate.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A seat reads a state value with a python one-liner (Priority: P1)

A seat or the planner prints one key of a state file with `python3 -c`, the way it would
with `jq`. The hook lets it run with no refusal and no warning, in every posture.

**Why this priority**: it is the reported false refusal; reads of state are routine and the
refusal costs a rewrite every time.

**Independent Test**: pipe the acceptance command through the PreToolUse hook in a fixture
workspace under each posture; the exit is 0 and no `hook.refusal` or `guard.would_refuse`
event is written.

**Acceptance Scenarios**:

1. **Given** a workspace in any posture, **When** a seat runs
   `python3 -c "import json,sys; print(json.load(open('.wuwei/state.json'))['day'])"`,
   **Then** the hook exits 0 with no warning.
2. **Given** the same, **When** the snippet reads the day's
   `.wuwei/days/<day>/state.json` (opened with no mode, `'r'` or `'rb'`), **Then** the hook
   exits 0 with no warning.

### User Story 2 - A write snippet stays refused and says why (Priority: P1)

A snippet that can write keeps today's refusal (exit 2, records floor), and the reason now
names the first write-like token, so the seat sees what made it more than a read.

**Why this priority**: the records floor must not weaken; a named token makes the refusal
coaching instead of a wall.

**Independent Test**: `check_bash` on the write snippets returns exit 2 with the token in the
reason, in every posture.

**Acceptance Scenarios**:

1. **Given** a snippet with `open(path, 'w')` naming a state file, **When** it runs, **Then**
   it is refused (exit 2) and the reason names `'w'`.
2. **Given** a snippet with `Path(...).write_text(...)` naming a state file, **When** it runs,
   **Then** it is refused (exit 2) and the reason names `write_text`.
3. **Given** a snippet that imports the CLI in process (`from wuwei.commands import main;
   main([...])`) or calls `subprocess`, `os.system`, `shutil`, `os.replace`, **When** it
   names a state file, **Then** it is refused and the reason names that token; an owner
   action written this way keeps its `Opaque owner action` refusal.

### Edge Cases

- A snippet given in any other form (attached `-c<code>`, `-i`, `-m` other than `json.tool`,
  stdin, a heredoc, a script file) is not a reader and keeps today's refusal and reason.
- A shell redirect of a read snippet into a protected file (`> .wuwei/days/<day>/state.json`)
  is refused by the existing redirect check with that file's hint (exit 1); a redirect into an
  ordinary file passes, the same as `cat`.
- A read snippet whose `sys.argv` operand names a records file passes, the same as `cat` on
  that operand.
- A mode or name built at run time (string concatenation, `chr`, a value from `sys.argv`,
  the environment or stdin) is not seen by a token scan. This is the existing residual of
  design spec 4.5 (constructed names, a script with no state operand); the scan is aimed at
  ordinary writes, not at an adversary who already bypasses the state mention itself.
- A false positive (a dict key `'a'`, `str.replace`) keeps today's refusal with the token
  named; it never lets a write through.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `shell.reads` MUST return true for `python[ver]|pypy[ver] [-flags] -c <code>
  [args]`, flags limited to no-value letters, when `<code>` contains no write-like token.
- **FR-002**: The write-like tokens MUST include: an open mode string literal containing `w`,
  `a`, `x` or `+`; any identifier containing `write`, `remove`, `rename`, `replace`, `unlink`,
  `rmdir`, `mkdir`, `touch`, `truncate`, `chmod`, `chown`, `symlink`, `hardlink`; `os.link`,
  `os.open`, `os.fork`; `shutil`, `subprocess`, `system`, `popen`, `spawn`, `exec`, `eval`,
  `getattr`, `__import__`, `importlib`, `runpy`; and the CLI package word `wuwei` as an import
  or module name (not the `.wuwei/` directory or a `cli/wuwei/` path).
- **FR-003**: A `python -c` call refused by the records guard MUST give the reason
  `Opaque interpreter: <token> in the snippet is not a read; use the wuwei CLI for state
  changes.` with the first (leftmost) token found. Every other interpreter refusal keeps
  `Opaque interpreter; use the wuwei CLI for state changes.`
- **FR-004**: Exits and areas are unchanged: a refused snippet is exit 2 under the records
  floor in every posture; redirects, owner actions and every other guard decide as today.
- **FR-005**: The design spec 9.2 table and `tests/test_invariants.py` MUST carry an
  invariant for this rule (constitution, Workflow, #530).
- **FR-006**: `docs/site/security.md` MUST say that a read-only `python -c` snippet passes and
  a write-like token is named in the refusal.

### Key Entities

- **Write-like token**: the leftmost match of one closed pattern in `shell.py`; the empty
  string means the snippet only reads.

## Success Criteria *(mandatory)*

- **SC-001**: The issue's acceptance command exits 0 through the hook in observe, guarded
  and strict, with no refusal or warning event.
- **SC-002**: The `'w'` and `write_text` snippets exit 2 in every posture and their reasons
  contain `'w'` and `write_text`.
- **SC-003**: Every existing protect_state, shell and invariant test passes, the one exact
  reason assertion for a `-c` write updated to the new reason.

## Assumptions

- The orchestrator notes file named in the task (`notes/643-full.md`) did not exist; the issue
  text and the reproduction above are the inputs. The dry-run reproduction was a temporary
  fixture workspace, read-only.
- "Classified as a reader by the shell classifier" means `shell.reads`, the predicate the
  issue names and the state guard shares. `shell.classify` keeps marking any `-c` call as
  inline code (its `inline` flag feeds the #347 unparsed and #530 opaque warnings, which only
  apply to calls some guard already refused); changing that is out of scope.
- The issue's token list is extended with obvious writers and dynamic code (`write` in any
  identifier, `mkdir`, `touch`, `exec`, `eval`, `getattr`, `__import__`, the CLI import). Making
  python `-c` a reader also makes `_owner_action` skip it, so a snippet that runs the CLI in
  process must never count as a read; any false positive only keeps today's refusal.
- "No redirect" is met by the existing redirect check: `command.writes` is checked against
  protected paths for every command, readers included. A read snippet redirected into an
  ordinary file passes, as `cat` does.
- The refusal stays exit 2 (could not read it as a read) rather than exit 1, so existing exit
  expectations and the records floor line are unchanged.
- Flag letters accepted before `-c` are the no-value ones `B E I O P S d q s u`; `-i`, `-W`, `-X`
  and anything else make the call not a reader.

## Deferred

- None.
