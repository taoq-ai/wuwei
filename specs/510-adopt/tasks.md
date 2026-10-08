# Tasks: gradual adoption of open PRs, branches and worktrees

Test first: each test task is written, run and seen to fail for the expected reason before its
implementation task. Fixtures are neutral (repository `acme/widget`, PRs `acme/widget#7` and
`#8`, items `A`, `PR-8`, goals `G-1`, `G-2`, branch `feature-x`, paths under `tmp_path`). Run
`python -m pytest -q` from the repository root.

## Phase 1: vcs port (FR-009)

- [X] T001 Test in `tests/test_vcs.py`: on a real temporary repository with one linked
  worktree on `feature-x` and one detached, `worktrees(repo)` returns the main checkout, the
  `feature-x` worktree (`branch == 'feature-x'`, `head` its SHA) and the detached one
  (`branch` None); `worktree_checkout(repo, 'feature-x', path)` on an existing branch creates
  the worktree on it without a new branch; `worktree_checkout` with branch `--force` returns
  exit 2 (argument table at `:132`).
- [X] T002 Test in `tests/test_adapters.py`: the port table lists `('vcs', 'worktrees',
  ('repo',), True)` and `('vcs', 'worktree_checkout', ('repo', 'branch', 'path'), False)`.
- [X] T003 Implement `worktrees` and `worktree_checkout` in `adapters/vcs/git.py`, register them
  in `cli/wuwei/registry.py` `PARAMETERS['vcs']`, add both to `tests/fakes/vcs.py`.

## Phase 2: state (FR-005, FR-010)

- [X] T004 Test in `tests/test_state.py`: `test_all_transition_edges` expects `planned` to
  allow `raised`; a new test: `record_worktree` sets `items.A.worktree`, writes
  `worktree.adopted` with item, worktree and head, is idempotent for the same path, refuses
  (StateError) a different path and an item outside `approved_items`.
- [X] T005 Test in `tests/test_state.py`: `pr claim REF --item A` on a `planned` approved
  item moves it to `raised` in the same write as the link (one `pr.claimed` event, no
  `state.transition`).
- [X] T006 Implement in `cli/wuwei/state.py`: `PHASES['planned']` adds `raised`; `record_pr`
  moves a `planned` item to `raised` for a claim; `record_worktree`; `_producer_error` entries
  for `worktree`, `source`, `title`.
- [X] T007 Test in `tests/test_worktree_command.py`: `main(['event', 'worktree.adopted', '{}'])`
  exits 1 and stderr names `wuwei worktree adopt`.
- [X] T007a Implement the `EVENT_PRODUCERS` entries in `cli/wuwei/commands/event.py`.

## Phase 3: shared worktree helpers and the worktree command (FR-007, FR-008)

- [X] T008 Test in `tests/test_worktree_command.py` (`hooked_workspace` fixture): an existing
  linked worktree made with plain git, the repository's `core.hooksPath` set to a husky-style
  relative directory `.husky/_` holding a marker `pre-commit` that is committed (so the
  worktree's checkout has it), item `A` approved;
  `main(['worktree', 'adopt', <path>, '--item', 'A'])` exits 0; a commit in it records
  `git-hook pre-commit` and the marker; the worktree's git directory holds `wuwei-workspace`
  naming the workspace; `items.A.worktree` is the resolved path; the last event is
  `worktree.adopted` with the worktree HEAD; the worktree's `user.email` is the configured
  identity.
- [X] T009 Test in `tests/test_worktree_command.py`: adopt on that worktree with one modified
  and one untracked file exits 1, stderr names both files and `stash push --include-untracked`,
  and state, events and the worktree's hook config are unchanged.
- [X] T010 Test in `tests/test_worktree_command.py`: adopt exits 1 with no state change for a
  plain directory, for a worktree of a repository not in config, and for the configured main
  checkout (message names `worktree add A --branch`); adopt before gate approval exits 1;
  adopt of a second path onto an item that records another worktree exits 1.
- [X] T011 Test in `tests/test_worktree_command.py`: with branch `feature-x` existing,
  `main(['worktree', 'add', 'A', '--branch', 'feature-x'])` exits 0, `worktrees/A` is on
  `feature-x`, no branch `a` exists, the hooks run on commit, and `items.A.worktree` is
  recorded; plain `worktree add B` still creates branch `b` and records nothing on `B`
  (unchanged behaviour).
- [X] T012 Implement in `cli/wuwei/workspace.py`: `_require_gate`, `_anchor` (moved out of
  `create_worktree` unchanged), `create_worktree(..., existing=False)`, `adopt_worktree`,
  `branch_worktree`; in `cli/wuwei/commands/worktree.py`: `add --branch`, `adopt PATH --item`.

## Phase 4: plan add source (FR-004)

- [X] T013 Test in `tests/test_intraday_intake.py`: `plan.add('PR-8', goal='G-1',
  title='Fix login', source='adopted')` admits the item with `source` `adopted` and the title,
  and the `plan.added` payload has `source: adopted`; `plan.add` without `source` adds no
  `source` or `title` key (unchanged).
- [X] T014 Implement `source` in `cli/wuwei/plan.py` `add`.

## Phase 5: pr claim creates and adopts (FR-004, FR-006)

- [X] T015 Test in `tests/test_shepherd.py` (issue Acceptance 1, part 1): open PR
  `acme/widget#8`, goals `['G-1']` in the day, no item; `main(['pr', 'claim',
  'acme/widget#8', '--goal', 'G-1'])` exits 0; item `PR-8` is approved, `source` `adopted`,
  phase `raised`, `pr` linked, PR in `claimed_prs`; `main(['pr', 'claim', '8'])` on a fresh
  day with one configured repository and one goal claims the same ref; with goals
  `['G-1', 'G-2']` and no `--goal` it exits 1 naming `--goal` and writes nothing; a second
  claim of the same ref is idempotent (no second item).
- [X] T016 Test in `tests/test_shepherd.py`: with the vcs fake's `worktrees` returning a clean
  worktree on the PR branch, the claim adopts it (`items.PR-8.worktree` set) and prints its
  path; with that worktree dirty (`status` rows), the claim exits 0, stderr has
  `worktree not adopted:` and the item has no worktree; `worktrees` exit 2 makes the claim
  exit 2 after the link (reason printed).
- [X] T017 Implement in `cli/wuwei/shepherd.py` `claim_pr(root, ref, item=None, goal=None)` and
  `cli/wuwei/commands/pr.py` (`--item` optional, `--goal`).

## Phase 6: pr act without a checkout (FR-001, FR-002, FR-003)

- [X] T018 Test in `tests/test_pr_actions.py` (issue Acceptance 1, part 2): an item linked to
  the owned PR with no `worktree` key; a `threads_unanswered` question: `pr act REF` exits 1
  with the `reply` action and `pr act REF --reply "..."` drafts it; `review_stale`: `pr act`
  calls the review request path (no worktree error); `pr state REF` rows carry the state.
- [X] T019 Test in `tests/test_pr_actions.py` (issue Acceptance 2, part 1): same item, PR
  `ci_red`: `pr act` exits 1 with `action` `adopt`, `command`
  `bin/wuwei worktree add A --branch <the fake PR's branch> --repo acme/widget` (vcs fake
  `worktrees` returns none on that branch) and `then` `bin/wuwei pr act acme/widget#7`; with `worktrees` returning
  one on the PR branch, `command` is `bin/wuwei worktree adopt <path> --item A`; `conflicted`
  with no worktree returns the same action; a review fix request with no worktree too.
- [X] T020 Test in `tests/test_pr_actions.py` (issue Acceptance 2, part 2): item in `raised`
  with a recorded worktree and no build record, the repository configured with
  `fast_checks` (`build.next_action` needs them), PR `ci_red`: `pr act` exits 1, a builder brief
  `A-adopted-fix` is logged with the worktree and the failed check names in its body, the
  printed action is `launch` with `worktree` the recorded path, and the item stays `raised`;
  with no `fast_checks` configured, `pr act` exits 2 naming them (no traceback); a tracker in
  force with no ticket exits 1 with the ticket command (the `PortExit` path).
- [X] T021 Test in `tests/test_listen.py` (its headless seat fixture): `headless` for a linked item with no worktree
  dispatches the runtime with the workspace root as the directory.
- [X] T022 Implement in `cli/wuwei/pr_actions.py` (`_item`, `_adopt`, `act`, `_fix`, `_thread`)
  and `cli/wuwei/shepherd.py` (`headless` directory).
- [X] T023 End-to-end check in `tests/test_worktree_command.py` (issue Acceptance 2 and 3
  together, real git, fake code host): claim with no worktree, `pr act` on `ci_red` prints the
  adopt command, run it, `pr act` again prints `launch` on the adopted path, and a commit there
  runs the chained pre-commit.

## Phase 7: board and docs (FR-011, FR-012)

- [X] T024 Test in `tests/test_board_mcp.py`: an item with `source` `adopted` renders as
  `PR-8 (adopted)` in the Work table.
- [X] T025 Implement in `cli/wuwei/commands/board.py`.
- [X] T026 Test in `tests/test_docs.py`: `daily.md` has `## Starting with work in progress`
  naming `pr claim`, `worktree adopt` and `worktree add <item> --branch`; `concepts.md` has
  `### Adopted`; `reference.md` names `worktree adopt` and `--branch`; the phase table test
  (`:462`) passes with `planned` listing `raised`.
- [X] T027 Write the docs in `docs/site/daily.md`, `docs/site/concepts.md`,
  `docs/site/reference.md`.

## Phase 8: full suite

- [X] T028 Run `python -m pytest -q`; fix fallout named in plan.md; check every written file for
  em-dashes, emojis and absolute local paths.

## Phase 9: review findings

- [X] T029 Test in `tests/test_plan.py`, `tests/test_code_host.py`, `tests/test_adapters.py`:
  `plan propose` lists the owner's open PRs (`open_prs`), the gate card and record name them and
  `plan approve` claims each one (F1). Implement in `adapters/code_host/*.py`,
  `cli/wuwei/registry.py`, `cli/wuwei/plan.py`; rewrite the `daily.md` section.
- [X] T030 Test in `tests/test_workspace.py`, `tests/test_docs.py`, `tests/test_listen.py`:
  `shepherd.autostart` defaults to true (F2). Implement in `cli/wuwei/workspace.py`, the
  workspace template and the docs.
- [X] T031 Test in `tests/test_worktree_command.py`: adopt refuses a subdirectory of a
  worktree and a path another item records (F3, F4). Implement in `cli/wuwei/workspace.py`
  (`adopt_worktree`) and `cli/wuwei/state.py` (`record_worktree`).
