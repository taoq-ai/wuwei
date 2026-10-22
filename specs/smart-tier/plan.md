# Implementation plan: smart-tier

**Spec**: `specs/smart-tier/spec.md`
**Item**: smart-tier, tier full, goal G-4

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, cap 3,600 lines. Main 86b2e56 holds
  3,396; the brief's budget is +20.
- `evidence.gates_for` reads the item's tier, raises it on the error budget, and asks `needed()`
  for the gates; `gaps` and `guards.create_door` call it. `evidence.spec_gaps` reads the
  artifacts per tier. `plan.TIERS` and `plan.add` hold the item fields; `__main__` the flags.
- `gh.file(repo, path, ref)` reads a file at a ref; `_cached` keeps an answer a day.

## Design

1. `plan.TIERS` gains `smart`; `plan.add` takes `domain` (checked against
   `(clear|complicated|complex): <why>`) and `in_doubt`; `--tier` defaults to smart, with
   `--domain` and `--in-doubt`; the candidates file defaults to smart and carries both fields.
2. `evidence.cynefin(item)`: `clear` or `complicated` when the field starts so, else `complex`.
3. `evidence.needed(root, tier, files, item, rose)`: at smart, the standard rows, plus security
   for complex or a rise, plus arch for complex, a guard-word patch, a code file with no patch, or
   a trust path below clear, plus goal when in doubt.
4. `evidence.rose(repo, pr, files)`: decision nodes per function name at the PR's base and head
   sha, read with `ast`; a rise to MCCABE (10) is True; an unread head is True. `gates_for` calls
   it lazily, cached by base and head sha.
5. `gaps`: spec artifacts for smart only when complex, and then as safety.
6. `create_door` passes the branch head and merge base shas in its PR shape.
7. Charters: `_common.md` Done, `_gate.md` rule 2, `builder.md` 3 and 4, `lead.md` tier and
   classification; trims keep every agent under the word ceiling.

## Cost

Two contents reads per changed non-test Python file, only when security is not already owed,
cached a day per (base, head). No read for standard, light or full items.

## Proof

- Tests first: the four acceptance scenarios and the lowering probes, red at 86b2e56.
- `probe.py`: 7 domain spellings x 10 diff signals through `evidence.gaps` at main and the head.
- `route_diff.py`: the route corpus under five hosts at main and the head.
- 20 mutants of the changed expressions, applied to both runtime copies one at a time.
