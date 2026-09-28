# Tasks: Verdict lint and retro-note capture

## Setup and foundation

- [X] T001 Read the source guard, constitution and existing hook/state contracts;
  record scope and assumptions in specs/013-verdict-lint/spec.md.
- [X] T002 Design shared lint and capture in specs/013-verdict-lint/plan.md and
  specs/013-verdict-lint/contracts/verdict.md; validate requirements checklist.

## US1: Verdict lint (P1)

Independent check: valid files pass, incomplete evidence is returned to the seat.

- [X] T003 [US1] Write and run failing source-refusal, quality, finding and I/O
  tables in tests/test_verdict.py.
- [X] T004 [US1] Implement shared lint in cli/wuwei/verdict.py.
- [X] T005 [US1] Write and run failing CLI, Write/Edit routing, alias and disabling
  mutation tests in tests/test_verdict.py.
- [X] T006 [US1] Implement cli/wuwei/commands/verdict.py and PostToolUse registration
  in cli/wuwei/guards/verdict.py.

## US2: Retro capture (P1)

Independent check: stopping a seat appends a captured retro or gap event.

- [X] T007 [US2] Write and run failing retro, retained-change, retry, I/O and mutation
  tables in tests/test_retro.py; preserve unmodified real-shim replay in tests/test_hooks.py.
- [X] T008 [US2] Implement SubagentStop capture in cli/wuwei/guards/verdict.py using
  cli/wuwei/state.py and cli/wuwei/workspace.py writers.

## Verification

- [X] T009 Run focused tests and full pytest suite, review the diff and scan all
  changed files for machine paths, em-dashes and emojis; update this tasks.md.

## Dependencies and execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009.
US1 is the first usable increment; US2 reuses its retro field parsing. Shared files
make sequential implementation simplest. No parallel agent work is needed.

## Deferred

Issue #81 owns proposal enrichment, promotion lint, landing and history. Semantic
review and general shell write mediation remain outside this verdict guard.

## Initial implementation verification

- Source and added lint tests failed before implementation; CLI/write and retro
  test groups likewise failed before their guard registrations existed.
- Disabling either guard makes its acceptance assertion fail.
- Independent review found two parser defects; regressions reproduced both, and
  the bounded delta review confirmed the fixes with no remaining blockers.
- Pre-review full suite: `1079 passed in 14.40s`.
- Hook p95: CPU 36.62 ms, wall 47.41 ms over 60 runs.
- Diff whitespace and changed-file hygiene checks passed.


## Adversarial review fixes

- [X] T010 [F1, F9] Test and fix workspace/charter-role scope, stop retry behavior,
  unmodified fixture replay and retro-only Change capture.
- [X] T011 [F2, F3, F4] Test and fix all write-tool routing, relevant Bash gate
  files and opaque one-liners, case-insensitive paths and prefixed role identity.
- [X] T012 [F5, F6, F7, F8] Test and fix PASS/blocking contradictions, independent
  numbered/ID findings, explicit probe rows and exactly one hex Head row.
- [X] T013 [F10, F11] Scope class sweeps to engineering verdicts, align the
  common charter and document the Codex CLI/runtime adapter contract.
- [X] T014 [Residual] Test and add verdict.rejected events with file and reasons;
  fail closed if event persistence fails.
- [X] T015 Run the requested full pytest suite and check the final diff.

Review regression evidence: retro failures reproduced before fixes (17 failing),
lint shape/scope failures reproduced (32 failing), routing/event failures
reproduced (30 failing). Additional numbered multiline and interpreter-script
cases reproduced before correction (4 failing). Focused suite passes.

Final review-fix verification: `1177 passed in 12.15s` with the requested
interpreter. Charter tests, original recorded fixture replay, diff whitespace
and changed-file text hygiene checks passed. No commits created.

## Adversarial delta review fixes

- [X] T016 [F1, F3] Replace shell path extraction with the case-insensitive daily
  gate scan; add sentinel SubagentStop checks and retry recording. Reproduce the
  four cd/variable forms and verify interpreter refusal plus all-file diagnostics.
- [X] T017 [F2] Test workspace lookup from gate targets outside cwd; document
  the workspace context required by retro capture.
- [X] T018 [F4] Test and recognize paragraph finding-ID punctuation boundaries.
- [X] T019 [F5] Replace --quality with --role and share role-derived lint rules
  between the CLI and hooks; test prefixed roles and generic filenames.
- [X] T020 [F6] Document that Change lines stay in retro evidence for the steward
  until #81 fixes the proposal contract.
- [X] T021 Run the requested full pytest suite and inspect the final diff.

Regression evidence: daily Bash/stop checks initially had 21 failures; target
workspace lookup had 4; paragraph findings had 3; CLI role handling had 5.
Interpreter/all-file aggregation also reproduced before correction. All 269
focused verdict and retro tests pass after the fixes.

Final delta-fix verification with the requested interpreter: `1214 passed in 13.99s`.
Hook p95: CPU 30.57 ms, wall 36.64 ms over 60 runs. Diff whitespace and
changed-file text hygiene checks passed. Changes remain uncommitted.
