# Tasks: a multi-line command that names a door program is refused

## Phase 1: Tests first

- [x] T001 [US1] Multi-line commands naming each door program are refused with the hint (tests/test_guards.py)
- [x] T002 [US2] One-line unreadable commands naming a door program are refused (tests/test_guards.py)
- [x] T003 [US3] Ordinary multi-line work and one-line `git push origin feature`, `gh pr view 5` pass (tests/test_guards.py)
- [x] T004 [US3] The leak door reads a later line and a continued line (tests/test_guards.py)
- [x] T005 [US3] Infra on a later line asks the owner (tests/test_guards.py)
- [x] T006 `segments` splits at an unquoted newline, keeps a quoted one, returns None when unreadable (tests/test_guards.py)
- [x] T007 PostToolUse with an unreadable command records no hook error (tests/test_hook.py)
- [x] T008 Run the new tests red

## Phase 2: Implementation

- [x] T009 Newline splitting and None on unreadable in `segments` (cli/wuwei/guards.py)
- [x] T010 The raw-text door rule in `bash` (cli/wuwei/guards.py)
- [x] T011 `_unwrap` and `hook.post_tool` read None as no segments (cli/wuwei/guards.py, cli/wuwei/hook.py)
- [x] T012 Free lines until the runtime is at 3,000 (cli/wuwei/guards.py, cli/wuwei/hook.py)
- [x] T013 Run the full suite green

## Phase 3: Docs and checks

- [x] T014 docs/design.md section 7 names the rule
- [x] T015 Mutants of each new condition, run in a scratch copy, each fail a test

## Phase 4: Fix round 1 (security FIX at 82680c3)

- [x] T016 A quoted word holding only newlines stays one word for curl, wget and kubectl (tests/test_guards.py)
- [x] T017 An even backslash run before a newline ends the command; an odd run continues it (tests/test_guards.py)
- [x] T018 `wuwei` must be followed by `hook`; a multi-line command naming cli/wuwei/hook.py passes (tests/test_guards.py)
- [x] T019 Word boundaries pinned for git, push and gh pr (tests/test_guards.py)
- [x] T020 Run the new tests red, then split newlines with one quote-aware regex and tighten the wuwei pair (cli/wuwei/guards.py)
- [x] T021 Module docstring names the door rule for unreadable commands (cli/wuwei/guards.py)

## Phase 5: Fix round 2 (security FIX at 802ced3)

- [x] T022 A whole-word quoted `".../wuwei" hook` or `wuwei 'hook'` is refused when multi-line (tests/test_guards.py, cli/wuwei/guards.py)
