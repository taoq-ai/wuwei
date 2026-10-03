# Feature Specification: the next-step test also collects `x or 'literal'` fallbacks, and the fallbacks it then finds get a next step

**Feature Branch**: `456-reasons-or-fallbacks`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #456, "fix(reasons): the next-step test also collects `x or 'literal'`
fallbacks, and the two branch-protection fallbacks get a next step". A follow-up from the
resolution review of #362 (merged to main as d911002, #455).

## Root cause (read and reproduced on main, d911002)

`tests/test_reasons.py::test_every_reason_names_a_next_step` is the ratchet #362 added: it
collects every reason string at a reason site (`raise X(<arg>)`, `print(<arg>,
file=sys.stderr)`, `Result(1|2, ..., <reason>)`, guard `return 1|2, <text>`) and fails on any
that names no next step. The text of a site comes from `_text` (`tests/test_reasons.py:30-55`),
which understands a string constant, an f-string, a `+` concatenation and an `IfExp`, and
returns `[]` for anything else. A fallback `result.reason or 'literal'` is an `ast.BoolOp`
with `op=Or`, so `_text` returns `[]` and the literal is never checked.

Reproduced read-only with a scratch script outside the repository that wraps `_text` with
one extra branch (`BoolOp(Or)`: take the text of the last operand) and reruns the wall list
over `cli/wuwei`: 0 walls before, 19 after:

```
brief.py:91: adapter read unavailable
commands/build.py:335: fast check could not run
commands/config.py:265: {}: unreadable protection result
commands/config.py:302: {}: unreadable scopes
commands/doctor.py:547: dry run exit {}
commands/doctor.py:582: nothing to confirm
commands/doctor.py:598: nothing to promote
commands/runtime.py:52: runtime operation did not complete
consolidation.py:108: could not commit archived days
control_plane.py:120: control plane: poll failed
control_plane.py:137: control plane: echo failed
inbox.py:56: inbox: redactor returned malformed data
integrity.py:275: plugin integrity unmeasured
obligations.py:21: code-host read unavailable
registry.py:120: VCS operation unavailable
scanner.py:151: scanner unavailable
shepherd.py:168: branch protection unmeasured
shepherd.py:178: branch protection unmeasured
steward.py:230: steward runtime could not launch
```

The two shepherd lines are `cli/wuwei/shepherd.py:168` and `:178` in `ping_gate` (the issue
says 166 and 176; #455 moved them by two lines). Each reaches the seat as the whole reason
when the code host adapter fails without a reason of its own. The suite is green today
(`tests/test_reasons.py`: 16 passed), so the gap is invisible.

## User Scenarios & Testing

### User Story 1 - The collector sees `or` fallbacks (Priority: P1)

A reason written as `<expression> or 'literal'` (or `or f'...literal tail'`) inside a
collected call shape is checked like a literal written directly in that call.

**Why this priority**: without it any fallback can reach a seat as a bare wall and the
ratchet stays green.

**Independent Test**: `python -m pytest -q tests/test_reasons.py -k or_fallback`.

**Acceptance Scenarios**:

1. **Given** the source `raise ValueError(result.reason or 'branch protection unmeasured')`,
   **When** the collector runs on it, **Then** it reports exactly the text `branch protection
   unmeasured`.
2. **Given** `print(result.reason or f'{name}: unreadable scopes', file=sys.stderr)`,
   **Then** it reports `{}: unreadable scopes`.
3. **Given** `Result(2, None, a or b or 'poll failed now')`, **Then** it reports `poll
   failed now` (the last operand of the chain).
4. **Given** `raise ValueError(result.reason or f'{exc}')` or `raise
   ValueError(result.reason or f'build: {exc}')`, **Then** it reports nothing: a
   pass-through tail is exempt exactly as it is when written directly.

### User Story 2 - The fallbacks the collector then finds name a next step (Priority: P1)

**Why this priority**: it is the issue's acceptance line.

**Independent Test**: `python -m pytest -q tests/test_reasons.py`.

**Acceptance Scenarios**:

1. **Given** the extended collector and the code on main, **When**
   `test_every_reason_names_a_next_step` runs, **Then** it fails and its message lists
   `shepherd.py:168: branch protection unmeasured` and `shepherd.py:178: branch protection
   unmeasured` (with the other 17 sites above).
2. **Given** the rewritten fallbacks, **Then** the same test passes, both shepherd fallbacks
   read `branch protection unmeasured; retry; if it repeats, run bin/wuwei config check,
   which reads the protection and names the source`, and the full suite is green.
3. **Given** the rewritten seat-facing fallbacks, **Then**
   `test_seat_facing_reasons_have_no_pronoun` passes; **given** the three doctor fallbacks
   (person-facing), **Then** `test_person_facing_text_never_says_the_owner` passes.

### Edge Cases

- An `or` whose last operand is not a string (`a or b`, `x or None`) yields no text, as any
  non-literal does today.
- An `or` inside an `IfExp` branch or a `+` concatenation is handled by the same recursion.
- An `or` fallback outside the collected call shapes (assigned to a variable, then raised or
  returned) is not collected; see Deferred.
- `and` expressions are not collected (no reason site uses one).
- Existing exemptions are unchanged: the `KEEP` allowlist, one-word tokens, `raise
  AttributeError`, family constants, pass-through f-strings.

## Requirements

### Functional Requirements

- **FR-001**: `_text` in `tests/test_reasons.py` returns, for a `BoolOp` with `op=Or`, the
  text of its last operand, unless that operand is a pass-through f-string (`_passthrough`),
  in which case it returns nothing.
- **FR-002**: A new test feeds the collector source strings for US1 scenarios 1 to 4.
- **FR-003**: Each of the 19 fallbacks listed under Root cause keeps its leading text and
  gains a next step after `; ` (the #362 style), in the voice of its reader: seat-facing
  imperative with no "you"/"your"; the three in `commands/doctor.py` person-facing, never
  "the owner". The `inbox.py` one appends the `ADAPTER_DATA` family constant.
- **FR-004**: The two shepherd fallbacks use the issue's text verbatim.
- **FR-005**: The `KEEP` allowlist, `NEXT_STEP`, `PERSON_MODULES` and `PERSON_PARTS` are
  unchanged.

### Key Entities

- **Fallback**: the last operand of an `or` chain at a reason site; the text a reader sees
  when the left operands are empty.

## Success Criteria

- **SC-001**: `tests/test_reasons.py` reports zero walls with the extended collector.
- **SC-002**: No exit code, exception type, call or control flow changes; only string
  literals in `cli/wuwei` and the test file change.
- **SC-003**: The full suite passes.

## Assumptions

- "The fallbacks the test then finds" means all 19 sites under Root cause, not only the two
  shepherd ones: the extended test fails on every one of them, and the suite must be green.
- "F-strings with a literal tail" means an f-string as the `or` operand whose last part is a
  constant; one ending in a formatted value goes through the existing `_passthrough` rule,
  so `x or f'{exc}'` and `x or f'label: {exc}'` stay exempt.
- Only the last operand of an `or` chain is the fallback; earlier operands are values
  (`result.reason`), and a literal before the last operand would make the rest unreachable.
- The change lives in `_text`, not in `add`, so an `or` nested in an `IfExp` or a `+` is
  covered by the same recursion.
- `bin/wuwei config check` reads each repository's branch protection and names its source
  (`cli/wuwei/commands/config.py` `_protection`), so the issue's shepherd text is accurate.
- Next steps for the other 17 sites follow texts already on main (`retry; if it repeats, run
  bin/wuwei doctor`, with `which tests the code host adapter` where doctor does test it). The
  exact strings are in plan.md; the builder may reword one only if it keeps the leading text,
  matches `NEXT_STEP` and keeps its voice.
- No existing test pins any of the 19 fallback texts (checked with grep over `tests/`); tests
  that pass a reason of their own (`test_integrity.py:812`, `test_calibrate.py:322`,
  `test_mcp.py:265`) are unaffected.
- The orchestrator notes name no dry-run workspace; the reproduction ran the collector only,
  which needs no workspace.

## Deferred

- `or` fallbacks that are assigned first and raised or returned later are not reason sites
  for the collector (for example `shepherd.py:438`, `:452`, `obligations.py:322`, `:370`,
  `pr_actions.py:301`, `:323`, `discovery.py:85`, `:202`, `guards/deploy.py:69`,
  `mcp.py:568`, `listen.py:120`, `watch.py:155`). Collecting them needs data flow from the
  assignment to the site; the issue scopes this to "the same call shapes". A follow-up issue
  can widen the collector if a seat is seen hitting one.
