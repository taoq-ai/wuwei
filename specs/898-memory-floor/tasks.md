# Tasks: 898-memory-floor

- [X] T001 Tests: `free_percent` on the local adapter (darwin `memory_pressure`, linux
  `/proc/meminfo`, failures) in `tests/test_brief_adapters.py`; the interface row in
  `tests/test_adapters.py`.
- [X] T002 Tests: `dispatch.host` with the floor (below, at, unmeasured, off) in
  `tests/test_dispatch.py`.
- [X] T003 Tests: `launch_set` holds every seat launch with a timed wait; counts only live
  seats (adhoc and handed-back seats excluded) in `tests/test_dispatch.py`; `next` sleeps on a
  memory-only hold in `tests/test_next.py`.
- [X] T004 Tests: the launch hook ignores adhoc seats in its ceiling count
  (`tests/test_agent_launch.py`); doctor's memory row (`tests/test_doctor.py`); the config key
  default and range (`tests/test_workspace.py`); upgrade adds it (`tests/test_config_transition.py`).
- [X] T005 Run the tests, see them fail.
- [X] T006 Implement: adapter op and registry interface, `agent_launch.free_percent`,
  `dispatch.host` and `launch_set`, `brief.live` at the three counters, doctor, config schema
  and template, docs.
- [X] T007 Run the tests named in the plan under the pipeline venv and Python 3.11.
