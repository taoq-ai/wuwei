# Tasks: every subagent launched in a workspace is traced as a seat

**Input**: `specs/676-trace-every-agent/spec.md`, `specs/676-trace-every-agent/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Tests build untyped payloads in-process on the `day` fixture from `tests/test_brief.py`
(observe or strict set with `[security]\nposture = "..."` in its `config.toml`).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Shared helpers

- [X] T001 [US1] In `tests/test_brief.py`, test `brief.first_prompt` (a transcript whose
  first user row is a str, one whose content is a list of text parts, one with no user row:
  None), `brief.prompt_digest` (equal for a prompt with and without surrounding
  whitespace), and `brief.adhoc_seat` (bound seat wins; else the oldest running adhoc seat
  with the digest and no session; a stopped seat, another digest or a brief seat never
  match). Run; fails with AttributeError.
- [X] T002 [US1] In `cli/wuwei/brief.py`, add `first_prompt`, `prompt_digest` and
  `adhoc_seat` as in plan.md, sharing the content extraction with `transcript_reference`
  without changing it. T001 passes.

## Phase 2: User Story 1, an untyped agent is an auditable seat (P1)

### Tests first

- [X] T003 [US1] In `tests/test_agent_launch.py`, under observe and guarded, a
  `general-purpose` launch (and one with no `subagent_type`, and `Explore`) returns
  `(0, '')`, writes seat `adhoc-1` with `role adhoc`, `item adhoc-1`, `type` (missing type:
  `general-purpose`), `label` equal to the type, `launcher`, the redacted first prompt line,
  `prompt_sha256` and status `running`, and the last event is `seat launched` naming it. A
  second launch is `adhoc-2`. A blank prompt in a day is exit 2. Without today's
  `state.json` the launch returns `(0, '')` and creates nothing. Run; fails (no seat).
- [X] T004 [US1] In `tests/test_agent_launch.py`, rewrite
  `test_unrelated_agents_pass_before_parsing` and
  `test_default_general_purpose_agent_passes_before_validation` per plan.md (remove today's
  `state.json` first, keep the broken config and the missing prompt, still `(0, '')`).
- [X] T005 [US1] In `tests/test_traces.py`, with an adhoc seat registered from a prompt and a
  subagent transcript (at `<transcript dir>/<session>/subagents/agent-<id>.jsonl`) whose
  first user row is that prompt, a PostToolUse payload with `agent_id` and
  `agent_type: general-purpose` appends its span and puts `<session>:<id>` in the seat's
  `trace_sessions` and the transcript path in `transcript`. With no matching seat, or with
  no `state.json` today, the span is written, `state.json` is unchanged (or still absent)
  and no event is appended besides what the span path appends today. Run; fails (no
  binding).
- [X] T006 [US1] In `tests/test_agent_launch.py`, an untyped SubagentStop whose
  `agent_transcript_path` first user row is the seat's prompt stops the adhoc seat
  (`stopped`, `agent_id` recorded, `seat stopped` event) and returns `(0, '')`; a seat
  already bound to `<session>:<agent_id>` is the one stopped when two share the prompt.
  Run; fails (seat stays running).
- [X] T007 [US1] In `tests/test_why.py`, `wuwei why adhoc` with one adhoc seat prints one
  line naming `adhoc seat adhoc-1`, its type, prompt line and trace session, exit 0; with
  none it exits 1 naming how one is registered. Run; fails.
- [X] T008 [P] [US1] In `tests/test_watch.py` (beside
  `test_activity_tracks_launched_seat_worktree_from_brief`), a running adhoc seat with no
  brief does not raise
  `running seat needs one logged brief`. In `tests/test_memory.py`, the current briefs line
  leaves out an adhoc seat. Run; both fail.
- [X] T008a [P] [US1] In `tests/test_traces_seats_only.py`, a critical chain from session
  `P:a1` where a running adhoc seat holds `P:a1` in `trace_sessions` (P the planner) is one
  silent `traces.noted` with role `planner`, no `scanner.finding` and no decision file
  (#352 holds). Run; fails (the adhoc seat counts as a seat).

### Implementation

- [X] T009 [US1] In `cli/wuwei/guards/agent_launch.py`, add `_adhoc` and call it from
  `_check` where `seat is None` (plan.md steps 1 to 8, the refusal in step 6 included but
  exercised in Phase 3). T003 and T004 pass.
- [X] T010 [US1] In `cli/wuwei/guards/traces.py` `_record`, bind a subagent call with no
  brief reference to its adhoc seat by digest, writing state only on a match. T005 passes.
- [X] T011 [US1] In `cli/wuwei/guards/agent_launch.py`, add `_stop_adhoc` and route the
  untyped case of `stop` to it. T006 passes.
- [X] T012 [US1] In `cli/wuwei/commands/why.py`, add the `adhoc` target and `adhoc(root)`.
  T007 passes.
- [X] T013 [US1] In `cli/wuwei/watch.py:183` exclude adhoc seats from the brief check; in
  `cli/wuwei/memory.py:104` list only seats with a brief; in `cli/wuwei/scanner.py:71` skip
  adhoc seats in the seat test. T008 and T008a pass.
- [X] T014 [US1] In `tests/test_agent_launch.py`, the end-to-end acceptance test (SC-001):
  launch, PostToolUse through `traces.check`, `why adhoc`, SubagentStop, under observe.
  Passes with T009 to T013.

## Phase 3: User Story 2, strict refuses; seat start registers (P1)

### Tests first

- [X] T015 [US2] In `tests/test_agent_launch.py`, under strict an untyped launch returns
  exit 1 whose reason contains `bin/wuwei seat start --role <role> --adhoc` and writes no
  seat; with `security.areas.seats = "block"` under guarded the same; a WUWEI brief launch
  under strict is unchanged (the existing table covers it). Run; fails until T009's refusal
  is in place, or passes if T009 already added it: confirm it fails with the refusal line
  removed.
- [X] T016 [US2] In `tests/test_agent_launch.py` (built there: it shares the `day` fixture and the
  adhoc payload helpers),
  `main(['seat', 'start', '--role', 'reviewer', '--adhoc',
  prompt])` exits 0, appends `seat adhoc` with role, `sha256 == brief.prompt_digest(prompt)`
  and the redacted first line, and prints the launch instruction; an invalid role and a
  blank prompt exit 2; without today's state it exits 2 naming the morning plan. Then under
  strict the same prompt's launch passes and the seat has `label: reviewer`; another prompt
  is still refused. `seat stop adhoc-1 --verdict <file>` exits 1 naming `--unmeasured`.
  Run; fails (no `start` subcommand).
- [X] T017 [P] [US2] In `tests/test_next.py` (beside the reserved-kind check at line 222),
  `main(['event', 'seat adhoc', '{}'])` and `main(['event', 'subagent.untraced', '{}'])`
  exit 1 naming `wuwei seat start` and `wuwei hook SubagentStop`. Run; fails.

### Implementation

- [X] T018 [US2] In `cli/wuwei/commands/seat.py`, add the `start` subcommand and the
  `--verdict` refusal for adhoc seats. T016 passes (with T009).
- [X] T019 [US2] In `cli/wuwei/commands/event.py` add both producers; in
  `cli/wuwei/signal.py` add `seat adhoc` to `SILENT`; in
  `tests/test_signal_status.py::test_emitted_kinds_have_intended_tiers` add
  `'seat adhoc': 'silent'` and `'subagent.untraced': 'nudge'`. T017 passes.
- [X] T020 [US2] In `tests/test_invariants.py`, add `i38` (I36 is #636 on main) (per posture: `agent_launch.check`
  on a general-purpose launch with no record is `0` below strict and registers a seat, is
  `1` naming `seat start --adhoc` under strict, and `0` under strict after a `seat adhoc`
  record) to `INVARIANTS` and `READS` (`(0,)`); add the I38 row to design 9.2 in
  `docs/specs/2026-09-24-wuwei-design.md`. Run `test_invariants_hold` and
  `test_table_matches_the_checks`; they fail before the row and pass after.

## Phase 4: User Story 3, doctor names untraced subagents (P2)

- [X] T021 [US3] In `tests/test_agent_launch.py`, an untyped SubagentStop with today's state
  and no matching seat (and one with no `agent_transcript_path`) returns `(0, '')` and
  appends `subagent.untraced` with the agent type, id and a reason; without `state.json` it
  appends nothing. Run; fails until T011 records the event (confirm it fails with the event
  line removed if T011 already added it).
- [X] T022 [US3] In `tests/test_doctor.py`, `test_day_rows` lists `untraced subagents` after
  `traces` at `ok` (`none today`); with one `subagent.untraced` event today the row is
  `warn` naming the count and `seat start --role <role> --adhoc`. Run; fails.
- [X] T023 [US3] In `cli/wuwei/commands/doctor.py` `_day`, add the row after `traces`.
  T022 passes.

## Phase 5: Docs

- [X] T024 [P] `docs/specs/2026-09-24-wuwei-design.md` 4.1 hook table, `Agent` launch row:
  the strict refusal and the adhoc registration (plan.md Docs).
- [X] T025 [P] `docs/site/reference.md`: the adhoc seats paragraph in Stuck seats, the
  `untraced subagents` doctor row, the `adhoc` target in Why, the `bin/wuwei seat` table
  row. Run `tests/test_docs.py`; it passes.

## Phase 6: Verify

- [X] T026 Run the full suite (`python -m pytest -q` from the repository root with the
  interpreter the task names); all green. Grep the changed files for em-dashes, emojis and
  absolute local paths.
- [X] T027 Review fix round: rebase onto main (invariant renumbered to I38, #684's
  `subagent_transcript` and `seat_of` kept beside the adhoc helpers), add `seat start` to
  `commands.WRITES`, give the three new reasons a next step, and split the `why adhoc`
  docs sentence to stay within the tone budget. Run the full suite once.
