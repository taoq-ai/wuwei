# Feature Specification: the invariant walk runs with headroom under its budget

**Feature Branch**: `626-fast-invariant-walk`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #626: "On 2026-10-09 tests/test_invariants.py::test_invariants_hold
failed on the runner at 1.05 s and 1.01 s for 18000 cases against the 1.0 s budget, on a
branch that is not slower than main." The owner's rule from #346 applies: reduce the cost,
never the budget or the case count. Deliver: profile the walk and name the top five costs;
bring p95 on the runner under 0.7 s with the same 18000 cases and the same assertions; a
test asserts the walk's own overhead per case stays under a fixed fraction of the budget.

## Root cause

Profiled on `main` (66b3720) in this worktree with the pipeline interpreter (CPython 3.12):
`time.process_time` around `walk(world)`, exclusive CPU per `Rules.memo` kind, and cProfile
over one walk. The walk is already memoised by projection: 12185 invariant calls cover the
18000 cases, and the loop itself costs 3 ms. The time is in the real rules the invariants
call, plus work that lands inside the clock but is not the rules' cost.

Top five costs (one walk, file run alone; the walk took 0.63 to 0.73 s, median 0.665 s
over 12 walks):

| # | Cost | Where | CPU | Share |
|---|---|---|---|---|
| 1 | `outward.classify`, 3018 calls, one per OUTWARD projection | `Rules.outward`, tests/test_invariants.py:184-204 | 0.17 s | 18% |
| 2 | `protect_state.check_bash`, 72 calls in 18 computes; 48 repeat a call on the same inputs | `Rules.record`, tests/test_invariants.py:224-246 | 0.17 s | 17% |
| 3 | 18 in-process PreToolUse hook runs | `Rules.evidence`, `tag`, `opaque`, tests/test_invariants.py:292-325 | 0.12 s | 12% |
| 4 | Imports inside the clock: 26 `wuwei` modules plus `zoneinfo`, `sysconfig` and `tarfile` are first imported by the walk when the file runs alone | the `from wuwei ... import` lines inside the computes | 0.12 s without a bytecode cache (a fresh checkout), 0.02 s with one | up to 15% |
| 5 | The deploy guard on a seeded grant state, 18 computes | `Rules.grant`, tests/test_invariants.py:206-222 | 0.08 s | 9% |

Smaller, and avoidable without losing a case:

- Config parses: the walk parses 86 distinct config texts (about 0.8 ms each); 27 come from
  I35's `max_rounds` product (tests/test_invariants.py:1033-1036), one parse per
  (cap, tier, override). The per-process parse cache (`cli/wuwei/workspace.py:588-589`,
  `CONFIGS_KEPT = 128`) is cleared whole when full (`workspace.py:662-663`). In the full
  suite it already holds 77 texts from earlier tests when the walk starts, so it clears
  mid-walk and texts the walk already parsed are parsed again. Measured in the full suite
  the walk took 0.726 s, against 0.63 to 0.67 s alone.
- I20 calls `calibrate.host` 37 times; 12 repeat the call made one iteration earlier (the
  `plain` call at tests/test_invariants.py:687 equals the budget-0 call before it).

The issue's suspects, measured: config loading per case does not happen (one parse per
text, above); the `Unread` guards are part of the 3 ms loop (0.3 us per projection);
`CHECKS_RECORD` costs two string replaces per record; I32 and I33 take 0.045 s and 0.017 s
and their cost is the CLI path (`decision route`, `config set --from-card`,
`undo.correct`), not the file writes, which already go to the fixture's temporary
workspace. One-shot invariants are already memoised (`rules.memo` or `functools.cache`).

Why cost 2 repeats: `Rules.record` is keyed on `(posture, grant)`, but its four
`check_bash` calls read only the planner session, its `gate_asked` topics
(`sessions.gate_topics`, `cli/wuwei/sessions.py:28-38`), the posture and the D-1 record;
neither `cli/wuwei/guards/protect_state.py` nor `cli/wuwei/sessions.py` reads the grant
rows. For one posture the five answered grant states (`asked`, `keep`, `once`, `today`,
`always`) make the same four calls on the same inputs. `record_gate` and the grant-row
comparison I5 needs do depend on the seeded rows and stay per grant state.

Why cost 4 lands in the clock: #562 FR-009 put imports outside the timed region, and the
invariants added since (I20 to I35) import inside their computes. In the full suite,
`tests/test_hooks.py:58-60` and `:1298-1302` also drop the guard modules from
`sys.modules` before this file runs.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which costs are cut? A: Only work that repeats a call on the same inputs or is not
  the rules' cost: the repeated `check_bash` calls (cost 2), the imports inside the clock
  (cost 4), the parses repeated after a mid-walk cache clear, I35's 27 parses (9 cover
  the same triples) and I20's repeated calls. Costs 1, 3 and 5 are the rules under test,
  one call per projection; cutting them would drop a case.
- Q: Is importing before the clock a loosened budget? A: No. #562 FR-009 already requires
  imports outside the timed region. The budget measures the rules' CPU.
- Q: Is clearing the parse cache before the clock a loosened budget? A: No: the walk then
  parses each of its own texts inside the clock exactly once, whatever earlier tests left.
- Q: Production code? A: Unchanged. Every cut is in `tests/test_invariants.py`.
- Q: What does the overhead test measure? A: `walk` with every invariant replaced by a
  no-op and the same READS and PARTS positions, so the same 12185 calls over the 18000
  cases; CPU under 5 percent of the 1.0 s budget, and the message names the cost per case.
- Q: Is the 0.7 s target asserted? A: No. `elapsed < 1.0` stays the assertion; 0.7 s is
  the runner target read on main after merge.

## User Scenarios and Testing

### User Story 1 - A required check stops flipping at the budget (Priority: P1)

The walk costs less without a case, an assertion or the budget changing, so
`test_invariants_hold` passes on the runner with margin and no merge is held by chance.

**Acceptance Scenarios**:

1. **Given** the runner, **When** five consecutive Tests runs on main finish after the
   merge, **Then** each passes `test_invariants_hold` with the walk under 0.7 s CPU.
2. **Given** the walk, **Then** it still asserts exactly `CASES` cases (at least 18000),
   every invariant still runs once per distinct value of the dimensions it reads, every
   `BROKEN` rule is still caught and an undeclared read still raises.
3. **Given** the full suite, where earlier tests filled the config parse cache and dropped
   the guard modules, **When** the walk runs, **Then** it imports no module inside the
   clock and parses each of its config texts once.

### User Story 2 - The margin is visible before a merge is held (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the walk with no invariants, **When** `test_walk_overhead` runs, **Then** it
   asserts the CPU is under 5 percent of the 1.0 s budget, and its message names the cost
   per case, the total and the share.
2. **Given** a change that imports a module inside the walk, **When** the file runs alone,
   **Then** `test_invariants_hold` fails naming the modules imported inside the clock.

### Edge Cases

- A later invariant imports a new module inside its compute: the import assertion names
  it; the fix is one name in `WALK_IMPORTS`, never a budget change.
- A later change makes `protect_state` read the grant rows: the `record checks` memo key
  must then take the grant; the comment at the memo says so.
- The file runs alone with no bytecode cache: the imports are paid before the clock.

## Requirements

### Functional Requirements

- **FR-001**: `Rules.record` runs `record_gate` and the grant-row comparison per
  `(posture, grant)` as today, and its four `check_bash` calls once per
  `(posture, grant != 'none')`.
- **FR-002**: I20 reuses the budget-0 result as the plain call for the budget after it;
  every combination and both comparisons stay.
- **FR-003**: I35 checks every (cap, tier, override) triple it checks today with one parse
  per cap and rotation of the overrides over the tiers (9 parses for 27 triples); the
  `open_fix` half is unchanged.
- **FR-004**: `test_invariants_hold` imports every module the walk uses before the clock,
  clears the config parse cache before the clock, and fails naming any module imported
  inside the clock. The gc collect and freeze stay as they are.
- **FR-005**: `test_walk_overhead` times `walk` with no-op invariants over the same
  projections and asserts under `OVERHEAD * BUDGET` (0.05 of 1.0 s), naming the cost per
  case.
- **FR-006**: `BUDGET = 1.0` is the one budget constant both tests read. No budget, case
  count, dimension, READS entry, PARTS entry, invariant, `BROKEN` rule or fixture is
  loosened or dropped.

### Key Entities

None.

## Success Criteria

- **SC-001**: on the runner, five consecutive Tests runs on main pass
  `test_invariants_hold` with the walk under 0.7 s (read after merge).
- **SC-002**: locally on the pipeline interpreter, alternating `main` and this branch in
  one session, the median walk CPU over at least 10 walks drops by at least 15 percent
  with the file run alone and by at least 20 percent in the suite run up to this file
  (prototype of this plan, file alone: median 0.665 s to 0.554 s, minimum 0.625 s to
  0.473 s).
- **SC-003**: `test_walk_overhead` passes; the prototype measured 0.013 s cold (0.7 us per
  case), under the 0.05 s line.
- **SC-004**: the full suite passes; `test_broken_rule_is_caught` still catches
  `host cap of one` (I20) and `a fix round past the cap` (I35).

## Assumptions

- The runner cannot be run from here: SC-001 is the issue's acceptance and is read from
  the Tests runs on main after merge. Local evidence is SC-002 and SC-003. The issue
  measured the runner (1.01 to 1.05 s) and the owner's machine (1.04 s) at about the same
  figure, so a local cut is expected to carry over roughly in proportion.
- If the runner p95 stays at or above 0.7 s after this change, the next cuts are in
  production code on shared paths (the config copy on every `load_config`, the security
  material read per argument in `protect_state._protected`). They go to a follow-up issue,
  recorded under Deferred, never a budget change. A parallel worktree
  (`626-hotfix-copy-data`) exists; this item does not touch `cli/`, so the two cannot
  conflict.
- "The gc hunk from #610" is the `gc.collect()` and `gc.freeze()` before the clock in
  `test_invariants_hold`; it stays unchanged.
- "Move file writes to a per-walk temporary set up once": the writes already land in the
  fixture's temporary workspace, created once per walk, and measured small; no change.
- "Parse fixture records once at module level": `CHECKS_RECORD` is already a module-level
  string imported at the top; the duplicate import inside I33's compute costs a dictionary
  lookup and is left alone.
- No guard, refusal, posture or decision rule changes, so the design spec 9.2 table does
  not change (#530).
