# Tasks: selective second opinion

- [X] T001 [US1] Test (`tests/test_dispatch.py`): with `second_opinion_when = ["trust_surface"]`
  a STANDARD item flagged `trust_surface` gets `quality@codex`, one without it does not; the
  default keeps today's behaviour. Test (`tests/test_workspace.py`): an unknown flag name is a
  config error. Run: red.
- [X] T002 [US1] Implement FR-001 and FR-002; T001 green.
- [X] T003 [US2] Test (`tests/test_dispatch.py`): an item tiered with the second opinion whose
  three gates passed, after `second_opinion = "off"`, gets `raise` from `dispatch next`, the
  tier record has no `second_opinion`, a `gate.released` event is written, and
  `dispatch opinion` refuses `no second opinion`; the same through a selector that no longer
  matches. Run: red.
- [X] T004 [US2] Implement FR-003; T003 green.
- [X] T005 Document the key (template, configuration page).
- [X] T006 Run every test file that imports `dispatch`, `workspace`, `signal` or `why`, under
  3.12 and 3.11.
- [X] T007 [F1] Test (`tests/test_dispatch.py`): a recorded Codex FIX survives switching
  `second_opinion` off and narrowing `second_opinion_when`; `dispatch next` returns the fix
  round for `quality@codex` and no `gate.released` is written. Run: red (raise).
- [X] T008 [F1] `_released` keeps a second opinion whose latest verdict blocks; T007 green.
