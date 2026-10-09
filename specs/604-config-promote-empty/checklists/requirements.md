# Requirements Checklist: 604-config-promote-empty

**Purpose**: check the spec is complete, testable and inside the program rules before
implement.
**Created**: 2026-10-09
**Feature**: `specs/604-config-promote-empty/spec.md`

## Completeness

- [x] CHK001 Each item acceptance scenario maps to a user story scenario (US1.1, US2.1 and
  US2.2, US3.1 and US3.2) and to a test task.
- [x] CHK002 Both root causes are named with file and line and were reproduced.
- [x] CHK003 The skip rule applies only to `config promote` without `--keys`; `setup` and
  `--keys` apply as today.
- [x] CHK004 The exact output lines are specified: the `Skipped` line, the
  `Not in today's answers` line, the three Next line forms, `No config.toml changes`.
- [x] CHK005 Out-of-scope items (#599, #600, deploy.deny patterns) and the profile import
  gap are recorded under Deferred or Assumptions.

## Clarity and testability

- [x] CHK006 "Owner set it later" has one definition: the key is present in `config.toml`
  and the setting would change it.
- [x] CHK007 An absent key, a key already equal, and a deploy list are each covered by a
  scenario or edge case.
- [x] CHK008 `--keys` behaviour is stated without implementation detail: what it applies,
  what it skips (survey, snapshot), its exit when nothing changes.

## Program rules

- [x] CHK009 #530: no new refusal under observe or guarded; a skipped key is listed, not
  refused.
- [x] CHK010 #551: every next step is an exact command the CLI prints.
- [x] CHK011 The changed rule has its 9.2 row and its `tests/test_invariants.py` check,
  with a broken-rule case.
- [x] CHK012 No forgeable trust: no new record; the rule reads only `config.toml`.
- [x] CHK013 No absolute local paths, no emojis, no em-dashes in the artifacts; fixtures
  use neutral names.
