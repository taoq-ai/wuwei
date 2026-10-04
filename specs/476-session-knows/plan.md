# Implementation Plan: the session knows the whole plugin at start

**Branch**: `476-session-knows` | **Date**: 2026-10-04 | **Spec**: `spec.md` | **Issue**: #476

## Summary

Two outputs from one set of tables. A static reference (`wuwei.guide.text()`) is generated
from the CLI's own tables and written once into the `memory.export_to` file by `init` and
`init --upgrade`, through the managed-block writer that `memory.export` already has
(extracted, not copied). A short dynamic part is added to the existing SessionStart
orientation: the plan or report skill's numbered steps read from the skill file, or nothing
beyond the Next line. Drift shows up through the doctor's existing `template` row because
`init --upgrade --dry-run` reports a stale guide block; the existing `init-upgrade` fix
rewrites it. The conformance run is a start mode of the existing opt-in headless runner.

## Technical Context

Python 3.11+, stdlib only (`hashlib`, `re`, `argparse`, `pkgutil`). Tests: pytest, in
process, `tmp_path` workspaces, the recorded SessionStart payload in
`tests/payloads/SessionStart/recorded.json`, the `root` and `calibrated` helpers of
`tests/test_next.py`, the `hook` helper pattern of `tests/test_cli_known_command.py` for
PreToolUse replay, the `evidence()` pattern of `tests/test_headless_e2e.py` for the
validator. No network, no real Claude in the suite.

## Constitution Check

- I stdlib only: yes.
- II exits: `wuwei guide` exits 0 (it reads no input that can fail; an unexpected error is
  exit 2 through `__main__._call`); the guide write fails closed through the existing
  `init --upgrade` handler (exit 2 with the reason); a skill read failure at SessionStart is
  one "steps unmeasured" line, never a crash and never a silent omission.
- III one behaviour one function: block writing in `memory.write_block`; reference text in
  `guide.text`; block assembly and writing in `guide.export`; steps in `next.steps`.
- IV test first: `tasks.md` orders every test before its code.
- V ponytail: no new config key (the block shares `memory.export_to`), no new doctor row or
  fix, no second exporter, no new hook import; the conformance mode reuses `validate`.
- VII security: the block is outside `.wuwei/`, written only by the CLI; the export path
  checks of #443 (relative, no `..`, not under `.wuwei`, no symlink) apply unchanged. The
  guide holds no workspace data and no absolute path.
- Hook latency (#346): SessionStart reads at most one skill file and only in states `plan`
  and `close`; `wuwei.guide`, `argparse`, `pkgutil` and `hashlib` are never imported on a
  hook path.

## Changes

### `cli/wuwei/memory.py` (shared block writer, FR-003)

Extract the second half of `export` (lines 141-149 path checks and 169-185 marker handling)
into:

```python
def write_block(root, start, end, block, fix, write=True, raw=None):
    """Put block (start marker through end marker, newline-terminated) into the file
    memory.export_to names, replacing the one block between start and end, keeping all other
    text. fix: the command named when the markers are damaged. (path, changed)."""
```

Behaviour is the current one: same path validation and messages, same marker refusal with
the `fix` command in place of the hard-coded `bin/wuwei memory export --claude`, same
replace or append, `atomic_write(..., mode=0o644)` only when `write` and the content
changed. `write_block` runs the path checks first, before it reads the file. `export(root)` keeps
building its lines and ends with
`return write_block(root, EXPORT_START, EXPORT_END, block, 'bin/wuwei memory export --claude')`.
The only order change: `export` now reads the charters before the path is checked, so a
workspace with both a bad `export_to` and a symlinked charters directory reports the
charters first; both still exit 2. No other change to `memory.py`.

### `cli/wuwei/guide.py` (new: the reference, FR-001, FR-004)

```python
START, END = '<!-- wuwei:guide:start -->', '<!-- wuwei:guide:end -->'
WIDGETS = ('decision show D-n --widget', 'mcp check --widget', 'doctor --fix --widget',
           'close --widget', 'consolidate --widget', 'telemetry proposals --widget',
           'plan gate', 'calibrate --questions')
RECORDS = (...)   # the rows of today's agent.md "Where each record lives" table

def text(): ...            # the reference, a pure function of the tables, read at call time
def export(root, write=True): ...   # block = START, stamp, text(), END; memory.write_block
```

`text()` builds the full parser the way `__main__._main` does (an `ArgumentParser`, then
`register` of every non-private module from `pkgutil.iter_modules(commands.__path__)`) and
reads the one-line help from `subparsers._choices_actions` as `__main__._help` does. Do not
refactor `__main__` (it is the hot entry path). Layout, all lines generated from the named
source; headings are `##` so the text sits under agent.md's own title:

1. One line: what this is and that `wuwei guide` prints it; `wuwei next` gives the step.
2. `## Commands the session runs`: one line, `next.EXECUTABLE` plus the exit contract stated
   once (0 clean, 1 findings to resolve with the owner, 2 could not run: show the reason and
   stop that path); then `- <name>: <help>` for every name in the GROUPS headings starting
   `Daily` and `Recovery`, in GROUPS order; then one line `Read-only, never refused:` with
   `commands.READ_ONLY` sorted (`calibrate` rendered with its `commands._NEEDS` flag) and
   "and --help on any command".
3. `## Owner only: ask the owner to run these in a host terminal`: one line, the
   `protect_state._OWNER_ACTIONS` keys rendered `group verb` (verb may be empty), sorted.
4. `## Command forms`: one plain command per Bash call; `shell.UNPARSED` and
   `shell.WORKSPACE_ROOT` with their `unparsed: ` and `workspace guard: ` prefixes cut;
   Python only with `-P`.
5. `## Records and questions`: `protect_state._STATE_HINT`; the records rule (the workflow
   writes records through the CLI, the owner answers cards and never edits a file); the ask
   rule (AskUserQuestion with the widget a command prints, unchanged: `wuwei <w>` for each of
   `WIDGETS`; record with the widget's `record` command; without AskUserQuestion,
   `wuwei decision route D-n` sends it to the DM).
6. `## Guard areas by posture`: a Markdown table, one row per `workspace.AREAS` entry, one
   column per `workspace.POSTURES` key, cells from `POSTURES`; one line naming the
   `workspace.FLOORS` areas as floors and the owner-only actions as blocked in every posture;
   one line "A refusal names its reason and the accepted form: use that form."
7. `## Where records live`: a Markdown table from `RECORDS`.

Target about 75 lines; the test caps the block (stamp and markers included) under 100.

`export(root, write=True)`: `body = text()`; stamp line
`<!-- generated by wuwei init from the plugin tables: plugin <integrity.version()>, tables
<sha256(body)[:12]>; edits here are overwritten -->` (one line); block
`'\n'.join([START, stamp, body.rstrip('\n'), END]) + '\n'`; returns
`memory.write_block(root, START, END, block, 'bin/wuwei init --upgrade', write)`.

### `cli/wuwei/commands/guide.py` (new, FR-002)

`register`: `subparsers.add_parser('guide', help='Print the plugin reference the session
reads at start')`; `run`: `print(guide.text(), end='')`, return `CLEAN`.

### `cli/wuwei/commands/__init__.py`

Add `'guide'` to `READ_ONLY` (the #348 one-set test requires every registered path in
exactly one set).

### `cli/wuwei/__main__.py`

Add `guide` to the Daily group string right after `next`. Nothing else.

### `cli/wuwei/commands/init.py` (FR-005)

- `run` (new workspace): after `os.rename(staging, destination)` and before the
  `Created ...` print, `path, _ = guide.export(destination.parent)`; print
  `Guide: <path relative to the workspace> block written`. An error propagates to
  `__main__._call` (exit 2 with the reason), as other post-rename failures do.
- `upgrade` (built: `guide.export` and `write_block` take `raw`, the repaired config text, so a
  `repos = []` workspace still upgrades): inside the existing `try`, after the charter loop,
  `guide_path, guide_changed = guide.export(destination.parent, write=False)`; when not
  dry-run and `guide_changed`, `guide.export(destination.parent)`; print
  `f'{prefix} {relative path}: guide block'` when `guide_changed`; add `not guide_changed`
  to the "No workspace changes needed" condition. The existing `ValueError`/`OSError`
  handler turns a bad `export_to` or damaged markers into exit 2 with the reason.
- Import `guide` locally in both functions (init is not on a hook path, but keep the module
  import list as is).

### `cli/wuwei/commands/doctor.py`

No code change. The `template` row (lines 233-243) already counts every `Would upgrade`
line of `init --upgrade --dry-run` and applies `init-upgrade`, which now rewrites the block.

### `cli/wuwei/commands/next.py` (FR-007, FR-008, FR-009)

- `EXECUTABLE = 'wuwei is the absolute path in .wuwei/executable: read it once and use it as
  the first word of a plain command, never through a variable'`; the owner/session line of
  `orientation` uses it (text unchanged) and `guide.text()` reuses it.
- `step()` decision row command: `f'wuwei decision show {identifier} --widget'`.
- `steps(skill)`: read `integrity.PLUGIN / 'skills' / skill / 'SKILL.md'`; return the first
  sentence of every line matching `^\d+\. ` (`re.match(r'(\d+\. .+?\.)(?=\s|$)', line)`,
  falling back to the whole line); on `OSError` or `UnicodeError` return
  `[f'steps unmeasured: {exc}; read {path}']`. `ponytail:` comment: first sentence only to
  keep SessionStart short; the skill path carries the full step.
- `orientation(row, posture, spec=None, session=None)`: the seat branch is unchanged. For a
  non-seat session the old entry line is replaced by:
  - state `plan`: `Start the day now; no command needed. Steps (full text:
    <plugin>/skills/wuwei-plan/SKILL.md):`, then `- Register this session as the planner:
    wuwei plan session <session or "<session id>"> (add --take-over when it names another
    planner)`, then `steps('wuwei-plan')`, then `Do this now.`;
  - state `close`: `The day is closable. Steps (full text:
    <plugin>/skills/wuwei-report/SKILL.md):`, then `steps('wuwei-report')`, then
    `Do this now.`;
  - any other state: nothing.
  The last line becomes `Reference: wuwei guide (every command, the accepted forms and the
  rules; the same text is the guide block in the memory.export_to file); run wuwei next
  when the next step is unclear; owner guide: <plugin>/docs/site/daily.md`.
- `re` is already loaded on the hook path by `workspace`; add `import re` at the top.

### `cli/wuwei/guards/lifecycle.py` (session_start only)

Pass the payload's session id to `orientation`: `session=payload.get('session_id') if
isinstance(payload.get('session_id'), str) and payload['session_id'].strip() else None`.
Do not touch `subagent_stop` (#473 edits it in parallel).

### `scripts/headless_e2e.py` (FR-010)

- `start_prompt()`: "Start the day." plus the fixture owner's answers in plain words: the
  owner approves `proposal.json` as supplied (goals G-1, queue A, CAP 1, seat policy,
  envelope) and it is the lead proposal (no discovery); a headless run asks nothing; this
  fixture publishes nothing, so when item A's gates pass, park A with the decision in
  `park.md` as today's D-1; then close the day. No skill name, no numbered step, no `wuwei`
  subcommand, no CLI path.
- `conformance(events, hooks)`: one finding per `hook.refusal` event (its reason); one per
  `cli` hook row whose `args` contain `--help` or `-h`; one per PreToolUse Bash row whose
  `input.command` words contain `--help` or `-h`.
- `validate(data, events, hooks, start=False)`: when `start`, skip the refusal-probe, the
  explicit plan-skill and the scripted Stop-block requirements, and require one successful
  `close` row instead; append `conformance(events, hooks)`.
- `exercise(*, local_login=False, start=False)` picks the prompt and passes `start`;
  `main` gains `--start`.

### Docs (FR-011)

- `docs/site/agent.md`: title, a three-line intro (every SessionStart points at
  `wuwei guide`; this page prints the same text), the existing Roles section, then the guide
  block between `<!-- wuwei:guide:start -->` and `<!-- wuwei:guide:end -->` holding exactly
  `guide.text()` (no stamp). The hand-written sections the reference replaces go: day in
  order, what the hooks refuse, where each record lives, how the owner answers, first day.
- `docs/site/daily.md`: section 1 ends with "Then open Claude Code in the workspace and say
  what you want; the session knows the rest."
- `docs/site/configuration.md`: the `memory.export_to` row adds "and the generated guide
  block (`init`, `init --upgrade`)".
- `docs/site/reference.md`: a `bin/wuwei guide` row in the Commands table.
- `docs/headless-e2e.md`: one paragraph on `--start` (what it gives the session and what it
  asserts).

### Tests that change with the new contract

- `tests/test_next.py`: `test_orientation_block` swaps the agent.md and `/wuwei:wuwei-plan`
  phrases for `wuwei guide`, `Do this now.` and the skill path; `test_orientation_seat_entry`
  asserts `Do this now.` instead of "Start or resume"; line 102 expects `--widget`;
  `test_issue_acceptance_session_start_orients` asserts `wuwei guide` instead of agent.md.
- `tests/test_docs.py`: `test_agent_guide_ships_and_is_linked` asserts the agent.md block
  equals `guide.text()` and keeps the phrases the reference carries (`wuwei next`,
  `.wuwei/executable`, `-P`, `host terminal`, `first word of a plain command`, the role
  names from the Roles section); drop the `3. Morning gate` agent.md assertion in
  `test_one_gate_question` and the `specify first` agent.md assertion in
  `test_charters_carry_the_spec_mode` (the skill, charters and daily.md keep pinning both).
- `tests/test_workspace.py` and `tests/test_doctor.py`: an upgrade of a workspace built
  without `init` now also reports the guide block; where a test asserts "No workspace
  changes needed", write the block first with `guide.export(root)` in its setup.

## What must not change

- The rules block (`<!-- wuwei:memory:start -->`) content and its callers (`memory export`,
  `promote`, `consolidate`); their error messages keep naming `memory export --claude`.
- `next.step()` rows other than the decision command; `wuwei next` output format.
- The hook path import set (`tests/test_hooks.py` pins it): no `wuwei.guide`, `argparse`,
  `pkgutil` or `hashlib` import from SessionStart.
- `lifecycle.subagent_stop`, `stop`, `pre_compact`.
- `skills/wuwei-plan/SKILL.md` and `skills/wuwei-report/SKILL.md` (read, never restructured).
- The scripted headless day (`prompt`, `validate` with `start=False`) and the rehearsal.
- Doctor rows and fixes.

## Project Structure

```text
cli/wuwei/guide.py               new
cli/wuwei/commands/guide.py      new
cli/wuwei/memory.py              write_block extracted
cli/wuwei/commands/init.py       guide block on init and upgrade
cli/wuwei/commands/next.py       EXECUTABLE, steps, orientation, decision --widget
cli/wuwei/commands/__init__.py   guide in READ_ONLY
cli/wuwei/__main__.py            guide in the Daily group
cli/wuwei/guards/lifecycle.py    session id to orientation
scripts/headless_e2e.py          --start, conformance
docs/site/{agent,daily,configuration,reference}.md, docs/headless-e2e.md
tests/test_guide.py              new
tests/test_next.py, tests/test_memory.py, tests/test_headless_e2e.py, tests/test_docs.py,
tests/test_workspace.py, tests/test_doctor.py
```
