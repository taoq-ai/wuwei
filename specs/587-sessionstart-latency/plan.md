# Implementation Plan: SessionStart under 75 ms wall on the runner

**Branch**: `587-sessionstart-latency` | **Date**: 2026-10-08 | **Spec**: `spec.md`

## Summary

Remove work from the SessionStart path without touching what it measures: the imports the
session block does not need (`shutil`, `tempfile`, `uuid`, `calendar`, `wuwei.decision`,
`wuwei.cruise` and what they pull), one re-read of the day state, and the second thread that
makes the two SessionStart guards take turns on one interpreter lock. The integrity
measurement (every installed file hashed, `ssh-keygen`, two Git reads, its records) stays
whole. Root cause and figures: `spec.md` and `research.md`.

## Technical Context

Stdlib-only Python 3.11+ runtime; pytest dev-only. The latency job runs Python 3.12 on a
2-CPU `ubuntu-latest` runner. This host is shared and loaded: judge by CPU, with the
interleaved method below; read the runner wall from the job artifact on the pull request.

## Constitution Check

Test first per behaviour; stdlib only; exits unchanged; no new refusal under observe or
guarded (#530); no planner action changes (#551, SessionStart keeps calling `next.step`
only); no budget, margin, probe, run count, fixture or job setting loosened (#346, #562);
no guard or decision rule changes, so the 9.2 invariant table and `tests/test_invariants.py`
stay as they are. Pass.

## Method (binding)

1. Baseline before the first edit: `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k
   "workspace_hook_latency and SessionStart" -s` (keep CPU, wall, floor and load), and
   `python3 -X importtime` plus cProfile over 60 runs as #346 did.
2. Interleaved A/B for each cut, in a scratch test outside the repository that imports the
   `seeded_workspace` fixture: copy the fixture plugin to a second directory, apply the cut
   to the copy, run `integrity.write_manifest` and sign it with the fixture key (remove the
   old `.sig` first), then run SessionStart alternately on both copies 60 times with
   `reset()` before each run, dropping the first two. Report CPU median and p95, wall median
   and p95, and assert the same `additionalContext`. Keep a cut only when its CPU median
   drops and its wall p95 does not rise.
3. PR body: the before and after figures of steps 1 and 2 and of the latency job artifacts
   (`latency.jsonl` of the last green main run and of the pull request). No absolute local
   path in any file.

## Changes

### 1. Shared modules import their heavy helpers where used (FR-001)

- `cli/wuwei/promotion.py`: delete `import shutil` and `from uuid import uuid4` (lines 6-7);
  add `from uuid import uuid4` inside `_cruise_write` (line 76), `_snapshot` (143) and
  `promote` (322), and `import shutil` inside `_snapshot`. `last_run` (344) and the rest
  are unchanged.
- `cli/wuwei/digest.py`: delete `from calendar import monthrange` (line 3); import it inside
  `period` (line 15), its only user.
- Why here and not in `memory.py`: every caller of `last_run` and `latest` (SessionStart,
  `memory export`, status) pays for imports the readers never use; one change at the
  shared spot fixes them all.

### 2. `answered` only where decision routes are read (FR-002)

- `cli/wuwei/commands/next.py`: delete line 8; in `step`, import
  `from wuwei.decision import answered` on the line before `pending = [...]` (line 212).
  No test patches `next_command.answered` (checked).
- `cli/wuwei/memory.py` `constraints` (line 100): read `routes = data.get('decision_routes',
  {})`; import `answered` only when `routes` is not empty; `open_ids` from `routes`.

### 3. ssh adapter without `shutil` and `tempfile` (FR-003)

`adapters/integrity/ssh.py`:

- Imports: `os`, `pathlib.Path`, `subprocess`, `Result`. No `shutil`, no `tempfile`.
- `_installed()`: true when any `os.path.join(d, 'ssh-keygen')` for `d` in
  `os.get_exec_path()` is a file with `os.access(..., os.X_OK)`. `verify` raises
  `FileNotFoundError('ssh-keygen')` when it is false, at the same place as today (before the
  manifest and signature checks), so `ssh-keygen` absent with a missing manifest is still
  exit 2.
- Allowed signers: `directory = Path(os.environ.get('TMPDIR') or '/tmp') /
  f'wuwei-{os.urandom(8).hex()}'`; `os.mkdir(directory, 0o700)` (fails if it exists); write
  the one line through `os.open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o600)`
  (the `workspace.atomic_write` pattern; `atomic_write` itself is not reused because it
  renames and syncs, which this throwaway file does not need); run `_run` as today; in a
  `finally`, unlink the file if present and remove the directory. Every existing `except`
  clause and reason stays.
- `sign` is unchanged.

### 4. One day state read fewer (FR-004)

`cli/wuwei/guards/lifecycle.py` `session_start`: keep `day = None` before the registry
`try`; set `day = _seen(root, payload, 'SessionStart')` there (as `stop` does at line 146);
at line 69 read `day = state.read_state(root) if day is None else day`. The constraints, the
decision branch and the output use that `day` as before. On a registry error `day` stays
`None` and the later read runs as today.

### 5. SessionStart guards in turn (FR-005)

`cli/wuwei/commands/hook.py` lines 84-90: delete the SessionStart branch, so
`outcomes = map(outcome, selected)` for every event; replace the #346 comment with one line:
guards run in order; the integrity guard overlaps its own children with its hashing. Output
order, the HEADER sort at line 126 and every result check stay.

### 6. Docs (FR-007)

`docs/site/reference.md` line 451, last sentence: the SessionStart guards run in turn; the
integrity guard runs its Git and `ssh-keygen` children while it hashes the installed files;
on two CPUs two Python guards on two threads only take turns on the interpreter lock; a day
without decision routes reads its events once and its state twice. Budgets and the CI job
text are unchanged.

## Tests (test first; each fails before its change)

- `tests/test_hooks.py`: `run_launcher(..., printed=False)` gains a keyword that skips its
  empty-stdout assert. New `test_session_start_loads_only_what_it_prints(seeded_workspace,
  tmp_path)`: two `run_launcher` runs of `SessionStart` (the second warm), assert none of
  `shutil`, `tempfile`, `bz2`, `lzma`, `random`, `uuid`, `calendar`, `wuwei.decision`,
  `wuwei.cruise`, `wuwei.novelty` is loaded. Fails today on every name but `wuwei.novelty`.
- `tests/test_hooks.py`: `test_session_start_guards_run_together_in_guard_order` becomes
  `test_session_start_guards_run_in_guard_order`: the barrier goes; each installed guard
  records `threading.current_thread() is threading.main_thread()` and the order it ran in;
  assert both ran on the main thread, first before second, and the same
  `'first\nValueError: second failed'` output. Fails today (the second guard runs on a
  worker thread).
- `tests/test_sessions.py`: new `test_session_start_reads_the_day_state_twice(root,
  monkeypatch)`: wrap `state.read_state` with a counter of calls that resolve to today's
  `state.json`, run the SessionStart hook through the file's `hook` helper, assert 2
  (`next.step` and the registry write). Fails today with 3.
- `tests/test_integrity.py`: the three `monkeypatch.setattr(adapter.shutil, 'which', ...)`
  lines (95, 123, 130) patch `adapter._installed` instead (same truth values). New
  `test_verify_leaves_no_signers_file(tmp_path, monkeypatch)`: `TMPDIR` set to an empty
  directory; `verify` with a stubbed `subprocess.run` returning 0, then 1, then raising
  `TimeoutExpired`; after each the directory is empty, the stub saw a `-f` path inside it,
  and the exits are 0, 1 and 2. Fails today only on the attribute name (`_installed`), so
  write it first against the new name.
- Unchanged and run: `tests/test_memory.py`, `tests/test_next.py`, `tests/test_promotion.py`,
  `tests/test_digest.py`, `tests/test_sessions.py`, `tests/test_integrity.py` (real
  `ssh-keygen` roundtrip included), `tests/test_hooks.py`.

## Shared helpers reused

`registry.together` stays the integrity guard's overlap; `sessions.touch` return as in
`lifecycle.stop`; the exclusive-create pattern of `workspace.atomic_write`;
`LAUNCHER_MODULES`, `run_launcher` and `seeded_workspace` in `tests/test_hooks.py`; the
`hook` helper and `root` fixture in `tests/test_sessions.py`.

## What must not change

The budgets in `tests/test_hooks.py` (50 ms CPU, 100 ms wall workspace, 200 ms heartbeat),
`assert_latency_budget`, `startup_floor`, the probe fixtures and run counts, the margins in
`scripts/latency_report.py`, the latency job; the SessionStart `additionalContext` text and
line order; every guard result, refusal and exit; the integrity measurement (every file
hashed, the signature verified, both Git reads, both verdict records with their syncs); the
session registry write; the events decode that health validates; `next.step` output;
`registry.together` and its test.

## Files

- `cli/wuwei/promotion.py`, `cli/wuwei/digest.py`, `cli/wuwei/commands/next.py`,
  `cli/wuwei/memory.py`, `adapters/integrity/ssh.py`, `cli/wuwei/guards/lifecycle.py`,
  `cli/wuwei/commands/hook.py`, `docs/site/reference.md`
- `tests/test_hooks.py`, `tests/test_sessions.py`, `tests/test_integrity.py`

No `MANIFEST.sha256` is checked in; the release writes and signs it, so changing
`adapters/` and `cli/` needs no manifest step here.
