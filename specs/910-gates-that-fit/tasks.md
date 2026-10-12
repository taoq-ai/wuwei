# Tasks: 910-gates-that-fit

- [X] T001 Tests: `launch_set` launches the gate seats that fit (host seats, a runtime window)
  and holds new builds that sweep, in `tests/test_dispatch.py`; replace the all-or-nothing test.
- [X] T002 Tests: a stopped builder awaiting checks keeps its slot; a fix-round builder past the
  first CAP holders waits in the launch set, in `tests/test_dispatch.py`.
- [X] T003 Tests: end to end three gates on two seats reach raise without a third running seat;
  a head move refuses the deferred seat, in `tests/test_parallel_dispatch.py`.
- [X] T004 Tests: the guard counts build slots (a Codex loop holds one; plan order), in
  `tests/test_agent_launch.py`; existing CAP tests set their items building; `tests/test_enforce.py`.
- [X] T005 Run the tests, see them fail.
- [X] T006 Implement `building`, `slot`, the subset in `launch_set`, the shared count at each
  caller, the guard and capacity text.
- [X] T007 Run the named test files under the pipeline venv and Python 3.11.
- [X] T008 Review fix: revert the design spec hunk (proposed amendment in the spec); a fix round
  opened in the sweep takes its slot (fresh count); a running gate batch holds new builds; F4
  under Assumptions. Tests first in `tests/test_dispatch.py`.
