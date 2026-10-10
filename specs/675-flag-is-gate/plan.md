# Implementation Plan: a trust_surface flag asks for the security gate, not the owner

**Branch**: `675-flag-is-gate` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

The security gate that `trust_surface` asks for already runs and is already checked at the
head: a flagged item's gate set holds `security` (dispatch.tier) and `merge.check` already
calls `gate_check` for that set. So the flag rule in `merge.item_evidence` only has to stop
refusing `trust_surface` and instead require that `security` is in the item's gate set. A gate
not passed at the head gets one wait reason in place of "the owner merges". The owner route
moves from the flag to an explicit `[merge] owner_paths` list, checked in the same file loop
as `never_auto_paths` and reported at the end of `check`, where no grant lifts it. All in
`cli/wuwei/merge.py`, one schema line, docs, tests.

## Technical Context

Python 3.11+ stdlib only. pytest dev-only. No new module, no new port operation, no new event
kind, no new state key. One config key, `merge.owner_paths`. One `Refused` subclass.

## Constitution Check

- I stdlib: nothing new imported (`gate_set` is already imported lazily in `check`).
- II exits: refusals stay exit 1; unreadable evidence stays exit 2 (`gate_check` raising is
  still `ERRORS`).
- III one behaviour one function: the merge decision stays in `merge.check`; the owner command
  string moves to one helper both owner routes use.
- IV test first: tasks.md orders each test before its code.
- V simplicity: no new verdict reader (the existing `gate_check` is the security PASS at head,
  delta included), no card route for owner paths, no output field.
- VII security: the change lowers a wall the owner asked to lower, only for `trust_surface`,
  and only when the security gate is in the item's set and PASS at the head; `boundary_relevant`
  and `agent_surface` keep the old rule; the plan event flags are still read so a forged item
  row cannot drop the security requirement; `merge.owner_paths` is owner config (config.toml
  writes are owner edits) and nothing lifts it.
- Workflow: the merge decision rule changes, so design 9.2 I3 gains the rule and
  `tests/test_invariants.py` its check; design 4.6 gets an owner amendment line (#675 is the
  owner's own item 43).

## Design

### cli/wuwei/workspace.py

`SCHEMA['merge']` (line 83) gains the list:

```python
"merge": {"default_tier": (str, "", ("", "ask", "owner_only", "today")),
          "owner_paths": [(str, None)]},  # #675: globs only the owner merges, whatever the grant
```

### cli/wuwei/merge.py

1. Beside `Refused` (line 18):

```python
class Routed(Refused):
    """#675: a refusal whose route no grant changes (a gate to wait on, an owner path); its
    text is the whole reason after `merge: `."""
```

2. `item_evidence` (lines 152-174), the flag loop: keep the schema validation, then

```python
        # #675: trust_surface asks for the security gate (checked at head below), not the owner
        require(not (flags['boundary_relevant'] or flags['agent_surface']), 'item carries a risk flag')
    if any(flags['trust_surface'] for flags in [item['flags'], *approved]):
        from wuwei.dispatch import gate_set
        require('security' in gate_set(item), 'trust_surface needs the security gate and the '
                f'recorded gate set of {name} has none; run bin/wuwei dispatch next {name}')
```

   The `granted` early return is unchanged (a grant still lifts auto eligibility).

3. One helper for the owner command, used by `by_grant` (lines 372-375, message text
   unchanged) and by the owner-path reason:

```python
def owner_command(ref, head):
    repo, number = ref.split('#')
    return f'gh pr merge https://github.com/{repo}/pull/{number} --squash --match-head-commit {head}'
```

4. `check` (line 208):
   - Before the file loop (line 259): `owner = None`. In the inner path loop, beside the
     never-auto line (268), for both granted and not (first match wins):
     ```python
     hit = matched(path, config['merge']['owner_paths'])
     if hit is not None and owner is None:
         owner = (path, hit)
     ```
   - The gate line (276-277) becomes:
     ```python
     if code:
         raise Routed(f'waits on the gate: {reason}; no grant lifts this; run bin/wuwei pr act {ref} once it holds')
     ```
   - Just before `return Result(0, ...)` (line 318), after the freshness and config checks:
     ```python
     if owner:
         raise Routed(f'{ref} is ready at {head}; {owner[0]} matches merge.owner_paths {owner[1]}: '
                      f'the owner merges: ask the owner to run {owner_command(ref, head)} in a host terminal')
     ```
   - The `except Refused` branch (line 323) gets a first case:
     ```python
     except Routed as exc:
         return Result(1, None, f'merge: {exc}')
     ```
     placed before `except Refused`.

`execute` and `by_grant` need no other change: a `Routed` result from the non-granted check
falls to `by_grant`, whose granted check returns the same `Routed` reason, and `execute`
records `merge.policy_blocked` with it as for any refusal. No card, no `grant.used`.

### What must not change

- The 4.6 preconditions and their order; `granted=True` still lifts auto eligibility and
  pacing (merge.auto, breaker, cap, quiet hours, approved plan, cycle budget, never-auto
  paths, size, soak) and the `boundary_relevant` / `agent_surface` flags.
- The `granted` reason `merge: <reason>; no grant lifts this; run bin/wuwei pr act <pr> once it
  holds` for every other precondition, and the `owner_only` tier message text.
- `gate_check`, `_recorded_gates`, `gate_set` and `dispatch.tier`: reused as they are.
- `risk_evidence`, the flag schema validation, `decision.waits` (its own `trust_surface` rule
  for assumptions), the scanner blocking rule, `dispatch.tier`'s flag raise.
- The evidence JSON shape of a cleared check (journaled in `merges`).

### Existing tests touched

- `tests/test_merge.py::test_policy_preconditions[forged-flags-risk]` forges
  `trust_surface` in a `plan.approved` event and expects `risk`. Under the new rule that PR
  clears (its gate set holds security and the gates PASS). Change the forged flag to
  `agent_surface`, which keeps the test's point (plan events are read, not only the item row).
- `[gate-security]` keeps passing: the hint `security` is in the wait reason.
- `test_grant_never_lifts_a_precondition[gates]` and `test_moved_head_merges_under_no_grant`
  keep passing: the wait reason ends with the same `no grant lifts this; run bin/wuwei pr act
  ... once it holds` and has no `ask the owner`.
- `test_strict_without_grant_names_the_owner_command` pins the `owner_only` message after the
  helper extraction.
- `tests/test_workspace.py::test_config_defaults_and_independence` pins the full default config,
  so its `merge` table gains `'owner_paths': []` (found while building).
- `test_merge_uses_quality_delta_record`'s setup moves into a `delta_record(root, role)` helper
  that the security delta test reuses.

### Docs

- `docs/specs/2026-09-24-wuwei-design.md` 4.6: after the eligibility bullets, one paragraph
  `Amended (owner, 2026-10-10, #675): ...` saying `trust_surface` makes the security gate
  required instead of the item ineligible (eligible once `security` is in its gate set and
  PASS at the head, delta included; until then the PR waits on the gate, never on the owner),
  `boundary_relevant` and `agent_surface` unchanged, and a diff touching a `[merge] owner_paths`
  glob is merged by the owner in a host terminal whatever the grant or `merge.default_tier`,
  the reason naming the path and glob.
- Design 9.2 I3: Checked by adds `x flag (trust_surface with security PASS, FIX) x owner path`;
  Notes add `#675: a trust_surface item waits on its security gate, never on the owner; a
  merge.owner_paths path merges only by the owner's hand, whatever the grant`.
- `docs/site/configuration.md`: a `merge.owner_paths` row after `merge.default_tier`
  (default `[]`; globs matched on any path suffix of a changed or renamed path; a match is
  merged by you in a host terminal, the reason names the path and the glob and prints the
  `gh pr merge` command; no grant or `merge.default_tier` lifts it).
- `docs/site/concepts.md` line 195 (merge paragraph): one sentence: a `trust_surface` PR waits
  on its security gate, not on you, and merges like any other once it passes at the head; a
  path in `merge.owner_paths` is always yours.

## Project Structure

Files changed: `cli/wuwei/merge.py`, `cli/wuwei/workspace.py`, `tests/test_merge.py`,
`tests/test_invariants.py`, `docs/specs/2026-09-24-wuwei-design.md`,
`docs/site/configuration.md`, `docs/site/concepts.md`. No new files outside this feature
directory.
