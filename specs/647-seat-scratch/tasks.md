# Tasks: a scratch directory per seat

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process: fakes for the VCS and code host, no network, no git, no real
subagent. Paths come from `tmp_path`. Run only the touched test files, then the full suite
with `python -m pytest -q` from the repository root.

## Phase 1: the brief names and creates the seat's directory (FR-001, FR-002, US1)

- [X] T001 Test in `tests/test_brief.py`: with fixture `day`, `brief(monkeypatch, 'body',
  'builder', 'X', 'sx')` and `brief(monkeypatch, 'body', 'builder', 'Y', 'sy')` both exit 0;
  each brief has exactly one line starting `Scratch: <your scratchpad>/X/builder/` (resp.
  `Y/builder/`) that also names `.wuwei/scratch/X/builder/` (resp. `Y`) and contains
  `write every temporary file there`; the two lines differ; `day[0] / '.wuwei/scratch/X/builder'`
  and `.../Y/builder` are directories. The unresolved-ruling refusal (`per D-ABC-9`) leaves no
  `.wuwei/scratch/X`. Fails: no `Scratch:` line today.
- [X] T002 Add `SCRATCH = '.wuwei/scratch'` to `cli/wuwei/workspace.py`; in
  `cli/wuwei/brief.py` `write`, append the `Scratch:` line after `Seat policy:` and
  `mkdir(parents=True, exist_ok=True)` the directory just before `return relative`.

## Phase 2: one subagent-transcript helper (FR-003)

- [X] T003 Test in `tests/test_traces.py`: `brief.subagent_transcript` returns None for a
  payload without `agent_id` and for one with `agent_id` and an empty `transcript_path`,
  raises `ValueError` naming `invalid agent_id` for `agent_id: ''`, and returns
  `<parent of transcript_path>/<session_id>/subagents/agent-<id>.jsonl` otherwise.
  `brief.seat_of` returns the seat whose `brief` equals the transcript's `WUWEI brief:`
  reference, and None when the transcript file is missing. Fails: no such functions.
- [X] T004 Add `subagent_transcript` and `seat_of` to `cli/wuwei/brief.py` next to
  `transcript_reference`; replace the inline derivation in `cli/wuwei/guards/traces.py`
  `check` (lines 104-112) with `brief.subagent_transcript(payload)`. The existing subagent
  cases in `tests/test_traces.py` and `tests/test_hooks.py` stay green.

## Phase 3: the guard warns below strict (FR-004, US2)

- [X] T005 Test in `tests/test_protect_state.py`: a fixture helper writes today's state
  (`WUWEI_NOW=2026-09-28T12:00:00+00:00`) with items `A` and `B`, seat `b-a` (`role`
  `builder`, `item` `A`, `brief` `.wuwei/days/2026-09-28/briefs/b-a.md`, `status` `running`)
  and a subagent transcript at `<workspace>/fixture/subagents/agent-x.jsonl` whose first line
  is a `user` row with content `WUWEI brief: .wuwei/days/2026-09-28/briefs/b-a.md`. Through
  `wuwei.commands.hook.run(SimpleNamespace(event='PreToolUse'))` with a Write payload carrying
  `agent_id: 'x'`, parametrized over posture `observe`, `guarded`, `strict` and base
  `<workspace>/.wuwei/scratch` or `<tmp_path>/scratchpad`:
  a Write to `<base>/B/x.sh` exits 0, no stdout, stderr one line starting
  `warning: scratch:` that names `<base>/A/builder/` (observe, guarded); exits 2 with that
  reason and `posture: seats = block (set security.areas.seats)` in stderr (strict).
  Silent (exit 0, empty stdout and stderr) under guarded: `<base>/A/x.sh`, the same Write
  without `agent_id`, `<base>/notes/x.sh`, and `agent_id: 'missing'` (no transcript).
  Fails: the hook is silent for every case today.
- [X] T006 Add `check_scratch` and its `Guard('PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit',
  check_scratch)` entry (and `import sys`) to `cli/wuwei/guards/protect_state.py`; add
  `'protect_state.check_scratch': 'seats'` to `AREAS` in `cli/wuwei/guards/__init__.py`.
  `tests/test_posture.py::test_guard_areas_table` and the existing
  `test_discovered_guards_through_hook` cases stay green.

## Phase 4: the directory goes with the confirmed merge (FR-005, US3)

- [X] T007 Test in `tests/test_pr_actions.py`: with `linked(case)`, files
  `.wuwei/scratch/A/builder/x` and `.wuwei/scratch/B/builder/y` under the workspace root,
  `host.results['pr'].data.update(state='closed', merged=True)` and `main(['pr', 'state'])`:
  item `A` is `merged`, `.wuwei/scratch/A` does not exist, `.wuwei/scratch/B/builder/y` does.
  A second `pr state` with no scratch directory left exits as before. Fails: the directory
  stays today.
- [X] T008 In `cli/wuwei/pr_actions.py` `observe`, collect the names moved to `merged` and,
  after `state._write_state`, `shutil.rmtree(root / workspace.SCRATCH / name,
  ignore_errors=True)` each, with the `ponytail:` comment on the host scratchpad.

## Phase 5: docs and the full suite (FR-006)

- [X] T009 Add the `Scratch directory` row to the table under "Seat briefs and the build
  loop" in `docs/site/reference.md` and the `protect_state.check_scratch` mention to the
  `seats` row in `docs/site/security.md`; run `tests/test_docs.py` (the posture table test
  reads only the level columns).
- [X] T011 Review F1: in `cli/wuwei/guards/protect_state.py` exempt `.wuwei/scratch/` from
  `_STATE_MENTION` and `_STATE_GLOB` unless the path climbs out with `..`, so a seat can run
  `python3` or `bash` on a script it saved there. Test first in `tests/test_protect_state.py`.
- [X] T010 Run `python -m pytest -q`; check every file written for em-dashes, emojis and
  absolute local paths.
