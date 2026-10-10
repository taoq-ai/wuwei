# Feature Specification: a scratch analysis.md is an ordinary write for WUWEI, and the builder knows why Claude Code refuses it

**Feature Branch**: `649-spec-guard-path`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #649 (owner report, 2026-10-10, point 12): the Write tool refused a
scratch file named `analysis.md` as a "report file"; the owner read it as a guard false
positive on a file name, and the builder worked around it by renaming the file. Deliver: the
spec-mode guard matches `specs/<dir>/analysis.md` (and the other spec-kit report names) by
path under the item's spec directory only; a file by the same name anywhere else is an
ordinary write.

## Root cause

The refusal does not come from WUWEI. Reproduced on 2026-10-10 from a Claude Code subagent
(WUWEI plugin installed), writing into the session scratchpad, outside every repository:

| Write target (basename) | Result |
|---|---|
| `analysis.md`, `report.md`, `summary.md`, `findings.md` | refused: "Subagents should return findings as text, not write report files." |
| `specs/x/analysis.md` (under a scratch directory) | refused, same text |
| `analysis.txt`, `mutation-analysis.md`, `mutate-notes.md` | written |

So Claude Code's own Write tool refuses a subagent's write of a Markdown file whose basename is
a report name, in any directory. The text appears in no file of this repository and in no
installed plugin. #614 already met the same check on `specs/<dir>/analysis.md` and answered it
with `bin/wuwei spec analysis` (`cli/wuwei/commands/spec.py`).

WUWEI's spec guard already decides by path, never by file name:

- `cli/wuwei/guards/spec.py` `_item` (lines 11 to 30) returns None, so `check_edit` exits 0,
  for a path outside every recorded item worktree.
- Inside an item worktree, `specmode.own` (`cli/wuwei/specmode.py`, `OWN` at line 17) lets any
  path under the engine's own directories (`specs`, `.specify` for spec-kit) through, and every
  other path goes to `specmode.check`, which gates on the spec steps alone.
- `cli/wuwei/specmode.py` lines 28 and 29 are the `analyze` row; its command text names
  `bin/wuwei spec analysis {item}`. That text is a hint in the brief's `Spec:` line and in the
  strict refusal, not a matcher.

Reproduced in process with the `tests/test_spec_mode.py` fixtures (strict, item `A` with a
worktree): a PreToolUse Write or Edit of `<tmp>/scratch/analysis.md` outside the worktree
exits 0 with empty stderr; inside the worktree, before the spec steps, `scratch/analysis.md`
and `scratch/notes.txt` get the same refusal (`needs specify first`); after the steps both
exit 0; `specs/001-a/analysis.md` exits 0 at any time.

The fix is therefore not a guard change. It is a regression test that pins the path-only
decision (so a future name matcher cannot slip in), and a corrected builder instruction: the
charter says only that a subagent cannot write spec-kit's `analysis.md`, so the builder took
the scratch refusal for a WUWEI guard and lost a round finding out.

## Clarifications

### Session 2026-10-10

- Q: Should WUWEI add a PreToolUse refusal for a seat's Write of `<spec dir>/analysis.md` that
  names `bin/wuwei spec analysis`? A: No. Claude Code refuses that write in the tool itself,
  with a tool error, so a hook adds nothing a seat sees; under a harness without that check the
  write is the intended artifact and must pass. The pointer stays where it is: the `analyze`
  command text in the brief's `Spec:` line and in the strict refusal, plus the charter.
- Q: Can WUWEI turn Claude Code's check off for scratch files? A: No. It is inside the Write
  tool, not a hook or a setting WUWEI owns. The seat names scratch files otherwise.
- Q: Which names does the charter list? A: The four the reproduction refused (`analysis.md`,
  `report.md`, `summary.md`, `findings.md`), as examples, with the rule "a Markdown file named
  like a report, in any directory"; Claude Code's exact list is not published.
- Q: Does the item reword `specmode.py` line 29 or the docs that say "a Claude Code subagent
  cannot write analysis.md"? A: The step text stays (it is true and pinned by tests). One
  sentence in `docs/site/configuration.md` says the refusal is Claude Code's, by name, in any
  directory.

## User Scenarios and Testing

### User Story 1 - A scratch file named analysis.md is an ordinary write for WUWEI (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a WUWEI workspace with spec mode strict and an item with a recorded worktree,
   **When** a seat's PreToolUse Write (or Edit) targets `<scratch>/analysis.md` outside every
   item worktree, **Then** the hook exits 0 with no output and records no `spec.*` or
   `hook.refusal` event.
2. **Given** the same item, **When** the Write targets `analysis.md` inside the item worktree
   but outside `specs/` and `.specify/`, **Then** the decision is the one for any other file at
   that place (`notes.txt`): refused while a step before implementation is missing, exit 0 once
   the steps are done. The file name never changes the decision.

### User Story 2 - The spec report write keeps today's refusal and its pointer (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a builder seat under Claude Code, **When** it Writes `specs/<dir>/analysis.md`,
   **Then** Claude Code refuses it as today; WUWEI's hook lets the path through (`specs/` is the
   engine's own directory), and the seat's instructions name `bin/wuwei spec analysis <item>`:
   the brief's `Spec:` line, the strict refusal at the `analyze` step, and the builder charter.
2. **Given** the builder charter, **Then** it says the refusal is Claude Code's, matches a
   Markdown file named like a report in any directory, and is avoided for a scratch file by
   another name (for example `<item>-analysis.md`).

## Requirements

- **FR-001**: No change to `cli/wuwei/guards/spec.py` or to `specmode.own`, `specmode.check`
  and `specmode.STEPS`. The spec guard decides by path only.
- **FR-002**: A regression test in `tests/test_spec_mode.py` pins US1.1, US1.2 and US2.1 (the
  hook exit and output for the paths named there, and that the strict refusal at the `analyze`
  step names `bin/wuwei spec analysis a`).
- **FR-003**: `charters/builder.md` replaces "A subagent cannot write spec-kit's
  `analysis.md`" with the US2.2 wording and keeps the `wuwei spec analysis <item>` instruction;
  its version goes from 1.2.0 to 1.2.1, and `agents/builder.md` is regenerated with
  `bin/wuwei agents build`.
- **FR-004**: `docs/site/configuration.md` (the sentence at line 119) adds that the refusal is
  Claude Code's, by file name, in any directory, and that a scratch file takes another name.

## Success Criteria

- **SC-001**: The new test passes against the unchanged guard (the decision is already
  path-only) and fails if a name-based match is added to the spec guard.
- **SC-002**: `tests/test_agents.py`, `tests/test_charters.py` and `tests/test_docs.py` pass
  with the regenerated agent; the full suite passes.

## Assumptions

- The orchestrator notes file for this issue does not exist; the issue text, the owner's report
  and the reproduction above are the inputs.
- The owner's "guard" is Claude Code's built-in subagent report-file check, not a WUWEI hook.
  The issue's "today's refusal" in its second acceptance line is that Claude Code refusal; the
  "spec analysis command" pointer is the existing step text and the charter.
- The test is a regression pin, so it is green on first run against the unchanged guard. Test
  first is shown by temporarily adding a name match (for example refusing any basename
  `analysis.md`) in `check_edit`, watching the test fail, and removing it; the builder records
  that red run in its handoff.
- A charter wording fix is a patch version bump (design 11, charters carry a version).
- Owner points 10 (one scratch directory per seat) and 11 (one fix item for a shared main
  breakage) are separate issues and out of scope here.

## Deferred

- None.
