# Implementation Plan: the runtime budget is 3,600 lines and the agents have word headroom

**Branch**: `leone/free-lines-7` | **Spec**: `specs/free-lines-7/spec.md`

## Technical Context

Docs, one charter, the generated agents and two tests. Runtime 3,390 lines
(`cat cli/wuwei/*.py | wc -l`); it does not change. `_common.md` is 903 words; sentinel-arch is
2,250 words, so `_common.md` must lose at least 100.

## Constitution Check

- V. Test first: the size test fails on a padded copy of main at 3,500 (red); the head passes at
  3,500 and fails at 3,601. The headroom test fails on sentinel-arch at main (red).
- VI. Budgets: this item sets the runtime budget. Runtime lines: 0.
- Governance: the amendment is a commit to the constitution with a dated line in its message.

## Design

- tests/test_setup.py: 3400 to 3600 in the assertion and its message.
- tests/test_charters.py: a headroom test per agent; the threshold test reads the new delta phrase.
- charters/_common.md: shorter wording, every rule kept, the delta sentence reordered.
- `bin/wuwei agents build`, then `setup.vendor('.')` for the `.claude/` copy.
- Constitution VI and version line; AGENTS.md, CONTRIBUTING.md, SECURITY.md, design.md,
  philosophy.md: 3,600.
