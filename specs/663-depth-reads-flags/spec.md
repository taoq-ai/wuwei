# Feature Specification: the gate depth reads the item's flags

**Feature Branch**: `663-depth-reads-flags`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #663 (owner, 2026-10-10, item 20): an item flagged `trust_surface`
whose main change is token masking got gate prompts saying "step zero: skip (no guard code or
trust path in the diff)". `trust_surface` or `boundary_relevant` true forces step zero to run
and the security reviewer at the first round; the reason names the flag; the diff heuristic
only adds depth, never removes it. Companion to #657 (lines excluded) and #631.

## Root cause (read on main at 35306d9)

The gate brief's `Depth:` line is written by `brief.depth_line` (`cli/wuwei/brief.py:30-45`),
called from the brief writer at `cli/wuwei/brief.py:448-451` with the item's depth, its changed
paths and the repository `trust_paths`. It never receives the item row's `flags`. It asks
`dispatch.step_zero(value, paths, trust_paths)` (`cli/wuwei/dispatch.py:220-232`), which at
standard depth decides from the paths alone: a path matching `trust_paths` or `GUARD_CODE`
runs step zero, anything else returns `(False, 'no guard code or trust path in the diff')`.

So an item the lead flagged `trust_surface: true` (raised to standard by `dispatch.tier`,
`cli/wuwei/dispatch.py:73-75`, reason `lead flag trust_surface`) whose diff is outside guard
code and trust paths gets, in every gate brief including the security one:

`Depth: standard; step zero: skip (no guard code or trust path in the diff); write Mutation: skipped (depth standard)`

Reproduced on main with the `day` fixture of `tests/test_brief.py`: item `X` with
`flags.trust_surface = true`, recorded tier `standard`, diff `cli/wuwei/mask.py`; `wuwei brief
security X g --gate --worktree tree` writes exactly that line. The orchestrator notes file
named in the task (`notes/663-full.md`) does not exist, so there was no dry-run workspace; the
reproduction above stands in for it.

The security reviewer half already holds on main: `dispatch.tier` raises any flagged item to
at least standard (`dispatch.py:73-75`), the pace never lightens a flagged item
(`pace.adjust`, `cli/wuwei/pace.py:34`), a flagged diff is never docs-only (`_docs_role` runs
only while the computed tier is light, `dispatch.py:97`), and the standard role set is
`arch, quality, security` (`dispatch.py:132`), which `next_step` launches in the initial round
(`dispatch.py:337`). It is pinned today only for a document diff
(`tests/test_dispatch.py:852`). This feature pins it for the issue's case (a source diff
outside guard paths) so #657's analysis-only rule cannot remove it unnoticed.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Where does the rule live? A: In `dispatch.step_zero`, the one function that decides when
  step zero runs. It gains an optional `flags` argument (the item's flag dict). After the light
  and full checks and before the path loop, a true `trust_surface` or `boundary_relevant`
  returns `(True, <flag names>)`. Only the gate brief passes flags.
- Q: Which flags? A: `trust_surface` and `boundary_relevant`, as the issue says. Not
  `agent_surface`: it already has its own security step (the scanner on the reviewed worktree,
  `dispatch.py:661`) and the issue does not name it.
- Q: What does the reason say? A: The true flag names, comma-joined in the order
  `trust_surface, boundary_relevant`: `Depth: standard; step zero: run (trust_surface)`. A flag
  wins over a matching guard path: the flag is the lead's judgement, the path only a
  heuristic.
- Q: At full depth? A: Unchanged, `Depth: full; step zero: run`: full always runs it, so the
  flag adds nothing to say.
- Q: At light depth? A: Unchanged, `LIGHT_GATE`. A flagged item is never light: `dispatch.tier`
  raises it to standard and `pace.adjust` refuses to lighten it, so WUWEI cannot record a light
  gate depth for a flagged item. No branch is added for a state the code cannot reach.
- Q: Do `dispatch.tier` and `pace._guard` pass the flags too? A: No. They call `step_zero`
  only to compute the pace's `guard` argument, and a guard makes every non-steady pace raise
  the tier to full (`pace.adjust`, `pace.py:30-31`). Passing flags there would move flagged
  items to full under fast and careful pace, a tier change this issue does not ask for. Both
  already hand the flags to `pace.adjust` separately as `flagged`.
- Q: Does "the diff heuristic only adds, never removes" need code? A: No. With the flag check
  ahead of the path loop, no path can turn a flagged run into a skip, and a guard path still
  adds step zero to an unflagged standard item as today.

## User Scenarios and Testing

### User Story 1 - A flagged item runs gate step zero whatever its diff (Priority: P1)

The lead flags an item `trust_surface` or `boundary_relevant`. Its diff touches no guard code
and no trust path. Every gate brief tells the sentinel to run step zero and names the flag, so
the trust-sensitive change gets the mutation sweep.

**Independent Test**: a gate brief for a flagged standard item with a non-guard diff carries
`Depth: standard; step zero: run (<flag>)`.

**Acceptance Scenarios**:

1. **Given** an item with `trust_surface: true`, recorded tier standard, and a diff of
   `cli/wuwei/mask.py` (outside guard code and trust paths), **When** the security gate brief
   is written, **Then** its `Depth:` line is `Depth: standard; step zero: run (trust_surface)`.
2. **Given** the same item with `boundary_relevant: true` instead, **Then** the line is
   `Depth: standard; step zero: run (boundary_relevant)`.
3. **Given** both flags true and a diff touching `cli/wuwei/guards/x.py`, **Then** the line is
   `Depth: standard; step zero: run (trust_surface, boundary_relevant)`.
4. **Given** only `agent_surface: true` and a non-guard diff, **Then** step zero is skipped as
   today.
5. **Given** an unflagged item, **Then** every existing `Depth:` line is unchanged (guard path
   runs, plain path skips, full runs, light keeps `LIGHT_GATE`).

### User Story 2 - A flagged item gets the security reviewer at the first round (Priority: P1)

**Independent Test**: `dispatch.tier` for a flagged item with a small non-guard source diff
records roles `arch, quality, security`.

**Acceptance Scenarios**:

1. **Given** `trust_surface: true`, floor light and a 4-line diff of `cli/wuwei/mask.py`,
   **When** the gate tier is computed, **Then** the tier is standard, `security` is in the
   recorded roles and the reasons name `lead flag trust_surface`.

### Edge Cases

- A flagged item at full depth: `Depth: full; step zero: run`, unchanged.
- The builder brief: unchanged (`depth_line` for the builder never asks about step zero).
- `flags` absent or `None`: `step_zero` treats it as no flag set.

## Requirements

### Functional Requirements

- **FR-001**: `dispatch.step_zero` MUST return `(True, <names>)` at standard depth when the
  given flags have `trust_surface` or `boundary_relevant` true, whatever the paths, naming each
  true flag in that order, comma-joined.
- **FR-002**: The gate brief MUST pass the item's flags to the step-zero decision, so its
  `Depth:` line reads `step zero: run (<flag>)` for a flagged standard item.
- **FR-003**: With no such flag true, `step_zero` and every `Depth:` line MUST behave exactly
  as on main; `dispatch.tier` and `pace` MUST NOT change.
- **FR-004**: A flagged item with a non-guard source diff MUST get `security` in its initial
  gate roles (pinned by a test; no code change expected).
- **FR-005**: The rule MUST be recorded as invariant I43 in design 9.2 and
  `tests/test_invariants.py` (constitution, Workflow: a changed gate rule adds its invariant),
  and the step-zero row of the design 5.3 table, `docs/site/concepts.md` and
  `docs/site/daily.md` MUST name the flags.

## Success Criteria

- **SC-001**: The issue's acceptance case produces `Depth: standard; step zero: run
  (trust_surface)` in the security gate brief and `security` in the tier roles.
- **SC-002**: The full suite passes with no existing assertion changed.

## Assumptions

- No orchestrator notes or dry-run workspace exist for #663; the failure was reproduced on main
  with the brief test fixture, and the root cause is read from the code cited above.
- `agent_surface` does not force step zero (the issue names only the other two; it has its own
  scanner step). Overturned if the owner names it.
- A flag forces step zero at standard only; light is unreachable for a flagged item and full
  always runs. A future change that lets a flagged item be light owns the rule for that case.
- The tier and the pace keep ignoring flags for the step-zero guard: making flagged items full
  under fast or careful pace is a tier policy change, not this issue.
- #657 (generated and data lines; analysis-only diffs without security) may land in parallel.
  Its scope already keeps security for a `trust_surface` item, and the US2 test here pins it.

## Deferred

- None.
