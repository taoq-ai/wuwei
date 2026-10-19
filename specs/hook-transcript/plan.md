# Implementation Plan: an owner answer and a seat stop are recorded only when the session transcript shows them

**Branch**: `fix/hook-transcript` | **Spec**: `specs/hook-transcript/spec.md`

## Summary

The hook stops trusting its payload for the two records G-1 rests on. An owner answer is kept
until the session transcript shows the AskUserQuestion and its answer row, then recorded as today.
A seat stop is recorded only when the harness's meta file and the session transcript show the
launch. The guards refuse writes under the harness's projects folder.

## Technical Context

Python 3.11 stdlib (`pathlib.Path.resolve(strict=True)`, `is_relative_to`, `pwd`). Tests in
tests/test_hook.py, tests/test_guards.py and the tests that answer owner questions or stop seats
(test_breaking, test_codex, test_models, test_plan, test_report, test_view), with two conftest
helpers that write the transcript rows a real flow has. Runtime cap 3,400 lines; base 5a33509 is
at 3,178.

## Constitution Check

- I. Stdlib only: yes (`pwd` is stdlib on the platforms WUWEI runs on; `O_NOFOLLOW` already ruled
  out Windows).
- III. An auditor: the guard refusal extends the records door to the harness's transcripts, which
  the trust ruling names; no new class of door.
- IV. The owner decides only what matters: the trust model is the owner's ruling of 2026-10-19.
- V. Test first: the new tests ran red on base code (223 in test_hook.py, 255 in test_guards.py).
- VI. Budgets: no config key; runtime 3,178 to 3,251 (see Lines).
- VII. Security first: never simplify away a trust-boundary check; the transcript check is one.

## Design

- `ws.PROJECTS`: `.claude/projects` in the account's home from `pwd.getpwuid(os.getuid())`, never
  `HOME` or `CLAUDE_CONFIG_DIR`, which a hand-made call sets.
- `hook.transcript_rows(path, key)`: `Path(path).resolve(strict=True)` must be a regular file
  under `ws.PROJECTS.resolve()`; returns the JSON rows of the lines naming `key`, else None. Any
  OSError, TypeError, ValueError (a bad line, a NUL) or RuntimeError (a link loop) is None.
- `hook.parts(rows, kind)`: the content parts of one type in those rows.
- PostToolUse on AskUserQuestion: `kept = {id, path, answers, questions}`. A path that is not a
  transcript records `answer.unconfirmed` at once and returns a note. Else `kept` goes to the
  cache as `answer-<session>--<id>.json`.
- `hook._shown(kept)`: '' when the rows naming the id hold an AskUserQuestion tool_use with it and
  the last row with a tool_result for it carries `toolUseResult.answers` equal to the kept answers;
  else the reason.
- `hook._confirm(root, session, final)`: for each kept answer of the session, rereads until shown
  or, at a Stop, for up to `WAIT` (1.5) seconds in 0.1 s steps; an unshown one waits for a later
  call unless `final`. The hook claims an entry by `unlink`; the loser of a race skips it. Then
  `_answers(root, kept)` (the rows and notes as today) or `_unconfirmed`.
- `deliver` calls `_confirm` on every planner call it already handles (PreToolUse, PostToolUse,
  Stop, no `agent_id`), and joins the notes with the kept seat reports.
- SubagentStop: `agent_transcript_path` must be named `agent-<agent_id>.jsonl`; the
  `agent-<id>.meta.json` beside it (under `ws.PROJECTS`) gives `agentType`, compared with the
  payload's type after its plugin prefix, and `toolUseId`; the session transcript must hold a
  tool_use with that id named Agent or Task. Else `seat.unconfirmed` and return.
- `hook.running` subtracts `seat.unconfirmed` agents, so an unconfirmed stop never silences the
  Stop reminder for the day.
- `guards.records(path, below, cap, name)` takes the folder name; `guards.harness(path)` is
  `records(path, ('projects',), cap, '.claude')`. `guards.bash` refuses a redirect target or a
  writer argument it matches, and any writer or file redirect after `cd`/`pushd` into it, with a
  session directory in it, or with a `-C`, `--chdir` or `-D` value naming it. The edit tools refuse
  a path it matches. The reason (`HARNESS`) names the read routes.

## Lines

hook.py +60 (the transcript reader, the deferred confirmation with its claim and wait, the seat
launch check, the docstrings), guards.py +11, ws.py +2: runtime 3,178 to 3,251, under the 3,400
cap. The item's budget is 22. See the spec's Assumptions.

## Guard testing (AGENTS.md)

- Route corpus `tests/fixtures/routes.json` through `guards.bash` and the PreToolUse hook at main
  and at the head, with its sha256 (probe_differential.py and compare.py), listing moved routes.
- `write_probe.py`: generated writes (writers x path spellings x wrappers, and working-directory
  wrappers x local writes) and reads, run under real bash with a scratch HOME, at main and at the
  head. Counts generated, landed, refused and holes. The path classes `//`, `%xx`, `/./`, `/../`
  and the wrappers `cd`, `pushd`, `env -C`, `--chdir`, `sudo -D` (when sudo exists) are classes.
- `entry_probe.py`: each forge-door shape run for real under bash against the head's hook entry,
  with a forged answer and a forged seat stop, counting the shapes that ran the entry (a row in
  the scratch ledger) and any ruling, prompt, `seat.stopped` or attestation (holes).
- No parser change: segments and the door words are untouched, so no command becomes unreadable.
  The checks that do not rely on door words (leak, infrastructure) are read with the new shapes
  in the differential.
