# Specification Analysis Report

Read spec.md, plan.md, tasks.md, data-model.md, research.md and the constitution after the prerequisite check.

| ID | Category | Severity | Location | Summary | Recommendation |
| --- | --- | --- | --- | --- | --- |
| None | Consistency | None | All artifacts | No unresolved critical, high, medium or low finding. | Proceed with final checks. |

| Requirement | Covered | Tasks |
| --- | --- | --- |
| FR-001 mapping | Yes | T001, T002, T003 |
| FR-002 precedence | Yes | T002, T003 |
| FR-003 shared generation/doctor | Yes | T002, T003 |
| FR-004 distinct metadata and bounded parsing | Yes | T004, T005, T008, T009, T010 |
| FR-005 report and no attestation | Yes | T004, T005, T006 |
| FR-006 budgets and reuse | Yes | T003, T005, T007 |
| SC-001 consumer tests | Yes | T002, T004, T007 |
| SC-002 route differential | Yes | T007 |
| SC-003 checks and artifacts | Yes | T006, T007 |

Constitution: stdlib only, six config keys, test first, existing records and no added refusal. At source a2a91f064b68dd3d8c273f46662350f4fc56a90b runtime is 3,800 lines, +23 against parent 0d83e22e's 3,777. The owner approved the two additional parser lines and the current 4,000-line global cap. Source deletes the obsolete no-model docstring and Codex advice skip.

Metrics: 9 requirements and criteria, 10 tasks, 100% coverage, 0 ambiguity, 0 duplication, 0 critical or high findings, no unmapped tasks. Scope and precedence are consistent across the artifacts. Fork policy records a request, never measured inheritance.

Validation: generation red 8, telemetry red 8, malformed metadata red 1. Whitespace and fresh-fork advice each had a failing consumer check before a one-line fix. Focused green 119 and wider green 356. Route differential: 288 routes, 1,152 cases per tree, zero moved verdicts/reasons against original main and immediate parent. Initial full suite: 3,811 passed, 7 skipped at cacc2c2c. Final focused checks cover the two validation fixes. Parent metadata and concurrency fix integration is pending and will be verified separately.

Parent integration: e341ab45 includes the shared sanitizer and identity/report fixes. Ten new metadata consumer cases failed before integration, then the Codex/model/hook suite passed 768 tests. Brief requested models are extracted from the fully scrubbed prompt before clipping; all new turn/fork fields are inside the shared sanitized seat dictionary. The final 1254 retention follow-up and root's combined full suite remain pending.

First native FIX round at 702986c1: two blocking defects and one advice inconsistency were reproduced. Expanded consumers ran red with 13 failures and 9 passes. The single fix batch accepts only nonblank strings for turn metadata, requires a separate effort token, and shares requested-model extraction. Codex/model consumers plus vendor and runtime checks then passed 164 tests. Both blocking findings are addressed; native delta review remains pending. No shell command parser changed and no full suite was repeated.

## Approved linear parser correction

Security found quadratic missing-effort parsing at b6310c55. The owner approved one additional correction round. The source captures the model line once, splits horizontal whitespace, skips the first model token and recognizes a separate effort token, including immediately before `(`. No other runtime path changed. Source and vendor hooks match.

Red: `uv run --no-project --with pytest python -m pytest -q tests/test_models.py -k 'long_model_lines or horizontal_token_boundaries' --tb=short` produced 2 failures and 9 passes. Both 64,000-character missing-effort consumers were killed by the subprocess timeout after two seconds, bounding the reproduction. Long separate-effort controls and horizontal-boundary cases passed before implementation.

Green: `uv run --no-project --with pytest python -m pytest -q tests/test_models.py tests/test_codex.py tests/test_setup.py::test_the_runtime_holds_its_size_budget tests/test_setup.py::test_the_vendored_plugin_matches_the_tree_it_was_copied_from` passed 198 tests in 1.84 seconds at a2a91f06. These retain owner precedence, multiword names, model-ID effort words, malformed metadata and redaction consumers.

Actual-hook growth ran from a fresh `git archive a2a91f06` copy with `uv run --no-project --with pytest python -m pytest -q -s tests/test_builder_linear_probe.py --basetemp=../pytest-growth`. All 28 cases passed: 1,000 through 64,000 characters, doubling each step, token and space-tail shapes, with absent effort and separate `high` controls. Maximum time was 0.001998 seconds. At 64,000 characters, missing-effort token and space-tail launches took 0.001998 and 0.001535 seconds. Measurements are under `.wuwei/scratch/builder-1261-linear/latency-growth.json` in the planner workspace. Native provider transport remains unmeasured.

`python3 .wuwei/scratch/builder-1261-linear/routes.py` ran 288 routes under green, running, red and approved-exception hosts, 1,152 cases per tree. Fresh archives of main 3feedf5c, dependency parent 0d83e22e and pre-fix b6310c55 each had zero raw verdict or reason moves against a2a91f06. No refusal changed repository or PR wording. Corpus SHA256: de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1. Every moved row: none. Results are under `.wuwei/scratch/builder-1261-linear/routes-comparison.json`. Shell command-parser combinatorial probes are N.A.; this change only parses the brief's Model field.

AUTH N.A.: no guard or credential route changed; the route differential remains identical. VAL PASS: bounded token/space-tail controls and horizontal boundaries passed. TEST PASS: assertions reach native PreToolUse and existing recording/report consumers. ERR PASS: missing effort stays unrecorded and never denies a launch. STATE N.A.: no read-check-write behavior changed. CON PASS: existing native and Claude launch fixtures reach their consumers. INF N.A.: no new secret, environment key, entry point or permission.

No full suite or mutants were repeated in this correction round; the planner controls the serial slot. Independent security and quality review, CI and owner review remain separate requirements.
