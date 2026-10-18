# Feature Specification: the wide-change trigger counts code and spec lines, never prose, and a spec contract takes arch

**Feature branch**: `fix/wide-specs`
**Item**: wide-specs, tier full, goal G-2
**Input**: bug #1131. taoq-ai/taoqi#124 changed only `specs/**` (about 1,780 lines, tier standard).
The planner briefed "docs need no gate"; `wuwei evidence` asked for arch, because `needed()`
counted every file's lines, prose included, for the wide trigger. The rule and the code disagreed.

## The promise in my words

The issue's second option, made true in both the code and the rules:

1. In `evidence.needed`, the wide trigger (over 200 changed lines) counts only the lines of code
   files and spec files (paths under `specs/` or `openspec/`). Prose never counts: a `.md`, `.rst`,
   `.txt` or `.adoc` outside those folders, anything under `docs/`, `LICENSE` and `NOTICE`. So a
   prose-only diff needs no gate at any size, and a large spec diff at standard takes arch.
2. A change under `specs/**/contracts/` or `openspec/**/contracts/` takes arch at any tier, as a
   contract file (an OpenAPI or Swagger file, `.proto`, `.graphql`, `.schema.json`) already does.
3. `charters/_common.md` says so: a wide change is over 200 lines of code and specs, or 10 code
   files; a spec contract takes arch at any tier. `docs/design.md` line 77 and the site's evidence
   page match, `tests/test_charters.py` reads the new threshold text, and the agents are rebuilt.

The quality and security triggers do not change, nor does the 10 code files count.

The acceptance scenarios, restated:

1. A standard item with 1,780 lines under `specs/` only: `needed` returns `('arch',)`.
2. A standard item with 300 lines of `README.md` and `docs/site/*.md` only: `needed` returns `()`.
3. A light item adding `specs/001-x/contracts/api.yaml`: arch is in the result.
4. At the head, `bin/wuwei agents build` leaves git status clean and `tests/test_charters.py`
   passes with the new threshold text.

## How this fails

1. A spec contract is missed, so an outward contract change merges without arch. Ways in: a
   contract folder directly under `specs/` (`specs/contracts/api.yaml`), an OpenSpec change
   (`openspec/changes/x/specs/contracts/events.md`), a `.md` contract (prose by its extension), or
   the full tier with no code (where the early return for code does not fire). The pattern is
   anchored at `specs/` or `openspec/` and allows zero or more folders before `contracts/`; each
   of these has a test.
2. A false hold: prose or a near-miss path is read as a spec contract or as wide, so a docs PR
   waits for arch. Ways in: `docs/contracts/api.md`, `specs/contracts.md`, a 200-line spec (the
   bound is over 200), 150 code lines plus 300 lines of README and LICENSE. Each has a test that
   expects no arch.
3. The delta rule moves the wrong way after review fixes. `gate_gaps` runs `needed` on the delta,
   so the same counting applies there: a 300-line README delta now carries the passes (on main it
   asked arch to re-read), a 200-line spec delta carries them, a 201-line spec delta and a 2-line
   spec contract delta are re-read by arch. The delta test pins all four through the REST compare
   shape.

## Clarifications

### Session 2026-10-18

- Q: Which files count as spec files? A: The paths `needed` already leaves out of code as specs:
  those starting with `specs/` or `openspec/`, the same prefixes `gaps`, `PROSE` and `SPEC_RULES`
  use. A spec folder nested deeper (`packages/x/specs/`) is not a spec anywhere in WUWEI today and
  stays prose or code by its extension.
- Q: Does a code file count twice when it sits under `specs/` (a risky `.txt` such as
  `specs/requirements.txt`)? A: No. The counted set is one list filtered once, so each file counts
  once.
- Q: Does a contract file pattern (OpenAPI, `.proto`) inside `specs/` now take arch? A: Yes. The
  contract pattern runs over code and spec files together. Such a file is a contract by the
  existing rule; on main it slipped past only because spec paths were not code. Recorded under
  Assumptions.
- Q: Does the wide trigger fire at full or light? A: As before, only at standard; light stays the
  ceiling, and full takes all four once there is code. A full item whose diff is specs only takes
  arch only for a spec contract. Unchanged by this item.
- Q: Are generated files under `specs/` counted? A: No. `lines()` already drops generated paths
  (lockfiles, `dist/`, `vendor/`, snapshots), wherever they sit.

## Assumptions

- The owner prefers arch on large spec diffs and on spec contracts (the issue says the second
  option "seems more useful"; the plan item takes it). Overturned if the owner picks "count code
  lines only", a one-line change in `needed`.
- A contract file (OpenAPI, Swagger, `.proto`, `.graphql`, `.schema.json`) under `specs/` takes
  arch at any tier, as it would anywhere else. Overturned if the owner wants only the
  `contracts/` folder to count inside specs.
- Code is what `needed` already calls code, so a code file under `docs/` (`docs/conf.py`) does
  not count toward the wide trigger. On main a 300-line `docs/conf.py` change took arch at
  standard only through the count of every line; at the head it takes no gate, as a 100-line one
  already did on main (probe at the head, `probe-needed.py`, main against head). The real gap is
  that code under `docs/` takes no quality gate at any size, which the promise puts outside; it is
  a candidate item. Overturned if the owner wants the wide trigger to count code under `docs/`.
- "Spec contract" is a new term; a grep of charters, docs, skills and cli at the base found no
  other meaning for it.

## Rollback

Revert the merge commit. `needed` then counts every file's lines again and spec contracts stop
calling arch; no state, config or ledger format changes.

## User scenarios

### US1: the wide trigger counts code and specs, never prose (P1)

Acceptance 1 and 2. Tests in tests/test_evidence.py.

### US2: a spec contract takes arch at any tier (P1)

Acceptance 3. Tests in tests/test_evidence.py.

### US3: the rules say what the code does (P1)

Acceptance 4. Test in tests/test_charters.py.

## Requirements

- FR-001: `needed` counts the lines of code and spec files only for the wide trigger.
- FR-002: `CONTRACT` matches `specs/**/contracts/` and `openspec/**/contracts/`, and `needed` runs it
  over code and spec files at any tier.
- FR-003: The delta rule in `gate_gaps` follows FR-001 and FR-002 with no change of its own.
- FR-004: charters/_common.md, docs/design.md and docs/site/concepts/evidence.md state the rule;
  agents rebuilt; `.claude/` re-vendored; runtime at most 3,000 lines (2,976 to 2,978).

## Success criteria

- SC-001: Every acceptance scenario has a test that passes at the head. Scenarios 2 to 4 ran red
  on main; scenario 1 already held on main (it counted every line) and is pinned so the new count
  keeps it.
- SC-002: The full suite passes.
