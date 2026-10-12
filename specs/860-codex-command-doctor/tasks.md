# Tasks: codex.command doctor row

- [X] T001 [US1] Test (`tests/test_doctor.py`): empty `codex.command` plus a plugins file with a
  `codex@openai-codex` entry whose script exists gives one warn row naming the script path and
  the `config set` fix; with `gates.second_opinion = "codex:m1"` and no plugin, the row has the
  generic fix; with the command set, no row. Run: red.
- [X] T002 [US1] Implement FR-001 and FR-002 in `doctor.py`; T001 green; `test_host_rows_healthy`
  still lists five host rows.
- [X] T003 [US2] Test (`tests/test_plan.py`): a proposal with
  `seat_policy.builder.runtime = "codex"` and an empty `codex.command` writes the reason on the
  plan's `Seat policy:` line and in the gate card. Run: red.
- [X] T004 [US2] Implement FR-003 in `plan.py`; T003 green.
- [X] T005 Run every test file that imports `doctor` or `plan`, under 3.12 and 3.11.
