# Tasks: Hook shims and payload harness

## Setup

- [X] T001 Read design, constitution, CLI, and supplied reference; record decisions in specs/006-hooks-harness/spec.md and plan.md.

## US1: Hook wiring and routing

Independent check: replay every fixture through the configured executable with fake guards.

- [X] T002 [US1] Add sourced fixtures in tests/payloads/ and failing clean replay/configuration tests in tests/test_hooks.py.
- [X] T003 [US1] Add hooks/hooks.json, cli/wuwei/commands/hook.py, and cli/wuwei/guards/__init__.py for clean replay and discovery.
- [X] T004 [US1] Add failing refusal, context, matching, aggregation, and stop-active tests in tests/test_hooks.py.
- [X] T005 [US1] Implement guard dispatch and event-specific responses in cli/wuwei/commands/hook.py.

## US2: Fail closed

Independent check: malformed payload and broken-guard tables return meaningful exit 2.

- [X] T006 [US2] Add failing malformed-input, required-field, bad-registry, exception, and invalid-result tables in tests/test_hooks.py.
- [X] T007 [US2] Implement validation and guard failure isolation in cli/wuwei/commands/hook.py and cli/wuwei/guards/__init__.py.

## US3: Shared shell normalization

Independent check: static argv, scope, parse-error, and opaque-snippet tables.

- [X] T008 [US3] Add failing separator, quoting, wrapper, subshell, parse-error, and interpreter tests in tests/test_shell.py.
- [X] T009 [US3] Implement tested normalization and opaque predicate in cli/wuwei/shell.py.

## Verification

- [X] T010 Run the full suite with the requested interpreter; inspect diff and authored characters; record evidence in specs/006-hooks-harness/tasks.md.

## Dependencies and execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010.
US3 is independent of US1/US2 and could be developed in parallel in its own files;
this seat executes sequentially. Within US1/US2 tests share one replay harness and are
sequential. MVP is US1, but acceptance requires all three stories. Every implementation
task follows its failing test task. Extension hooks are skipped as instructed.

## Test-first evidence

- Hook wiring: 12 failing tests for missing mappings/registry, then 12 passing.
- Guard routing: 31 new failures before dispatch, then 43 passing.
- Validation: 150 failures including missing session_id accepted as clean, then 204 passing.
- Shell normalization: 57 missing-module failures, then 57 passing.
- Review regressions: attached/combined/repeated interpreter flags and expanding nested
  scripts reproduced before fixes. Mixed quote and continuation cases reproduced too.
  Shell suite now has 69 passing cases.
- Review: one fix round addresses opaque interpreter options and outer-shell expansion.
  Delta review: PASS, both findings closed; reviewer independently ran 69 shell tests.

## Initial verification (before adversarial fix round)

- Required interpreter, full suite: `425 passed in 37.71s`.
- All 22 authored files (including the ignored feature pointer) scanned: no em dashes,
  emojis, or trailing whitespace. `git diff --check` passed.
- No real guard modules shipped; changes remain uncommitted in this worktree.

## Adversarial fix round

- [X] T011 [US3] Reproduce F1-F7 with failing shell rows before implementing each fix.
- [X] T012 [US3] Expose launcher argv, preserve Command.env, reject unsupported expansions
  and shell mutation, and extend the shared opaque predicate with the later-word backstop.
- [X] T013 [US2] Reproduce F8, accept envelope-only payloads, and retain guard error refusal.
- [X] T014 [US1] Move validation/dispatch tables in-process for F9; retain every payload's
  subprocess replay and three malformed subprocess replays.
- [X] T015 [US3] Reproduce F10 and implement static redirections, background separators,
  quoted here-doc data, and literal cat substitution for commit messages.
- [X] T016 [US2] Reproduce F12 against discover() and move record validation there.
- [X] T017 Reproduce eager command imports and implement lazy dispatch; measure 40 real
  Bash hook invocations, always print p95, and assert below 50 ms outside CI.
- [X] T018 Run the specified full suite, inspect the final diff, and record final evidence.
- F11 is deferred as directed: headless Claude cannot authenticate on this host.

### Fix-round test-first evidence

- F1: 4 failures for option placement and named shell options, then green.
- F2: comment continuation regression failed, then green.
- F3: 21 launcher/backstop failures, then green; positional expansion is now rejected.
- F4: 6 environment propagation failures, then green.
- F5: 7 failures for expansion rejection and literal-dollar decoding, then green.
- F6: 8 interpreter-variant failures, then green.
- F7: 7 shell-mutation failures, then green.
- F8: 38 failures for optional-field acceptance and guard-owned validation, then green.
- F9: hook validation/dispatch now runs in-process; hook suite initially passed in 2.17s.
- F10: 10 redirection/here-doc failures, then green; unsupported substitutions stay errors.
- F12: 2 discovery validation failures, then green.
- Latency: unrelated module import failed the dispatch regression, then green.
- Final inspection added four failing edge cases: dynamic environments, background
  scope, and combined Node eval/print flags. All four passed after fixes.

### Final fix-round verification

- Required interpreter, full suite: `494 passed in 7.16s`.
- Bash hook median: `29.48 ms` over 20 runs (budget: below 50 ms).
- The full suite is below the requested 10-second target, including subprocess replays
  and the benchmark.
- `git diff --check` and authored character/whitespace checks passed.
- Changes remain in the working tree. No commit, push, or gh command was run.

## Delta review fixes

- [X] T019 Replace identifying SessionStart fixture paths and session ID with neutral
  placeholders; remove the local reference path from the payload README.
- [X] T020 Correct the benchmark to 40 Bash PreToolUse replays and p95, enforcing the
  50 ms budget locally and printing the measurement in CI (design section 10.6).
- Regression evidence: the neutral-path test and both local/CI benchmark cases failed
  before the fixes. A simulated 10 ms median with a 100 ms p95 now fails the local
  budget while remaining advisory in CI. Both modes check 40 replays and printed p95.
- These checks live in tests/test_hooks.py and do not depend on tests/test_hygiene.py.
- Required interpreter, full suite: `497 passed in 8.96s`; Bash hook p95: `35.51 ms`
  over 40 runs. The full suite remains below 10 seconds on this host.

## Load-sensitive benchmark and fixture review fixes

- [X] T021 Enforce the local 50 ms p95 budget on hook child CPU time (user plus
  system) over 40 runs; report CPU and wall-clock p95 and document host-load effects.
- [X] T022 Replace all four PreToolUse scratchpad placeholders with
  `/tmp/scratch/example` and add a neutral-path regression.
- Test-first evidence: all five regression cases failed before the fixes, then passed.
  Simulated 100 ms wall time with 20 ms CPU p95 passes; a 100 ms CPU tail fails
  locally despite its 10 ms median. CI remains advisory and reports both metrics.
- Required interpreter, full suite: `500 passed in 7.58s`; 40-run hook p95:
  CPU `27.56 ms`, wall-clock `34.16 ms`. `git diff --check` passed and the
  payload fixtures contain no flagged scratchpad paths. Changes remain uncommitted.

## Second delta review fixes

- [X] T023 [US3] Reproduce R1 and D1-D4 with fail-closed shell table rows and a hook
  regression. Account for every raw git/gh mention, reject nonliteral argv and unsafe
  launchers, preserve literal commit-message here-docs, and flag interpreter stdin.
- [X] T024 Delete the mocked latency-budget self-test for D5; retain the real 40-run
  benchmark and document that CI prints measurements while local runs assert p95.
- [X] T025 Reproduce missing command help descriptions for D6, import all commands
  for top-level help, and retain lazy imports for dispatch and other invocations.
- [X] T026 Run the required full suite and inspect the final working-tree changes.
- Test-first evidence: R1/D1-D4 produced 50 failures, then the focused 58-case table
  passed. Eight additional failures exposed discarded wrapper words, quote boundaries,
  and interpreter option operands; two more caught continuation erasure and a discarded
  redirection delimiter. All now pass.
  D6's help description assertion failed before the fix; dispatch laziness stayed green.
- Required interpreter, final full suite: `561 passed in 8.26s`. Hook p95 over 40
  runs: CPU `29.41 ms`, wall-clock `34.41 ms`. Diff and authored whitespace/character
  checks passed. Changes remain uncommitted; no commit, push, or gh command was run.

## G review fixes

- [X] T027 [US3] Reproduce G1 and G2 before fixing quote/backslash mention checks,
  decoded launcher argv checks, and resolved xargs git/gh refusal.
- [X] T028 [US3] Reproduce G3 and allow literal Git revision braces while refusing
  comma and range brace expansion.
- [X] T029 [US3] Reproduce G4 and exempt dot-prefixed paths and here-doc data owned
  by plain git/gh. Keep other commands' here-doc bodies checked on shared lines.
- [X] T030 Increase the real CPU/wall p95 benchmark to 60 runs for G5; retain the
  local 50 ms CPU assertion and printed measurements.
- [X] T031 Run the required full suite and inspect the final working-tree changes.
- Test-first evidence: G1 and G2 produced nine failures before their fixes; the
  xargs-only fix passed all four G2 rows. G3 produced five failures and three
  passing refusal controls. G4 produced ten failures and five passing ownership
  controls. All 241 shell cases now pass.
- G1 supersedes the older nested continuation allow expectation: a quote-obfuscated
  git name inside a nested script now fails closed. G3 similarly supersedes the
  old rejection of a lone closing brace, which cannot expand.
- Required interpreter, full suite: `592 passed in 8.79s`. Hook p95 over 60 runs:
  CPU `29.71 ms`, wall-clock `37.54 ms`. The 50 ms local CPU assertion remains.
- Diff and authored whitespace/character checks passed. Changes remain uncommitted.

## Post-rebase review fixes

- [X] T032 Reproduce hyphenated dispatch and discovery fallback failures, map typed
  hyphens to module underscores, and document the convention in the CLI contract.
  Keep matching command dispatch lazy; unknown names now require full discovery.
- [X] T033 Extend neutral-path coverage to every payload, replace home-directory
  placeholders, and preserve the adapter and hygiene tests unchanged.
- Test-first evidence: all three reported failures reproduced. Three new dispatch
  cases and nine payload path cases failed before the fixes, then passed. Focused
  CLI, adapter, hygiene, and payload validation: `50 passed in 3.09s`.
- [X] T034 Run the required full suite and inspect the working-tree diff.
  Result: `761 passed in 16.03s`; hook p95 over 60 runs: CPU `42.36 ms`, wall
  `96.16 ms`. `git diff --check` passed. The rebased commit remains intact;
  these fixes are uncommitted.
