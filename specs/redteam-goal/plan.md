# Implementation plan: redteam-goal

**Spec**: `specs/redteam-goal/spec.md`
**Item**: redteam-goal, tier smart, domain complex, promise in doubt, goal G-2

## Technical context

- Stdlib-only Python 3.11+ under `cli/wuwei/`, cap 4,000 lines. Main b566362 holds 3,879; the
  item's estimate is 0 net, cap +3.
- `evidence.needed(root, tier, files, item, rose)` builds `wants` per gate. At smart, `deep` is the
  complex domain (`cynefin(item) == 'complex'`) and `risky` is owner paths or the `RISKY` pattern
  over the code files; goal read `smart and in_doubt` alone. `gates_for` calls it for `gaps`, the
  board and the create and ready doors.
- `agents.TABLE` holds the model rows the hook advises on; `charters/planner.md` is the table seats
  read; `tests/test_charters.py` pins both.
- The red-team brief: the spike's `brief-ship.md`, recorded by `wuwei plan run redteam-spike`.

## Design

1. `needed`: goal becomes `smart and (deep or risky or in_doubt)`. One line changed in each runtime
   copy; `smart` already requires code, so docs alone still owe nothing.
2. `charters/sentinel-goal.md`: a `## Red team` section with the brief (the three classes, archive
   copy probes, the blocking rule) and the seven goal duties under `## Goal duties`.
3. `_common.md` Done: the smart sentence names the three goal triggers; it drops the
   "`wuwei evidence` names them" aside to stay within one word of the old length (sentinel-arch
   had 2 words of room).
4. `lead.md` rule 3: clear adds goal on risky or owner paths; complex takes all four gates; the
   goal trigger sentence replaces "only then does the goal gate run".
5. Model row: Sonnet 5.5 high; Opus 5.5 high at full or on risky, owner or contract paths, in
   `planner.md`, `agents.TABLE` and `docs/site/concepts/models.md`.
6. Docs: design section 6, the evidence page's smart table, the team page row.
7. `bin/wuwei agents build`, then `setup.vendor` for `.claude/`.

## Proof

- Tests first: `tests/test_smart.py` (the trigger table, the moved rows), `tests/test_charters.py`
  (the red-team agent, the trigger in every home, the goal row).
- `route_diff.py` over the route corpus at main and head (AGENTS.md, a change to the needed gates).
- The smart tier tests crossed: head tests on the main runtime, main tests on the head runtime.
- Mutants on both runtime copies, one at a time.
