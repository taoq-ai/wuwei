# Tasks: the forged-hook door reads a hook call made through Python

## Phase 1: Tests first

- [x] T001 [US1] The readable forge shapes are refused (tests/test_guards.py)
- [x] T002 [US2] Legitimate commands pass (tests/test_guards.py)
- [x] T003 [US3] The real `bin/wuwei hook PreToolUse` entry answers and refuses a forged call (tests/test_guards.py)
- [x] T004 Run the new tests red on main's code (31 failed, 20 passed)

## Phase 2: Implementation

- [x] T005 FORGE, CLI and the rule in `guards.bash`; FORGE joins DOOR_WORDS (cli/wuwei/guards.py)
- [x] T006 The vendored copy (.claude/wuwei/cli/wuwei/guards.py)
- [x] T007 Route corpus rows for the 5 acceptance shapes and 4 pass rows (tests/fixtures/routes.json)
- [x] T008 SECURITY.md open limit; design.md and the doors page

## Phase 3: Checks

- [x] T009 [US4] Generated probe under real bash (specs/forge-door/probe.py) at main and at the head
- [x] T010 Probe holes closed, each red first: filled program and subcommand after `x=hook`, `wuwei.__main__`, a filled path program, xargs with `--`
- [x] T011 A filled word read in linear time; a test holds three 100,000-character words under 5 s
- [x] T012 Route corpus at main and at the head: sha256 of both and every moved route
- [x] T013 The checks that do not rely on door words, at main and at the head
- [x] T014 Mutants on both copies (specs/forge-door/mutants.py)
- [x] T015 Full suite, `bin/wuwei agents check`, runtime count
