# Feature Specification: the runtime budget is 3,600 lines and the agents have word headroom

**Feature branch**: `leone/free-lines-7`
**Item**: free-lines-7, tier standard, goal G-4
**Input**: the owner's `goal:` answer of 2026-10-22 raises the runtime budget from 3,400 to 3,600
lines. The runtime is at 3,390 lines on main 415e8fe, and sentinel-arch sits at exactly its
2,250-word ceiling, so no rule fits in `_common.md`.

## The promise in my words

Every place that states the runtime budget says 3,600 lines: constitution VI, AGENTS.md,
CONTRIBUTING.md, SECURITY.md, design section 11 and the philosophy page. The size test asserts 3600.
The constitution goes from 3.2.0 to 3.3.0 with a new amendment date. `_common.md` is reworded so
each generated agent is at least 100 words under the 2,250-word ceiling, and no rule is lost. The
Done delta sentence reads "a delta off risky paths of docs, generated files or at most 20 lines".
No runtime line is freed unless the code becomes plainly clearer.

The acceptance scenarios, restated:

1. A copy of the runtime padded to 3,500 lines passes the size test, and one at 3,601 fails.
2. `bin/wuwei agents build` leaves every generated agent at least 100 words under its ceiling,
   and the agents match the charters.

## Requirements

- FR-001: `test_the_runtime_holds_its_size_budget` asserts at most 3600 lines and names 3600.
- FR-002: the six documents state 3,600 lines; the constitution is 3.3.0, amended 2026-10-22.
- FR-003: a test holds every generated agent at or under 2,150 words (2,250 less 100).
- FR-004: `_common.md` keeps every rule; the PR body maps each reworded sentence to its rule.
- FR-005: the Done sentence reads "a delta off risky paths of docs, generated files or at most 20
  lines carries the passes", and the threshold test reads that phrase.
- FR-006: no runtime line changes.

## Assumptions

- A budget raise is a minor constitution amendment (3.2.0 to 3.3.0), as budget-3400 was (3.1.0 to
  3.2.0). Overturned if the owner reads it as a major.
- The CHANGELOG and earlier specs keep 3,400: they record history.
- No runtime lines are freed: the owner chose the raise over line golf, and no change in reach
  was plainly clearer.
