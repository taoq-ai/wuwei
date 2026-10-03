# Tasks: Memory graph proof of concept

**Input**: `spec.md`, `plan.md`, `data-model.md`
**Tests**: all in `tests/test_memory_graph_poc.py`. Each test task comes before its
implementation task; run the test, see it fail for the stated reason, then implement.
Run tests with `python -m pytest -q tests/test_memory_graph_poc.py` from the repository
root.

The test file loads the PoC like `tests/test_headless_e2e.py:load` does (by path, with
`scripts/poc/memory-graph` on `sys.path` while the module executes): one `load(name)`
helper at the top of the test file, used by every test.

## Phase 1: Setup

- [X] T001 Create the directory `scripts/poc/memory-graph/` (no `__init__.py`, no
  README).

## Phase 2: User Story 1, corpus and golden set (P1)

Written before any graph code so the questions are fixed before the index exists.

- [X] T002 [US1] Test `test_golden_set_matches_corpus(tmp_path)` in
  `tests/test_memory_graph_poc.py`: `corpus.generate(tmp_path, days=6)` returns 30
  questions, six of each type (why, touched, lesson, revert, reversed); every expected
  `[path, line]` exists under `tmp_path` and has that line; the answer phrase occurs in at
  least one expected line, and scanning every file under `tmp_path/.wuwei`, the files that
  contain the phrase (case-insensitive) are a subset of the expected paths; every planted
  decision file in an expected set passes `wuwei.decision.evaluate`; calling `generate`
  twice into two directories gives byte-identical trees. Fails: `corpus` not found.
- [X] T003 [US1] Implement `generate(root, days=90, seed=444)` and `LAST_DAY` in
  `scripts/poc/memory-graph/corpus.py` per data-model.md (Corpus, Golden set), raising
  `ValueError` when a planted phrase leaks into noise. T002 passes.

## Phase 3: User Story 1, graph

- [X] T004 [US1] Test `test_graph_answers_and_rebuilds_identically(tmp_path, fts)` in
  `tests/test_memory_graph_poc.py`, parametrized over `fts` in `(True, False)` (skip
  `True` when `graph.fts_available()` is false): on a 6-day corpus, `graph.build` twice
  into two files gives equal `graph.dump_hash`; `ask` with the words of the first `why`
  question returns the expected decision path and Question line among its top 5 hits;
  `around` with the form of the first `reversed` question returns both expected decision
  paths; `around` with the form of the first `touched` question returns three `pr` nodes;
  the node types present are exactly item, decision, pr, file, lesson, retro, incident, ticket (retro added in build: the lesson questions expect the retro record, and without a retro node no graph result could cite it).
  Fails: `graph` not found.
- [X] T005 [US1] Implement `fts_available`, `build`, `ask`, `around` and `dump_hash` in
  `scripts/poc/memory-graph/graph.py` per plan.md and data-model.md (Graph). T004 passes
  in both modes.

## Phase 4: User Story 1, measurement runner

- [X] T006 [US1] Test `test_thresholds_and_conclusion()` in
  `tests/test_memory_graph_poc.py`, a table of cases: `h1_verdict` supported at a
  25-point rise and at exactly half the tokens, unsupported at 24 points and 51 percent;
  `h3_verdict` unsupported when any one of time over 10 s, an `events.jsonl` over 20 MB,
  an index of 50 MB or more, or a non-identical rebuild; `h4_verdict` supported at 0.51,
  unsupported at 0.5; `conclude` gives drop for an unsupported or unmeasured H1, park for
  a supported H1 with an unsupported H3 or a supported H4, build for supported H1 and H3
  with an unsupported H4. Fails: `run` not found.
- [X] T007 [US1] Implement `h1_verdict`, `h3_verdict`, `h4_verdict` and `conclude` in
  `scripts/poc/memory-graph/run.py`. T006 passes.
- [X] T008 [US1] Test `test_runner_prints_four_tables(capsys, args)` in
  `tests/test_memory_graph_poc.py`, parametrized over `args` in `([], ['--no-fts'])`
  (skip `[]` when FTS5 is unavailable): `run.main(['--days', '6', *args])` returns 0;
  stdout has a `Search: fts5` or `Search: like` line matching the mode; the four headings
  `### H1`, `### H2`, `### H3`, `### H4`, each followed later by one
  `Verdict H<n>: (supported|unsupported|unmeasured)` line; `Verdict H2: unmeasured`;
  exactly one `Conclusion: (build|park|drop)` line, equal to `run.conclude` applied to the
  printed H1, H3 and H4 verdicts. Fails: `main` not defined.
- [X] T009 [US1] Test `test_runner_exits_2_on_error(monkeypatch, capsys)` in
  `tests/test_memory_graph_poc.py`: with the loaded runner's `graph.build` replaced by a
  function raising `sqlite3.OperationalError('disk I/O error')`,
  `run.main(['--days', '6'])` returns 2, stderr starts with
  `memory-graph poc unmeasured:` and names the error, and stdout has no `Verdict` or
  `Conclusion` line. Fails: `main` not defined.
- [X] T010 [US1] Implement `grep_baseline`, `export`, `h1`, `h2`, `h3`, `h4` and
  `main` in `scripts/poc/memory-graph/run.py` per plan.md (Functions, run.py), reusing
  `wuwei.memory.estimated_tokens` for every token count. T008 and T009 pass.

## Phase 5: User Story 2, the spike document (P1)

- [X] T011 [US2] Test `test_spike_document_decision_record()` in
  `tests/test_memory_graph_poc.py`: `docs/specs/2026-10-03-memory-graph-poc.md` exists;
  it has exactly one line matching `^Conclusion: (build|park|drop)$`; the text after the
  `## Decision record` heading passes `wuwei.decision.evaluate` with `Decided-by: owner`;
  the recommended option's description starts with `Build` for build, `Defer` for park,
  `Do nothing` for drop; for build the document has a `## Follow-up issue` section, for
  park or drop it contains `closes with this document linked`; the document contains no
  em-dash. Fails: document missing.
- [X] T012 [US2] Run `python3 scripts/poc/memory-graph/run.py` from the repository root
  (and `python3 scripts/poc/memory-graph/run.py --no-fts`); keep both outputs for T013.
  If the 90-day run takes over 60 seconds, record the time in the document (SC-001) and
  do not tune the code to the threshold.
- [X] T013 [US2] Write `docs/specs/2026-10-03-memory-graph-poc.md`: question and scope;
  method (corpus, golden set, baseline, graph, token model, rerun command); the four
  tables pasted as printed with the run date, Python and SQLite versions and search mode
  (the `--no-fts` H1 row only if it differs); threats to validity (plan.md, Measurement
  notes); `Conclusion: <rule result>` on its own line with what build would be, reduced
  to what the tables support; then `## Follow-up issue` (build) or the closing sentence
  (park or drop); and last, `## Decision record` in the `wuwei decision template` shape
  with options A `Build ...`, B `Defer: park ...`, C `Do nothing: drop ...`,
  Musts and Wants rows taken from the verdicts so the rule's option scores highest,
  `Reversibility: two-way`, `Decided-by: owner`, `Outcome: pending`. Under 1800 words.
  T011 passes.

## Phase 6: Checks

- [X] T014 Scope check: `git status --porcelain` lists only `scripts/poc/memory-graph/`,
  `tests/test_memory_graph_poc.py`, `docs/specs/2026-10-03-memory-graph-poc.md` and
  `specs/444-memory-graph-poc/`; `grep -rn memory-graph cli adapters hooks` finds nothing.
- [X] T015 [P] Style check on the paths from T014: no em-dash, no emoji, no absolute
  local path (`tests/test_hygiene.py` pattern), neutral names only.
- [X] T016 [P] Budget checks: `wc -w docs/specs/2026-10-03-memory-graph-poc.md` under
  1800; `python -m pytest -q tests/test_memory_graph_poc.py --durations=0` totals under
  5 seconds.
- [X] T017 Run the full suite, `python -m pytest -q`, from the repository root; it
  passes.

## Phase 7: Review fix, a stronger baseline

- [X] T018 Test `test_h1_judged_against_the_stronger_grep(tmp_path, capsys)` in
  `tests/test_memory_graph_poc.py`: on a 6-day corpus, `grep_baseline` with each non
  reversed question's `key` puts every expected record in its top 5; the runner's H1
  verdict equals `h1_verdict` applied to the stronger of word grep and key grep (more
  answered, then fewer tokens). Fails: golden questions have no `key`.
- [X] T019 Add `key` to each golden question in `corpus.py` (the setting's first two
  words, the symptom, the PR ref, the path, the item id); in `run.py` `h1`, add the key
  grep columns and judge H1 against the stronger baseline. T018 passes.
- [X] T020 Rerun both modes and rewrite the document's tables, Reading the numbers,
  Threats, Conclusion and decision record to the rule's result (drop), with the closing
  sentence in place of the follow-up issue.

## Dependencies

T001, then T002 before T003, T004 before T005, T006 before T007, T008 and T009 before
T010, T011 before T013. T003 before T004 (the graph test needs the corpus), T005 before
T008. T012 needs T010. T014 to T016 after T013 and in any order; T017 last.
