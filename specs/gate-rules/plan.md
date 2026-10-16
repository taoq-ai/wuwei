# Implementation Plan: gate-rules

**Branch**: `claude/gate-rules` | **Spec**: `specs/gate-rules/spec.md`

## Summary

Seven charter rules and four wording sites, `agents/` rebuilt and `.claude/` re-vendored.

## Technical Context

Charters in `charters/` are the one source for `agents/`; sentinels are built from `_common.md`,
`_gate.md` and the role charter. Runtime edits are in-place string changes in `verdict.py` and
`hook.py`.

## Constitution Check

- I. Stdlib only: no new import.
- III. An auditor: no door or guard logic changes; strings only.
- V. Test first: three tests ran red before the edits.
- VI. Budgets: runtime stays at 2,986 lines.

## Design

- `_common.md` Evidence 4: one sentence on the main worktree.
- `_gate.md` rule 3: the main worktree sentence and the mutant re-run; rule 4: the stub rule; The
  verdict: Write tool, never heredoc; the template PR line.
- `sentinel-security.md` rule 6, `builder.md` AUTH, `lead.md` Scope 3, `planner.md` The day 3.
- `verdict.py` FORMAT and PR error; `hook.py` Stop line; `reference.md` template PR line.
