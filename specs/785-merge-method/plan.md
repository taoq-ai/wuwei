# Implementation Plan: the merge method follows the repository

**Branch**: `785-merge-method` | **Date**: 2026-10-10 | **Spec**: `specs/785-merge-method/spec.md`

## Summary

The adapter reports which merge methods the repository allows instead of one squash boolean;
`merge.check` picks the method with one pure helper (the setting, or squash then rebase then
merge under `auto`) and carries it in its evidence; `execute`, the owner's host-terminal
command and the GitHub merge call use it. Two one-line watch changes keep a merge-commit
merge from failing the 14-day measure and keep the breaker seeing its revert.

## Technical Context

Python 3.11 stdlib only; pytest for tests. GitHub only through `adapters/code_host/github.py`
and its closed `_run` allowlist. No new adapter operation, no new state key, no new event
kind; one new config key; one new parameter on the existing `code_host.merge` port.

## Constitution Check

- I stdlib only: yes.
- II fail closed: a missing or non-boolean `allow_*` field and malformed `methods` evidence
  are exit 2; an unknown method never reaches a subprocess (`_run` allowlist).
- III one behaviour one function: the choice lives in `merge.method_for`, read by `check`
  and by the invariant.
- IV test first: tasks.md orders each test before its code.
- V ponytail: one helper, one schema entry, one port parameter; the outcome change is one
  condition with a `ponytail:` comment; no first-parent history walker (Deferred).
- VII and Workflow: the merge precondition is a decision rule, so I72 goes into design 9.2
  and `tests/test_invariants.py`, plus a 4.6 amendment line (precedent: #668).

## Design

### `cli/wuwei/workspace.py`

In `SCHEMA['repos'][0]`, next to `"merge_deploys"`:

```python
"merge_method": (str, "auto", ("auto", "squash", "rebase", "merge")),  # #785
```

### `adapters/code_host/github.py`

`protection` (lines 443-475): drop `result['squash']`; after the rules loop read the
repository once and intersect:

```python
repository = _api(f'repos/{_repo(repo)}')
allowed = {method for method, key in (('squash', 'allow_squash_merge'),
           ('rebase', 'allow_rebase_merge'), ('merge', 'allow_merge_commit'))
           if _field(repository, key, bool)}
```

In the `pull_request` rule branch, a ruleset's `allowed_merge_methods` narrows a set
collected across rules (start `narrow = None`; each list intersects it), then
`result['methods'] = [m for m in ('squash', 'rebase', 'merge') if m in allowed and (narrow is None or m in narrow)]`.
Read all three `_field`s before filtering so a missing field is exit 2 whichever flags are
true. Update the `#524` comment to `#785`.

`_run` (line 65): the merge case becomes

```python
case ['pr', 'merge', url, '--squash' | '--rebase' | '--merge', '--match-head-commit', sha]:
```

`merge` (line 615): `def merge(ref, sha, method, root=None)`; raise
`ValueError('invalid merge method')` unless `method in ('squash', 'rebase', 'merge')`, then pass
`'--' + method`.

### `adapters/code_host/none.py`, `cli/wuwei/registry.py`, `tests/fakes/code_host.py`

`merge(ref, sha, method, root=None)`; `PARAMETERS['code_host']['merge'] = ('ref', 'sha', 'method')`;
the fake records `('merge', (ref, sha, method), root)`.

### `cli/wuwei/merge.py`

Next to `green`:

```python
METHODS = ('squash', 'rebase', 'merge')  # #785: the order auto prefers


def method_for(setting, allowed):
    """#785: the configured merge method when the repository allows it; under auto the first
    allowed of squash, rebase, merge; else None."""
    if setting != 'auto':
        return setting if setting in allowed else None
    return next((m for m in METHODS if m in allowed), None)
```

In `check`, lines 316-321: remove `'squash'` from the boolean key loop; then

```python
allowed = protection['methods']
if not isinstance(allowed, list) or not set(allowed) <= set(METHODS):
    raise ValueError(f'invalid merge method evidence; {DAMAGED}')
setting = settings['merge_method']
method = method_for(setting, allowed)
require(method, (f'{repo_name} does not allow the {setting} method into {pr["base"]} '
                 f'(repos.merge_method = {setting}); the owner sets an allowed method with '
                 'bin/wuwei config set or merges it in a host terminal') if setting != 'auto' else
        f'{repo_name} allows no merge method into {pr["base"]}; ask the owner to merge it in a host terminal')
```

Add `'method': method` to the exit 0 data dict (line 408). The `owner_paths` route (line 407)
calls `owner_command(ref, head, method)`.

`owner_command(ref, head, method)` (line 453): `--{method}` in place of `--squash`.
`by_grant` (line 473): `owner_command(ref, head, result.data['method'])`.
`execute` (line 507): `read(host.merge, ref, evidence['head'], evidence['method'], root=root)`.

`monitor` (line 694):

```python
# ponytail: line outcomes assume one squash commit; a merge commit or rebase is followed for
# red checks and reverts only, first-parent tracking when the cohort needs them (#785 Deferred).
measure = (age >= timedelta(days=14) and 'outcome' not in entry
           and entry['evidence'].get('method', 'squash') == 'squash')
```

Line 697: the revert pattern ends `r'[.,]'` instead of `r'\.'`.

### Design spec and docs

- `docs/specs/2026-09-24-wuwei-design.md` 4.6, after the #524 amendment paragraph: `Amended
  (owner, 2026-10-10, #785): the merge method follows the repository: repos.merge_method
  (auto, the default, squash, rebase or merge); under auto WUWEI uses the first method the
  repository and its rulesets allow of squash, rebase, merge, and an explicit method is used
  only when allowed; where the text above says --squash it reads --<method>, and where it
  says the repository must allow squash merges it reads the chosen method. A merge commit or
  rebase merge is followed for red base checks and reverts; the 14-day line outcome is
  measured for squash merges.`
- Adapter table (line 1902): `merge(ref, sha, method)`.
- 9.2 table, last row (after I41): `| I72 | WUWEI merges only with a method the repository
  allows: an explicit repos.merge_method only when allowed, auto the first allowed of squash,
  rebase, merge, none allowed the owner's merge | merge.method_for on every setting x every
  subset of allowed methods | #785; one choice in merge.method_for, read by merge.check; the
  adapter allowlist admits only --squash, --rebase and --merge |`.
- `docs/site/configuration.md`: row `repos.merge_method` after `repos.merge_deploys`; the
  `merge.default_tier` row's command reads `--<method>` (the method `merge check` chose).
- `docs/site/concepts.md` line 195: `the repository must allow squash merges` becomes `the
  repository must allow the merge method (repos.merge_method; under auto squash, then
  rebase, then merge)`.

## What must not change

- The order of rules in `check`; the method rule sits where the squash rule was.
- Exit 2 wording (`merge policy unmeasured: ...`) and the `Refused`/`Routed` routing.
- Every other `protection` field and its sources (`shepherd.py:166`, `config.py:339` read
  them; neither reads `squash`).
- `guards/pr.py` and `guards/deploy.py` merge parsing (they already accept every method flag).
- The `history` adapter, `outcome` and the 5.6 cohort for squash merges.
- No `--subject`, `--body`, `--admin` or `--auto` is ever passed.

## Files

| File | Change |
|---|---|
| `cli/wuwei/workspace.py` | `repos.merge_method` schema entry |
| `adapters/code_host/github.py` | `protection` `methods`; `_run` merge case; `merge(ref, sha, method)` |
| `adapters/code_host/none.py`, `cli/wuwei/registry.py` | `merge` signature |
| `cli/wuwei/merge.py` | `METHODS`, `method_for`; method rule and evidence in `check`; `owner_command`, `by_grant`, `execute`; `monitor` measure and revert pattern |
| `tests/fakes/code_host.py` | fake `merge` signature |
| `tests/test_code_host.py`, `tests/fixtures/code_host/recordings.json` | methods and merge argv tests; recordings |
| `tests/test_merge.py` | method tests; fixture `methods`; updated call tuples |
| `tests/test_path_day.py`, `tests/test_shepherd.py`, `tests/test_env_credentials.py` | fixtures: `methods`, repository fields, merge call tuple |
| `tests/test_invariants.py` | `i72`, `INVARIANTS`, `READS` |
| `docs/specs/2026-09-24-wuwei-design.md` | 4.6 amendment, adapter table, 9.2 row I72 |
| `docs/site/configuration.md`, `docs/site/concepts.md` | key row, command and paragraph |
