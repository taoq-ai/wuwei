# Tasks: Assume and record on two-way doors, the mandate block, external confirmation is never a seat precondition, time-boxed waits

The amendment text (T003 to T006) was written by the spec author and is already in the
working tree. The builder runs the phrase check (T002) red against a `git archive main`
export and green on the worktree before accepting the amendment, then reviews and
verifies. No runtime code, no committed test.

## Phase 1: Setup

- [X] T001 Write specs/301-negotiation-spec/spec.md, plan.md and tasks.md from issue #301, the orchestrator notes and the owner's request for a ping-pong signal.

## Phase 2: Test first (US1, US2, US3)

Independent test: the check script in specs/301-negotiation-spec/plan.md "Verification commands".

- [X] T002 [US1] [US2] [US3] Copy the check script from specs/301-negotiation-spec/plan.md into a scratch directory outside the repository as check_301.py. Run it against a `git archive main docs/specs` export and confirm it fails with `AssertionError: mandate block`; then run it on the worktree and confirm it prints `OK: negotiation rules stated once`.

## Phase 3: Amendment (written by the spec author; builder reviews)

- [X] T003 [US1] Amend docs/specs/2026-09-24-wuwei-design.md 5.2 (Briefs: the mandate block), 5.3 (Assume and record), 5.4 (never asked what a mandate lets a seat decide), 5.8 (records only for owner or cruise answers; every-runtime question rule) and the 4.1 SubagentStop row.
- [X] T004 [US2] Add the External confirmation paragraph and the `decisions.wait_hours` time box to the new `#### 5.8.2` in docs/specs/2026-09-24-wuwei-design.md, and point the 5.8.1 `message` row to it.
- [X] T005 [US3] Replace the 5.3 Cycle budget bullet with the Negotiation budget in docs/specs/2026-09-24-wuwei-design.md and point 4.6 to it; add the Negotiation loops paragraph to 5.8.2, the loop tiers and status-line count to 5.9, and owner asks per item and unnecessary asks to the 5.8 metrics.
- [X] T006 [US1] Point the 5.8.1 `approach` row in docs/specs/2026-09-24-wuwei-design.md to 5.3 (an assumption, not a record, at L2 or L3).
- [X] T007 [US1] [US2] [US3] Consistency review of docs/specs/2026-09-24-wuwei-design.md as plan.md "Consistency review" lists (G1, 4.2, 4.6, 4.9, 5.5, 5.7, 5.8.1, 5.9, 15.4) and of .specify/memory/constitution.md Cycle budget. Edit only the design spec, only for a real conflict, keeping the T002 phrases; rerun T002 on the worktree after any edit (extend the check first and see it fail when an edit adds a rule).

- [X] T010 [US1] [US2] [US3] Review fixes (_pipeline review F1 to F4): the time box confirms the `assumption: external` reading only when it is two-way and no other 5.8.1 ceiling applies, the draft stays unsent; 5.3 sends 5.8.1 ceilings and trust-surface areas to a record; the 5.2 L2/L3 clause defers to 5.8.1's conditions; the reconsideration is recorded in the item's spec; `steward.loop_threshold` defaults to 9. Extend the T002 check first and see it fail on the pre-fix text.

## Phase 4: Verify (US4)

- [X] T008 [US4] Run `git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts .github docs/site tests README.md .specify` (must be empty) and `git status --short` (only docs/specs/2026-09-24-wuwei-design.md and specs/301-negotiation-spec/).
- [X] T009 [US4] Run `python -m pytest -q` from the repository root; everything passes, including tests/test_docs.py. Check docs/specs/2026-09-24-wuwei-design.md and every file in specs/301-negotiation-spec/ for em-dashes, emojis and absolute local paths.
