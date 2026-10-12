# Tasks: the trace sweep reads only new spans, and the scanner audit's polish

- [X] T001 [US1, US2, US3] Tests in `tests/test_traces_seats_only.py`: a second sweep with no
  new span runs no ZIRAN; a sweep gives ZIRAN only new lines plus the last earlier line of each
  tool a session used; more than 20 new spans of one session make two windows and two offsets; a damaged or
  out-of-range offset restarts at 0; a resumed seat that repeats its chain in new spans parks
  again; a retried window parks once; a credential read before a park does not re-park a
  later local chain, a new one does; one read of events and state per sweep. Run: red.
- [X] T002 [US1, US2, US3] Implement FR-001 to FR-004 in `scanner.trace_sweep` and
  `_trace_response`; T001 green, the existing sweep tests green.
- [X] T003 [US1] Tests: a failed window keeps the offset, appends one `scanner.unmeasured` per
  distinct reason; doctor shows an unmeasured `trace sweep` row until a measured sweep; a seat
  write to `trace-sweep.json` is refused (`tests/test_protect_state.py`). Run: red.
  Implement FR-001 (protection) and FR-005; green.
- [X] T004 [US4] Tests in `tests/test_plan.py`: an absolute ZIRAN path becomes relative in id
  and evidence; `discovery_threshold` drops lower rows; `discovery_rows` keeps the most severe
  and names the rest. Run: red. Implement FR-006 with the schema keys, template and docs; green.
- [X] T005 [US5] Tests: `why` names the trace sweep for a scanner park; two audits in one
  process run one `--version`, a failed check is not cached. Run: red. Implement FR-007,
  FR-008 (and the per-test cache clear in `tests/conftest.py`); green.
- [X] T006 [US5] FR-009 docs in `docs/site/security.md` and `docs/site/configuration.md`.
- [X] T007 Run every test file that imports a changed module plus invariants, docs and hygiene
  under the pipeline venv, and scanner, ziran, traces, close, doctor, why and plan under 3.11.
- [X] T008 Live: the audit's tracescale driver through `trace_sweep` at 3000 varied spans,
  before and after, and a second sweep with new spans (quickstart.md).
- [X] T009 [review F1, F2, F3] Tests: a chain split by padding, by a busy session's window cut
  and by a sweep boundary parks; carried spans do not re-park a recorded chain; an unrelated park
  does not clear a credential read; a second sweep parses only new lines. Run: red. Implement the
  per-tool carry, the source-and-sink rule, the credential-reason `seen`, and the stored maps;
  green. Live: the review's split.py probe with real ZIRAN finds all three.
- [X] T010 [review D1, D2] Tests: after a resumed credential park, a different local chain parks
  with the credential wording; a non-local park of a session that read a credential says so.
  Run: red. Key `seen` by chain; add the wording to any park after a read; green.
