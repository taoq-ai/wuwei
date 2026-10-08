# Tasks: The autonomy principle, the posture sweep, and the invariant table with its exhaustive test

**Input**: `spec.md`, `plan.md` in this directory. Test first: each test task runs red for
the expected reason before its implementation task. Run tests with `python -m pytest -q`
from the repository root using the interpreter the task names.

## Phase 1: User Story 1, no wall under observe and guarded except records (P1)

- [X] T001 [US1] Write the reason-corpus walk in `tests/test_invariants.py` (plan step 1 and 2: `WALL`, `CARD`, `wall()`, the sources with their function ranges, `OWNED`, `EXEMPT`, `test_reason_corpus_has_no_wall`). Run it: it fails, listing at least the `owner-only action; no setting lowers it` lines of the `pr` and `deploy` reasons, the canary line, and the four reasons of FR-004.
- [X] T002 [US1] In `tests/test_posture.py`, add `test_owner_only_line_below_strict`: `hook.posture` with stubs (`fixed`) under observe and guarded: `deploy` `'deploy generic'` and `pr` `'other'` get line `''`; `pr` `'merge policy requires an explicit PR; use wuwei merge <pr>'` keeps `posture: publish = block (owner-only action; no setting lowers it)`; `outward.check_tier` `'outward: security.canary'` and `pr` `'owner disposition markers must be posted by the owner; ask the owner to post the marker comment'` get `posture: records = block (floor; no setting lowers it)`; every decided level stays `block`; under strict every owner-only stub keeps the owner-only line except the two records-floor reasons. Update the assertions that pin the old lines: `tests/test_posture.py:232`, `:252`, `tests/test_hooks.py:1267-1320` (`test_posture_levels_at_the_hook`, `test_missing_reviewer_refusal_carries_no_posture_line`, `test_held_draft_posture_line_names_the_card`). Run: red.
- [X] T003 [US1] Add `MERGE` and `RECORDS_FLOOR` to `cli/wuwei/guards/__init__.py` and the line rule to `posture()` in `cli/wuwei/commands/hook.py` (plan "Changes"). Run T002 and the touched tests: green.
- [X] T004 [P] [US1] Pin the four reworded reasons (FR-004) in tests: `tests/test_grants.py` (no repository target), `tests/test_deploy.py` (a non-opaque could-not-inspect, for example an unresolved push destination), `tests/test_commit_push.py` (a `core.hooksPath` change and a `GIT_*` override): each reason has no `host terminal`, `ask the owner`, `only the owner` or `by hand`, and keeps its seat step. Run: red.
- [X] T005 [US1] Reword the reasons in `cli/wuwei/guards/deploy.py:369`, `cli/wuwei/grants.py:134-136`, `cli/wuwei/guards/commit_push.py:411` and `:424` (plan "Reason text"). Run T004, `tests/test_reasons.py` and T001: green. If T001 still lists a wall, apply the plan's rule (reword when a seat path exists, else an `OWNED`/`EXEMPT` row plus its design 9.2 note).

## Phase 2: User Story 2, the invariant table and the exhaustive walk (P1)

- [X] T006 [US2] Write `test_broken_rule_is_caught` in `tests/test_invariants.py` (the two mutations of spec US2 scenario 3) against a `walk()` stub that returns no failures. Run: red (no failure reported for a broken rule).
- [X] T007 [US2] Write the product walk in `tests/test_invariants.py` (plan step 3): `DIMENSIONS`, the memoised projections (`outward`, `grant`, `record`, `merge`, `marker`, `evidence`, `opaque`, `card_to_send`) on fixtures built from the existing test helpers, the invariant functions I1 to I10, `walk()`, and `test_invariants_hold` (case count >= 2000, elapsed walk < 1 s, failures reported with the full tuple). Run `test_invariants_hold` and `test_broken_rule_is_caught`: both green; a broken-rule failure names `posture=` and `mode=`.
- [X] T008 [US2] Write `test_table_matches_the_checks` in `tests/test_invariants.py` (plan step 4). Run: red (design 9.2 does not exist; the old phrase is still in the design spec and `docs/site/security.md`).
- [X] T009 [US2] Add design section `### 9.2 Safety invariants (owner, 2026-10-05, #530)` to `docs/specs/2026-09-24-wuwei-design.md` with rows I1 to I10 and their notes (owned rows by issue, exempt rows), and rewrite 9.1's principle sentence, the line under the posture table and the floors list (plan). Rewrite `docs/site/security.md:42-58` and `:73` the same way. Run T008: green.

## Phase 3: User Story 3, the principle where later items read it (P2)

- [X] T010 [P] [US3] Update the text assertions first: `tests/test_posture.py:91` (the `config check` owner-only line), `tests/test_next.py:218` if it pins the replaced sentence, and `tests/test_docs.py::test_agent_guide_ships_and_is_linked` stays as is (it compares `docs/site/agent.md` with `guide.text()`). Add one assertion to `tests/test_posture.py` that `config check` output says owner-only actions ask on a card below strict. Run: red.
- [X] T011 [US3] Change `cli/wuwei/commands/config.py:94-95`, the observe and guarded strings of `cli/wuwei/commands/next.py:14-20`, and `cli/wuwei/guide.py:85-87`; copy the new `guide.text()` between the markers of `docs/site/agent.md`. Run T010 and `tests/test_docs.py`: green.
- [X] T012 [P] [US3] Edit `docs/site/concepts.md:163`, `docs/site/daily.md:186-188` and `docs/site/reference.md:370` (plan). Run `tests/test_docs.py`: green.
- [X] T013 [US3] Amend `.specify/memory/constitution.md`: Principle VII's autonomy sentence, the Workflow bullet on invariants, version 1.5.0, Last Amended 2026-10-05 (plan). No test pins constitution prose; the design 9.2 table and T008 carry the checked rule.

## Phase 4: Polish

- [X] T014 Run the full suite (`python -m pytest -q`); everything passes. Check every file written for em-dashes, emojis and absolute local paths; remove any.

## Build notes

- T004: the non-opaque `deploy: could not inspect` case is pinned in `tests/test_grants.py`
  next to the no-target case, since both go through the deploy guard's `run` helper there.
- T001: a helper's reason is levelled under the guard checks whose body calls it (else every
  check of the module), so `agent_launch._check` reasons level as `seats`, not as the MCP gate.
  The walk also fails on an `OWNED` or `EXEMPT` row that matches no corpus reason.
- T007: one workspace serves every projection: `item_case` of `tests/test_commit_push.py`
  (fake vcs, item worktree DIV-1) plus the gate verdicts of `tests/test_pr_guards.py`, a
  registered planner and one deploy card. I9 and I10 run through the whole hook; the timed
  walk stays under one second, so the plan's fallback was not needed.
- Review 530b: a tag push with a release grant was still refused by `commit_push.push_check`
  ("leave tagging to the owner"), a wall the corpus regex missed. `push_check` now passes a
  `refs/tags/` destination below strict, since the deploy guard's release card and grants
  (once, today, always) gate it, and refuses it under strict; the git adapter's `push_context`
  measures `refs/tags/<tag>` and `HEAD:refs/tags/<tag>` instead of raising; I9 checks the tag
  push through the hook with a standing grant and with an Allow once card,
  `WALL` also matches `leave <x> to the owner`, and the walk is timed in CPU time.
