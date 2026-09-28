# Tasks: Adapter interfaces and registry

## Setup

- [X] T001 Read existing config, init, state and tests; write specs/005-adapters/spec.md and plan.md.

## US1: Honest absent integrations

Independent check: all none operations return exit 2 and append a safe event.

- [X] T002 [US1] Write and run failing contract, result, event and I/O tests in tests/test_adapters.py.
- [X] T003 [US1] Implement shared result/recorder in cli/wuwei/registry.py and adapters/*/none.py; pass T002.

## US2: Adapter selection

Independent check: discovery, module loading, config diagnostics and shell import paths.

- [X] T004 [US2] Write and run failing discovery, loading and shell tests in tests/test_adapters.py and unknown-name tests in tests/test_workspace.py.
- [X] T005 [US2] Implement registry discovery/loading and config checks in cli/wuwei/registry.py and cli/wuwei/workspace.py; update bin/wuwei, pyproject.toml and tests/test_stdlib.py; pass T004.

## US3: Workspace reliability

Independent check: required fields, duplicate names, correct lines and staging prefix.

- [X] T006 [US3] Write and run failing repo and staging tests in tests/test_workspace.py.
- [X] T007 [US3] Fix repo validation/lines in cli/wuwei/workspace.py and prefix in cli/wuwei/commands/init.py; pass T006.

## Final validation

- [X] T008 Run full suite, review diff, check whitespace and prohibited characters; record results in specs/005-adapters/tasks.md.

## Adversarial review fixes

- [X] T009 [F1] Reproduce CLI package shadowing from the working directory; add `-P` to the shim and documented invocations; pass the shim regression.
- [X] T010 [F2] Reproduce accepted wrong signatures and rejected extra imports; check each discovered operation's function type and parameters, and require `none` membership rather than exclusivity.
- [X] T011 [F3] Reproduce duplicate resolved repo paths; reject aliases relative to the workspace root with the duplicate entry's line.
- [X] T012 [F4] Share adapter selection validation in registry.py, retaining the reserved runtime default and config source locations.
- [X] T013 Run the full suite with the requested interpreter and check the final diff.

## Dependencies and Execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008.
US1 is the smallest useful slice; implement incrementally through US2 and US3.
Independent test cases within each story can run in parallel; source edits run sequentially.
No parallel agents are needed.

## Evidence

- US1 red: 18 failures because the registry was absent. Green: 18 passed.
- US2 red: 16 failures for missing discovery/loading and accepted unknown names.
  Green with US1, workspace and stdlib checks: 87 passed.
- US3 red: 11 repo validation failures and a staging-prefix failure after correcting
  the test wrapper signature. Green with preceding checks: 99 passed.
- Full suite: 198 passed in 5.56s using the requested interpreter.
- Extension hooks skipped as requested. Requirements checklist: 6/6 complete.
- Character scan: all 17 changed/added files contain no em dashes or emojis.
- Independent review found a blocking workspace adapter import collision. Added two
  subprocess regressions (namespace and regular packages); both failed by executing
  the conflicting workspace module. Loading the discovered absolute file fixes both.
  Adapter tests after the fix: 30 passed. Delta review: no blocking findings.
- Final full suite after the fix: 200 passed in 5.34s. All tasks complete.
- Review F1 red: shadow CLI printed SHADOWED and exited 0. Green: both shim cases passed.
- Review F2 red: two wrong signatures passed the contract and an extra Result import
  failed it. Green: all 34 adapter tests passed with the corrected contract checks.
- Review F3 red: five duplicate path forms were accepted. Green: 75 workspace tests
  passed, including relative, absolute, normalized, symlink and home path aliases.
- Review F4: existing selection, unknown-name, runtime-default and source-location
  tests pass with the shared validator; config still accepts reserved claude while loading fails.
- Review final suite: 209 passed in 9.81s using the requested interpreter.
  Diff whitespace and character checks passed; all three shell/documented Python CLI
  invocations use `-P`. Changes remain uncommitted.
