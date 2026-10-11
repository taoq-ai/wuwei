# Tasks: posture becomes one boolean, guards.enforce; the traces recorder never refuses

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at 703b40de.
This part is built first on `b5-guards`; part 16 follows.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: The switch and the hook (US1, P1)

- [X] T001 [US1] Create `tests/test_enforce.py`:
  - default config has `guards.enforce is True`;
  - a hook table: one refusal from each guard module (stub checks named as the real ones) with
    enforce true (blocks, no `posture:` line) and false (off the floor: one
    `guard.would_refuse` without `area`, `level`, `posture`, exit 0; on the floor: blocks);
  - an unreadable config blocks;
  - move the hook-chain cases and `fixed` from `tests/test_posture.py` (plan.md, Files to
    delete) and point `tests/test_invariants.py` at `test_enforce.fixed`.
  Run: red.
- [X] T002 [US1] `workspace.py`: schema `guards.enforce`, `security.required` only; delete
  `POSTURES`, `AREAS`, `AREA_LEVELS`, `FLOORS`, `posture`, `posture_source`, the
  `shadow_since` and floor validation; add the five keys to `RETIRED`.
  `guards/__init__.py`: `FLOOR` and `floor()` replace `AREAS`, `OWNER_ONLY`, `level()`.
  `commands/hook.py`: `posture()` becomes `enforce()` (plan.md, The hook). Delete
  `tests/test_posture.py`. Run `tests/test_enforce.py tests/test_hooks.py
  tests/test_invariants.py tests/test_parser_warns.py tests/test_answers.py`, after converting
  their posture writers (plan.md, tests): green.

## Phase 2: The table rows keep blocking (US4, P1)

- [X] T003 [US4] Red tests with the default config: a WUWEI seat type with no brief line is
  refused (`tests/test_agent_launch.py`); a brief mismatch is refused; an untyped launch
  registers adhoc and is never refused; a bare `gh pr create` for a recorded item is refused
  (`tests/test_pr_guards.py`); `pr raise --item` gate miss refuses, and with enforce = false
  logs and raises (`tests/test_shepherd.py`). Run: red.
- [X] T004 [US4] `guards/agent_launch.py` `_unbriefed`, `_adhoc`; `guards/pr.py:249`;
  `shepherd.py:309`. Run the three files: green.

## Phase 3: The traces recorder never refuses (US3, P1)

- [X] T005 [US3] `tests/test_traces.py`: the slow, unreadable-material and failed-record cases
  exit 0 with the event and the stderr reason, in both settings. Run: red for the cases that
  refused under strict.
- [X] T006 [US3] `guards/traces.py`: delete `_strict`; `return 0, ''`. Run
  `tests/test_traces.py tests/test_traces_seats_only.py`: green.

## Phase 4: init --upgrade maps observe (US2, P1)

- [X] T007 [US2] Red tests in `tests/test_workspace.py` and `tests/test_config_transition.py`:
  observe, shadow, guarded, strict, enforce-mode, areas and shadow keys; `--dry-run`; an
  explicit `guards.enforce` kept; `init --shadow` writes enforce = false; `--posture` is
  unknown. Run: red.
- [X] T008 [US2] `commands/init.py`: `_enforce` replaces `_retired_mode`; `--posture` goes;
  `--shadow` rewrites `enforce = true`; the `--upgrade` refusal names `guards.enforce`.
  `templates/workspace/config.toml` per plan.md. Run the two files and `tests/test_doctor.py`:
  green.

## Phase 5: Every other reader takes the default branch (US1, US5)

- [X] T009 [US1, US5] Update each remaining reader in the plan.md table: `mcp.py`,
  `guards/commit_push.py`, `commands/git_hook.py`, `guards/protect_state.py`,
  `guards/outward.py`, `guards/lifecycle.py`, `commands/next.py`, `commands/config.py`,
  `commands/doctor.py`, `commands/status.py`, `commands/seat.py`, `commands/why.py`,
  `commands/event.py`, `commands/outbound.py`, `outward.py`, `drafts.py`, `tracker.py`,
  `plan.py`, `sessions.py`, `scanner.py`, `brief.py`, `specmode.py`, `signal.py`,
  `telemetry.py`, `shell.py`. Update their tests first (red where behaviour changes: config
  check line, doctor `guards` row, status `enforce`, orientation sentences, MCP enforce off
  note, scratch refusal), then the code. Delete the strict-only cases with their branches.
  Delete the three `tracker.py` LEFT rows in `tests/test_reasons.py`. Run every test file named
  in plan.md "Files to edit, tests": green.
- [X] T010 Grep check (SC-001): `grep -rnE "posture\(|POSTURES|AREA_LEVELS|FLOORS|security\.areas|\['security'\]\['posture'\]|guards\.AREAS|shadow_days|shadow_since|\['mode'\] == 'shadow'" cli` returns only the `init.py` migration and the telemetry vocabulary.

## Phase 6: Governance and docs

- [X] T011 Constitution VII amendment and version 2.2.0 (plan.md); design spec sections 4.1,
  4.3, 4.5, 5.9, 5.10, 5.11, 5.13, 7, 9.1, 9.2; `docs/site/configuration.md` and the `init`
  row of `docs/site/reference.md`. Run `tests/test_docs.py tests/test_reasons.py
  tests/test_tone.py tests/test_charters.py`: green.
- [X] T012 Run every touched test file once more; record the run in the PR body.

## Dependencies

T001 to T002 first (the schema and hook every other task uses). T003 to T008 in any order after
T002. T009 after T002. T011 last.
