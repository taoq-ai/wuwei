# Tasks: outward send is an exact tool allowlist and the owner's own surfaces are local; tiers, drafts, learning cards, graph, who and reply go

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at 703b40de.
Part 15 (#837) is done on this branch first.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: The allowlist and the owner's surfaces (US1, US2, P1)

- [X] T001 [US1, US2] Red tests in `tests/test_outward.py`: an unlisted write refused with the
  exact line (enforce true and false); an exact listed tool passes; exact match only; an
  unknown name refused; a canary on a listed tool refused; one case per owner surface row (Slack
  DM, canvas, Notion parent page, mail to self); mixed destinations, no destination and
  `owner` unset are not local. In `tests/test_workspace.py`: `outward.allow` validation and
  `outbound.owner.pages`. In `tests/test_config_set.py`: the card command shows `--add`. Run:
  red.
- [X] T002 [US1, US2] `workspace.py` (`outward.allow`, its validation, `outbound.owner.pages`);
  `outward.py` (`DESTINATIONS` `canvas_id`, `OWNER` `docs`, `_owner_ids` with `pages`);
  `guards/outward.py` (`check_send`, `local`, `NOT_ALLOWED`, `check_lint` scope, `GUARDS`);
  `guards/__init__.py` (`FLOOR` names `outward.check_send`); `commands/config.py` (`--add` in
  the card command). Rewrite the canary floor tests onto `check_send` (`tests/test_canary.py`,
  `tests/test_stop.py`, `tests/test_profiles.py`, `tests/test_guard_mutation.py`). Run those
  files, `tests/test_outward.py`, `tests/test_hooks.py`, `tests/test_enforce.py`,
  `tests/test_workspace.py`, `tests/test_config_set.py`: green.

## Phase 2: WUWEI's duties still go out (US4, P1)

- [X] T003 [US4] Red tests: a port call sends after the lint with no draft
  (`tests/test_reference_adapters.py`, `tests/test_tracker_adapters.py`); `plan approve` and
  `plan add` create the ticket (`tests/test_plan.py`, `tests/test_intraday_intake.py`);
  `pr act --reply` posts through `obligations.reply` and a lint refusal exits 1
  (`tests/test_pr_actions.py`). Run: red.
- [X] T004 [US4] `outward.check_call` (canary and lint), `registry.outward_operation` (no
  `drafts.hold`), `plan.py`, `tracker.py`, `docs.py`, `pr_actions.py` (and the route name).
  Run the files of T003 and `tests/test_tracker.py tests/test_docs_system.py
  tests/test_pr_ownership.py tests/test_shepherd.py tests/test_headless_shepherd.py`: green.

## Phase 3: Delete tiers, drafts, learning cards, graph, who, reply, lint tone (US3, US5)

- [X] T005 [US3] Move the shared test helpers (plan.md, Files to delete). Inline the
  `commands/lint.py` measure helpers into `tests/test_tone.py` and drop its command cases.
  Delete the five test files with their modules: `drafts.py`, `commands/drafts.py`,
  `commands/outbound.py`, `graph.py`, `commands/who.py`, `commands/reply.py`,
  `commands/lint.py`, `templates/workspace/graph.json`.
- [X] T006 [US3] Delete the tier machinery in `outward.py` and `_unmatched` in
  `guards/outward.py`. Edit every caller in plan.md "Files to edit, code": `guards/answers.py`,
  `metrics.py`, `commands/why.py`, `commands/doctor.py`, `commands/event.py`, `signal.py`,
  `state.py`, `status.py`, `decision.py`, `guards/protect_state.py`, `commands/next.py`,
  `commands/shepherd.py`, `commands/docs.py`. Delete the `drafts.py` and `commands/drafts.py`
  LEFT rows in `tests/test_reasons.py`. Update the tests plan.md lists for each file. Run them:
  green.
- [X] T007 [US3] Red tests in `tests/test_config_transition.py`: `init --upgrade` removes the
  retired keys, `.wuwei/graph.json` (not a symlink) and the graph comment lines, honouring
  `--dry-run`. Then `workspace.RETIRED`, `commands/init.py` (no graph block; the explicit
  removal), `commands/config.py` (no `graph.sync`), and `templates/workspace/config.toml`. Run
  `tests/test_config_transition.py tests/test_workspace.py tests/test_config_writer.py
  tests/test_doctor.py`: green.
- [X] T008 [US3] Grep check (SC-002): `grep -rnE "drafts|classify|outbound (learn|tier|answer|explain)|graph\.|wuwei who|wuwei reply|lint tone|default_tier|outbound\.tiers|outward\.modes|outward\.classes" cli adapters charters skills templates docs/site README.md`
  finds nothing outside the kept names (the port payload's `draft` wrapper key, `metrics`
  legacy rows, telemetry vocabulary).

## Phase 4: Governance and docs

- [X] T009 Charters (`_common-authoring.md`, `_common.md`, `shepherd.md`), then
  `bin/wuwei agents build`; skills `wuwei-plan` and `wuwei-report`; the design spec (4.1, 4.3,
  4.9, 5.8, 5.11, 5.12, 9.2); the docs pages and README lines in plan.md. Run
  `tests/test_docs.py tests/test_charters.py tests/test_reasons.py tests/test_tone.py
  tests/test_skill_evals.py`: green.
- [X] T010 Run every touched test file once more, plus `tests/test_telemetry.py` (unchanged),
  and record the run in the PR body.

## Dependencies

T001 to T002 first. T003 to T004 before T006, because the port and the callers lose the draft
path first. T005 to T007 after T004. T009 last.
