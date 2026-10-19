# Implementation Plan: semver-policy

**Branch**: `docs/semver-policy` | **Spec**: `specs/semver-policy/spec.md`

## Summary

One docs section declares WUWEI's public API and the SemVer classification; two charter rules and
four docs point to it. `agents/` rebuilt and `.claude/` re-vendored. No runtime change.

## Technical Context

Charters in `charters/` are the one source for `agents/`. Every sentinel is built from
`_common.md`, `_gate.md` and its role charter, so a word added to `_common.md` lands in
`agents/sentinel-arch.md`, which sits at the 2,250-word ceiling on main.

## Constitution Check

- I. Stdlib only: no runtime change.
- III. An auditor: the evidence rules (`Announcement:`, `breaking:`) are unchanged; only what
  counts as a break is defined.
- V. Test first: the new charter test ran red before the edits.
- VI. Budgets: AGENT_WORDS stays 2,250; the arch agent drops from 2,250 to 2,248 words and stays
  there after fix round 1.

## Design

- `docs/site/concepts/evidence.md` Breaking changes: the definition, the public API list, the
  base-commit read, the strict SemVer bump table, the documented-API condition for a patch, the
  exit-code meaning sentence, the history sentence, then the existing detection and evidence text.
- `charters/sentinel-arch.md` rule 7: 79 words for 65; 15 words cut from its preamble and last
  paragraph so the agent stays at 2,248.
- `charters/builder.md` rule 6: `!` and `BREAKING CHANGE:` for a major only; a stricter check of a
  documented rule is a `fix:`, a new capability a `feat:`.
- `charters/_common.md` Done: "a breaking change (a SemVer major)", one word fewer.
- `docs/design.md`, `docs/site/reference.md`, `docs/site/concepts/decisions.md`: link to the section.
