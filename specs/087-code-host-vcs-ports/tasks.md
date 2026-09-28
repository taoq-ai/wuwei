# Tasks: Code host and VCS ports

## Setup and foundational contracts

- [X] T001 Read source design, constitution, registry, adapters and harness queries; write specs/087-code-host-vcs-ports/spec.md and plan.md.
- [X] T002 Extend tests/test_adapters.py and tests/test_stdlib.py for signatures, defaults, none behavior and independent imports; run and confirm missing-port failures.
- [X] T003 Extend cli/wuwei/registry.py, cli/wuwei/workspace.py and adapters/code_host/none.py to satisfy foundational tests.

## US1: Repository evidence

- [X] T004 [US1] Write fixture replay and error tests in tests/test_code_host.py with tests/fixtures/code_host/recordings.json; run failing tests.
- [X] T005 [US1] Implement GitHub reads in adapters/code_host/github.py; pass evidence and error tests.
- [X] T006 [US1] Write fixture replay and error tests in tests/test_vcs.py with tests/fixtures/vcs/recordings.json; run failing tests.
- [X] T007 [US1] Implement git reads in adapters/vcs/git.py; pass evidence and error tests.

## US2: Constrained writes

- [X] T008 [US2] Add write replay and injection tests in tests/test_code_host.py and tests/test_vcs.py; confirm failures before writes exist.
- [X] T009 [US2] Implement constrained writes in adapters/code_host/github.py and adapters/vcs/git.py; pass tests including match-head and no admin/approve assertions.

## US3: Replaceable integrations

- [X] T010 [US3] Write recording-fake and core subprocess boundary tests in tests/test_adapters.py; confirm detection and missing-fake failures.
- [X] T011 [US3] Add recording fakes in tests/fakes/code_host.py and tests/fakes/vcs.py with fixture replay support in tests/fakes/replay.py; pass tests.

## Verification

- [X] T012 Run the specified full pytest suite, review final diff and scan authored files for prohibited characters; record results in specs/087-code-host-vcs-ports/tasks.md.

Dependencies: T001 -> T002 -> T003; T004 -> T005; T006 -> T007; T008 -> T009; T010 -> T011; all -> T012. Read ports are the MVP. GitHub and git replay work are independent after foundational contracts. Tests precede implementation for each behavior, including writes.


## Verification results

- Foundational red run: 12 failed, 40 passed; missing ports/modules were the expected failures.
- Read adapters red run: 69 failures from absent modules; green run: 69 passed.
- Write adapters red run: 33 failed, 73 passed; missing write operations were the expected failures.
- Recording fake red run: 2 failed, 6 passed; fake modules were absent as expected.
- Additional regression tests covered revert response selection, filename carriage returns, template defaults, pinned API host and useful error diagnostics; each failed before its corresponding fix.
- Final full suite with the user-specified interpreter: 385 passed in 19.41s.
- Initial reviews reported no blockers; the subsequent adversarial review identified F1 through F4, addressed below.
- git diff --check passed. Prohibited-character scan passed for all 21 authored files.
- Extension hooks skipped as instructed. No commits, pushes or live gh calls performed.


## Adversarial review fixes

- [X] T013 F1: Reproduce private-helper command bypasses, then allow only the supported REST argv shapes, module-constant GraphQL queries and exact head-constrained squash merge.
- [X] T014 F2: Reproduce inherited GIT_DIR selecting a different repository and strip all GIT_* environment keys before spawning git.
- [X] T015 F3: Reproduce all eight scanner evasions and replace argv inference with an AST ban on core process-launcher imports and os launch references.
- [X] T016 F4: Reproduce replay process spawning, move fixture replay in process with argv/input assertions, and retain one real-PATH smoke test per adapter.
- [X] T017 F5/F6: Reproduce and catch RecursionError in both adapters; add a successful thread body plus GraphQL errors regression (already fails closed).
- [X] T018 Run the full specified pytest command and final diff checks after review fixes.

Review scope notes:

- F7 deferred: repository rulesets need an additional API contract, fixtures and aggregation semantics, beyond a small correction.
- F8 deferred: dynamic fake signatures are optional refactoring; moving the subprocess-aware decorator into the registry conflicts with F3's core import ban.
- Initial regression run: 25 failed, 6 passed, 160 deselected, reproducing F1/F2/F3/F5. F6 passed without a runtime change.
- Before replay refactoring: 191 adapter-focused tests passed in 12.19s.
- Replay no-spawn regression: 2 failures before conversion. In-process assertions also exposed an identity error test relying on cassette exhaustion; it now supplies malformed output for every expected call.
- Final full suite with the specified interpreter after review fixes: 415 passed in 6.80s. All blocking findings fixed. Diff whitespace and authored-character checks passed; changes remain uncommitted.

## Follow-up adversarial review fixes

- [X] T019 F9: Add no-spawn regressions for unsupported git commands and option injection; restrict _run to the exact supported command shapes and a module-constant log format.
- [X] T020 F10: Add scanner rows for top-level asyncio launchers, aliases, direct imports and star imports; extend the AST scan and document its dynamic-access ceiling in a ponytail comment.
- [X] T021 F11: Replace T014's blanket GIT_* filtering with repository-variable and GIT_CONFIG* filtering; retain effective author/committer overrides and verify identity plus repository isolation with local git.
- [X] T022 Residual: Extend the log replay fixture, parser and contract with committer name and email.
- [X] T023 Run the specified full pytest suite and inspect the final changes.

Verification:

- F9 red: 15 unsupported-command cases reached the intercepted subprocess; green: 50 VCS tests passed.
- F10 red: 6 newly covered scanner cases failed (subprocess star imports were already caught); green: 26 core-related tests passed.
- F11 red: environment retention and effective author email failed while repository isolation passed; green: 51 VCS tests passed.
- Residual red: log replay rejected the old format before the format and parser were extended.
- Full suite with the specified interpreter: 438 passed in 6.87s. Changes remain uncommitted.
