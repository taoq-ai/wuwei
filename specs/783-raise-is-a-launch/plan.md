# Implementation Plan: the raise action is a ready-to-run shepherd launch that opens the PR with wuwei pr raise --item

**Branch**: `783-raise-is-a-launch` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

The shepherd brief command and launch that `wuwei next` already builds (`next._shepherd`)
move into one helper, `dispatch.raise_action`. `dispatch.next_step` returns it at both raise
points, so `dispatch next`, `dispatch next --all`, `build next` (#666) and `wuwei next` all
answer with the same gate-shaped action: the brief command first, then the launch. The
brief body and the shepherd charter name `bin/wuwei pr raise ... --item <item>`. The PR
guard's `create_check` adds one block: for a recorded item that links no PR, `gh pr create`
warns naming `pr raise` below strict and is refused under strict.

## Technical Context

Python 3.11+, stdlib only; pytest for tests. Tests are in-process: the `root` fixture,
`built`, `record`, `cli` and `build_next` helpers in `tests/test_dispatch.py`; the `case` and
`item` fixtures in `tests/test_pr_guards.py` (fake VCS, no network, no `gh`).

## Constitution Check

- I (stdlib): unchanged.
- II (exits, fail closed): `dispatch next` and `build next` keep their exit codes for raise
  (0). The guard's new branch returns 0 with a warning or 1 under strict. Its errors fall
  into the existing `except` and `create_check` wrapper (exit 2 with the reason).
- III (one behaviour, one function): the raise action lives in `dispatch.raise_action` only.
  `next._shepherd` renders it and builds nothing of its own.
- IV (test first): every behaviour has its test task before its implementation task.
- V (ponytail): no new config key, no new event kind, no new port call. The guard reuses
  `_recorded` (#534) and `workspace.posture`. The helper is lifted from `next.py`, not
  rewritten.
- VII (security, posture): below strict no new wall (design invariant I1); under strict the
  refusal stays (design 9.1). The guard acts only inside a workspace, because `check` only
  reaches `action` for a directory with a workspace context.
- Design spec: 4.1 hook table row and the 5.3 build-loop paragraph gain #783 (FR-009). No
  9.2 invariant row: the change adds no new rule a policy trusts.

## Design

### 1. `cli/wuwei/dispatch.py`: `SHEPHERD_BODY` and `raise_action` (new, next to `GATE_BODY`)

```python
SHEPHERD_BODY = ('Raise the PR for {item} and own it until merged. Open it with bin/wuwei pr raise '
                 '<owner/repo> --base <branch> --title <title> --body-file <file> --item {item}. It '
                 'links the PR to {item} and requests the ranked reviewers.')


def raise_action(root, data, item, notes):
    """#783: raise in the gate shape (#551): the shepherd's brief command, then its launch."""
    name = f'shepherd-{item}'
    path = workspace.day_dir(root) / 'briefs' / f'{name}.md'
    worktree = data['items'][item].get('worktree') or str(root)
    action = {'action': 'raise', 'notes': notes, 'seats': []}
    if not path.is_file():
        body = '\n'.join([SHEPHERD_BODY.format(item=item), *(f'Review note: {note}' for note in notes)])
        action['commands'] = [f'wuwei brief shepherd {item} {name} --worktree {shlex.quote(worktree)} '
                              '--body ' + shlex.quote(body)]
    elif name not in data['seats']:
        action['seats'] = [brief.seat_action('shepherd', path, worktree, root)]
    else:
        action['reason'] = (f'{name} is {data["seats"][name].get("status")} and the PR is not raised; '
                            f'bin/wuwei why {item} shows it')
    return action
```

The body, the brief name, the worktree fallback and the `Review note:` lines are exactly
what `next._shepherd` (`next.py:401` to `417`) does today; only the first sentence grows.
`shlex`, `brief`, `workspace` are already imported in `dispatch.py`.

### 2. `cli/wuwei/dispatch.py`, `next_step`

- Line 379: `return {'action': 'raise', 'notes': []}` becomes
  `return raise_action(root, data, item, [])`.
- Line 397: `return {'action': 'raise', 'notes': notes}` becomes
  `return raise_action(root, data, item, notes)`.

`data` is the state `next_step` read at its start; the seats it reads do not change inside
`next_step`. Nothing else in `next_step` changes.

### 3. `cli/wuwei/commands/next.py`, `_shepherd` (lines 401 to 417)

Render the shared action; delete `SHEPHERD_BODY` (line 84) from `next.py`:

```python
def _shepherd(root, item, notes, why):
    """The shepherd raises the PR: dispatch's brief command, its launch, or a card when it
    stopped without one (#783: one raise action for dispatch, build and next)."""
    from wuwei import dispatch
    action = dispatch.raise_action(root, state.read_state(root), item, notes)
    if action.get('commands'):
        return _row('raise', f'{why} Every gate passed; brief the shepherd to raise the PR.',
                    action['commands'][0], item=item)
    if action['seats']:
        return {'state': 'raise', 'item': item, **action['seats'][0],
                'why': f'{why} Launch the shepherd to raise the PR.', 'then': THEN['agent']}
    return _row('raise', f'shepherd-{item} stopped without raising the PR.', f'wuwei why {item}',
                'card', THEN['owner'], item=item)
```

It calls the helper again rather than reading the action `resolve` received. The cost is
one state read, and `tests/test_next.py` fakes `next_step` with a bare
`{'action': 'raise', 'notes': [...]}`, so `test_verdict_rows_return_the_gate_action` and
`test_shepherd_launch_then_card` keep exercising the real helper unchanged.

### 4. `cli/wuwei/guards/pr.py`, `create_check`

Add `import sys` at the top. After the `if operands or values(found, '--web', '-w')` check
and before the reviewer check (so under strict the reason names `pr raise`, which also
requests reviewers):

```python
    from wuwei import state
    linked = (item, cwd) if item else _recorded(root, config, path=cwd)
    if linked and not state.read_state(root)['items'][linked[0]].get('pr'):
        # #783: pr raise links the PR to its item; a PR from gh pr create stays unlinked.
        hint = (f'{linked[0]} is a WUWEI item: raise its PR with bin/wuwei pr raise '
                f'{repo or "<owner/repo>"} --base <branch> --title <title> --body-file <file> '
                f'--item {linked[0]}. It links the PR to {linked[0]}; gh pr create does not')
        if workspace.posture(config)[0] == 'strict':
            return 1, hint
        print(f'warning: {hint}', file=sys.stderr)
```

- `item` is set only by the `--repo`/`--head` branch (#534), where `cwd` is already the
  item's tree. Otherwise `_recorded(path=cwd)` finds the item whose recorded worktree is
  the directory; `cwd` is already resolved (`protect_state._cwd`, or the resolved `cd`
  target).
- `gate_check(root, cwd, config, item=item)` keeps the original `item` (FR-008): the
  resolved `linked` item is used for the warning only.
- `action()` prefixes a non-zero `create_check` reason with `RAISE` (`pr raise: `), and
  `hook.posture` levels such a reason as `publish` (block under strict). No hook change.
- The warning line follows `protect_state.check_scratch` (#647). No event is recorded.

### 5. `charters/shepherd.md` and `agents/shepherd.md`

Bump `version: 1.0.1` to `1.1.0`. In "PR raise" step 2, replace
"Raise the PR through the configured adapter." with:

> Raise the PR with `bin/wuwei pr raise <owner/repo> --base <branch> --title <title>
> --body-file <file> --item <item>`. It links the PR to its item and requests the ranked
> reviewers. Never open it with `gh pr create`: that PR is not linked. Link a PR that
> already exists with `bin/wuwei pr claim <ref> --item <item>`.

Keep the rest of step 2 (the anchor "rank authors over the past 90 days" stays exactly once,
`tests/test_charters.py` RULES). Then run `bin/wuwei agents build` and check that only
`agents/shepherd.md` changed.

### 6. Docs

- `docs/specs/2026-09-24-wuwei-design.md`:
  - 4.1 hook table, `gh pr create` row (line 174): append "; under strict, a recorded item
    that links no PR (#783: below strict a warning naming `bin/wuwei pr raise ... --item`)".
  - 5.3, after "answers what `dispatch next` decides (#666)." (line 624): add "At raise both
    return the shepherd's brief command, then its launch, in the gate shape (#783)."
- `docs/site/daily.md` step 5 (line 326) and step 6 (line 329): `raise` carries the
  shepherd's brief command in `commands` (the body carries the review notes), then the
  shepherd launch in `seats`, and `build next` returns the same. The shepherd opens the PR
  with `wuwei pr raise ... --item <item>`. A `gh pr create` for a recorded item warns below
  strict and is refused under strict.
- `docs/site/reference.md` posture paragraph (line 397): after "runs from any directory.",
  add one sentence: for a recorded item that links no PR, `gh pr create` prints
  `warning: <item> is a WUWEI item: raise its PR with bin/wuwei pr raise ... --item <item>`
  below `strict` and is refused under `strict` (#783).

### What must not change

- The gate, fix, delta and escalate actions of `next_step`, and their equality tests.
- `build.run` (`commands/build.py:48` to `55`): no change; it agrees through #666.
- `launch_set`: no change; it already counts `len(seats)` for an action with `seats`.
- `create_check`: the env-override, opaque, reviewer and gate results for every input that
  is not a recorded item with no PR. The `gate_check` argument `item` stays as today.
- `shepherd.raise_pr`, `shepherd.claim_pr`, `commands/pr.py`: no change.
- `test_verdict_rows_return_the_gate_action`, `test_shepherd_launch_then_card`,
  `test_create_from_the_workspace_root_names_a_recorded_branch` (still `(0, '')`): pass
  unchanged.

### Tests

`tests/test_dispatch.py` (fixtures `root`, `built`, `record`, helpers `cli`, `build_next`):

- Acceptance, all PASS: `dispatch next A` and `build next A` print equal JSON with
  `action: raise`, `seats: []`, one `commands` entry starting
  `wuwei brief shepherd A shepherd-A --worktree ` whose body has `bin/wuwei pr raise`,
  `--item A`, never `gh pr create` (the PR guard refuses a git or gh mention), and passes the PR guard. Write `briefs/shepherd-A.md` (as `test_next` does): both
  print `seats == [brief.seat_action('shepherd', path, tree, root)]` and no `commands`.
  Record seat `shepherd-A` running: `seats == []`, no `commands`, `reason` names
  `shepherd-A`, `running` and `bin/wuwei why A`.
- Delta notes: in `test_delta_nonblocking_residual_becomes_review_note` (line 175), assert
  `commands[0]` carries `Review note: `.
- Update the whole-dict equality asserts (lines 107, 698, 777, 813, 1223) and
  `tests/test_parallel_dispatch.py:127` to compare `action` and `notes`.

`tests/test_pr_guards.py` (fixture `item`, recorded `DIV-1`):

- The three commands of `test_create_from_the_workspace_root_names_a_recorded_branch`:
  `(0, '')`, and stderr has `warning: DIV-1 is a WUWEI item` and
  `bin/wuwei pr raise example/project` and `--item DIV-1`.
- `[security]\nposture = "strict"` appended to the config:
  `cd worktrees/DIV-1 && gh pr create -r alice` returns exit 1 with a reason starting
  `pr raise: DIV-1 is a WUWEI item` and containing `--item DIV-1`.
- `DIV-1` with `pr = 'example/project#5'` recorded: `(0, '')` and no `pr raise` in stderr.
  The `case` fixture's `gh pr create -r alice` (no recorded item): `(0, '')` and no warning.

`tests/test_charters.py`, `test_amended_role_rules`: `shepherd.md` contains
`wuwei pr raise`, `--item <item>`, `gh pr create` and `wuwei pr claim`.

## Files

| File | Change |
|---|---|
| `cli/wuwei/dispatch.py` | add `SHEPHERD_BODY`, `raise_action`; `next_step` returns it twice |
| `cli/wuwei/commands/next.py` | `_shepherd` renders `dispatch.raise_action`; drop `SHEPHERD_BODY` |
| `cli/wuwei/guards/pr.py` | `create_check`: warning below strict, refusal under strict |
| `charters/shepherd.md` | version 1.1.0; step 2 names `pr raise --item`, never `gh pr create`, `pr claim` |
| `agents/shepherd.md` | regenerated by `bin/wuwei agents build` |
| `docs/specs/2026-09-24-wuwei-design.md` | 4.1 row, 5.3 paragraph |
| `docs/site/daily.md`, `docs/site/reference.md` | raise shape and the warning |
| `tests/test_dispatch.py`, `tests/test_parallel_dispatch.py` | acceptance test; equality updates |
| `tests/test_pr_guards.py`, `tests/test_charters.py` | guard and charter tests |

No `research.md`, `data-model.md`, `contracts/` or `quickstart.md`: the raise action reuses
the gate shape and adds no entity, port or command.
