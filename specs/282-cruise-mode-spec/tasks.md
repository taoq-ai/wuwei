# Tasks: Cruise mode, graduated autonomy per decision class, promoted from the ledger, with ceilings

The amendment text (T003 to T005) was written by the spec author and is already in the
working tree. The builder runs the phrase check (T002) red against a `git archive main`
export and green on the worktree before accepting the amendment, then reviews and
verifies. No runtime code, no committed test.

## Phase 1: Setup

- [X] T001 Write specs/282-cruise-mode-spec/spec.md, plan.md and tasks.md from issue #282 and the orchestrator notes.

## Phase 2: Test first (US1, US2)

Independent test: the check script in specs/282-cruise-mode-spec/plan.md "Verification commands".

- [X] T002 [US1] [US2] Copy the check script from specs/282-cruise-mode-spec/plan.md into a scratch directory outside the repository as check_282.py. Run it against a `git archive main docs/specs` export and confirm it fails with `AssertionError: `Class:``; then run it on the worktree and confirm it prints `OK: cruise mode stated once`.

## Phase 3: Amendment (written by the spec author; builder reviews)

- [X] T003 [US1] Amend design 5.8 in docs/specs/2026-09-24-wuwei-design.md: heading amended date; `Class:` in the record shape; `Decided-by:` values; Routing by class; Enforcement refuses an unknown class and counts by class.
- [X] T004 [US1] Add `#### 5.8.1 Cruise mode` to docs/specs/2026-09-24-wuwei-design.md: levels, class table with defaults and ceilings, `[decisions.cruise]` keys, conditions, ceilings, merge mapping, promotion and demotion with the weekly sample, kill switch and status-line text.
- [X] T005 [US2] Reword G1, 4.6 (one sentence), 5.4, 5.9 tiers and the 6.8 promote lint target in docs/specs/2026-09-24-wuwei-design.md so none contradicts 5.8.1.
- [X] T006 [US1] [US2] Consistency review of docs/specs/2026-09-24-wuwei-design.md as plan.md "Consistency review" lists (4.6, 4.7, 4.9, 5.3, 5.5, 5.6, 5.7, 5.9, 6.8, 15.8). Edit only the design spec, only for a real conflict, keeping the T002 phrases; rerun T002 on the worktree after any edit.
- [X] T006a [US1] Review fixes in docs/specs/2026-09-24-wuwei-design.md 5.8.1 and 6.8: name `memory/cruise.json` as the running-level store with `levels.<class>` only lowering; add scope agreed with other people to the ceilings; the margin's runner-up counts options failing a must; merge keeps the ceilings. Extend the plan.md check script first and see it fail.

## Phase 4: Verify (US3)

- [X] T007 [US3] Run `git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts .github docs/site tests README.md .specify` (must be empty) and `git status --short` (only docs/specs/2026-09-24-wuwei-design.md and specs/282-cruise-mode-spec/).
- [X] T008 [US3] Run `python -m pytest -q` from the repository root; everything passes, including tests/test_docs.py. Check docs/specs/2026-09-24-wuwei-design.md and every file in specs/282-cruise-mode-spec/ for em-dashes, emojis and absolute local paths.
