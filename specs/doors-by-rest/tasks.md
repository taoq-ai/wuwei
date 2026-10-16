# Tasks: every code-host route to a door meets that door

## Phase 0: Evidence

- [x] T001 Probe gh 2.89.0 through a logging proxy: method spellings, leading `/`, query, `{owner}/{repo}`, field spellings, `-F k=@file` versus `-f k=@file`, `--input`, full URL, `gh pr new` alias
- [x] T002 Record main's verdict for 138 commands (corpus, door, leak, infra, ledger, hook, every `gh api` route in the runtime, charters and skills)

## Phase 1: Tests first

- [x] T003 [US1] REST create in five spellings equals `gh pr create --head x --base main` (tests/test_guards.py)
- [x] T004 [US1] REST create reads the item from `-F body=@`, `--field=body=@` and `--input`; `-f body=@` stays literal (tests/test_guards.py)
- [x] T005 [US1] `gh pr new` reaches the create door (tests/test_guards.py)
- [x] T006 [US1] Ten REST merge and auto-merge spellings reach the merge door for PR 5 (tests/test_guards.py)
- [x] T007 [US1] Eleven GraphQL mutations refused, naming gh pr merge and create; a mutation in a `-F query=@file` too (tests/test_guards.py)
- [x] T008 [US1] Follow-up and read routes pass: resolveReviewThread, CCR threads and resolve, replies naming a mutation, GET with fields (tests/test_guards.py)
- [x] T009 [US1] REST writes on git/refs, contents and merges and a repository delete refused (tests/test_guards.py)
- [x] T010 [US2] MCP push_files, create_or_update_file and delete_file refused on main, refs/heads/main and no branch, pass on a feature branch; in DOORS (tests/test_guards.py)
- [x] T011 [US2] push_files fails closed when the guard raises; hook.py holds no push suffix (tests/test_hook.py)
- [x] T012 Run red: 41 failed, 584 passed

## Phase 2: Implementation

- [x] T013 [US1] `API` route table, `API_FLAG`, `_api`, `MUTATIONS`, `PUSHED`; shared create path with `gh pr new` (cli/wuwei/guards.py)
- [x] T014 [US2] `DOORS['push']` and the MCP push branch in pre_tool (cli/wuwei/guards.py)
- [x] T015 Shepherd Raise names the REST create route; `bin/wuwei agents build` (charters/shepherd.md, agents/shepherd.md)
- [x] T016 Corpus: 15 routes with sources (tests/fixtures/routes.json)
- [x] T017 SECURITY.md paragraph on the `gh api` reader
- [x] T018 Re-vendor `.claude/` with `setup.vendor('.')`
- [x] T019 Full suite green; runtime at 2,996 lines
- [x] T020 Main-versus-head over 153 commands: 13 deliberate moves, no other change
