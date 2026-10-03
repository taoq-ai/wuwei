# Tasks: Telemetry: signals at no hook cost, weekly aggregation with proposals, anonymous sharing

The amendment text (T003 to T006) was written by the spec author and is already in the
working tree. The builder runs the phrase check (T002) red against a `git archive main`
export and green on the worktree before accepting the amendment, then reviews and
verifies. No runtime code, no committed test. The implementation is #422 (plan.md,
"Hand-off to #422").

## Phase 1: Setup

- [X] T001 Write specs/421-telemetry-spec/spec.md, plan.md and tasks.md from issue #421, the owner's addition (anonymous means no login) and the orchestrator notes.

## Phase 2: Test first (US1, US2, US3)

Independent test: the check script in specs/421-telemetry-spec/plan.md "Verification commands".

- [X] T002 [US1] [US2] [US3] Copy the check script from specs/421-telemetry-spec/plan.md into a scratch directory outside the repository as check_421.py. Run it against a `git archive main docs/specs .specify/memory` export and confirm it fails with `AssertionError: section 5.13`; then run it on the worktree and confirm it prints `OK: telemetry stated in 5.13`.

## Phase 3: Amendment (written by the spec author; builder reviews)

- [X] T003 [US1] Add `### 5.13 Telemetry (owner, 2026-10-03, #421)` before `## 6. Memory` in docs/specs/2026-09-24-wuwei-design.md: config keys, Signals, Aggregation, Metrics, Proposals.
- [X] T004 [US2] In the same section of docs/specs/2026-09-24-wuwei-design.md: Sharing (anonymisation rules, anonymous, attributed, off), preview and off, Interview, Project side, Residual risk.
- [X] T005 [US1] Point docs/specs/2026-09-24-wuwei-design.md to 5.13 from the hosted-service non-goal, the 3.3 workspace layout (`metrics/`), the 5.9 nudge list and the section 8 `code_host` row (`issue(repo, title, body)`).
- [X] T006 [US3] Amend .specify/memory/constitution.md Constraints: scope "No hosted service" to the plugin and name the collector; add the telemetry constraint; version 1.2.0, last amended 2026-10-03.
- [X] T007 [US1] [US2] [US3] Consistency review of docs/specs/2026-09-24-wuwei-design.md and .specify/memory/constitution.md as plan.md "Consistency review" lists. Edit only those two files, only for a real conflict, keeping the T002 phrases; when an edit adds or changes a rule, extend check_421.py first, see it fail, then edit and rerun T002 on the worktree.

- [X] T010 [US1] The issue's OpenTelemetry addition (owner, 2026-10-03) was missing from 5.13. Extend check_421.py with its phrases, see it fail (`AssertionError: a day is a trace`), then add the "OpenTelemetry export" paragraph and `[telemetry.otlp]` keys to 5.13, FR-013 and an assumption to spec.md, and the exporter to the plan's hand-off; rerun T002.

- [X] T011 [US1] Review fixes F1 to F3: extend check_421.py with the payload shape, the value patterns, the 409-as-sent rule and the collector limits, see it fail (`AssertionError: exactly these top-level keys`), then state in 5.13 the exact top-level payload keys and the added value patterns, a 409 counting as sent, and the collector's week window, per-IP limit (memory only) and daily cap with 429, plus its residual risk; rerun T002.

## Phase 4: Verify (US4)

- [X] T008 [US4] Run `git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts .github docs/site tests README.md SECURITY.md` (must be empty) and `git status --short` (only docs/specs/2026-09-24-wuwei-design.md, .specify/memory/constitution.md and specs/421-telemetry-spec/).
- [X] T009 [US4] Run `python -m pytest -q` from the repository root; everything passes, tests/test_docs.py included. Check docs/specs/2026-09-24-wuwei-design.md, .specify/memory/constitution.md and every file in specs/421-telemetry-spec/ for em-dashes, emojis and absolute local paths.
