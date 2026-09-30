# Tasks: Hooks are cooperative mistake prevention; publication policy is enforced where changes land

The amendment text (T003 to T006) was written by the spec author and is already in the
working tree. The builder writes the test (T002) and shows it red against a `git archive
main` export before accepting the amendment, then reviews and verifies. No runtime code.

## Phase 1: Setup

- [X] T001 Write specs/237-spec-guard-boundaries/spec.md, plan.md and tasks.md from issue #237, the orchestrator notes and the #222 review notes.

## Phase 2: Test first (US1 to US4)

Independent test: `python -m pytest -q tests/test_docs.py -k guard_boundaries`.

- [X] T002 [US1] [US2] [US3] [US4] Append `test_guard_boundaries_are_stated_once` to tests/test_docs.py as sketched in plan.md "What the builder adds". Run it against a `git archive main` export in a scratch directory (plan.md "Verification commands") and confirm it fails on the first 4.5 phrase (`the parser is the only local check`); then run it in the worktree and confirm it passes.

## Phase 3: Amendment (written by the spec author; builder reviews)

- [X] T003 [US1] [US2] Amend design 4.5 in docs/specs/2026-09-24-wuwei-design.md: own records keep normalisation and the bypass table; publishing actions refuse what is recognisable with the guarantee in host plus credential layout (`wuwei init` documents, `wuwei config check` verifies); `pre-push` and `permissions.deny` are local checks, not boundaries; narrow argv allowlist for privileged publish only; development-wide allowlist rejected with the reason.
- [X] T004 [US1] Amend design 9.1 in docs/specs/2026-09-24-wuwei-design.md: cooperative mistake prevention, never an isolation boundary, no hook is a hard boundary; hard boundaries listed once including publication credentials; "Local anchors" reworded to local checks that are not boundaries.
- [X] T005 [US4] Add the "What a real day must prove" bullet at the end of section 10 in docs/specs/2026-09-24-wuwei-design.md, naming #239.
- [X] T006 [US3] Amend the cycle budget bullet and the version footer (1.1.0, 2026-09-30) in .specify/memory/constitution.md.
- [X] T007 [US1] Align the Threat model 9.1 paragraph in docs/site/security.md with design 9.1.
- [X] T008 [US1] Consistency review as plan.md "Consistency review" lists (design 4.1, 4.5, 4.6, 4.7, 7.1, 9.1; docs/site/security.md; docs/integrity.md; docs/site/reference.md lines 59 and 71). Edit only the three amended documents, only for a real conflict, and keep the T002 phrases intact.
- [X] T011 [US1] Review fix F1: take merge out of the seat credential rule in design 4.5 and 9.1 and docs/site/security.md (the shepherd merges through `wuwei merge`; merge is guaranteed by the protected ref's required checks and reviews), with the phrases pinned in tests/test_docs.py. F2: the cycle budget consequence in .specify/memory/constitution.md is one sentence naming #222.

## Phase 4: Verify (US5)

- [X] T009 [US5] Run `git diff --stat $(git merge-base HEAD main) -- cli adapters hooks bin agents charters skills templates scripts .github` (must be empty) and `git diff $(git merge-base HEAD main) -- tests` (must show only the added function in tests/test_docs.py, no removed lines).
- [X] T010 Run `python -m pytest -q` from the repository root; everything passes. Check every changed file for em-dashes, emojis and absolute local paths.
