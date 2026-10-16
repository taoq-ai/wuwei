# Tasks: a draft PR opens before its gates, and the flip to ready waits for them

## Phase 0: Evidence

- [x] T001 Read #1050 and #1074; restate the promise and acceptance (spec.md)
- [x] T002 Check gh pr create's flags against gh 2.89.0 source and pflag v1.0.6 (82 argument lists)
- [x] T003 Check what gh 2.89.0 sends for `-F draft=...`, `-f draft=...`, duplicates and `--input` plus fields, through a local logging server on a non-door endpoint
- [x] T004 Check the GitHub MCP server v1.14.0 schema: `update_pull_request` (pullNumber, draft, reviewers), `create_pull_request` (draft, reviewers), `request_copilot_review`
- [x] T005 Record main's verdict for 204 commands and MCP payloads (corpus plus draft, ready and reviewer spellings)

## Phase 1: Tests first

- [x] T006 [US1] Draft creates pass with the PR standard note once: gh, gh pr new, REST `-F draft=true` in every flag spelling and any host, `--input` JSON (tests/test_guards.py)
- [x] T007 [US1] Creates that are not drafts stay held and name `gh pr create --draft`: missing, false, bad values, eaten by a value flag, reviewers, positionals, clusters, `-f draft=true`, typed strings and numbers, nested `--input` draft (tests/test_guards.py)
- [x] T008 [US1] MCP create with draft true passes; false, absent, a string or with reviewers is held (tests/test_guards.py)
- [x] T009 [US2] `gh pr ready`, the CCR ready route, `gh pr edit --add-reviewer` and REST `requested_reviewers` on draft PR 7 are held naming the missing gate, then pass once it passes (tests/test_guards.py)
- [x] T010 [US2] `--undo`, reads, DELETE and a PR that is not a draft pass (tests/test_guards.py)
- [x] T011 [US2] No number or an unreadable PR keeps the ready door shut (tests/test_guards.py)
- [x] T012 [US2] MCP update with draft false or reviewers and `request_copilot_review` meet the ready door; in `guards.DOORS` (tests/test_guards.py)
- [x] T013 [US2] GraphQL `markPullRequestReadyForReview` and `requestReviews` refused with the routes to use (tests/test_guards.py)
- [x] T014 [US2] The new MCP tools and `gh pr ready` fail closed when the guard raises; hook.py holds no ready suffix (tests/test_hook.py)
- [x] T015 Run red: 86 failed, 461 passed before the change; the final tests against main's guards.py: 97 failed, 471 passed

## Phase 2: Implementation

- [x] T016 [US1] `_draft`, the draft flag from `_api`, the draft pass in `gh_command` and `pre_tool`, the create refusal text (cli/wuwei/guards.py)
- [x] T017 [US2] `ready_door`, the `ready` API row, `gh pr ready` and `--add-reviewer`, `DOORS['ready']`, the MCP branch, the two mutations (cli/wuwei/guards.py)
- [x] T018 Charters `_way.md`, `builder.md`, `shepherd.md`, `planner.md`, `_gate.md`; `bin/wuwei agents build`
- [x] T019 Docs: docs/design.md, docs/site/concepts/doors.md, docs/site/concepts/evidence.md, skills/wuwei/SKILL.md, skills/wuwei-watch/SKILL.md
- [x] T020 Corpus: 15 routes with sources; six sources re-cited where the charter lines changed (tests/fixtures/routes.json)
- [x] T021 Re-vendor `.claude/` with `setup.vendor('.')`
- [x] T022 Full suite green; runtime at 2,999 lines
- [x] T023 Main-versus-head over 204 commands and payloads: 21 drafts now pass, 23 ready or reviewer routes on draft PR 7 now held, 2 new mutations refused, 42 refusals with new text only; no other verdict moved
