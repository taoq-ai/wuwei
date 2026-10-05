# Implementation Plan: Opaque commands warn, and a branch push, a PR raise and a local merge are never owner-only

**Branch**: `530-opaque-pr-raise` | **Spec**: `spec.md`

## Summary

Two shared spots carry most of the change. The hook's `posture()` levels refusals; it gains
one rule for opaque calls (warn below strict unless the text names a publish target) and one
rule that levels PR create refusals as `publish` instead of owner-only. The #478 grant card
(`grants.gate`) gains an `evidence` action class, and one helper, `grants.evidence`, decides
warn, card or refusal for a missing piece of evidence; the push guard, the PR guard and
`pr raise` call it. The rest is small: `--repo/--head` and `cd <worktree> &&` in the PR
guard, one deleted refusal in the deploy guard, the native pre-push hook levelling an
evidence miss by posture, and one guide line.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. In-process tests with the existing fakes
(`tests/fakes/`, the `Fake` of `tests/test_pr_guards.py`, the fixtures of
`tests/test_commit_push.py`, `tests/test_shepherd.py`, `tests/test_grants.py`) and the
in-process hook harness of `tests/test_parser_warns.py` and `tests/test_posture.py`. No
network, no real `gh`.

## Constitution Check

- Exits stay 0/1/2; an error while computing the opaque reason enforces the refusal (fail
  closed).
- One behaviour, one function: opaque levelling lives only in `hook.posture`; the
  evidence decision lives only in `grants.evidence`; the fast-check evidence read lives only
  in `commit_push.fast_evidence`.
- No subprocess in the core; branch reads go through the vcs port (`branch` already exists).
- No new config key, no new state key, no new event kind (`guard.would_refuse`,
  `grant.asked`, `grant.used` are reused; only their producer descriptions widen).
- Security: the records floor and the owner-only merge, approval, admin, protection,
  deploy and release rules are untouched. Opaque text that names a publish target keeps
  today's refusal. Pass.

## Changes

### `cli/wuwei/shell.py`: `unreadable(command, cwd=None) -> str`

New, next to `unread`. What a guard cannot read in this call, or `''`, checked in this
order:

1. `script_path(command, cwd)` is not None: `f'script {path.name}'`;
2. `classify(command, cwd=cwd).inline` (an interpreter given `-c`/`-e` code or a here-doc):
   `'inline interpreter code'` (checked before parsing: `normalize` rejects an inline
   snippet that mentions `gh` as an unaccounted mention, which would hide the real cause);
3. `normalize(command)` raises `ParseError`: the error text before its first `;` (for
   example `command substitution is unsupported`);
4. a parsed command whose `is_opaque(argv)` is true (an interpreter reading code from
   input): `f'{program} code from input'` with the program's base name;
5. else `''`.

Read only; never raises for a `ParseError` (other exceptions are caught by the caller).

### `cli/wuwei/guards/deploy.py`

- `git()` (`:133-135`): delete the `merge` branch. `git merge` then falls through to
  `git_kind`, which returns `write`, so `git()` returns `(0, '')`. A local merge publishes
  nothing; pushes stay checked by the push rules and the pre-push hook.
- New `floor_named(text, config) -> bool` (#530, FR-002): the literal text names a publish
  target or an owner-only action, so an opaque call naming it keeps today's refusal. With
  `m = lambda words: shell.mentions(text, words, script=True)`, true when any holds:
  - `m((*PROGRAMS[2:], 'deploy', 'deployments', 'release', 'releases', *(pattern.split()[0]
    for pattern in config['deploy']['deny'])))`;
  - `m(('gh',))` and `m(GH_FLOOR)`, with the module constant `GH_FLOOR = ('merge',
    'approve', 'APPROVE', 'admin', 'review', 'protection', 'rulesets', 'alias', 'secret',
    'workflow', 'dispatches', 'rerun', 'environments', 'refs', 'comment', 'create', 'edit')`
    (merges, approvals and the other owner-only `pr` rules, workflow dispatch, and `gh` text
    writes, which the outward canary check must read);
  - `'hookspath' in text.lower()` or `m(('wuwei-workspace',))` (the pre-push anchor);
  - `m(('push',))` and a word of `text`, split on `[\s'"`;&|()<>$=]+`, is a force or anchor
    form (`--force*`, `--mirror`, `--tags`, `--follow-tags`, `--no-verify`, a short bundle
    `-[a-zA-Z]*f[a-zA-Z]*`, a leading `+`), contains `refs/tags/`, or, after stripping a
    leading `+`, everything up to the last `:`, and `refs/heads/`, matches
    `v?\d+\.\d+.*`, equals `main`, `master` or a configured `default_branch`, or satisfies
    `environment(branch, config)`.
  Comment: `# ponytail: literal words only; a branch built at run time is anchored by the
  pre-push hook and protected refs (spec 4.5).` `gh` reads (`gh pr view --json
  reviewRequests`, `gh api .../comments`, `gh pr checks`) name none of these words.

### `cli/wuwei/guards/__init__.py`

- Add `RAISE = 'pr raise: '` beside `NO_REVIEWER`, with a comment: the prefix of every PR
  create refusal; the hook levels it as `publish` (#530), not owner-only.
- `OWNER_ONLY` is unchanged (the merge policy, approvals and the rest stay owner-only).

### `cli/wuwei/commands/hook.py`: `posture(payload, refusals, root)`

- Keep the loaded config: `config = workspace.load_config(root)`; `name, levels =
  workspace.posture(config)`.
- After `level()`:
  1. PR raise: `if guard == 'pr' and (reason == NO_REVIEWER or reason.startswith(RAISE))`:
     `area, decided = 'publish', levels['publish']`, and `line = '' if reason == NO_REVIEWER
     else f'posture: publish = {decided} (set security.areas.publish)'`.
  2. Line suppression: replace `guard == 'deploy' and reason.startswith('publish: ')` with
     `reason.startswith('publish: ')` (the evidence card from `commit_push` and `pr` names
     its own way out, like the deploy card).
  3. Existing `UNPARSED` / `WORKSPACE_ROOT` / `UNKNOWN_GIT` branch unchanged.
  4. New, `elif area == 'publish' and code == UNRUN and name != 'strict' and (opaque :=
     opaque_reason())`: `reason = opaque`; skip when `opaque` or `UNPARSED` is already in
     `seen`, else add both; `decided = 'warn'`; `line = ''`. Adding `UNPARSED` lets the
     existing branch's `if reason in seen` skip a later `UNPARSED`, so a call writes one
     event; the existing branch itself is unchanged.
     `opaque_reason()` is a local closure computed once per call: `''` unless the tool is
     Bash; `what = shell.unreadable(command, cwd)`; `''` when `what` is empty or
     `deploy.floor_named(command + '\n' + (shell.script_text(command, cwd) or ''),
     config)`; else `f'opaque: {what}; the guards could not read it, so it ran with this
     warning (strict refuses it)'`. Any exception returns `''` (enforce as before). Import
     `deploy` inside the closure: hook tests replace the guards package path.
- The event payload is unchanged in shape (`guard`, `area`, `level`, `posture`, `reason`,
  `exit`, `target`, `session`, `item`).

### `cli/wuwei/grants.py`

- `ACTIONS['evidence'] = ('publish without evidence', 'publishes without evidence')`.
- `action(rule)`: return `'evidence'` when `rule.startswith('evidence: ')`, before the
  existing branches.
- `gate()`, only where `name == 'evidence'`:
  - `tail = f'has no recorded evidence ({rule.removeprefix("evidence: ")})'` instead of the
    owner-only tail;
  - when no target is found, return `(1, rule.removeprefix('evidence: '))` (no host
    terminal text; callers always pass the repository, so this is a guard against misuse);
  - the kept answer reads `f'{head}; the owner asked for the check first ({kept}): run it,
    then retry'`;
  - options `('keep', 'Defer until the check passes', 'The seat runs the named check, then
    retries.', 'Nothing publishes without its evidence.', 9)`, `once` and `today` as today,
    never `always`; recommendation `keep`; reasoning `The check is cheap and the seat can
    run it; allow only when the check cannot run.`; blast `publish without evidence on
    <repo>.`; pre-mortem `The change publishes with a failing check.`
    (Builder fix: the decision lint needs one option title starting with Do nothing, Defer
    or Keep, so the keep title is `Defer until the check passes`.)
  - The `PERMISSIONS_DENY` check is skipped for `evidence` (it never matches a push or a PR
    create; skipping avoids importing the deploy guard on this path).
- New `evidence(payload, root, config, argv, reason, repo, record=False)`:

  ```python
  def evidence(payload, root, config, argv, reason, repo, record=False):
      """#530: a push or PR raise without its recorded evidence. Where publish warns, (1,
      reason) for the hook to record and let through, or with record (a CLI command, no
      hook) the guard.would_refuse event, the warning on stderr and (0, None); under strict,
      (1, reason); otherwise the owner's card (run the check first, once, today)."""
  ```

  `name, levels = workspace.posture(config)`. `levels['publish'] == 'off'` -> `(0, None)`.
  `name == 'strict'` -> `(1, reason)`. `levels['publish'] == 'warn'` -> with `record`,
  `state.append_event('guard.would_refuse', {'guard': 'pr', 'area': 'publish', 'level':
  'warn', 'posture': name, 'reason': reason, 'exit': 1, 'target':
  hook.redacted_target(payload, root), 'session': payload.get('session_id'), 'item':
  hook.claimed(root, payload.get('session_id'))}, root)` and print `warning: <reason>` to
  stderr, return `(0, None)`; without `record`, `(1, reason)`. Otherwise `return gate(payload,
  root, config, argv, 'evidence: ' + reason, repo)`.

### `cli/wuwei/guards/commit_push.py`

- Extract the fast-check loop of `push_check` (`:137-151`) into `fast_evidence(repo, sha,
  path, root) -> (code, reason)`; `push_check` no longer reads evidence. The hint stays
  `run bin/wuwei build check <item>` (item from `_item(path, root)`).
- `check()`: after `result = push_check(...)` passes, `result = fast_evidence(repo,
  push['head']['sha'], actual['path'], root)`; on a miss `result = grants.evidence(payload,
  root, workspace.load_config(root), command.argv, result[1], repo['name'])`; return it when
  nonzero; when `result[1]` is callable append it to a local `used` list. Before the final
  `return 0, ''`, call each `use()` (the deploy guard's pattern, `deploy.py:337-338`).

### `cli/wuwei/commands/git_hook.py`: `run`

After `push_check` passes, `found = guard.fast_evidence(repo, push['head']['sha'],
actual['path'], root)`; if `found[0]` and `workspace.posture(workspace.load_config(root))[0]
== 'strict'`, `result = found`; otherwise print `wuwei pre-push warning: <reason>` to stderr and
continue. The non-fast-forward check runs after as today.

### `cli/wuwei/guards/pr.py`

- `check()`: after `commands = shell.normalize(raw)`, before the directory walk: when
  `len(commands) == 2`, the first is `cd` with separator `&&` and no writes, and its target
  `(cwd / _cd_target(commands[0])).resolve()` is a recorded item worktree
  (`_recorded(root, config, path=...)` with the workspace of `workspace.scope(target)`),
  set `cwd = target`, `initial = workspace.scope(target)`, `commands = commands[1:]`. Any
  other `cd` keeps today's path.
- Pass `payload` to `action()`; collect a callable `result[1]` from `action()` into `used`
  and call each before the final `return 0, ''`.
- `action(command, cwd, root, config, isolated, payload)`, `verb == 'create'`: run the
  isolation check and `create_check` inside `try/except ValueError as exc: (2, str(exc))`;
  return `(code, RAISE + reason)` when `code` and not `reason.startswith('publish: ')` and
  `reason != NO_REVIEWER`; else the result unchanged.
- `create_check(args, command, cwd, root, config, payload)`:
  - replace the two refusals at `:197-200`: when either `--repo/-R` or `--head/-H` is given,
    both are required (`ValueError('name both --repo <org>/<name> and --head <item branch>,
    or run gh pr create from the item worktree with neither')`); the repository must be in `config['repos']`
    (else `return 1, f'repository {repo} is not configured in this workspace; use a repository from
    .wuwei/config.toml'`); `found =
    _recorded(root, config, repo=repo, branch=head)`; None -> `return 1, f'head {head} is
    not a recorded item branch of {repo}; run gh pr create from the item worktree instead'`;
    else `cwd, item = found[1], found[0]`;
  - keep the environment, operand and reviewer checks;
  - evidence: `code, reason = gate_check(root, cwd, config, item=item)` (item None in the
    cwd form, as today); on a miss, when a branch is known prefix `f'head {head}: '`; then
    `return grants.evidence(payload, root, config, command.argv, reason, repo)` where `repo`
    is the `-R` value or the single name `merge.configured(root, config, cwd)` returns.
- New `_recorded(root, config, *, path=None, repo=None, branch=None)`: iterate
  `state.read_state(root)['items']`; for each with a recorded `worktree`, `tree = (root /
  row['worktree']).resolve()`; with `path`, match `tree == path`; with `branch`, match
  `repo in merge.configured(root, config, tree)` and `data(vcs.branch(str(tree),
  root=root))['name'] == branch`. Return `(item, tree)` or None. One function, used by both
  forms.

### `cli/wuwei/shepherd.py`: `raise_pr`

At `:306-309`: on a gate miss, `code, reason = grants.evidence(payload, root, config, argv,
reason, repo_name, record=True)` with `payload = {'session_id': sessions.current() or '',
'cwd': str(repo_path), 'tool_input': {'command': shlex.join(['bin/wuwei', 'pr', 'raise',
repo_name, '--item', item])}}` and `argv` the same list; print and return on a nonzero
code; keep a callable `reason` as `use` and call it after `state.record_pr` succeeds.

### `cli/wuwei/guide.py`

In `## Command forms`, add: `- Review comments, threads and the reviewer list: wuwei pr
state <ref> and wuwei pr ping-check <ref>; use them before writing a loop.` Regenerate the
block in `docs/site/agent.md` (`test_agent_guide_ships_and_is_linked` pins it; the page stays
within 100 lines and the guide within 97).

### Producer descriptions

`cli/wuwei/commands/event.py:22` (`guard.would_refuse`): `wuwei hook (shadow mode) or wuwei
pr raise`; `:86-87` (`grant.asked`, `grant.used`): add `the push and PR guards, wuwei pr
raise`; `cli/wuwei/state.py:268` (`grants`): the same widening.

### Docs (minimal; part B rewrites the posture table)

- `docs/specs/2026-09-24-wuwei-design.md` 4.1: the `git push` and `gh pr create` rows say a
  missing piece of evidence warns under observe and asks on the owner's card under guarded
  (owner, 2026-10-05, #530), and `gh pr create` is accepted with `-R` and `--head` of a
  recorded item branch or after `cd <recorded worktree> &&` (#534). 4.5: the opaque sentence
  becomes: below strict an opaque command runs with one `guard.would_refuse` warning unless
  its literal text names a publish target; the records floor stays. 9.1 floors bullet:
  raising a PR is not owner-only; it follows `publish`.
- `docs/site/security.md:57`, `docs/site/reference.md:370`: the same two facts in one
  sentence each.

## What must not change

- `OWNER_ONLY` and every non-create `pr` refusal; the deploy ban and grants for deploy,
  release and `deploy.deny` publish; `grants.active` matching; the standing-grant schema.
- The records floor: `protect_state`, `decision`, `verdict`, `traces`, `lifecycle` refusals.
- `UNPARSED`, `WORKSPACE_ROOT` and `UNKNOWN_GIT` levelling and reasons (#347, #470).
- Identity, force, default-branch, environment-branch and non-fast-forward push refusals,
  in the tool hook and in the native hook.
- The heartbeat session is always enforced; a config that does not load enforces.
- `gate_check` and `_recorded_gates` evidence rules.

## Existing tests whose expectations change (deliberately)

- `tests/test_deploy.py:127` `('git merge topic', 2, 'branch')` -> `0`.
- `tests/test_pr_guards.py:72-73`: `--head other` and `-R other/project` rows -> the new
  reasons (`both`, `not configured`); `test_solo_owner_create_needs_no_reviewer` and the
  gate-miss rows: reasons start with `pr raise:` (or `publish:` under guarded when the case
  passes a hook payload; these call `check()` with the default guarded posture, so a gate
  miss now writes a card: assert code 1 and the card id).
- `tests/test_parser_warns.py:78-86`: `for f in a b; do git push origin $f; done` and `for
  f in a b; do git commit -m $f; done` move to a new "opaque, no publish target: warns below
  strict" case; the other rows keep refusing in every posture. `:170-178`
  `test_issue_470_commit_substitution`: guarded now warns.
- `tests/test_commit_push.py`, `tests/test_git_hook.py`: push without evidence under the
  default guarded posture refuses with a card reason; under observe the native hook warns.
- `tests/test_shepherd.py:348` (`test_raise_refuses_failed_gate_without_creating`): still
  no PR created; the reason is the card's.
- `tests/test_posture.py` owner-only table: unchanged (`pr` stays in `OWNER_ONLY`).

## Deferred

- Invariant rows and `tests/test_invariants.py`: part B of #530.
- Turning the missing-reviewer refusal into a card under guarded: part B's sweep.
- Inline interpreter code naming a deploy program without `git` or `gh`: unchanged (spec
  4.5 anchors).
