# Implementation Plan: a fix to a broken base skips the soak, and merge check says either wait or who merges

**Branch**: `668-soak-base-fix` | **Date**: 2026-10-10 | **Spec**: `specs/668-soak-base-fix/spec.md`

## Summary

Two changes in `cli/wuwei/merge.py`, one config key, one printed line. At the soak rule,
`check` reads the checks at the PR's base commit (only when the soak would hold) and skips
the soak when the head turns a failing base check green. The refusal reasons split into
`waits: soak ends at <time>` (soak) and `owner merges: <rule>` (everything else), each with
a `next` step that `merge check` prints as a `Next:` line.

## Technical Context

Python 3.11 stdlib only; pytest for tests. Code host reached only through the existing
`code_host` port (`host.checks(ref, sha)`, already called with a base SHA by
`discovery.py:175`). No new adapter call, no new state key, no new event kind.

## Constitution Check

- I stdlib only: yes.
- II fail closed: an unreadable base check result raises inside `check` and is exit 2 via the
  existing `ERRORS` handler.
- III one behaviour one function: the red-to-green rule lives in `merge.fixes_base`, read by
  `check` and by invariant I40.
- IV test first: tasks.md orders each test before its code.
- V ponytail: one pure helper, one schema entry, the soak line rewritten in place. No item
  kind read (that would be #648's and seat-writable).
- VII and Workflow: the merge policy is a decision rule, so I40 goes into design 9.2 and
  `tests/test_invariants.py`.

## Design

### `cli/wuwei/workspace.py`

`MERGE_SCHEMA` gains `"soak_skip": (str, "base_fix", ("base_fix", "never"))` (the same
choices form as `scanner.severity_threshold`).

### `cli/wuwei/merge.py`

New helper next to `green`:

```python
def fixes_base(base, head):
    """#668: the checks failing at the base commit that pass at head; a PR that turns a
    broken base green skips the soak."""
    passed = {c['name'] for c in head if c['conclusion'] == 'success'}
    return sorted({c['name'] for c in base if c['conclusion'] in ('failure', 'error')} & passed)
```

In `check`, replace line 313 (`require(granted or ... 'soak window has not passed')`) with:

```python
end = last + timedelta(minutes=policy['soak_minutes'])
soak = None
if not granted and workspace.now() < end:
    fixed = policy['soak_skip'] == 'base_fix' and fixes_base(
        checks_at(host, ref, pr['base_sha'], root), checks)
    if not fixed:
        return Result(1, {'next': f'run bin/wuwei merge {ref} after {end.isoformat()}'},
                      f'merge policy: waits: soak ends at {end.isoformat()}')
    soak = (f'skipped: fixes the broken base: {", ".join(fixed)} fail at '
            f'{pr["base_sha"]} and pass at head')
```

and add `'soak': soak` to the exit 0 data dict. `checks` is the head list already read at
line 287 and passed through `green`, so every head check is green there.

In the `except Refused` branch, the non-granted return becomes:

```python
return Result(1, {'next': f"run bin/wuwei merge {ref}: it merges under the owner's grant, "
                          'or asks the owner on a card'},
              f'merge policy: owner merges: {exc}')
```

`ref` is always the canonical `owner/repo#n` there: every `Refused` is raised after
`reference()` returns.

### `cli/wuwei/commands/merge.py`

After the existing `print(...)`:

```python
if result.exit == 1 and result.data:
    print(f"Next: {result.data['next']}")
```

Only `check` puts data on an exit 1; `execute` returns the grant path's result (data `None`),
so `wuwei merge <pr>` output is unchanged.

### Design spec and docs

- `docs/specs/2026-09-24-wuwei-design.md` 4.6: after the soak bullet's section, one line
  `Amended (owner, 2026-10-10, #668): ...` saying a PR whose head turns a check failing at
  its base commit green skips the soak (`merge.soak_skip`, `base_fix` or `never`), every
  other precondition unchanged, and that a held merge reads `waits: soak ends at <time>` or
  `owner merges: <rule>`.
- 9.2 table: row `I40 | The soak is skipped only for a head that turns a check failing at its
  base commit green | merge.fixes_base on a table of base and head conclusions | #668; the
  check path stays in tests/test_merge.py`.
- `docs/site/configuration.md`: a row `repos.merge.soak_skip` after `repos.merge.auto`.
- `docs/site/concepts.md` Soak entry: one sentence on the base-fix skip, appended to an
  existing line (`test_concepts_opens_with_the_glossary` allows at most two lines per entry).

## What must not change

- The order of rules in `check`: the soak stays the last policy rule before the fresh
  re-read, so a `waits` reason means every other rule passed.
- The granted path (`granted=True`): no base read, the `no grant lifts this` wording, and
  `by_grant`, `execute`, `pr act`.
- Exit 2 wording (`merge policy unmeasured: ...`).
- `guards/pr.py:merge_check` and its suffix (`test_pr_guards.py:243` pins it); it now wraps
  the new reason.
- `checks_at` validation (reused as is for the base commit).
- The `case` fixture in `tests/test_merge.py`: tests that need base checks route
  `host.checks` by SHA locally; a global SHA-stamping fake would break the stale-check test.

## Files

| File | Change |
|---|---|
| `cli/wuwei/workspace.py` | `soak_skip` schema entry |
| `cli/wuwei/merge.py` | `fixes_base`; soak block in `check`; owner refusal wording; `soak` in evidence |
| `cli/wuwei/commands/merge.py` | `Next:` line |
| `tests/test_merge.py` | new tests; the two existing soak cases get green base checks |
| `tests/test_invariants.py` | `i40`, `INVARIANTS`, `READS` |
| `docs/specs/2026-09-24-wuwei-design.md` | 4.6 amendment line, 9.2 row I40 |
| `docs/site/configuration.md`, `docs/site/concepts.md` | key row, Soak sentence |
