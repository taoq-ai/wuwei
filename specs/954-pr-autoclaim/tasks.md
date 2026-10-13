# Tasks: PR Auto Claim

- [X] T001 Reproduce the planner field case with a failing PostToolUse test.
- [X] T002 Parse successful PR output and record matched or unclaimed PRs.
- [X] T003 Offer unclaimed PRs from next and cover failure and fail-open paths.
- [X] T004 Restore the original bare PR creation refusal and its tests.
- [X] T005 Test and prevent an ungated item's automatic PR link.
- [X] T006 Filter configured repositories, choose or request a goal, refresh open PR evidence, and rank recovery first.
- [X] T007 Test ambiguous commands and output, claim refusal, branch recording, approved matching, and timeout.
- [X] T008 Run every affected test file, inspect the diff, and record verification.

Verification: 23 explicit test files, including `tests/test_signal_status.py`, passed with
`2713 passed in 188.08s (0:03:08)`.

- [X] T009 Test the matched-item claim offer and replace the advice to create an existing PR.
- [X] T010 Test fresh cache reuse, event refresh, poll cadence and cleared rows; limit the refresh path.
- [X] T011 Run every affected test file after round 2 and inspect the final diff.

Round 2 verification: 19 explicit test files passed with `2099 passed in 131.53s (0:02:11)`.
