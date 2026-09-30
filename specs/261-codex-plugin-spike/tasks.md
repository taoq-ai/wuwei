# Tasks: Codex plugin spike

**Input**: `spec.md`, `plan.md`
**File under check**: `docs/specs/2026-09-30-codex-plugin-spike.md` (written by the spec
author). No pytest test is added (spec Assumptions); each check below is a read-only
command run from the repository root before the document is accepted, and each fails on
the defect it names.

## Phase 1: Acceptance checks (run first; each must pass before T008)

- [X] T001 [US1] Citation check for `docs/specs/2026-09-30-codex-plugin-spike.md`: every
  row of the gap table has a non-empty last (Source) cell whose ids appear in the Sources
  table. Command: `awk -F'|' '/^## Gap table/{t=1} /^## Planner/{t=0} t && /^\| [^-W]/{print $(NF-1)}' docs/specs/2026-09-30-codex-plugin-spike.md`
  prints no blank line, and each id (H, P, SA, R, SK, SEC, CFG, CLI, I1 to I4, AP) it
  prints is defined under `## Sources`.
- [X] T002 [US1] Unverified marker check in the same file: the rows resting on AP or on no
  source (apply_patch grammar, seat launch guard, PreCompact exit 1, plugin `args`,
  execpolicy inside the sandbox, `--resume-last`) carry `**Unverified**` or
  `**unverified**`. Command: `grep -ci 'unverified' docs/specs/2026-09-30-codex-plugin-spike.md`
  returns at least 7.
- [X] T003 [US1] Enforcement-loss check in the same file: the `## Recommendation` section
  names what is lost when a hook cannot block before the tool runs and what still holds.
  Command: `grep -n 'cannot block before the tool runs' docs/specs/2026-09-30-codex-plugin-spike.md`
  finds a line, and the paragraph lists push, merge, deploy, `state.json` and the
  outward-text lint.
- [X] T004 [US1] Scope check: `git status --porcelain` lists only
  `docs/specs/2026-09-30-codex-plugin-spike.md` and `specs/261-codex-plugin-spike/`.
- [X] T005 [P] [US1] Style check on both paths from T004: no em-dash
  (`grep -rnP '\x{2014}'` finds nothing), no emoji, no absolute local path.
- [X] T006 [P] [US1] Budget check: `wc -w docs/specs/2026-09-30-codex-plugin-spike.md`
  is under 1500.
- [X] T007 [US2] Follow-up check in the same file: `## Follow-up issues` lists numbered
  issues, each with a conventional-commit prefix and a size S, M or L.

## Phase 2: Document fixes

- [X] T008 [US1] Fix `docs/specs/2026-09-30-codex-plugin-spike.md` only where T001 to T007
  failed; rerun the failed check until it passes.

## Phase 3: Suite

- [X] T009 Run `python -m pytest -q` from the repository root; it passes with no test
  added or changed (`tests/test_hygiene.py` covers the new tracked files once staged or
  committed by the owner).

## Dependencies

T001 to T007 before T008; T008 before T009. T005 and T006 can run in parallel with the
others.
