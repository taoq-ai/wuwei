# Tasks: Session registry: several Claude Code sessions in one workspace, with one planner

**Input**: `specs/260-session-registry/spec.md`, `specs/260-session-registry/plan.md`

**Tests**: required (constitution IV). Each test task is written, run with
`python -m pytest -q <file>` and seen failing for the stated reason before its
implementation task starts.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency)
- **[Story]**: US1 registry and listing, US2 one planner, US3 item claims, US4 remote rows

## Phase 1: Setup

- [X] T001 Test isolation, `tests/conftest.py`: in the autouse fixture add
  `monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)` and
  `monkeypatch.delenv('CLAUDE_ENV_FILE', raising=False)` so a developer's session never
  leaks into claims or the env export.

## Phase 2: Foundational (registry module and config key)

- [X] T002 [US1] Test, new `tests/test_sessions.py` (fixture `root`: `WUWEI_WORKSPACE`,
  `WUWEI_NOW=2026-09-30T10:00:00+00:00`, `.wuwei/config.toml` empty, day state seeded with
  `state._write_state(lambda d: None, reserved=False)`):
  (a) `sessions.record` inserts `{'role': 'adhoc', 'started', 'last_seen', 'cwd',
  'last_hook'}` and a second call with a later `WUWEI_NOW` moves only `last_seen` and
  `last_hook`; (b) `record` with `role='bogus'`, `session_id=''` or `sessions` not an
  object raises `ValueError`; (c) `sessions.rows` derives `planner` from
  `planner_session_id`, computes `age_seconds`, `idle_seconds`, `stale` against the given
  threshold, lists claimed `items`; (d) `sessions.touch` with no today `state.json`
  returns None and creates no file; with one, appends exactly one `session.seen` event;
  (e) `sessions.stale_seconds` returns the config value and 3600 by default.
  Fails: module missing.
- [X] T003 [US1] Implement, `cli/wuwei/workspace.py`: `"sessions": {"stale_seconds": (int,
  3600, 1)}` in `SCHEMA`.
- [X] T004 [US1] Implement, new `cli/wuwei/sessions.py`: `ROLES`, `current`,
  `stale_seconds`, `record`, `touch`, `rows` as in plan.md. T002 passes.

## Phase 3: User Story 1 - every session visible (P1)

- [X] T005 [US1] Test, `tests/test_sessions.py`, hook level through
  `wuwei.commands.hook.run` with a SessionStart payload on stdin (base payload from
  `tests/payloads/SessionStart/recorded.json`, `cwd` set to the workspace):
  (a) two SessionStart payloads with session ids `A` and `B` then `main(['sessions'])`
  prints two rows with role `adhoc` and `last_hook` `SessionStart:<source>`; after
  `main(['plan', 'session', 'A'])` row A has role `planner`;
  (b) SessionStart adds exactly one state event (`session.seen`) and no other;
  (c) SessionStart with `CLAUDE_ENV_FILE` pointing at a `tmp_path` file appends
  `export WUWEI_SESSION_ID=A`; an id with a space is written shell-quoted;
  (d) SessionStart with no today `state.json` creates none and still exports the id;
  (e) a Stop payload for A and a SubagentStop payload for A (`agent_type`
  `Explore`, so the retro guard for `wuwei:` seats does not refuse) each move A's `last_seen` and set `last_hook` to `Stop` and
  `SubagentStop:Explore`, and change no other state key;
  (f) Stop and SubagentStop with a `cwd` outside any workspace write nothing;
  (g) `main(['sessions'])` with no day state prints `[]` and exits 0; with an unreadable
  `state.json` exits 2.
  Fails: no registration, no `sessions` command.
- [X] T006 [US1] Test, `tests/test_guard_mutation.py`: `PROBES` row
  `('lifecycle', 'SubagentStop', None, 'subagent_stop'): ('Bash', {}, 'message')`. Inert
  until T007 registers the guard; then
  `test_disabling_guard_makes_its_probe_red[lifecycle.SubagentStop.subagent_stop]` must
  pass, and `test_every_registered_guard_has_a_mutation_probe` fails if the row is missing.
- [X] T007 [US1] Implement, `cli/wuwei/guards/lifecycle.py`: `_seen`, the SessionStart
  registry and export block, Stop reusing the written state, new `subagent_stop` guard and
  its `GUARDS` entry, as in plan.md.
- [X] T008 [US1] Implement, `cli/wuwei/guards/__init__.py`: `MODULES['lifecycle']` gains
  `'SubagentStop': None`.
- [X] T009 [US1] Implement, new `cli/wuwei/commands/sessions.py`: the `sessions` command.
  T005 passes.
- [X] T010 [US1] Test, `tests/test_sessions.py`: with sessions A and B registered,
  `main(['status', '--line'])` output contains `sessions 2` and `status --json` has
  `"sessions": 2`; advancing `WUWEI_NOW` past `stale_seconds` for A only gives
  `sessions 1` and A's row `stale: true`; with no registered session the line has no
  `sessions` part. Fails: no count.
- [X] T011 [US1] Implement, `cli/wuwei/commands/status.py`: `snapshot` count and `run`
  line part, placed before `reply`/`meeting`. T010 passes.

## Phase 4: User Story 2 - one planner (P1)

- [X] T012 [US2] Test, `tests/test_sessions.py`:
  (a) `plan session A` then `plan session B` exits 2, stderr names `A` and `--take-over`,
  `planner_session_id` stays `A`, `events.jsonl` unchanged;
  (b) `plan session B --take-over` exits 0, `planner_session_id` is `B`, last
  `plan.session` payload is `{'session_id': 'B', 'previous': 'A'}`;
  (c) `plan session A` twice exits 0 both times with no `previous`;
  (d) after the take-over, a planner wake (seed `watch` state as
  `tests/test_watch.py::test_only_registered_planner_consumes_wake` does, or write
  `watch.wake` with `state._write_state(..., reserved=False)`) is not consumed by
  `lifecycle.stop` for A and is consumed by B;
  (e) `plan session B --take-over` with no planner registered behaves as plain
  registration (no `previous`).
  Fails: second registration exits 0 and overwrites.
- [X] T013 [US2] Implement, `cli/wuwei/plan.py` `session(..., take_over=False)` and
  `cli/wuwei/commands/plan.py` `--take-over`, as in plan.md. T012 passes.
- [X] T014 [US2] Update, `tests/test_stop.py::test_planner_handoff_does_not_exempt_original_session`:
  the second registration becomes `['plan', 'session', 'replacement', '--take-over']`; the
  assertions stay (the original planner is still anchored).
- [X] T015 [US2] Test, `tests/test_sessions.py`: with planner A registered and A's
  `last_seen` older than `stale_seconds`, `main(['nudges'])` lists one row with source
  `session.planner_stale` whose reason names `A` and `wuwei plan session <session id>
  --take-over`; with A live, or with no registry row for the planner, no such row; the row
  is counted in `status --json` `nudges`. Fails: no row.
- [X] T016 [US2] Implement, `cli/wuwei/commands/status.py` `scan`: the stale planner row.
  T015 passes.

## Phase 5: User Story 3 - item claims (P2)

- [X] T017 [US3] Test, `tests/test_brief.py` (existing `day` fixture):
  (a) with `WUWEI_SESSION_ID=A`, `brief builder X b1` exits 0, `claims.X == 'A'`, the
  `brief written` payload has `session: 'A'`, and A has a registry row;
  (b) then with `WUWEI_SESSION_ID=B`, `brief builder X b2` exits 2, stderr names `A`, no
  `briefs/b2.md`, no new event;
  (c) with A's row made stale by advancing `WUWEI_NOW`, B's brief succeeds and
  `claims.X == 'B'`;
  (d) with no `WUWEI_SESSION_ID` and a live claim by A, `brief builder X b3` exits 2;
  with no claim, it exits 0 and records no claim;
  (e) a sentinel gate brief for X from B is not refused by the claim (it may still be
  refused by existing gate rules; assert the stderr does not name the claim).
  Fails: no claim.
- [X] T018 [US3] Implement, `cli/wuwei/sessions.py` `claim` and `cli/wuwei/brief.py`
  `write` wiring, as in plan.md. T017 passes.
- [X] T019 [US3] Test, `tests/test_worktree_command.py` (existing `fake` fixture plus a
  `repos` config): with a live claim on `ITEM-1` by A in state and
  `WUWEI_SESSION_ID=B`, `worktree add ITEM-1` exits 2 naming `A` and `adds(vcs) == []`;
  with `WUWEI_SESSION_ID=A` it creates the worktree and appends `item.claimed`; the gate
  refusal test still makes no claim write (no `item.claimed` event). Fails: no check.
- [X] T020 [US3] Implement, `cli/wuwei/sessions.py` `claim_item` and the call in
  `cli/wuwei/workspace.py` `create_worktree` after the gate check. T019 passes.

## Phase 6: User Story 4 - remote rows (P3)

- [X] T021 [US4] Test, `tests/test_sessions.py`, hook level: `sessions.touch(root, 'R',
  hook='remote start', cwd=str(root), role='remote', thread='slack:D1/1')`, then a Stop
  payload for `R` through `wuwei.commands.hook.run`; `main(['sessions'])` shows role
  `remote` and thread `slack:D1/1`; `touch(..., role='planner')` raises and leaves
  `state.json` and `events.jsonl` unchanged. Record and touch already carry role and thread
  (T002, T004); this pins the Stop path (T007) not dropping them.

## Phase 7: Producer-only, silence and polish

- [X] T022 Test, `tests/test_state_allowlist.py`: rows `('sessions', 'wuwei hook
  SessionStart')`, `('sessions.A.role', 'wuwei hook SessionStart')`, `('claims', 'wuwei
  brief builder')` in `test_nonallowlisted_state_paths_refuse_without_write`; rows
  `('session.seen', 'wuwei hook SessionStart')`, `('item.claimed', 'wuwei worktree add')` in
  `test_nonfree_events_refuse_without_append`. Fails: producer names absent (the write is
  already refused by default-deny; the message names "its dedicated command").
- [X] T023 Implement, `cli/wuwei/state.py` `STATE_PRODUCERS` and
  `cli/wuwei/commands/event.py` `EVENT_PRODUCERS` entries. T022 passes.
- [X] T024 Test, `tests/test_sessions.py`: after a SessionStart, Stop and `worktree`-style
  `sessions.claim_item`, `main(['nudges'])` prints `[]` (registry events are silent).
  Fails: `session.seen` and `item.claimed` classify as nudges.
- [X] T025 Implement, `cli/wuwei/signal.py` `SILENT`: add `session.seen` and
  `item.claimed`. T024 passes.
- [X] T026 [P] Docs, `templates/workspace/config.toml` (`[sessions]` with
  `stale_seconds = 3600`), `docs/site/configuration.md` (row), `docs/site/reference.md`
  (`## Sessions` section and the `sessions N` sentence in `## Watch state`),
  `skills/wuwei-plan/SKILL.md` line 10 (`--take-over` when resuming in a new session).
  Run `python -m pytest -q tests/test_docs.py tests/test_skill_evals.py` and fix any
  schema-coverage assertion.
- [X] T027 Full suite: `python -m pytest -q` from the repository root; all green, including
  `tests/test_hooks.py` (MODULES pin, SessionStart, Stop and SubagentStop latency) and
  `tests/test_state_allowlist.py::test_reader_inventory_cannot_be_written_generically`.
  Grep every written file for em-dashes and emojis.
- [X] T028 Review fix, `tests/test_sessions.py`: a `sessions.touch` fault in SessionStart
  returns code 2 with the `session registry unmeasured` line. Fails: the memory block
  overwrote the code. Implement `cli/wuwei/guards/lifecycle.py`: `code = max(code, ...)`.

## Dependencies

T001 first. T002 to T004 before everything else. US1 (T005 to T011) before US2's nudge
(T015) and US3 (claims read `rows`). T012 to T014 independent of US3. T022 to T025 after the
kinds exist. T026 and T027 last.
