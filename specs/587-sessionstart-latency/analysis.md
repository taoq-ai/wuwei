# Specification Analysis Report: 587-sessionstart-latency

Artifacts: spec.md, plan.md, tasks.md, research.md, against `.specify/memory/constitution.md`,
the item's Acceptance section and the orchestrator notes.

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Coverage | HIGH | spec SC-001, US1.1 | The runner target (SessionStart under 75 ms wall p95) cannot be measured here, and the planned cuts measured 8 to 13 percent of the above-floor CPU locally; the runner gap is about 22 ms of 97. The acceptance may not be met by these cuts alone. | Resolved: SC-002 is the local gate, SC-001 is read from the job artifact on the pull request, and spec Assumptions give the stop rule: if the job still shows 75 ms or more, the builder reports the figure and the next step is a design reconsideration with the owner, never a looser budget, margin, test or job. |
| A2 | Inconsistency | HIGH | spec FR-005, tasks T012 | FR-005 was stated as definite while T012 lets the builder revert it. | Resolved: FR-005 now carries the keep rule (lower CPU median, no higher wall p95 in the interleaved measure on top of FR-001 to FR-004), matching T012. |
| A3 | Constitution | MEDIUM | plan item 5, tasks T010 | FR-005 changes a #346 design test in `tests/test_hooks.py`; the item forbids changing that file's budgets. | Accepted: the test pins thread overlap, not a budget; it becomes a guard-order test with the same output assertion. Recorded under spec Assumptions. |
| A4 | Security | MEDIUM | plan item 3, FR-003 | The ssh adapter is a trust boundary; replacing `tempfile.TemporaryDirectory` could open a race or leave key material behind. | Resolved: private directory created with `os.mkdir(..., 0o700)` (fails if present) under an unpredictable name, file opened with `O_EXCL | O_NOFOLLOW`, removed in `finally`; T005 pins cleanup on success, failure and timeout, and the real `ssh-keygen` roundtrip still runs. The file holds only the pinned public key, as today. |
| A5 | Underspecification | MEDIUM | tasks T008 | "Reads that resolve to today's state" was ambiguous between `read_state(root)` and `read_state(directory=...)`. | Resolved: T008 counts both forms by today's day directory and names the two expected readers. |
| A6 | Ambiguity | LOW | plan item 3 | `os.get_exec_path()` and `shutil.which` differ only when `PATH` is unset (default path source). | Accepted: both report absent for the test's missing `PATH`, and the check order (absent tool before missing files) is kept and pinned by the existing test. |
| A7 | Coverage | LOW | spec FR-008 | Wall figures on this host are load-bound. | Accepted: CPU and interleaved pairs locally, runner wall from the job artifacts (orchestrator note). |
| A8 | Duplication | LOW | research.md, spec Root cause | Figures appear in both. | Accepted: the spec carries the attribution, research the method and tables. |

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 | T002, T003 |
| FR-002 | T002, T004 |
| FR-003 | T002, T005, T006 |
| FR-004 | T008, T009 |
| FR-005 | T010, T011, T012 |
| FR-006 | T002 |
| FR-007 | T013, T014 |
| FR-008 | T001, T007, T012, T014 |
| SC-001 | latency job on the pull request (T014) |
| SC-002 | T001, T007, T012 |
| SC-003 | T014 |

Every behaviour has a test task before its implementation task (T002 before T003, T004 and
T006; T005 before T006; T008 before T009; T010 before T011). No refusal is added or changed
(#530); no planner action changes (#551); no budget, margin, probe, run count, fixture or
job setting changes (#346, #562). No guard or decision rule changes, so the design 9.2
invariant table and `tests/test_invariants.py` are unchanged.

CRITICAL: 0. HIGH: 2, both resolved in the artifacts. MEDIUM: 3. LOW: 3.
