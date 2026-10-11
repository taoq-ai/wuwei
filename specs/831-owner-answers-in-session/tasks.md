# Tasks: the owner answers in the session, never in a terminal

**Input**: [spec.md](spec.md), [plan.md](plan.md). Part 9 (#814) is done on this branch first;
locate edits by name and text.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Never loosen a test: a test that pinned a terminal
prompt for a converted step is rewritten to pin the card.

## Phase 1: the card, the helper and the hook (US1, US2; FR-001, FR-002)

- [X] T001 [US1] Add `tests/fakes/owner.py` with `answer(root, command, token='', reply='Yes',
  session='planner-session', agent=None)`: build the question `Owner step: <command>[ (token)]`,
  call `wuwei.guards.decision.record_gate` with `{'cwd': str(root), 'session_id': session,
  'tool_name': 'AskUserQuestion', 'tool_input': {'questions': [{'header': 'Owner step',
  'question': question, 'options': [...]}]}, 'tool_response': {'answers': {question: reply}}}`
  (plus `agent_id` when `agent` is set) and return its result.
- [X] T002 [US1] `tests/test_card_confirms.py`, new tests. Run: red.
  - `test_needs_owner_names_the_card`: no answer returns a reason containing
    `Owner step: bin/wuwei plan set A owner_merge=false`, a JSON object with header
    `Owner step`, options `Yes` and `No` and `record` equal to the command, and no
    "host terminal".
  - `test_needs_owner_reads_the_recorded_yes`: after `answer(...)` it returns None; a `No`
    reply, another command or another token still returns the reason.
  - `test_a_seat_answer_records_nothing` (payload with `agent_id`).
  - `test_owner_answer_records_without_reading_state`: today's `state.json` holds `{` and
    `record_gate` still returns `(0, '')` and the answer counts.
  - `test_owner_answer_counts_under_strict`.
  - `test_gate_asked_is_reserved`: `main(['event', 'gate.asked', '{}'])` exits 1.
  - `test_owner_step_question_needs_no_citation`: `check_question` returns `(0, '')` for an
    Owner step question with no D-n.
- [X] T003 [US1] Code: `sessions.OWNER_STEP` and `sessions.needs_owner` (plan.md, Design);
  `record_gate` Owner step branch and `check_question` skip in `cli/wuwei/guards/decision.py`.
  Run `tests/test_card_confirms.py tests/test_sessions.py tests/test_decision.py
  tests/test_posture.py tests/test_guard_mutation.py`: green.
- [X] T004 [US2] `tests/test_protect_state.py`: `bin/wuwei hook PostToolUse`,
  `wuwei hook SubagentStop` and `python3 -P -m wuwei hook PreToolUse` give exit 2;
  `bin/wuwei next` gives `(0, '')`. Run: red.
- [X] T005 [US2] Code: the `wuwei hook` refusal in `protect_state.check_bash`. Run
  `tests/test_protect_state.py tests/test_hooks.py`: green.

## Phase 2: the seven call sites (US1; FR-003, FR-004)

- [X] T006 [US1] Rewrite the terminal cases in these tests to "no answer: exit 1, the reason
  names the Owner step card, nothing changes" and "`owner.answer(...)`: proceeds". Run each:
  red.
  - `tests/test_plan.py` (spec=skipped and owner_merge=false, near 480-565);
  - `tests/test_merge.py` (`set_owner_merge(..., 'false')`, near 1370);
  - `tests/test_state.py` (recover, near 650-710);
  - `tests/test_integrity.py` (reconfirm cases; keep the two `_host_confirm` unit tests);
  - `tests/test_doctor.py` (fix cases near 952 and 1283);
  - `tests/test_telemetry.py` (send, near 448);
  - `tests/test_handback.py` (seat stop under strict, near 365-375);
  - `tests/test_card_confirms.py` config set session and strict cases (plan.md list):
    in a session, outside one and under strict, no answer names the card and writes nothing;
    `owner.answer(root, 'bin/wuwei config set', <digest>)` writes it. Delete
    `test_config_set_in_a_host_terminal_prompts_as_today` and
    `test_strict_host_terminal_ignores_the_card_and_prompts`: the terminal path they pin is
    gone, and the new cases cover the step.
- [X] T007 [US1] Code: `plan.py:_owner_confirm` and its two callers; `commands/config.py:offer`
  (`command` kw, helper, help texts); `commands/setup.py:set_value` and `add_repo`;
  `integrity.py:reconfirm`; `state.py:recover` and `commands/state.py`; `commands/seat.py:run`;
  `commands/doctor.py:fix`; `commands/telemetry.py:_send` (plan.md, Callers converted). Run
  the files of T006 plus `tests/test_setup.py tests/test_config_transition.py
  tests/test_why.py tests/test_stop.py`: green.

## Phase 3: no text sends the owner to a terminal (US3; FR-006, FR-007)

- [X] T008 [US3] `tests/test_reasons.py`: add `TERMINAL = re.compile(r'host terminal|/dev/tty|
  \bon the host\b')`, the LEFT rows of plan.md as `(file, substring, part)`, and
  `test_no_text_sends_the_owner_to_a_terminal`: for every non-docstring string constant under
  `cli/wuwei` (reuse `_sources` and `_docstrings`), a TERMINAL match fails unless a LEFT row's
  file matches and its substring is in the text; then every LEFT row must match at least one
  constant. Run: red (the texts of plan.md, Texts rewritten).
- [X] T009 [US3] Code: rewrite the texts plan.md lists. Then update the tests that assert the
  old text (`tests/test_doctor.py`, `tests/test_integrity.py`, `tests/test_state.py`,
  `tests/test_workspace.py`, `tests/test_dispatch.py`, `tests/test_commit_push.py`,
  `tests/test_pr_guards.py`, `tests/test_shepherd.py`, `tests/test_build.py`, and any other
  failing file among those run), expected text only. In `tests/test_invariants.py` delete the
  OWNED rows plan.md names. Run `tests/test_reasons.py tests/test_invariants.py` and every
  test file edited here: green.

## Phase 4: governance and docs (FR-008)

- [X] T010 `charters/planner.md` rule 4 and the Owner step sentence; then
  `bin/wuwei agents build`. Run `tests/test_charters.py tests/test_tone.py`: green.
- [X] T011 `skills/wuwei-retro/SKILL.md` Owner step sentence; design spec 9.1 paragraph. Run
  `tests/test_docs.py`: green.

## Phase 5: close

- [X] T012 `grep -rn "host terminal" cli/wuwei` lists only LEFT rows and docstrings; no new
  file outside `tests/fakes/owner.py`; no emojis or em-dashes in the diff. Run every test file
  touched in T001 to T011 once more.
