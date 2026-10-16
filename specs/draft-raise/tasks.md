# Tasks: a draft PR opens before its gates, and the flip to ready waits for them

## Phase 0: Evidence

- [x] T001 Read #1050 and #1074; restate the promise and acceptance (spec.md)
- [x] T002 Check gh pr create's flags against gh 2.89.0 source and pflag v1.0.6 (96 argument lists after the fix round)
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

## Phase 3: Fix round at 8774129 (quality and security FIX)

- [x] T024 Tests first: PR and repository read past flag values and from `--repo=`, `-R<value>` (ready and merge doors); `--input` behind `cd` or `cp` held; `//` and `%5F` endpoints; `-dr=bob`, `-drbob`, `-dx`; `--input` draft `"false"` and `1` (the final tests against 8774129's guards.py: 34 failed, 586 passed)
- [x] T025 One pflag reader `_flags` for `_repo_number`, `_draft` and `gh api`; `--input` draft only when gh runs alone; endpoint decoded and slashes collapsed (cli/wuwei/guards.py)
- [x] T026 evidence.md row, shepherd cloud reviewer route, SECURITY.md line; agents rebuilt; re-vendored; 12 corpus routes with sources
- [x] T023 Main (034d067) versus head over 274 commands and payloads, at the fix round at 02be6b9: 26 drafts now pass; 44 ready or reviewer routes now held (draft PR 7, and a fullwidth-digit PR that names no number); 5 merge spellings (`//`, `%6D`, `.`, `5x`, `5%D9%A3`) now meet the merge door; 4 newly refused (2 GraphQL mutations, a `.` spelling of a `contents/` write, a write through `..`); `gh pr merge ７` now gets the merge door's no-number refusal instead of a check of PR 7; 2 GraphQL merge refusals reworded; of the refusals that keep their door, 51 change wording only and 4 merge refusals now name the PR or repository gh reads (`--repo=x/y 5`, `-Rx/y 5`, `-t 3 5`, a URL with `-R`); no other verdict moved

## Phase 4: Fix round at 76a738a (arch, quality and security FIX)

- [x] T027 Tests first: `.` segments on the ready, reviewer and merge routes; a write through `..` refused; `--input` behind `env -C`, `env --chdir=`, `sudo -D`, an earlier segment, `~`, `$HOME` or a glob held; the last `-R` and the URL's repository for ready and merge; an `--input` draft of `"true"`, `"false"`, `1` or null held; `--draft=yes -d` held (the final tests against 76a738a's guards.py: 19 failed, 645 passed)
- [x] T028 Endpoint segments: empty and `.` dropped after decoding, a `dots` route refuses writes through `..`; an `--input` draft needs gh as the first word of a one-segment command with no `~`, `$` or glob (cli/wuwei/guards.py)
- [x] T029 SECURITY.md, spec Breaking and Clarifications; 12 corpus routes; agents rebuilt; re-vendored; 12 mutants on the new and contested clauses all killed; runtime 3,000

## Phase 5: Fix round at f1ca82b (security FIX)

- [x] T030 Tests first: `--input={,sub/}d.json`, ``--input `printf sub/d.json` ``, `--input "$(echo d.json)"`, a substitution elsewhere and a redirect held, `--input=d.json` and `--input sub/d.json` pass; `pulls/7abc`, `%207`, `7%20`, `7.0` on the ready and reviewer routes and `5x`, `%205`, `5.0` on the merge routes meet their doors (the final tests against f1ca82b's guards.py: 13 failed, 671 passed)
- [x] T031 An allowlist of plain words (`[\w./=@:-]+`) replaces the `~ $ * ? [` denylist; the PR segment of the ready, reviewer and merge routes is read from its leading digits; in place, runtime 3,000 (cli/wuwei/guards.py)
- [x] T032 SECURITY.md, spec Breaking and Clarifications, 4 corpus routes, re-vendored; mutants: allowlist, gh-first and the four PR-segment mutants killed; the one-segment check survives as equivalent (the allowlist already rejects `&&`, `;` and `|` words) and stays as instructed

## Phase 6: Fix round at 02be6b9 (security FIX)

- [x] T033 Tests first: `pulls/7%D9%A3/requested_reviewers`, `pulls/7%EF%BC%97/...` and `pulls/5%D9%A3/merge` read PR 7 or 5 (with ready PRs 73, 77 and 53 in the fixture); `gh pr ready ５`, `gh pr edit ５ --add-reviewer bob`, `gh pr merge ７`, a URL ending in `７` and an MCP pullNumber `"５"` give no PR number (the final tests against 02be6b9's guards.py: 10 failed, 684 passed)
- [x] T034 `[0-9]` in the ready, reviewer and merge routes and the PR URL; `isascii() and isdigit()` for gh pr and MCP numbers; in place, runtime 3,000 (cli/wuwei/guards.py)
- [x] T035 Merged origin/main 034d067 (#1101): the skill lines follow the rename to skills/wuwei-rules/SKILL.md; agents rebuilt, re-vendored; 2 corpus routes
