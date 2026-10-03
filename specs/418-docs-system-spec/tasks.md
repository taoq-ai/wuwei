# Tasks: Documentation system: a configured docs system with a docs obligation per tier checked at the gate and at close, and pages written from the records

The amendment text (T003 to T006) was written by the spec author and is already in the
working tree. The builder runs the phrase check (T002) red against a `git archive main`
export and green on the worktree before accepting the amendment, then reviews and
verifies. No runtime code, no committed test.

## Phase 1: Setup

- [X] T001 Write specs/418-docs-system-spec/spec.md, plan.md and tasks.md from issue #418, the orchestrator notes and the owner's follow-up that the docs system belongs in the interview.

## Phase 2: Test first (US1, US2, US3)

Independent test: the check script in specs/418-docs-system-spec/plan.md "Verification commands".

- [X] T002 [US1] [US2] [US3] Copy the check script from specs/418-docs-system-spec/plan.md into a scratch directory outside the repository as check_418.py. Run it against a `git archive main docs/specs` export and confirm it fails with `AssertionError: section 5.12`; then run it on the worktree and confirm it prints `OK: documentation system stated once`.

## Phase 3: Amendment (written by the spec author; builder reviews)

- [X] T003 [US1] Add `### 5.12 Documentation system (owner, 2026-10-03, #418)` to docs/specs/2026-09-24-wuwei-design.md after 5.9: the `[docs]` configuration keys and defaults, and the setup, interview and doctor paragraph.
- [X] T004 [US2] In the same 5.12 of docs/specs/2026-09-24-wuwei-design.md: the docs obligation (value forms, who sets it, `light` exemption and `docs.exempt`) and the checks before the gate verdict and at close, with `strict_close`.
- [X] T005 [US3] In the same 5.12 of docs/specs/2026-09-24-wuwei-design.md: writes (`docs page`, `docs publish`), approval and content rules, `docs.written`, the MCP tool patterns, the port operations and the three adapters with credentials and the contract test, and the owner-facing surfaces.
- [X] T006 [US3] Widen the 4.1 PreToolUse outward row to "chat, tracker or docs (5.12) adapter call" and add the `docs (5.12)` row to the section 8 adapter table in docs/specs/2026-09-24-wuwei-design.md.
- [X] T007 [US1] [US2] [US3] Consistency review of docs/specs/2026-09-24-wuwei-design.md as plan.md "Consistency review" lists (3.4, 3.5, 4.3, 4.8, 4.9, 5.1, 5.2, 5.3, 5.4, 5.6, section 8, 9.1). Edit only the design spec, only for a real conflict, keeping the T002 phrases; extend the check first and see it fail when an edit adds a rule, then rerun T002 on the worktree.
- [X] T010 [US2] [US3] Review fixes in 5.12 of docs/specs/2026-09-24-wuwei-design.md, check extended first and seen red: every docs write goes through the humanizer pass (`[outward] humanize`, #420); under `markdown`, `plan set` refuses `new` and `docs page` runs before the gate; the doctor checks `space` and credentials only for `notion` and `confluence` and `root` for `markdown`.

## Phase 4: Verify (US4)

- [X] T008 [US4] Run `git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts .github docs/site tests README.md .specify` (must be empty) and `git status --short` (only docs/specs/2026-09-24-wuwei-design.md and specs/418-docs-system-spec/).
- [X] T009 [US4] Run `python -m pytest -q` from the repository root; everything passes, including tests/test_docs.py. Check docs/specs/2026-09-24-wuwei-design.md and every file in specs/418-docs-system-spec/ for em-dashes, emojis and absolute local paths.
