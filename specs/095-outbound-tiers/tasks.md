# Tasks: Outbound approval tiers

## Setup

- [X] T001 Read contracts and existing policy; write spec.md and plan.md in specs/095-outbound-tiers/.

## US1: Safe work replies

- [X] T002 [US1] Add failing acceptance, audience, risk-pattern and PR-evidence tables in tests/test_outbound.py.
- [X] T003 [US1] Implement destination-aware classification and defaults in cli/wuwei/outward.py and cli/wuwei/workspace.py.

## US2: Consistent enforcement

- [X] T004 [US2] Add failing CLI, hook, port, bypass and scope tests in tests/test_outbound.py; update superseded cases in tests/test_outward.py.
- [X] T005 [US2] Wire cli/wuwei/commands/outbound.py, cli/wuwei/guards/outward.py, cli/wuwei/registry.py and shared check_call in cli/wuwei/outward.py.

## Polish

- [X] T006 Document configuration and interface in templates/workspace/config.toml and specs/095-outbound-tiers/contracts/outbound.md.
- [X] T007 Run full pytest suite, review diff and check changed files for forbidden characters and local paths.

## Adversarial fix round

- [X] T008 [F1] Reproduce real chat thread payloads; draft all unmeasured chat threads.
- [X] T009 [F2] Reproduce forged tracker channels; remove tracker from auto-send kinds.
- [X] T010 [F3] Reproduce irrelevant-tool scope and invalid paths; match tools first and skip bad targets.
- [X] T011 [F4] Reproduce config file and shell writes; protect config.toml through normalized targets.
- [X] T012 [F5] Reproduce identity namespace collisions; require matching orgs for GitHub participants.
- [X] T013 [F6, F7] Share workspace scope and Git anchor lookup; document the auto-send ceiling.
- [X] T014 Run the full required pytest suite and guard pre-flight checks after fixes.

## Dependencies and execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007. Tests precede implementation.
US1 is the classifier MVP; US2 depends on it. No parallel work is needed because both
stories modify the shared policy. Each story is independently checked with in-process
tables; US2 additionally checks hook translation and port side effects.

## Verification evidence

- New classifier tables: 86 failing before implementation, then 86 passing.
- Hook/CLI/port/scope tables: 20 expected integration failures, then passing.
- Regression tables reproduced malformed SHA, targeted-thread scope, conflicting
  PR identifiers, external overall reviewers and malformed PR references before fixes.
- Independent review and delta review completed; reported blockers fixed and tested.
- Final full suite: 3017 passed in 23.24s.
- Diff whitespace, authored-character and machine-local-path checks passed.
- Configuration template and commented pattern examples parse as TOML.

## Fix-round verification

- F1: four thread regressions failed before the fix, then passed.
- F2: forged tracker channel failed through hook and port, then both passed.
- F3: both invalid-target cases and the relevance-before-scope test failed, then passed.
- F4: 23 config-write cases failed, then passed, including aliases and normalized writes.
- F5: legacy namespace trust and namespaced positive cases failed, then passed.
- Full required interpreter run: 3057 passed in 24.04s.
- Guard pre-flight: relevance precedes target scope, unrelated tools pass, relevant
  failures close, resolved config targets are protected, reads remain allowed, hook
  refusals translate correctly, and adapter refusals have no send side effects.
- Existing workspace/repo/worktree scope tests pass after the shared-helper move.
- Diff whitespace and template TOML checks passed; no authored em-dashes or local
  machine paths were introduced. Changes remain uncommitted.
