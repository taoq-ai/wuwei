# Tasks: Headless E2E

- [X] T001 Read existing producers and write spec and plan.
- [X] T002 Write failing offline tests for credential gating, bounded adapter,
  OAuth errors, scratch isolation and evidence mutations in tests/test_headless_e2e.py.
- [X] T003 Implement scripts/headless_adapter.py and scripts/headless_e2e.py.
- [X] T004 Write failing workflow and documentation contract tests.
- [X] T005 Add gated CI job and docs/headless-e2e.md local run guide.
- [X] T006 Run focused tests, full pytest, local skip/auth probe and hygiene checks;
  record measured results and deferred live validation.
- [ ] T007 Resolve blocking review F1: complete one credentialed live day and
  record exit code and duration for the PR body. Adjust the process deadline only
  if the measured run reaches it, keeping it within the eight-minute job cap.
- [X] T008 Resolve review F3: remove the fixed-call adapter allowlist and unused
  SYSTEMROOT inheritance; retain own_group for the observer shim. Verify the
  environment assertion fails before the change and passes after it.
- [X] T009 Fix the full-suite date-dependent retro fixture: align temporary Git
  author and committer dates with WUWEI_NOW after reproducing its failure.

## Verification evidence

- Full requested pytest rerun: 5367 passed, 5 skipped in 109.10s (0:01:49).
- Focused headless runner checks: 34 passed, including red-to-green mutations
  for launch prompt binding, required hooks, final close and malformed payloads.
- Real local signed-plugin fixture, integrity check, hook denial and build-next
  launch smoke passed. The no-key command printed its skip message.
- Local Claude execution exited 2, unmeasured: authentication unavailable.
  Claude auth status reported no logged-in session. The expired OAuth diagnostic
  is covered with recorded error results; a credentialed live pass is unverified.
- Adversarial review F1 remains blocking: no credentialed live pass is measured.
- Diff whitespace, authored-file character and local-path hygiene checks passed.

## Review fix evidence (2026-09-29)

- F1: no API key is exported; `claude auth status` reports `loggedIn: false`.
  `claude auth login` exited 1 in 0.14s: its OAuth callback server could not start.
  From the worktree root, `python3 scripts/headless_e2e.py --local-login` exited 2
  in 2.86s with `Claude authentication failed; run claude auth login or set
  ANTHROPIC_API_KEY`. This is unmeasured, not a live acceptance pass. The 300-second
  deadline remains unchanged because the attempt did not reach it. A successful
  credentialed run and its PR-body evidence remain outstanding.
- F2: retain the separate job for an independent eight-minute timeout and parallel
  execution with skill-evals.
- F3: the scratch environment assertion failed on inherited SYSTEMROOT before
  removal. The obsolete allowlist assertion was removed with its implementation.
- Full-suite follow-up (2026-09-30): the first run had 1 failure, 5366 passed and
  5 skipped. `test_promotion_changelog_and_real_stop` also failed in isolation:
  WUWEI_NOW fixed September 29 while real Git commits used September 30. Pinning
  the fixture's Git author and committer timestamps to WUWEI_NOW fixes the test
  without changing production behavior. The regression and all 34 headless tests
  then passed together (35 passed in 2.68s).
- Final full-suite rerun using the requested pipeline interpreter exited 0:
  `5367 passed, 5 skipped in 109.10s (0:01:49)`.
