# Tasks: a wake fires only for a change that needs an action

Test first: each test task runs and fails for the expected reason before its implementation
task. Use the existing fixtures in `tests/test_watch.py` (`case`, `events`, `advance`,
`lifecycle_module`, `measured_pr`, `thread`, `check`) and the fake code host; no test reaches
git or the network. Run the touched test files, then the full suite.

## Phase 1: a timestamp alone never wakes (FR-001, FR-002; US1)

- [X] T001 Tests in `tests/test_watch.py`: after a baseline poll, moving only
  `host.results['pr'].data['updated_at']` makes `watch.poll` return 0, writes no
  `pr.changed` and leaves no `wake` in `watch.saved(root)`; a baseline whose snapshot has an
  extra `updated_at` fingerprint (write it with `watch.save(root, {'prs': ...})`) is no change
  on the next poll. Drop `updated_at` from the parameters of
  `test_pr_poll_persisted_diff_wakes_once`.
- [X] T002 Implement in `cli/wuwei/watch.py`: remove `updated_at` from `snapshot`, and
  record a change in `poll` only when the field list over the current snapshot's keys is not
  empty. T001 passes.

## Phase 2: the parts list and the action map (FR-003, FR-004; US3, US4)

- [X] T003 Tests in `tests/test_watch.py`: rewrite `test_summary_rules`,
  `test_summary_names_comments_files_and_failed_checks` and
  `test_summary_without_prior_facts_names_fields` against `watch.parts(before, after,
  fields)`: each case asserts the `(kind, text)` pairs with today's texts (the `updated_at`
  row becomes kind `updated`, text `updated (updated_at)`; no prior facts gives one
  `updated (checks, head)` part). Add: a failed check on head `a` and on head `b` give
  different evidence; every key of `watch.ACTIONS` is a kind some case produces, and
  `resolved`, `check_passed`, `requested`, `new`, `gone` and `updated` are not in it.
- [X] T004 Implement `ACTIONS` and `parts` in `cli/wuwei/watch.py` (plan, Design), replacing
  `summary`; drop the unused `Counter` import. T003 passes.

## Phase 3: poll fires only actionable, undelivered parts (FR-005; US2, US3, US4)

- [X] T005 Tests in `tests/test_watch.py`:
  - merge delivered once: the PR merges, `poll` returns 1 with summary `PR <ref>: merged`;
    the planner's Stop consumes it; the next poll returns 0 and writes no `pr.changed`;
    then a check fails and the next poll returns 1 with summary
    `PR <ref>: check ci failed` only, and the Stop message carries only that line.
  - a passed check, a resolved conflict or an added reviewer alone returns 0, no
    `pr.changed`, and `watch.saved(root)['why'][REF]['suppressed']` names the part with
    `no action`.
  - a failed check and a passed check in one diff fire with the failed check only.
  - a part already in `watch.delivered` with the same fingerprint (reset `facts` for the PR
    to the pre-merge facts with `watch.save`, keep `delivered`) is suppressed with
    `already delivered` and returns 0.
  - a conflict that was resolved and returns fires again.
  - `delivered` and `why` carry over midnight (advance a day with the PR still owned) and
    keep only owned PRs.
  Update `test_poll_new_gone_and_midnight`, `test_midnight_without_day_state_keeps_polling`,
  `test_stop_wake_once_accumulates_until_seen` and
  `test_poll_in_place_edit_and_unordered_evidence` as the plan's "Tests that change" says.
- [X] T006 Implement in `cli/wuwei/watch.py`: `carried(root, key)`, used for `prs`, `facts`,
  `delivered` and `why` in `poll`; the per-part decision, the `delivered` and `why` records,
  and the wake block over fired PRs only (plan, Design). T005 passes, and
  `tests/test_listen.py`, `tests/test_pr_ownership.py` and `tests/test_signal_status.py`
  pass unchanged.

## Phase 4: SessionStart in the planner session delivers the wake (FR-006; US2.3, US2.4)

- [X] T007 Tests in `tests/test_watch.py`: with `planner_session_id = 'planner'`, a head
  change wakes; `session_start({'cwd': ..., 'session_id': 'planner'})` shows the summary and
  records `session: wake-seen`; a later actionable change and the planner's Stop carry only
  the new line. With `session_id: 'seat'` the summary is shown, the marker stays unseen and
  the planner's Stop still delivers it. `test_stop_and_session_start_lead_with_the_summary`
  (no session id) passes unchanged.
- [X] T008 Implement the `consume=` argument in `session_start`,
  `cli/wuwei/guards/lifecycle.py:100`. T007 passes.

## Phase 5: `wuwei watch why <pr>` (FR-007; US5)

- [X] T009 Tests in `tests/test_watch.py` through `main(['watch', 'why', REF])`: after a poll
  that fired `check ci failed` and suppressed `merged (already delivered)`, it exits 0 and
  prints `PR <ref> (<at>)`, `fired: check ci failed (start a fix round)` and
  `suppressed: merged (already delivered)`; a PR with no record exits 1 with
  `no recorded change`; `main(['watch', 'why', 'not-a-ref'])` exits 2 with the reference
  error; `main(['listen', 'why', REF])` is a usage error (no `why` for the listener).
- [X] T010 Implement `why` in `cli/wuwei/commands/watch.py` (`add` for `watch` only, `run`,
  `why`). T009 passes.

## Phase 6: docs and the full suite (FR-008)

- [X] T011 Update `docs/specs/2026-09-24-wuwei-design.md` 4.2.1 "Wake outside the model",
  `docs/site/daily.md` (the PR changes paragraph) and `docs/site/reference.md` (`watch why`
  and its exits), as the plan's Docs section says. Run `tests/test_docs.py`.
- [X] T012 Run the full suite with `python -m pytest -q` from the repository root; every test
  passes. Check the changed files for em-dashes, emojis and absolute local paths.
- [X] T013 Review fix F1: a delivered mark clears once its state clears (mergeable True,
  state open, check success), so a conflict, a failed check or a close that comes back after
  passing through a state no part names fires again. Tests in `tests/test_watch.py`.
