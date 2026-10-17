# Feature Specification: free runtime lines with no behaviour change and no complexity change

**Feature branch**: `claude/free-lines-5`
**Item**: free-lines-5, tier full, goal G-2
**Input**: after git-globals (PR #1122) the runtime sits at about 2,997 of its 3,000 lines, and
gh-args, scratch-remotes and push-refspecs need about 9 more. Line golf inside feature items made
git-globals' segments quadratic (50.7 s against 1.8 s at 500 KB), so this item frees the room on its
own, with a differential probe and a timing check for every rewritten function.

## The promise in my words

Shrink `cli/wuwei/` by at least 12 lines without changing any output, message, exit code or file
write, and without making any function slower in its order of growth. `guards.py` is out of
bounds here, because git-globals edits it; the lines come from the other runtime modules. The
vendored copy under `.claude/wuwei/` is re-vendored byte for byte.

The preferred sources, in order: dead code, merged duplicate helpers, a single-use variable that
the next line reads once, then the `x = f()` / `if x is None:` pairs that free-lines-4 left (it
rewrote only the truthy `if x:` form). No `;` joins and no squeezed lines.

The acceptance scenarios, restated:

1. The route corpus, every string literal of the suite and a generated set of at least 5,000
   commands go through `guards.bash` on main and on the head; every decision and reason is the
   same. Guards is untouched, but the merge and create doors read `evidence.verdicts`, which this
   item rewrites, so the probe runs with attested, edited, missing and imported verdicts on record.
2. Each rewritten function is timed at its worst shape at 125 KB and 500 KB on both trees, and
   the head is never more than 20 percent slower.

## How this fails

1. A walrus binds a different value than the two-line form, or a merged helper reads a different
   cache window: `board.rows` through `evidence._cached` must keep the 60 s `TTL`, not the 86,400 s
   default. Guarded by the probe's cache cases at 59 s, 61 s and epoch age; a mutant that drops
   `TTL` changes 2 outputs.
2. A reused list holds different rows than the expression it replaces: `mine` in
   `board.compute` must be exactly the open items of the repository, in order, for both the
   unreadable-host path and the item loop. A mutant that reads `open_items` there changes 10 outputs.
3. A counter rewritten as a set-size difference counts something else: `upgrade.items` counts one
   per import only because each import adds an id that was not in `known`. A mutant that returns
   the line on `>=` changes 15 of 40 cases.

## Requirements

- FR-001: `cli/wuwei/*.py` totals 2,984 lines or fewer (12 or more freed from 2,996).
- FR-002: `cli/wuwei/guards.py` is byte-identical to main.
- FR-003: every probe output is byte-identical on main and on the head.
- FR-004: no timed shape is more than 20 percent slower on the head.
- FR-005: `.claude/wuwei/` matches what `setup.vendor()` writes from the tree.
- FR-006: no new line over 150 characters, no `;` join.

## Clarifications

### Session 2026-10-17

- Q: The acceptance runs the guard corpus, but guards.py does not change. Is the guard probe still
  needed? A: Yes. `guards.bash` reaches `evidence.gaps` and so `evidence.verdicts`, which this item
  rewrites; the probe records attested, edited, missing and imported verdicts first so the merge
  and create doors read every branch of it.
- Q: Do the three gh wrappers used once (`deployments`, `releases`, `rules`) go? A: No. Tests
  monkeypatch `gh.deployments`, and moving REST paths out of `gh.py` spreads the code host over
  more modules. They stay.
- Q: Does `report.day`'s `now` move into its only f-string? A: No. It sits inside a generator over
  the open replies, so inlining it calls `ws.now()` once per reply: a complexity change.
- Q: Does `plan.add`'s lookup take the walrus form too? A: No. The line would pass 115 characters
  and the `is not None` branch is the long one; it reads worse.

## Assumptions

- A single-blank-line squeeze between top-level constants (hook.py `HANDLERS` and `PATCHED`) is
  left alone: it frees a line by layout only. Overturned if the owner asks for more room.
- `upgrade.items` keeps a short comment on `before` so the reader sees why a set-size difference
  is the import count. It costs nothing.

## Rollback

Revert the commit. No data, config or contract depends on the refactor.
