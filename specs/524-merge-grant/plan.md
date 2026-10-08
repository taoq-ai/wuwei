# Implementation Plan: Merge grant

**Branch**: `524-merge-grant` | **Spec**: `spec.md`

## Summary

No new module, event kind or state key. The #478 grant gate learns one more action, and the
one merge function grows a second way through: when the auto policy refuses, `merge.execute`
re-checks the PR with the auto-only eligibility and pacing skipped, then asks
`grants.gate` exactly as the deploy guard does (the synthetic payload pattern `pr raise`
already uses for #530). The code host's `protection` read gains one boolean so both paths
refuse a repository that does not allow squash before anything is journaled.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Tests in process with the existing fakes:
`tests/test_merge.py` (`case` fixture, `config_change`, `events`), `tests/test_grants.py`
(`root`, `answer`, `standing`, `strict`, `posture`), `tests/test_plan.py`,
`tests/test_pr_actions.py`, `tests/test_pr_guards.py`, `tests/test_code_host.py` with
`tests/fixtures/code_host/recordings.json`. Neutral fixtures only (`example/project`,
`fixture-org/app`).

## Constitution Check

- III one behaviour one function: the merge decision stays in `merge.check`/`merge.execute`;
  the grant decision stays in `grants.gate`/`grants.active`. Nothing is copied. Pass.
- II exits: an auto-policy exit 2 never reaches the grant path; adapter errors stay exit 2;
  a once-grant race raises inside `execute` and is exit 2. Pass.
- VII security: no approval, no `--admin`, no branch-protection change; a merge still lands
  only through `--match-head-commit` at the gated head with required checks and reviews. Only
  the owner's recorded answer creates a grant (the existing `decide` path). Pass.
- #530: under observe and guarded the new outcome is a card, never a new refusal; strict
  keeps the owner-only answer. Pass.
- #551: `pr act` and `wuwei merge` return the card command or the exact host-terminal command;
  `wuwei next` already returns `wuwei pr act <pr>`. No skill prose. Pass.
- No forgeable trust: grant rows and standing lines keep their #478 producers; the merge tier
  is owner config. Pass.
- `tests/test_invariants.py` does not exist on this base: no invariant row.

## Changes

### `cli/wuwei/grants.py`

- `ACTIONS`: add `'merge': ('merge', 'merges')`. Update the `#518` comment: deploy, release,
  publish and merge become grant cards; message and secret-set stay owner steps.
- `action(rule)`: first line `if rule.startswith('merge: '): return 'merge'` (the deploy
  guard's `merge_deploys` and `environment branch merge` rules do not start with it and stay
  `deploy`).
- `gate(payload, root, config, argv, rule, repo, moved=False, pr=None)`: after the existing
  `hit = active(...)` line, `hit = hit or (pr and active(config, data, name, f'pr:{pr}',
  standing=False))`. Nothing else in `gate` changes; the card, keep, pending reuse, strict
  without Always, once spending and `grant.used` are reused as they are.
- New, next to `active`:

  ```python
  def merge_tier(config):
      """#524: ask (a card) or owner_only (the host-terminal command); unset follows the posture."""
      from wuwei import workspace
      return config['merge']['default_tier'] or (
          'owner_only' if workspace.posture(config)[0] == 'strict' else 'ask')
  ```
- `plan()`: `repo_name = repo_target.split(':', 1)[1]` instead of `repo_target[5:]`, so a
  `pr:` target is named whole. Merge entries now reach `plan()` because merge is in `ACTIONS`.

### `cli/wuwei/merge.py`

- `item_evidence(root, ref, data, granted=False)`: after `require(len(items) == 1, ...)`,
  `if granted: return name`. The approved-plan, risk-flag and cycle-budget checks stay for
  the auto path.
- `check(ref, root=None, *, cwd=None, repo=None, granted=False)`: wrap each auto-only
  requirement in `if not granted:` with no reordering: `merge.auto` (:208), the breaker
  (:211-212), the daily cap (:216-218), quiet hours (:219), the size (:247) and never-auto
  (:256) requirements (the files are still read and validated; the evidence keeps them for
  the post-merge outcome), the soak (:294-296). Pass `granted` to `item_evidence`.
- `check`, the `except Refused` branch: with `granted`, return
  `Result(1, None, f'merge: {exc}; no grant lifts this; run bin/wuwei pr act {ref} once it holds')`
  (`ref` is resolved by then). The auto path keeps its current text. The granted path must
  never print the auto policy's `the owner merges; ask the owner`, the wall the owner hit.
- `check`, both paths: add `'squash'` to the protection boolean tuple and, right after it,
  `require(protection['squash'], f'{repo_name} does not allow squash merges into {pr["base"]};
  WUWEI merges only with --squash: ask the owner to merge it in a host terminal')`.
  New reason strings keep the `tests/test_reasons.py` next-step shape.
- New `by_grant(ref, root, cwd)` called from `execute` inside the lock (named apart from
  the `granted` keyword of `check`):

  ```python
  def by_grant(ref, root, cwd=None):
      """#524: the owner's grant replaces auto-merge eligibility and pacing, never the 4.6
      preconditions; without a grant the card (ask) or the host-terminal command (owner_only)."""
      import shlex
      from wuwei import grants, sessions
      result = check(ref, root, cwd=cwd, granted=True)
      if result.exit:
          return result
      config, ref, head = workspace.load_config(root), result.data['pr'], result.data['head']
      repo, number = ref.split('#')
      command = f'gh pr merge https://github.com/{repo}/pull/{number} --squash --match-head-commit {head}'
      targets = (f'pr:{ref}', f'repo:{repo}')
      if grants.merge_tier(config) == 'owner_only' and not any(
              grants.active(config, state.read_state(root), 'merge', t) for t in targets):
          return Result(1, None, f'merge: {ref} is ready at {head}; merges are owner-only here '
                                 f'(merge.default_tier = owner_only): ask the owner to run {command} in a host terminal')
      argv = ['bin/wuwei', 'merge', ref]
      payload = {'session_id': sessions.current() or '', 'cwd': str(Path(cwd or Path.cwd())),
                 'tool_input': {'command': shlex.join(argv)}}
      code, use = grants.gate(payload, root, config, argv, f'merge: {ref} at {head}', repo, pr=ref)
      if code:
          return Result(1, None, use)
      use()
      return result
  ```
- `execute`: after `result = check(ref, root, cwd=cwd)`, add
  `if result.exit == 1: result = by_grant(ref, root, cwd)`. The rest (policy_blocked event,
  intent, undo, host merge, accepted) is unchanged.

### `adapters/code_host/github.py`

- `protection(repo, branch)`: `result['squash'] = _field(_api(f'repos/{_repo(repo)}'),
  'allow_squash_merge', bool)`; in the ruleset loop's `pull_request` branch,
  `methods = params.get('allowed_merge_methods')` and when not None
  `result['squash'] &= 'squash' in _list(methods)`. The endpoint is already on the allowlist
  (`default_branch` reads it).

### `cli/wuwei/workspace.py`

- `SCHEMA`: top-level `"merge": {"default_tier": (str, "", ("", "ask", "owner_only"))}`
  with a `#524` comment; `grants.standing.action` choices add `"merge"`. The standing target
  validation (`repo:` shape) is unchanged.

### `cli/wuwei/pr_actions.py`

- `act`, state `approved`: `print(f'{ref}: {result.reason}')`.

### `cli/wuwei/guards/pr.py`

- `merge_check`: on `result.exit == 1`, return
  `f'{result.reason}; run bin/wuwei merge {pr}: it merges under the owner\'s grant, or asks the owner on a card'`.
  Exit 2 and the policy-passed redirect are unchanged.

### `cli/wuwei/state.py`

- The `grants` producer text adds `wuwei merge or wuwei pr act`.

### Docs and charters

- `docs/specs/2026-09-24-wuwei-design.md`: 4.6 gets `Amended (owner, 2026-10-05, #524)`: a
  merge the policy does not clear asks the owner on a grant card (once, today, always per
  repository; planned merges on the gate card); the grant replaces eligibility and pacing,
  never the preconditions; `[merge] default_tier`. 9.1's owner-only floor bullet names the
  merge grant next to the deploy one.
- `docs/site/concepts.md` Grants: merge joins the list, with the conditions that hold
  whatever the grant says and `merge.default_tier`.
- `docs/site/configuration.md`: a `merge.default_tier` row; `grants.standing` action list
  adds `merge`; the section index row lists `[merge]`.
- `charters/lead.md` and `agents/lead.md` (kept equal by `tests/test_agents.py`): `merge`
  becomes a card the gate pre-approves; message and secret-set stay owner steps.

## What must not change

- The auto-merge path: `merge.check` without `granted` refuses exactly as today (only the
  new squash requirement is added), and its reasons are unchanged.
- The deploy guard's merge rules (`merge_deploys`, environment base) stay deploy-class
  grants; `--admin` merges and approvals stay refused; `guards.OWNER_ONLY` is unchanged.
- The shepherd seat refusal in `merge.execute` and `guards/pr.py`.
- Grant row and standing line shapes, `active`, `standing`, `ask`, `evidence`, the
  `wuwei grants` command, `decide`.
- The adapter `merge` call (`--squash --match-head-commit`).

## Complexity Tracking

None: one kwarg on `gate`, one on `check` and `item_evidence`, one small function in each of
`grants.py` (`merge_tier`) and `merge.py` (`by_grant`), one schema key.
