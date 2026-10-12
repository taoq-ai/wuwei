# Tasks: `wuwei pr wait`

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: tests first (red)

- [X] T001 [US1] `tests/test_pr_wait.py`: two claimed PRs, a new review thread on one: exit 1 within
  one poll, one line with that item, `shepherd` and its PR.
- [X] T002 [US2] `tests/test_pr_wait.py`: a tick with two PRs in one repository costs one listing
  call; a tick inside `pr.poll_seconds` costs none.
- [X] T003 [US1] `tests/test_pr_wait.py`: nothing changes: exit 0 at the timeout, no stdout; no
  owned PR: exit 0 at once.
- [X] T004 [US2] `tests/test_pr_wait.py`: a rate-limit refusal sleeps until its reset, never less
  than `pr.poll_seconds`.
- [X] T005 [US3] `tests/test_next.py`: the PR wait row is `wuwei pr wait` in the background.
- [X] T006 Run them and see them fail.

## Phase 2: implementation (green)

- [X] T007 `pr_actions.wait` and `pending`; `commands/pr.py` `wait` subcommand.
- [X] T008 `commands/next.py`: the PR wait row and its `then`.

## Phase 3: docs

- [X] T009 Planner charter, plan skill, `docs/site/daily.md`, `docs/site/reference.md`; agents
  rebuilt.

## Phase 4: verify

- [X] T010 The batch suite (see 906 T013).
