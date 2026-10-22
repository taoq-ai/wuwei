# Tasks: the runtime budget is 3,600 lines and the agents have word headroom

## Phase 1: Test first

- [x] T001 Size test at 3600; headroom test per agent; threshold test reads the new delta phrase
- [x] T002 Red: main padded to 3,500 fails the size test; sentinel-arch fails the headroom test

## Phase 2: Change

- [x] T003 Trim charters/_common.md with no rule lost; reorder the delta sentence
- [x] T004 Run `bin/wuwei agents build` and `setup.vendor('.')`
- [x] T005 Constitution VI 3,600, version 3.3.0 amended 2026-10-22
- [x] T006 AGENTS.md, CONTRIBUTING.md, SECURITY.md, design.md, philosophy.md: 3,600

## Phase 3: Checks

- [x] T007 Green: the head passes at 3,500 and fails at 3,601 naming 3600
- [x] T008 Every agent at or under 2,150 words
- [x] T009 Full suite green
