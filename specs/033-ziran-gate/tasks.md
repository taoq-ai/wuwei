# Tasks: ZIRAN agent-surface gate

## Setup

- [X] T001 Read existing ports, gate receive, verdict and state writers; write spec.md and plan.md in specs/033-ziran-gate/.

## US1: Measured scanner findings (P1)

Independent check: vulnerable recorded report yields FIX and rows; clean report permits PASS.

- [X] T002 [US1] Add failing audit/CI contract and config tests in tests/test_ziran.py with tests/fixtures/scanner/ payloads.
- [X] T003 [US1] Implement measured audit/CI adapter in adapters/scanner/ziran.py and threshold schema in cli/wuwei/workspace.py.
- [X] T004 [US1] Add failing flagged receive, row, threshold, trust-boundary and delta tests in tests/test_dispatch.py.
- [X] T005 [US1] Implement mandatory scanner orchestration in cli/wuwei/scanner.py and cli/wuwei/dispatch.py.

## US2: Unmeasured fails closed (P1)

Independent check: missing tool, errors, timeout and invalid bodies give exit 2 without a gate record.

- [X] T006 [US2] Add failing malformed/error/timeout/allowlist tests in tests/test_ziran.py and receive failure/HEAD tests in tests/test_dispatch.py.
- [X] T007 [US2] Complete validation and error handling in adapters/scanner/ziran.py and cli/wuwei/scanner.py; retain unavailable traces/MCP.

## Polish

- [X] T008 Document scanner selection and threshold in templates/workspace/config.toml and docs/site/configuration.md.
- [X] T009 Run the full suite and review modified files for scope, trust, paths and writing hygiene; record validation in specs/033-ziran-gate/tasks.md.
- [X] T010 Fix review F1 with a failing receive exit regression, then restore exit 0 for recorded verdicts.
- [X] T011 Fix review F2 with a failing below-threshold regression, then retain PASS for scanner notes.
- [X] T012 Fix review F3 with a failing flags-change/retry regression, then rewrite the verdict only after the state update succeeds.

## Dependencies and execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009.
US1 and US2 share files and run sequentially. Documentation and fixture review may be
checked independently after integration. Each implementation follows an observed failing
test, then a focused green run. No agent delegation is needed.

## Validation

- Observed failing tests before adapter, config, receive and failure-handling changes.
- Focused scanner, gate, docs, registry, config and stdlib checks passed.
- Review regressions each failed before their fixes; all 37 dispatch tests passed afterward.
- Full suite: `4591 passed, 3 skipped in 55.98s`. The three existing performance checks
  skipped under host load.
- `git diff --check` passed; all changed files passed local-path, emoji and em-dash checks.
- No commits, pushes or remote issue writes. Live CLI compatibility remains deferred as
  documented in research.md; contract fixtures do not claim a released JSON CLI.
