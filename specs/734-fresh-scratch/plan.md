# Implementation Plan: a seat starts from an empty scratch directory and checks only a clean copy

**Branch**: `734-fresh-scratch` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

Three small changes at the spots every seat already passes through: a move-aside before the
existing `mkdir` in `brief.write`, one sentence pair in `charters/_common.md` rule 2 (then
`agents build`), and one stderr warning at the end of `dispatch.receive`. One clause changes
in the `Scratch:` brief line, one docs row is extended.

## Technical Context

Python 3.11+ stdlib only (`pathlib`, `re`, `datetime`). pytest dev-only. No new module, no new
config key, no new event kind, no state field, no port operation, no guard.

## Constitution Check

- I stdlib: yes.
- II exits: `wuwei brief` keeps its exits; a failed `rename` is an `OSError`, exit 2 with the
  reason. `dispatch receive` keeps its exits: the warning never changes the code; an
  unparseable `Written:` in a WUWEI-written brief is exit 2 (damage), as for any unreadable
  record.
- III one behaviour one function: the workspace scratch directory is still made in one place
  (`brief.write`); the copy rule has one home (`_common.md` rule 2); the stale check is one
  private function in `dispatch.py`.
- IV test first: `tasks.md` orders each test before its change.
- V simplicity: no host-scratchpad discovery, no `agent_launch` change, no event, no state
  record of moved directories, no charter text naming how to make the copy.
- VII security: nothing new refuses. The warning reads a seat-written verdict and only
  advises; it is never trusted to pass or fail anything. No 9.2 invariant (no guard or
  decision rule changes).

## Design

### cli/wuwei/brief.py

1. `write`, the `Scratch:` header line (lines 424-426): replace `create it if missing and write
   every temporary file there` with

   ```python
   header.append(f'Scratch: <your scratchpad>/{item}/{role}/, or {scratch}/ when your host names '
                 'no scratchpad; create it if missing, or move it aside with a timestamp suffix '
                 'when it holds files you did not write, and write every temporary file there, '
                 "never at the scratchpad root or in another item's directory")
   ```

   The #647 test's assertions (`startswith`, the workspace path, `write every temporary file
   there`) still hold.

2. `write`, the last lines (line 586): replace `scratch.mkdir(parents=True, exist_ok=True)` with

   ```python
   if scratch.is_dir() and any(scratch.iterdir()):  # #734: a new seat never inherits files
       # ponytail: one move per timestamp; a fixed WUWEI_NOW moving twice is an OSError (exit 2)
       scratch.rename(scratch.with_name(f'{role}.{workspace.now():%Y%m%dT%H%M%S.%f}'))
   scratch.mkdir(parents=True, exist_ok=True)
   ```

   It stays after the brief and its event are written (the #647 placement), so a refused brief
   moves nothing. `rename` on a symlink moves the link, not its target. The moved directory is
   a sibling under `.wuwei/scratch/<item>/`, so `pr_actions.observe` (lines 232-234) removes it
   with the item, and `protect_state.check_scratch` keys on the item component and treats it
   as the same item.

### charters/_common.md

Rule 2 of `## Evidence and gates` (line 18), right after the sentence `Mutate only a whole-tree
detached copy at that sha in scratch, never the builder's worktree.`, insert:

> Make every copy of the tree you check, this one or a probe's, in a new, empty directory under
> your brief's `Scratch:` directory, never in one that already exists. Before any check in a
> copy, compare its file list with `git ls-tree -r --name-only <sha>`, list each extra file in
> the verdict and check only a copy without extras.

Bump the frontmatter `version: 1.9.0` to `1.10.0`. Then regenerate the checked-in agents from
the repository root with `WUWEI_WORKSPACE` unset: `python3 -P -m wuwei agents build` (with
`cli` on `PYTHONPATH`, as `bin/wuwei` sets it) or `bin/wuwei agents build`. All nine
`agents/*.md` change (every agent carries `_common.md`).

Not changed: `charters/sentinel-*.md`. The issue names them, but the detached-copy rule
already lives in `_common.md` rule 2, which every sentinel reads, and
`test_charter_sentences_have_one_home` forbids a second copy. The charter names no command for
making the copy: `git archive` is an unknown git subcommand to the deploy guard
(`cli/wuwei/shell.py:635-655`), a refusal under strict.

### cli/wuwei/dispatch.py

1. Module level, next to the imports:

   ```python
   # #734: a scratch path in verdict text, workspace-relative or absolute, maybe with :<line>
   SCRATCH_PATH = r'[^\s`\'"()<>\[\]{},;|]*(?:scratchpad|\.wuwei/scratch)/[^\s`\'"()<>\[\]{},;|]+'
   ```

2. A private helper above `receive`:

   ```python
   def _stale_scratch(text, brief_text, root):
       """#734: scratch paths the verdict names that existed before its seat's brief was written."""
       from datetime import datetime
       written = re.search(r'^Written: (\S+)$', brief_text, re.M)
       if not written:
           return []
       since = datetime.fromisoformat(written[1]).timestamp()
       stale = []
       for token in dict.fromkeys(re.findall(SCRATCH_PATH, text)):
           path = Path(root) / re.sub(r'(:\d+)+$', '', token.rstrip('.:'))
           try:
               # ponytail: ctime, since tar sets mtime to the commit time; a stale file the seat
               # rewrote reads as new, which is right: its content is the seat's
               if path.stat().st_ctime < since:
                   stale.append(token)
           except OSError:
               continue  # not on disk: nothing to date
       return stale
   ```

   `Path(root) / absolute` is the absolute path, so both forms resolve.

3. `receive`: compute `stale = _stale_scratch(text, brief_text, root)` right before
   `state._write_state(update, ...)`, so an unparseable `Written:` (exit 2) records nothing, and
   print after the write, before the return (changed in build from calling it after the write):

   ```python
   stale = _stale_scratch(text, brief_text, root)
   state._write_state(update, ...)
   for cited in stale:
       print(f"warning: {name}'s verdict names {cited}, which existed before its brief was "
             "written; its check may have read an earlier seat's files: rerun it in a new, "
             'empty directory', file=sys.stderr)
   ```

   `text` is the active verdict text (after the scanner merge for an agent-surface item, which
   adds no scratch paths); `brief_text` is already read at line 657. `opinion` returns through
   `receive`, so second-opinion verdicts are covered.

### docs/site/reference.md

The `Scratch directory` row (line 310) becomes:

> Each brief names `<your scratchpad>/<item>/<role>/`, or `.wuwei/scratch/<item>/<role>/` when
> the host names no scratchpad, for every temporary file. `wuwei brief` creates the workspace
> one empty: one that holds files is moved aside to `<role>.<timestamp>`. A gate makes every
> copy of the tree in a new, empty directory there and lists each file `git ls-tree` does not
> have before its checks. `wuwei dispatch receive` warns when a verdict names a scratch path
> older than the seat's brief. An observed merge removes `.wuwei/scratch/<item>/`. A seat's
> Write into another item's directory prints a warning naming its own under observe and
> guarded, and is refused under strict (area `seats`).

## What must not change

- `guards/agent_launch.py`: no change (Claude-only, runs on continues too).
- `protect_state.check_scratch`, `_SCRATCH`, `pr_actions.observe` cleanup: unchanged; the
  moved directory is under the same item.
- The `Scratch:` line's two paths and its `write every temporary file there` and
  `never at the scratchpad root or in another item's directory` wording.
- `receive`'s refusals, exits, recorded value and events: the warning is stderr only.
- `charters/sentinel-*.md`: unchanged.

## Files

- `cli/wuwei/brief.py`: the header clause, the move-aside.
- `cli/wuwei/dispatch.py`: `SCRATCH_PATH`, `_stale_scratch`, the warning in `receive`.
- `charters/_common.md`: the copy rule, version bump; `agents/*.md` regenerated.
- `docs/site/reference.md`: the row.
- `tests/test_brief.py`, `tests/test_charters.py`, `tests/test_dispatch.py`: one test each.
