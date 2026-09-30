# Tasks: command vocabulary and session-per-thread over headless Claude Code

**Input**: `specs/065-remote-vocabulary/spec.md`, `specs/065-remote-vocabulary/plan.md`

**Tests**: required (constitution IV). Each test task is written, run with
`python -m pytest -q <file>` and seen failing for the stated reason before its
implementation task starts.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency)
- **[Story]**: US1 parse and vocabulary, US2 gate and read-only commands, US3 sessions

Shared test fixture for `tests/test_remote.py` (new file): a workspace like
`tests/test_listen.py::case` (`WUWEI_WORKSPACE`, `WUWEI_NOW=2026-09-30T12:00:00+00:00`,
memory files, `.wuwei/config.toml` with `[owner] name = "Robin Example"`), day state seeded
with `state._write_state(lambda d: None, reserved=False)`, `SLACK_OWNER_DM_CHANNEL=D1`,
a fake transport (`dm(text, *, root=None)` appends to `sent`, returns `Result(0)`), a fake
runtime (`headless(prompt, session, tools, *, root=None)` appends the call, runs an
optional side effect such as writing and routing a valid decision from
`wuwei decision template`, returns the next scripted `Result`), and
`event(ident, text, channel='D1')` building an inbox row.

## Phase 1: Setup

- [X] T001 Test isolation, `tests/conftest.py`: in the autouse fixture add
  `monkeypatch.delenv('SLACK_OWNER_DM_CHANNEL', raising=False)`. Run the full suite: still
  green.

## Phase 2: Foundational (headless adapter)

- [X] T002 [US3] Test, `tests/test_runtime.py`: replace `adapter.subprocess.run` in
  `adapters.runtime.claude` (as the Codex tests do) and assert for `headless`:
  (a) a start passes argv exactly `['claude', '-p', '--output-format', 'json',
  '--permission-mode', 'dontAsk', '--allowedTools', 'Read,Glob']`, the prompt as
  `input`, `cwd` the workspace root, and an `env` without `SLACK_BOT_TOKEN` when it was
  set; returns `Result(0, {'session_id', 'result', 'denials': ['Bash']})` for a payload
  with `permission_denials: [{'tool_name': 'Bash', 'tool_use_id': 'x', 'tool_input': {}}]`;
  (b) a resume appends `['--resume', <uuid>]`; a payload whose `session_id` differs is
  exit 2; (c) `is_error: true` or a nonzero return code with a valid payload is exit 1
  with data; (d) non-JSON stdout, a missing or non-UUID `session_id`, a denial without a
  `str` `tool_name`, `subprocess.TimeoutExpired`, and `FileNotFoundError` are exit 2 and
  the reason contains no stdout text; (e) an empty prompt, a non-UUID session, or a tool
  name with a space or comma is exit 2 without calling `subprocess.run`.
  Fails: `headless` missing.
- [X] T003 [US3] Implement, `adapters/runtime/claude.py`: `SESSION`, `TIMEOUT`,
  `headless` with the ponytail comment, as plan.md section 1. T002 passes; the adapter
  contract and core boundary tests in `tests/test_adapters.py` still pass.

## Phase 3: User Story 1 - parse and vocabulary (P1)

- [X] T004 [US1] Test, `tests/test_remote.py`: `remote.parse` table:
  "plan" and "Plan today." -> `('plan', '')`; "status", "REPORT!" -> verbs;
  "stop all" -> `('stop', 'all')`; "stop 1a2b3c4d" -> `('stop', '1a2b3c4d')`;
  "run daily-brief" -> `('run', 'daily-brief')`; "ask What  changed Today?" ->
  `('ask', 'What changed Today?')`; "cloud repo fix it" -> `('cloud', '')`;
  `None` for "run rm -rf", "planet", "plan: x", "ask", "stop 1a2b", "status please",
  "rm -rf /", "approve D-1". Also every fixed line (`VOCABULARY`, `UNAVAILABLE`,
  `GUARDED`, `FAILED`) passes `outward.lint(text, 'D1', config)` with the fixture config.
  Fails: module missing.
- [X] T005 [US1] Implement, new `cli/wuwei/remote.py`: constants and `parse` (plan.md
  section 3). T004 passes.
- [X] T006 [US1] Test, `tests/test_remote.py`: `remote.dm` with `registry.load` patched to
  return a fake chat module whose `dm` carries a `__wrapped__` recording calls:
  (a) a clean text reaches `__wrapped__` once and returns its `Result`; no `drafts` key
  appears in state; (b) a text naming "Robin" returns exit 1 and calls nothing;
  (c) `security.outbound` patched to return `(1, 'outward: security.canary')` returns 1
  and calls nothing; (d) with `adapters.chat = "none"` the result is exit 2.
  Fails: `dm` missing.
- [X] T007 [US1] Implement, `cli/wuwei/remote.py`: `dm` and `TRANSPORT`. T006 passes.
- [X] T008 [US1] Test, `tests/test_remote.py`, `remote.handle` with the fakes:
  (a) acceptance "run rm -rf": returns 1, `sent == [VOCABULARY]`, the fake runtime was
  not called, no `remote.*` event and no state change; (b) "hello there" -> vocabulary,
  1; (c) "run daily-brief" and "cloud repo fix it" -> `UNAVAILABLE`, 1, nothing runs;
  (d) an event with `channel='C9'` -> 0, nothing sent; (e) with
  `control_plane.pending` patched to raise `ValueError`, "approve D-1" returns 2, prints
  `listen remote unmeasured`, and sends `FAILED`.
  Fails: `handle` missing.
- [X] T009 [US1] Implement, `cli/wuwei/remote.py`: `handle` steps 1 to 4 and the error
  wrapper, `_say` (plan.md section 3). T008 passes.
- [X] T010 [US1] Test, `tests/test_listen.py` (new tests only, existing ones untouched),
  with `SLACK_OWNER_DM_CHANNEL=D1` and `remote.handle` patched to record `(root, event)`
  and return 0: (a) a tick storing two DM events hands both, in order, once; a second
  tick hands nothing; `cursor(root)['handled'] == 2`; (b) with `remote.handle` raising
  `OSError` on the first call, the tick raises and `handled` is already 1; the next tick
  hands only the second event (at most once); (c) `responder.enabled = false` hands
  nothing and leaves `handled` unset; re-enabled, the next tick hands the stored event;
  (d) a cursor file with `"woken": 3` and no `handled` starts handing at line 3;
  (e) `"handled": -1` or `"handled": "1"` makes `cursor` raise `ValueError`.
  Fails: `listen.tick` never calls the handler.
- [X] T011 [US1] Implement, `cli/wuwei/listen.py`: `cursor` accepts `handled`; `tick`
  reads the inbox once, defaults `handled` to `woken`, saves before each
  `remote.handle(root, row)` (plan.md section 4). T010 and every existing
  `tests/test_listen.py` test pass.

## Phase 4: User Story 2 - the gate and read-only commands (P1)

- [X] T012 [US2] Test, `tests/test_remote.py`: (a) "status" returns 0 and sends exactly
  `status.line(status.snapshot(day)).removeprefix('WUWEI ')`, with no `WUWEI` in it; with
  `control_plane.content = "none"` it sends `An update is waiting in the workspace.`;
  (b) "report" writes today's `report.md` and sends `Report 2026-09-30: merged 0, open 0,
  parked 0, decisions answered 0.` (seed one merged item to see `merged 1`);
  (c) "plan today", "ask what changed", "stop all", "stop 1a2b3c4d" each return 1, send
  `GUARDED`, append one `remote.pending` event `{'id': <event id>, 'command': <verb>}`
  and never call the runtime; no event payload contains the message text;
  (d) with a pending routed decision D-1 and no remote session, "option B on D-1"
  appends `decision.replied {'id': 'D-1', 'option': 'B'}`, sends
  `Recorded D-1 option B. Confirm it on the host.`, returns 0, and
  `decision_outcomes` is unchanged; (e) with a live remote row whose `decisions`
  contain D-1, the same reply appends `decision.replied` and `remote.pending
  {'command': 'reply'}`, sends `GUARDED`, and calls no runtime.
  Fails: status, report and reply branches missing.
- [X] T013 [US2] Implement, `cli/wuwei/commands/status.py`: extract `line(data)`; `run`
  prints it (output unchanged, existing status tests pass).
- [X] T014 [US2] Implement, `cli/wuwei/remote.py`: the decision-reply branch,
  `owner_session`, the `EXECUTABLE` gate with `remote.pending`, and the `status` and
  `report` execution in `handle` step 5. T012 passes.

## Phase 5: User Story 3 - one thread, one headless session (P1)

- [X] T015 [US3] Test, `tests/test_remote.py`: `remote.DENIAL.format(session='1a2b3c4d',
  tool='Bash')` passes `decision.evaluate` with Recommendation `A`, routes to `owner`
  (`decision.route`), and has a `Do nothing` option; `remote.deny` writes the next
  `D-n`, records it in `decision_routes`, and replaces a tool name with a newline or `|`
  by `a tool`. Fails: `DENIAL` and `deny` missing.
- [X] T016 [US3] Test, `tests/test_remote.py`, issue acceptance 1, with
  `monkeypatch.setattr(remote, 'EXECUTABLE', remote.EXECUTABLE | {'plan', 'reply'})`:
  "plan today" (event id `D1/1.000001`) calls the runtime once with `(PLAN_PROMPT, None,
  [*planner tools from agents/allowlist.json, 'Skill'])`; the fake routes D-1 during the
  call and returns session `S` (a UUID); state `sessions[S]` has role `remote`, thread
  `D1/1.000001`, command `plan`, decisions `['D-1']`; one `remote.started` event; `sent`
  holds the escalation of D-1 (control-plane summary render plus `HELP`) and then
  `Session <S[:8]>: turn ended, 1 decisions waiting.`. Then "option B on D-1" calls the
  runtime with `('Decision D-1: option B.', S, same tools)`, appends `decision.replied`
  and `remote.resumed {'session': S}`, and the row keeps its thread.
  Also: a routed decision whose Question names "Robin" is not sent; the fixed
  `D-n is waiting in the workspace.` is. Fails: `start` and `resume` missing.
- [X] T017 [US3] Test, `tests/test_remote.py`, issue acceptance 3: the fake returns
  `denials: ['Bash']`; after `remote.start` a new owner-routed decision exists whose
  Question names `Bash`, it is escalated, and it is in the row's `decisions`, so
  "option A on D-n" (gate widened) resumes the same session.
  Fails: denials ignored.
- [X] T018 [US3] Test, `tests/test_remote.py`: (a) a runtime `Result(2, reason='x')`
  returns 2, registers nothing, emits no `remote.started`, sends `FAILED`; (b) a
  `Result(1, data)` (is_error) still registers the session and returns at least 1;
  (c) "ask what changed" (gate widened with `ask`) calls the runtime with
  `ASK_PROMPT + 'what changed'` and `['Read', 'Glob', 'Grep']`, notifies the result,
  and when the result names "Robin" sends `The answer is held in session <S[:8]>; open it
  on the host.` instead. Fails: `_turn` branches missing.
- [X] T019 [US3] Test, `tests/test_remote.py`: `remote.stop` with two live remote rows and
  one adhoc row: a unique 8-character prefix stops one (`stopped` set, one
  `remote.stopped {'sessions': [id]}` event, `Stopped 1 sessions.` sent); an ambiguous
  or unknown prefix returns 1, writes nothing, sends `No single session matches <p>.`;
  `all` stops the remaining remote row and never the adhoc one; a later
  "option B on D-1" for a stopped session's decision records `decision.replied`, sends
  the "Confirm it on the host" line and calls no runtime. Fails: `stop` missing.
- [X] T020 [US3] Implement, `cli/wuwei/remote.py`: `DENIAL`, `deny`, `tools`, `start`,
  `resume`, `_turn` (with its two ponytail comments), `stop`, and the `plan`, `ask`,
  `stop`, `reply` execution in `handle` (plan.md section 3). T015 to T019 pass.

## Phase 6: Reserved kinds, docs, polish

- [X] T021 [P] Test, `tests/test_remote.py`: for each of `remote.pending`,
  `remote.started`, `remote.resumed`, `remote.stopped`: `main(['event', kind]) == 1`,
  stderr names `wuwei listen`, and `kind in signal.SILENT`. Fails: kinds not silent and
  producer unnamed.
- [X] T022 Implement, `cli/wuwei/commands/event.py` (`EVENT_PRODUCERS`, plus
  `decision.replied` naming the listener), `cli/wuwei/state.py`
  (`STATE_PRODUCERS['sessions']`), `cli/wuwei/signal.py` (`SILENT`). T021 passes.
- [X] T023 [P] Docs, `docs/site/configuration.md`: "Commands from the owner DM" under
  "Running the listener" and the `responder.enabled` row, as plan.md section 6. Run
  `python -m pytest -q tests/test_docs.py`.
- [X] T024 Run `python -m pytest -q` from the repository root: everything passes, no
  existing test changed. Check every file written for em-dashes, emojis and absolute local
  paths and remove any.

## Phase 7: Review fixes

- [X] T025 Test, `tests/test_remote.py`: a send whose Slack id (`D1/<ts>`) polls back into
  the inbox is not handled as a command; `handle` replies exactly once. Implement,
  `cli/wuwei/remote.py`: `dm` keeps the last 200 sent ids in `.wuwei/inbox/sent.json`
  and `handle` returns 0 for an event whose id is among them (review F1: a reply sent
  with `SLACK_USER_TOKEN` is authored by the owner).
- [X] T026 Test, `tests/test_runtime.py`: the headless argv passes `--tools` with the same
  list as `--allowedTools`. Implement, `adapters/runtime/claude.py` (review F2, built-in
  tools only; MCP scoping and planner `Bash` scoping stay with #66).
