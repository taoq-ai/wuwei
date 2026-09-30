# Tasks: control-plane interface with Remote Control and push as default

Test first: every implementation task follows the test task that must fail before it.
Run tests with `python -m pytest -q <file>` from the repository root. All new tests live in
`tests/test_control_plane.py`, in process, with a `tmp_path` workspace, `WUWEI_NOW` set,
a pending decision made by saving a one-way copy of the `VALID` record from
`tests/test_decision.py` as `D-3.md` and running `main(['decision', 'route', 'D-3'])`, and a
fake transport class in the test file:
`dm(text, *, root=None)` appends to `self.sent` and returns `Result(0, {})`;
`poll(since, *, root=None)` returns `Result(self.exit, [{'id': str(n), 'text': t} ...],
self.reason)`.

## Setup

- [X] T001 Reproduce read-only in a scratch workspace: `[control_plane] content = "summary"`
  makes `workspace.load_config` raise `unknown key control_plane`.
- [X] T002 Write spec.md, research.md, plan.md and tasks.md.

## US4: content policy config

- [X] T003 Test in `tests/test_control_plane.py` (`test_config_*`): an empty config gives
  `control_plane.content == 'summary'`; `content = "none"` loads; `content = "all"` raises
  `workspace.ConfigError` naming `control_plane.content`. Run and see it fail.
- [X] T004 Implement: `cli/wuwei/workspace.py` `SCHEMA["control_plane"]`. T003 passes.

## US2: the shared reply parser

- [X] T005 Test in `tests/test_control_plane.py` (`test_parse_*`), table-driven against
  `{'D-3': fields}` from `decision.evaluate(VALID)` (Recommendation A, options A and
  B "Defer until tomorrow"): `option B on D-3` gives `('D-3', 'B')`; `Option b on d-3.`
  gives `('D-3', 'B')`; `approve D-3` gives `('D-3', 'A')`; `drop it` gives `('D-3', 'B')`;
  `approve something`, `approve D-9`, `option Z on D-3`, `approve D-3 please` and `` give
  `None`; `drop it` with two pending decisions gives `None`. Also `pending(root)` returns
  only D-3 after routing, and nothing once `decision_outcomes['D-3']` is an owner outcome.
  Run and see it fail (module missing).
- [X] T006 Implement `pending`, `options` and `parse` in `cli/wuwei/control_plane.py`.
  T005 passes.

## US1: escalate

- [X] T007 Test (`test_escalate_*`): with a fake transport and default content, exit 0 and
  one sent message containing `D-3: Which fix?`, `A: Implement fix`,
  `B: Defer until tomorrow` and the reply help, and not `Context`, `tests/test_example.py`
  or `Pre-mortem`; with `content = "none"`, the message is `D-3 options: A, B` plus help,
  without `Which fix` or `Implement fix`; with no transport, exit 0, nothing sent, and
  `guards.decision.check_question` on an `AskUserQuestion` payload whose question is the
  returned text returns `(0, '')`; `escalate('D-9')` and a D-3 with an owner outcome exit
  1 and send nothing; a pending D-3 whose record was replaced by invalid text exits 2 and
  sends nothing. Run and see it fail.
- [X] T008 Implement `HELP`, `render` and `escalate` in `cli/wuwei/control_plane.py`.
  T007 passes.

## US2: poll replies and record answers

- [X] T009 Test (`test_reply_*`): issue acceptance 1: reply `option B on D-3` gives exit 0,
  data `[{'id': 'D-3', 'option': 'B'}]`, the last event is `decision.replied` with payload
  exactly `{'id': 'D-3', 'option': 'B'}`, nothing sent, and `state.read_state` still has no
  `decision_outcomes['D-3']` (the decision stays pending). Issue acceptance 2: reply
  `approve something` gives exit 1, no `decision.replied` event, and one sent echo holding
  the help line, `D-3`, `A: Implement fix` and `B: Defer until tomorrow`. Also: the echo
  under `content = "none"` holds `D-3 options: A, B` and no descriptions; with no pending
  decisions the echo says `No pending decisions.`; a poll result with exit 2, a non-list
  data, or an item without a string `text` gives exit 2 and records nothing, even when an
  earlier item parses; a transport whose echo `dm` returns exit 2 gives exit 2; with no
  transport the result is exit 0 with `[]`; the reply text never appears in
  `events.jsonl`. Run and see it fail.
- [X] T010 Implement `poll_replies` in `cli/wuwei/control_plane.py` and add
  `'decision.replied'` to `EVENT_PRODUCERS` in `cli/wuwei/commands/event.py`. T009 passes.

## FR-009: reserved and silent

- [X] T011 Test: in `tests/test_decision.py::test_generic_event_reserves_all_decision_kinds`
  add `'decision.replied'` to the parameters and assert the refusal names
  `wuwei control plane poll_replies` on stderr for it; in `tests/test_control_plane.py`
  assert `signal.classify({'kind': 'decision.replied', 'payload': {'id': 'D-3',
  'option': 'B'}}, {})[0] == 'silent'`. Run and see the new assertions fail.
- [X] T012 Implement: `'decision.replied'` in `SILENT` in `cli/wuwei/signal.py`. T011
  passes.

## US3: notify

- [X] T013 Test (`test_notify_*`): with a transport and default content, the summary is
  sent unchanged and the transport's result is returned; with `content = "none"`, the sent
  text is exactly `An update is waiting in the workspace.`; with no transport, exit 0,
  data is the summary and nothing is sent. Run and see it fail.
- [X] T014 Implement `notify` in `cli/wuwei/control_plane.py`. T013 passes.

## Docs and template

- [X] T015 Test: in `tests/test_docs.py::test_daily_path_and_recovery_pages` add the
  phrases `Remote Control` and `Push when actions required` to the daily.md assertions;
  add `[control_plane]` with `content = "summary"` and a one-line comment to
  `templates/workspace/config.toml`. Run `tests/test_docs.py` and see
  `test_every_template_config_key_is_documented` and the daily page test fail.
- [X] T016 Implement: the `control_plane.content` row in `docs/site/configuration.md` and
  the Remote Control paragraph in `docs/site/daily.md` section 5 (plan.md, item 5). T015
  passes.

## Finish

- [X] T017 Run the full suite with `python -m pytest -q`; everything passes. Scan every file
  touched for em-dashes, emojis and absolute local paths and remove any. Mark the
  `# ponytail:` comment on the duck-typed transport in `cli/wuwei/control_plane.py`.
