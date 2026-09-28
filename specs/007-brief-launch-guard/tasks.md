# Tasks

## US1: Briefs
- [X] T001 [US1] Add ruling and protected-path tests and ordered refusals/header cases in tests/test_brief.py; run red.
- [X] T002 [US1] Add adapter contract tests in tests/test_brief_adapters.py; run red.
- [X] T003 [US1] Extend cli/wuwei/registry.py, adapters/vcs/git.py and tests/fakes/vcs.py for prior branches.
- [X] T004 [US1] Implement cli/wuwei/brief.py, cli/wuwei/commands/brief.py and config defaults in cli/wuwei/workspace.py; run brief tests green.

## US2: Launch guard
- [X] T005 [US2] Add 0/1/2 and bypass table tests in tests/test_agent_launch.py and host adapter tests; run red.
- [X] T006 [US2] Implement cli/wuwei/guards/agent_launch.py and adapters/host/local.py; run launch tests green.

## Validation
- [X] T007 Update templates/workspace/config.toml and hook replay expectations in tests/test_hooks.py; run full pytest suite and inspect file hygiene.

Dependencies: T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007.
Each story is verified independently; sequential execution keeps shared files simple.

## Review fixes

- [X] T008 F1/F7: test workspace scope and role relevance first; restore clean hook replay.
- [X] T009 F2: test Darwin available-page sum and Linux MemAvailable; keep invalid reads exit 2.
- [X] T010 F5: log and recheck HEAD for every worktree brief, including changes during launch probes.
- [X] T011 F3: default seats, atomically check capacity/reuse and reserve; release on SubagentStop.
- [X] T012 F6: use reservation liveness, correlate runtime stop ids, handle stand-down and report stale seats; move optional PID probes to host.
- [X] T013 F8/F9: remove private patterns and duplicate defaults; use owner patterns and repos[].default_branch.
- [X] T014 F4: prior deferral to issue #11, superseded by T017 now that state.RESERVED exists.
- [X] T015 Run full pytest with the requested interpreter, inspect the whole diff and leave changes uncommitted.

## Verification evidence

- Review regression tests were run red before each correctness change: workspace/role
  scoping (8 failures), memory (4), HEAD binding (3), reservation lifecycle (8), defaults
  (1), stale/stop handling (5), host PID port (7), and HEAD changing during launch (1).
- Targeted suites passed after fixes. Concurrent launch tests cover duplicate briefs and
  two distinct briefs competing for one slot. Stop tests cover named seats and runtime
  ids with string or text-block transcript prompts.
- Full suite before final HEAD timing regression: 1074 passed in 13.41s.
- Final full suite with the requested interpreter: 1075 passed in 13.68s.
- Whole diff (including untracked files) scanned for private-harness identifiers and
  machine paths: no matches. git diff --check passed. No commits, pushes or gh commands.

## Post-rebase review fixes

- [X] T016 Resolve the four conflict files preserving both VCS operations, the closed
  allowlist, owner/config defaults and isolated guard discovery. Adapt old fixtures to
  read-only state files and the merged retro guard without changing Git state.
- [X] T017 F4: test whole-seat and nested CLI writes red, reserve seats through
  state.RESERVED, and permit reservation writes only through launch and stop producers.
- [X] T018 F10: test stand-down event rejection red, remove its release branch and
  reserve its event kind. Document the dedicated owner command as an out-of-scope follow-up.
- [X] T019 F11: test overnight stop correlation and missing/unmatched transcripts red;
  use the transcript brief's day, log unmatched stops, and never block reservation cleanup.
- [X] T020 F12: test omitted/empty subagent_type red and allow before relevant validation.
- [X] T021 F13: test stale capacity/refusal behavior and four-hour defaults red; retain
  reservations, name them in refusals, and allow unrelated items when capacity permits.
- [X] T022 F14: remove unused host.process_alive from registry, adapters, fake and tests.
- [X] T023 Run the requested full pytest command and inspect the final working tree diff.

Follow-up outside #7: add a dedicated owner command for stale reservation release that
refuses seat callers. SubagentStop remains the only automatic release.

Regression evidence: F4 had 2 expected failures, F10 had 1, F11 had 7, F12 had 4,
and F13 had 6. Each targeted suite passed after its fix.

Final requested pytest run: 2087 passed in 15.37s. Conflict markers removed; the
Git index and rebase state remain for the orchestrator. Changes are uncommitted.
