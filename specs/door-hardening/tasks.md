# Tasks: the fail-closed check reads the doors from one table, through quotes, and covers the leak check

## Phase 1: Tests first

- [x] T001 [US1] Quoted door words and a curl call refused with guards.bash raising (tests/test_hook.py)
- [x] T002 [US1] MCP send, MCP read and network Bash calls join the fail-closed list; Read, Glob and `git clone https://...` stay open (tests/test_hook.py)
- [x] T003 [US1] hook.door reads guards.DOORS and hook.py holds no MCP suffix (tests/test_hook.py)
- [x] T004 [US1] A malformed apply_patch is refused, recorded, and does not raise (tests/test_codex.py)
- [x] T005 [US2] `env FOO=1 git push origin main` refused (tests/test_guards.py)
- [x] T006 Run the new tests red: 11 failed, 267 passed

## Phase 2: Implementation

- [x] T007 [US1] guards.DOORS and pre_tool reading it (cli/wuwei/guards.py)
- [x] T008 [US2] `_unwrap` NAME=value rule (reverted in the fix round)
- [x] T009 [US1] codex() inside handle's try; door() reads DOORS, strips quotes, counts network and MCP (cli/wuwei/hook.py)
- [x] T010 SECURITY.md paragraph on what a failing guard refuses
- [x] T011 Re-vendor .claude/ with setup.vendor('.')
- [x] T012 Run the full suite green and check the runtime size

## Phase 3: Fix round (security FIX at 9910e11)

- [x] T013 [US2] Pin nine wrapper assignment shapes as refused or asked; drop the env /opt/a=b/git test (tests/test_guards.py)
- [x] T014 [US1] A raising hook-seen stamp lets the guards decide (tests/test_hook.py)
- [x] T015 Run them red on 9910e11 merged with main: 10 failed, 267 passed
- [x] T016 Restore main's `_unwrap` rule; stamp in its own try; auto-merge by name
- [x] T017 docs/design.md and SECURITY.md name the fail-closed set the code reads
- [x] T018 Merge origin/main (#1091), re-vendor, full suite, route corpus from origin/claude/route-fixtures
