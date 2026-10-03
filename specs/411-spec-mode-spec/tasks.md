# Tasks: Specification mode, a configured spec engine (spec-kit by default) whose steps the hooks enforce on every non-trivial item, with superpowers and OpenSpec as alternatives

A spec-only feature. The amendment text is in specs/411-spec-mode-spec/plan.md "What
changes" (blocks A to E). The builder runs the phrase check (T002) red against a
`git archive main` export before pasting anything, pastes the text, reviews it, and runs
the check green. No runtime code, no committed test.

## Phase 1: Setup

- [X] T001 Write specs/411-spec-mode-spec/spec.md, plan.md and tasks.md from issue #411 and the orchestrator notes.

## Phase 2: Test first and analysis (US1, US2)

Independent test: the check script in specs/411-spec-mode-spec/plan.md "Verification commands".

- [X] T002 [US1] [US2] Copy the check script from specs/411-spec-mode-spec/plan.md into a scratch directory outside the repository as check_411.py. Export `git archive main docs/specs .specify/memory AGENTS.md` into `<scratch>/main` and run the check there; confirm it fails with `AssertionError: 5.10 section`.
- [X] T003 [US3] Run speckit-analyze over specs/411-spec-mode-spec/spec.md, plan.md and tasks.md (the rule this feature introduces, applied to itself) and save the report as specs/411-spec-mode-spec/analysis.md. Resolve any CRITICAL or HIGH finding in those three files before T004. Result: no CRITICAL or HIGH finding; one MEDIUM (no `checklists/`), resolved by adding checklists/requirements.md. The builder harness refused to write analysis.md from a subagent, so the report went to the orchestrator, which saves it here.

## Phase 3: Amendment (paste plan.md blocks A to E; builder reviews)

- [X] T004 [US1] Paste block A (3.3 `config.toml` line) and block B (two 4.1 rows and the SubagentStop row) into docs/specs/2026-09-24-wuwei-design.md.
- [X] T005 [US1] Paste block C, `### 5.10 Specification mode (owner, 2026-10-03, #411)`, into docs/specs/2026-09-24-wuwei-design.md after 5.9 and before `## 6. Memory`.
- [X] T006 [US2] Paste block D into .specify/memory/constitution.md: the Specification mode bullet after "One GitHub issue is one spec-kit feature", and Version 1.2.0 with Last Amended 2026-10-03.
- [X] T007 [US2] Paste block E into AGENTS.md, replacing the "Work follows spec-kit:" bullet; keep line 1 unchanged.
- [X] T008 [US1] [US2] Consistency review of docs/specs/2026-09-24-wuwei-design.md, .specify/memory/constitution.md and AGENTS.md as plan.md "Consistency review" lists (3.3, 4.1, 4.4, 5.1, 5.2, 5.3, 5.7, 9.1, 10.6; constitution and AGENTS.md step order). Edit only these three files, only for a real conflict, keeping the T002 phrases; rerun the check on the worktree after any edit (extend the check first and see it fail when an edit adds a rule).
- [X] T009 [US1] [US2] Run check_411.py on the worktree root; it prints `OK: specification mode stated once`.

## Phase 4: Verify (US3, US4)

- [X] T010 [US3] Read 5.10 against plan.md "Deferred": every file, function, config key, state field, event kind and refusal the implementation needs is named in one of the two; record anything missing under Assumptions in specs/411-spec-mode-spec/spec.md.
- [X] T011 [US4] Run `git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts .github docs/site tests README.md` (must be empty) and `git status --short` (only docs/specs/2026-09-24-wuwei-design.md, .specify/memory/constitution.md, AGENTS.md and specs/411-spec-mode-spec/).
- [X] T012 [US4] Run `python -m pytest -q` from the repository root; everything passes, including tests/test_docs.py and tests/test_calibrate.py. Check the three amended files and every file in specs/411-spec-mode-spec/ for em-dashes, emojis and absolute local paths.
