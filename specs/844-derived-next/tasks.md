# Tasks: derived next; every ready launch, due duty or one owner decision; state.json becomes a cache

**Input**: `specs/844-derived-next/spec.md`, `plan.md`.

Rules: test first (write the test, run it, see it fail, then implement). Run only the test
files a task touches, with explicit paths: `python -m pytest -q <files>`. Run every test file
that imports a module you change. CI is the gate. Never loosen a test to pass; a test goes
only with the code it covers. Do not commit.

Precondition: batches 5 to 7 are merged into the base, or the branch is rebased onto them
(plan.md, Handoff). T000 checks it.

## Phase 0: Base

- [X] T000 Confirm the base: `guards/pr.py` gone and `gate_check` in `merge.py` (part 17);
  no `mcp`, `docs`, discovery-intake or `rank` references in `commands/next.py`,
  `dispatch.py`, `plan.py` (parts 18, 19, 21); part 20's tracker duty and record command.
  Record what is missing in this file under "Base notes" and follow plan.md's fallback for it.
- [X] T001 Run `tests/test_loop.py` and record 22 passed, 9 xfailed.

## Phase 1: The log is the truth, state.json the cache (US5, FR-001 to FR-003)

- [X] T002 [US5] Red tests in `tests/test_state.py`: a write's event carries `patch`; deleting
  `state.json` then `read_state` returns the same data; a cache whose `log_size` differs is
  not read; an old day with no patches migrates once (`state.migrated`); a malformed log row
  is DAMAGED (exit 2 through a command); `_write_state` bases its patch on the raw fold; a
  configured secret never appears in a folded value.
- [X] T003 [US5] Implement in `cli/wuwei/state.py`: `_fold`, patch on write (event before
  cache), `read_state` fold and cache, `day_started`, `_validate` without the lifecycle checks,
  `_move` without `_check_transition`, no snapshot write or refusal. Delete the
  illegal-transition and snapshot-refusal tests with the checks.
- [X] T004 Replace every `state.json` existence check listed in plan.md with
  `state.day_started`; `commands/why.py` evidence path to `events.jsonl`.
- [ ] T005 Switch the 20 fixture files listed in plan.md from writing `state.json` to
  `state._write_state` with the same data; run each.
- [X] T006 In `tests/test_loop.py`: `materialise` writes the records through the writer and no
  `state.json` (plan.md); run it; `test_deleting_state_json_between_two_calls_changes_no_answer`
  now passes: remove its xfail marker.

## Phase 2: The world corrects the log (US3, US5, FR-004, FR-006, FR-013, FR-014)

- [X] T007 [US3] Red tests in `tests/test_derive.py`: `head` for a loose ref, a packed ref, a
  detached HEAD, a missing link (None); `listing` absent and stale; `refresh` keeps the old
  file on a failed call; each overlay (merged, closed, worktree gone, verdict at an old head,
  verdict edited after receipt, PARK at head, PARK after a resume, legacy `escalated`).
- [X] T008 [US3] Implement `cli/wuwei/derive.py` `head`, `listing`, `refresh`, `overlay`;
  wire `overlay` into `read_state`. Add the `pulls` port (`registry.py`, `github.py`,
  `none.py`) with a red adapter test first in `tests/test_adapters.py`.
- [X] T009 [US3] Red tests in `tests/test_dispatch.py`: a stale receipt reads as missing and
  `receive` replaces it; after a fix round every gate re-checks (a passing gate gets the light
  re-read prompt). Implement in `dispatch.next_step` and `dispatch.receive`; update the
  delta-only expectations (stricter).
- [X] T010 [US3] Red test in `tests/test_merge.py` (or `tests/test_pr_guards.py` before part
  17): `pr raise --item` refuses when a passing gate's Head is older than HEAD. Drop the
  exemption in `_recorded_gates`.
- [X] T011 In `tests/test_loop.py`: `materialise` adds the worktree registry files and the
  `prs.json` shape (plan.md). `test_669_a_pass_at_an_old_head_is_no_pass` and
  `test_729_a_pr_merged_on_the_host_is_merged` must still fail only on the offer shape; leave
  their markers until Phase 3.

## Phase 3: next returns the set (US1, US2, US6, FR-005, FR-007, FR-008, FR-012)

- [X] T012 [US1] Red tests in `tests/test_derive.py`: one per row of the decision table,
  including CAP and plan order, the gate-waits rule, `depends_on` (#637), the cap and ESCALATE
  decision, owner_merge as a decision at once, red checks at the cap as a decision, and at
  most one decision; `offers` writes nothing and runs no subprocess.
- [X] T013 [US1] Implement `derive.offers`.
- [X] T014 [US1] Red tests in `tests/test_next.py` for the set shape (launches with prompts
  after `run`, duties, decision, rows), the empty-set day rows, and no settle loop; rewrite
  the rows tests to the set; delete the `pr-flow`, `mcp`, `docs` and `doctor` row tests and
  the settle-loop tests with their code.
- [X] T015 [US1] Implement `commands/next.py` (`step`, `resolve`, `run`, `THEN`, `LOOP`).
- [X] T016 [US2] Red test in `tests/test_pr_actions.py`: `pr act` on red checks at the cap
  parks the item with the cap reason and prints `plan resume`'s Owner step card; a refresh
  follows an act. Implement in `pr_actions.py`; refresh after `merge.execute` and
  `shepherd.raise_pr`.
- [X] T017 [US1] `dispatch.launch_set` over `derive.offers`; its tests in
  `tests/test_dispatch.py` and `tests/test_parallel_dispatch.py`.
- [X] T018 In `tests/test_loop.py`: `answer` reads the set; `covered` is membership; `gate`
  and `offer` go; `test_614` resolves the offer; `test_729_an_owner_merge_row_ends_when_the_pr_merges`
  expects `[('owner', 'item-1')]` first. Remove the xfail markers of
  `test_every_ready_launch_is_offered`, `test_nothing_ready_is_exactly_one_owner_decision`,
  `test_never_a_raise_without_a_pass_at_head`, `test_637_...`, `test_669_...`,
  `test_729_a_pr_merged_on_the_host_is_merged`. Run the file.

## Phase 4: Duties (US4, FR-009 to FR-011)

- [X] T019 [US4] Red tests: `tests/test_workspace.py` and `tests/test_config_transition.py`
  (`duties.on` schema, defaults from channels, upgrade line and `--dry-run`);
  `tests/test_derive.py` (each duty row, recorded by `duty.recorded`, `pr.review_posted`,
  `tracker.call` done); `tests/test_close_branches.py` (an open duty is a close finding);
  a `duty` command test in `tests/test_derive.py` (unknown duty or item exits 1).
- [X] T020 [US4] Implement `SCHEMA['duties']`, the template block, `init` defaults,
  `derive.duties`, `commands/duty.py` (or part 20's command), the duty records in
  `shepherd.post_review_request` and `dispatch.tracker_call`, the close finding in
  `closing.unresolved`, and the duty gate on the day rows in `next.step`.
- [X] T021 In `tests/test_loop.py`: `configure` adds `[duties] on = ["ping", "tracker"]`.
  Remove the xfail markers of `test_every_due_duty_is_offered` and
  `test_never_done_with_an_open_duty`. Run the file: 31 passed, no xfail (SC-001).

## Phase 5: Readers, texts, docs

- [X] T022 Run and fix the readers of `next` output: `tests/test_path_day.py`,
  `tests/test_e2e_day.py`, `tests/test_handback.py`, `tests/test_sessions.py`,
  `tests/test_posture.py`, `tests/test_metrics.py`, `tests/test_shell.py`,
  `tests/test_hooks.py` (SessionStart latency case).
- [X] T023 `charters/planner.md`, `charters/shepherd.md`; run `bin/wuwei agents build`;
  `skills/wuwei-plan/SKILL.md`, `skills/wuwei-report/SKILL.md`; run `tests/test_charters.py`,
  `tests/test_tone.py`, `tests/test_reasons.py`.
- [X] T024 `docs/site/configuration.md` (`[duties]`), `docs/site/reference.md` (`duty`); run
  `tests/test_docs.py`.
- [X] T025 Design spec 5.2 and 5.3 and the state passages, marked (owner, 2026-10-11, #789
  part 22).

## Phase 6: Verify

- [X] T026 Grep: no `state.json` read outside `state.read_state` (SC-002); no `escalate` or
  `done` action returned by `next`; no `rows` queue without prompts.
- [X] T027 Run every touched test file and every file that imports `state`, `derive`,
  `dispatch`, `commands.next`, `pr_actions`, `merge`, `closing`, `shepherd` (list them with
  grep; pass explicit paths).
- [ ] T028 Write the two review briefs (general; state derivation only) for the lead.

## Base notes

- Batch 7 (parts 840 to 843) is on the branch: `gate_check` is in `merge.py`; no `mcp`, `docs`,
  discovery-intake or `rank` row in `next`. Part 842 already writes `duty.due`, `duty.done` and
  `duty.skipped` from `dispatch.tracker_call`; the configured duties (ping, shepherd, tracker,
  summary) reuse those events, and `wuwei duty` records the ones the model performs.
- T001: 22 passed, 9 xfailed. After T021: every test passes, no xfail.
- Lead calls applied over the spec: gate cost per design 5.3 (only the gates that asked for the
  fix re-read; a PASS carried by a recorded fix round stands, `items.<id>.fix_heads`); open
  duties carry from the latest earlier day closed without close.
- Deviations: the world overlays live in `derive.offers` and `dispatch` (not in `read_state`);
  `_validate` keeps its lifecycle checks; the patch rides beside the event payload (`patch`
  key of the row) so payload readers are unchanged; a `state.json` without `log_size` (an old
  day, or a test fixture) is read as the day's records and the next write's patch carries it
  into the log, so T005 (moving fixtures to the writer) is not needed; the `pr-flow` row stays.
- T028 is the lead's (review briefs).
