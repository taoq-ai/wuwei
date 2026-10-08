# Implementation Plan: gradual adoption of open PRs, branches and worktrees

**Branch**: `510-adopt` | **Date**: 2026-10-08 | **Spec**: `spec.md`

## Summary

Three small changes at the shared spots. (1) `pr_actions._item` stops requiring a worktree;
only the rebase step and a fix round need one, and with none they return an `adopt` action
naming the exact command. (2) `pr claim` creates the item through the existing `plan.add`
(source `adopted`) when the PR has none, links it through the existing `record_pr`, which now
moves a `planned` item to `raised`, and adopts the PR branch's worktree when one exists.
(3) One shared anchor helper (hooks, anchor, identity), split out of
`workspace.create_worktree`, serves `worktree add`, the new `worktree add --branch` and the new
`worktree adopt`; both new paths record the item's worktree through one new state writer.
Two vcs port operations, one event kind, one phase edge, a board marker and docs.

## Technical Context

Python 3.11 stdlib only; pytest for tests. Run `python -m pytest -q` from the repository root.
State writes go through `state._write_state`; git only through `adapters/vcs/git.py`.

## Constitution Check

- Stdlib only: yes. Git stays behind the vcs adapter with fixed argument lists.
- Three-state exits: adopt and claim exit 0 done, 1 refused with the reason, 2 could not run
  (adapter failure, unreadable state).
- One behaviour, one function: hooks, anchor and identity live in one helper
  (`workspace._anchor`); item creation stays in `plan.add`; PR linking stays in
  `state.record_pr`; the item worktree record is one writer (`state.record_worktree`).
- Test first: every behaviour has a test task before its implementation task.
- Ponytail: no new module, no new config key; two port operations because no existing one
  lists worktrees or checks out an existing branch.
- Autonomy (#530): no refusal is added to any guard. `pr act` returns an action where it used
  to error. Adopt's refusals are preconditions of the item's record the issue asks for.
- #551: the next step is returned as an exact command (`command`, `why`, `then`), never prose
  in a skill or charter. No skill or charter text changes.
- Design spec: amended only by its owner; this plan changes no design text.
  `tests/test_invariants.py` does not exist on this base, so no invariant row is added.

## Design

### 1. pr act without a checkout (`cli/wuwei/pr_actions.py`)

- `_item(root, ref)` (`:253-264`): keep the "exactly one linked item" check; return
  `(name, None)` when `worktree` is absent or empty instead of raising. A recorded but missing
  directory still raises (unchanged).
- New `_adopt(root, ref, item, pr)`: reads the configured repository for the ref
  (`shepherd._settings(config, ref)`), looks up a worktree on `pr['branch']` with
  `workspace.branch_worktree` (section 4), prints one JSON line and returns 1:
  `{"action": "adopt", "pr": ref, "item": item, "command": <cmd>, "why": "a <state> fix needs a
  checkout of <branch>; the item has no worktree", "then": "bin/wuwei pr act <ref>"}` where
  `<cmd>` is `bin/wuwei worktree adopt <path> --item <item>` when a worktree is found, else
  `bin/wuwei worktree add <item> --branch <branch> --repo <repo name>`. Quote with
  `shlex.join`.
- `act` (`:463-512`): after `_item`, read `measured = watch.evidence(...)` as today for the
  non-conflicted states; for `conflicted` with `tree is None`, read the evidence and return
  `_adopt(...)`. Pass `tree` into `_thread` and `_fix`.
- `_fix(root, ref, item, tree, measured, feedback=None)` (`:338-354`): keep the `delta` gate
  and the feedback derivation; then if `tree is None` return `_adopt(root, ref, item,
  measured['pr'])`. If the item has no build record
  (`state.read_state(root).get('builds', {}).get(item) is None`), write a builder brief with
  the existing `brief.write('builder', item, f'{item}-adopted-fix', body, worktree=str(tree),
  pr=ref, root=root)`, body `Fix round on <ref>, an adopted PR.\n\nFix feedback:\n<feedback>`,
  then print `build.next_action(item, root=root)` as JSON and return 1. A `brief.Refused`
  prints its reason and returns 1; a `build.PortExit` (not a ValueError, so `act`'s handler
  would miss it) prints its reason and returns its code. Otherwise call `build.open_fix` as
  today. (`next_action` moves only `planned` items, so a `raised` item stays
  `raised`.)
- `_thread(root, ref, item, tree, measured, reply=None)`: only passes `tree` through to `_fix`.

### 2. Headless shepherd (`cli/wuwei/shepherd.py:441-447`)

`runtime.dispatch('shepherd', ..., str(tree or root), True, root=root)`: the seat runs in the
workspace when the item has no worktree. Nothing else changes in `headless`.

### 3. Claim creates the item (`cli/wuwei/shepherd.py:373-389`, `cli/wuwei/commands/pr.py`)

- `commands/pr.py`: `claim` takes `ref`, optional `--item`, new optional `--goal`; `run_claim`
  passes both.
- `claim_pr(root, ref, item=None, goal=None)`:
  1. `config`; `ref = merge.reference(ref, root, config, repo=<the only repo name when
     len(config['repos']) == 1, else None>)` (reuse; a bare number resolves).
  2. `_settings`, `merge.checked_pr`, require open (unchanged).
  3. `data = state.read_state(root)`; `linked` = the item already linking `ref`, if any;
     `item = item or linked or f'PR-{pr["number"]}'`.
  4. If `item not in data['items']`: goal is `goal`, else the only entry of `data['goals']`,
     else refuse (exit 1) `bin/wuwei pr claim <ref> --goal <one of G-1, G-2>`; then
     `plan.add(item, root, goal=goal, title=pr['title'], source='adopted')`.
  5. `state.record_pr(root, item, ref, raised=False, head=pr['head'])` (unchanged call).
  6. If the item records no worktree: `path = workspace.branch_worktree(vcs, repo path,
     pr['branch'], root)`; when found call `workspace.adopt_worktree(root, item, path, vcs,
     config)`; a `state.StateError` from adopt is printed to stderr as
     `worktree not adopted: <reason>` and the claim still exits 0. A failed worktree listing
     or adapter read here exits 2 with the reason; the link from step 5 stays recorded.
  7. Print `ref` (unchanged), then the adopt result JSON when a worktree was adopted.
  `plan.add` raising `state.StateError` maps to exit 1 like `record_pr` today.

### 4. Shared worktree helpers (`cli/wuwei/workspace.py:769-789`)

- `_require_gate(root)`: the two checks now inline in `create_worktree` (workspace exists,
  gate approved), moved unchanged.
- `_anchor(path, root, vcs, identity)`: the `install(...)` call and the identity write now
  inline in `create_worktree`, moved unchanged (the shared helper).
- `create_worktree(repo, branch, path, root, vcs, identity=None, existing=False)`: same order
  (gate, claim, add, anchor); when `existing`, call `vcs.worktree_checkout` instead of
  `vcs.worktree_add`, then record the item worktree with
  `state.record_worktree(root, Path(path).name, path, head)` (head from `vcs.head`).
- `adopt_worktree(root, item, path, vcs, config)`:
  1. `_require_gate(root)`; `path = Path(path).resolve()`; not a directory: StateError.
  2. `repo, actual, _ = commit_push.context(path, {}, {}, root, identity=False)`; a ValueError
     becomes `state.StateError(f'{path} is not a worktree of a configured repository: {exc}')`.
  3. `actual['path'] == actual['common_dir']` (main checkout): StateError naming
     `bin/wuwei worktree add <item> --branch <branch>`.
  4. `rows = data(vcs.status(str(path)))`; any row: StateError
     `worktree has unrecorded changes: <paths>; commit them, or run git -C <path> stash push
     --include-untracked, then rerun bin/wuwei worktree adopt <path> --item <item>`.
  5. Records precondition read before side effects: item in `approved_items`, and no
     different worktree recorded (StateError otherwise).
  6. `sessions.claim_item(root, item)`; `_anchor(path, root, vcs, repo['identity'])`;
     `head = data(vcs.head(str(path)))['sha']`; `state.record_worktree(root, item, path, head)`.
  7. Return `{'item': item, 'path': str(path), 'head': head}`.
- `branch_worktree(vcs, repo_path, branch, root)`: `data(vcs.worktrees(str(repo_path)))`,
  return the `path` whose `branch` equals `branch`, else None.

### 5. State (`cli/wuwei/state.py`)

- `PHASES['planned']` gains `'raised'`.
- `record_pr` (`:405-434`): for a claim (`raised=False`), `if phase == 'planned': _move(data,
  item, 'raised')`, in the same write.
- New `record_worktree(root, item, path, head)` next to `record_pr`: one write that requires
  `item` in `items` and `approved_items`, refuses a different recorded worktree (resolved
  paths compared), sets `items[item]['worktree'] = str(path)`, kind `worktree.adopted`,
  payload `{item, worktree, head}`.
- `_producer_error`: `worktree` names `wuwei brief, wuwei worktree adopt or wuwei worktree add
  --branch`; add `source` and `title`: `wuwei plan add or wuwei pr claim`.

### 6. plan.add source (`cli/wuwei/plan.py:341-422`)

`add(..., source=None)`: the owner candidate's `source` is `source or 'owner'`; `admit` stores
`source` and `title` on the item only when `source` is given. The `plan.added` payload already
carries the candidate's source.

### 7. vcs port (`adapters/vcs/git.py`, `cli/wuwei/registry.py:43-60`)

- `worktrees(repo)`: `git worktree list --porcelain -z`; parse records into
  `[{'path', 'head', 'branch'}]` (`branch` short name, None when detached); a malformed record
  raises ValueError (exit 2).
- `worktree_checkout(repo, branch, path)`: `_run(repo, 'worktree', 'add', '--', path,
  _revision(branch))`; returns `{'branch', 'path'}`. Git's own remote-tracking guess applies
  when the branch exists only on one remote.
- Register both in `PARAMETERS['vcs']` and the fake (`tests/fakes/vcs.py`).

### 8. Commands (`cli/wuwei/commands/worktree.py`)

- `add` gains `--branch NAME`: passes `branch=NAME, existing=True` to `create_worktree`
  (default unchanged: `item.lower()`, new branch).
- New `adopt PATH --item ID [--repo]`: `workspace.adopt_worktree`; prints the JSON result;
  `state.StateError` exits 1 with `wuwei worktree: <reason>`, other errors exit 2 as today.
  `--repo` is not needed: the path selects the repository.

### 9. Event kind (`cli/wuwei/commands/event.py`)

`EVENT_PRODUCERS['worktree.adopted'] = 'wuwei worktree adopt, wuwei worktree add --branch or
wuwei pr claim'`; `item.claimed` and `worktree.hooks_skipped` add `wuwei worktree adopt`.

### 10. Board (`cli/wuwei/commands/board.py:140-147`)

The Work row's item cell is `name + ' (adopted)'` when `item.get('source') == 'adopted'`.

### 11. Docs

- `docs/site/daily.md`: new section "Starting with work in progress" after "3. Plan and the
  morning gate": claim each open PR (`bin/wuwei pr claim owner/repo#n --goal G-1`), what the
  shepherd does with no checkout, the `adopt` action on a fix round, `worktree adopt` and
  `worktree add --branch`; nothing is recreated.
- `docs/site/concepts.md`: glossary `### Adopted`; the PR ownership paragraph names claim
  without `--item`.
- `docs/site/reference.md`: "Item worktrees" documents `--branch` and `worktree adopt` (exits,
  refusals, what is recorded); the phase table row `planned` adds `raised`
  (`tests/test_docs.py:462` compares it with `state.PHASES`); "Seat briefs and the build loop"
  automatic phases add "`pr claim` moves `planned` to `raised`".

## What must not change

- Plain `worktree add <item>`: new branch `item.lower()`, no item record, same output.
- `install` in `commands/git_hook.py`, `hooks_path` and the chain scripts (#472).
- `pr act` outputs for items with a worktree (rebase step, fix round, replies, merge).
- `pr raise`, the push guard, the merge policy and every guard's posture handling.
- `record_pr`'s refusals and `pr claim --item` on an item already in the plan (apart from the
  `planned` to `raised` move).
- `plan add` without `source`: no new keys on the item.

## Test fallout to expect

`tests/test_state.py::test_all_transition_edges` (planned edges), the reference phase table
test in `tests/test_docs.py`, `tests/test_adapters.py` (port list), `tests/test_vcs.py`
(argument table), and any test that claims a `planned` item and then expects `planned`.

## Project Structure

No new files outside `specs/510-adopt/`. Tests go in existing files:
`tests/test_pr_actions.py`, `tests/test_shepherd.py`, `tests/test_worktree_command.py`,
`tests/test_state.py`, `tests/test_vcs.py`, `tests/test_adapters.py`,
`tests/test_docs.py`, `tests/test_intraday_intake.py` (plan add) and `tests/test_board_mcp.py` (board).
