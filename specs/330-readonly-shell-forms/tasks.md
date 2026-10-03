# Tasks: read-only shell forms are not refused for being uninspectable, and shadow mode records them

**Input**: `specs/330-readonly-shell-forms/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to fail
for the expected reason before its implementation task starts. Run from the repository root
with the interpreter your task names. No absolute local paths, client names, emojis or
em-dashes in any file. Never edit or remove an existing test row; only add rows and tests.
Fixture names stay neutral (`a`, `b`, `repo`, `repo.txt`, `f`).

## Phase 1: issue acceptance through PreToolUse (red)

- [X] T001 [US1] [US2] Test, `tests/test_seat_command_forms.py`: add
  `test_issue_330_read_only_forms_pass` (parametrized over
  `for r in a b; do git -C $r remote get-url origin; done`,
  `git -C "$(cat repo.txt)" log -1 | head -5`,
  `git -C repo symbolic-ref refs/remotes/origin/HEAD`): with the existing `workspace`
  fixture (enforce) and `hook(workspace, command, ...)`, assert exit 0, empty output and
  no `hook.refusal` in any `.wuwei/days/*/events.jsonl`. Add
  `test_issue_330_effectful_forms_refuse` parametrized over mode (`enforce`, `shadow`) and
  over (`for r in a b; do git -C $r push origin main; done`, words `('deploy',)`) and
  (`x=$(cat f); gh pr merge $x`, words `('deploy', 'PR guard')`): for shadow, write
  `[guards]\nmode = "shadow"\n` to `.wuwei/config.toml` first. Assert exit 2 and a deny
  decision in both modes; in shadow mode also assert exactly one `guard.would_refuse`
  event whose payload `guard` is `commit_push`, every listed word in the deny reason and
  `commit/push guard` not in it. Add `test_issue_330_shadow_records_commit_loop`: shadow
  mode, `for r in a b; do git -C $r commit -m wip; done`, assert exit 0, no deny output and
  one `guard.would_refuse` with guard `commit_push`. Run
  `python -m pytest -q tests/test_seat_command_forms.py -k issue_330`: the three
  read-only forms fail (exit 2) and the commit loop fails (deploy and pr refuse it too, so
  exit 2); `test_issue_330_effectful_forms_refuse` already passes (it pins behaviour the
  fix must keep).

## Phase 2: the shared relevance rule (FR-001)

- [X] T002 [US3] Test, `tests/test_shell.py`: add
  `test_command_mentions_ignores_directory_values`, parametrized `text, expected`, asserting
  `mentions(text, {'push', 'commit'}) is expected`. False rows:
  `for r in a b; do git -C $r remote get-url origin; done`, `git -C "$r" status`,
  `git -C$r status`, `gh -R $r issue list`, `gh --repo $r issue list`,
  `gh --repo=$r issue list`, `git --git-dir $d log -1`, `git --work-tree=$w status`,
  `git -C "$(cat repo.txt)" log -1 | head -5`. True rows: `git "$VERB" origin main`,
  `git -C $r $VERB`, `git -C "a b" "$VERB" origin main`,
  `git -c "x.y=a;b" "$VERB" origin main`, `git -c $cfg status`, `git log $ref`,
  `git p* -f origin main`, `sh -c 'git $VERB origin main'`, `git status; sh -c "$CMD"`,
  `for r in */; do git -C $r status; done`. Run
  `python -m pytest -q tests/test_shell.py -k directory_values`: the False rows fail.
- [X] T003 [US1] Implement plan change 1 in `cli/wuwei/shell.py` (`_VALUES` and the
  narrowed rule in `mentions`, with the `ponytail:` comment). Rerun T002; passes. Run
  `python -m pytest -q tests/test_shell.py tests/test_commit_push.py tests/test_deploy.py
  tests/test_pr_guards.py tests/test_protect_state.py`; all green, no existing row edited.

## Phase 3: the deploy guard's read-only git set (FR-002)

- [X] T004 [US1] [US2] Test, `tests/test_deploy.py`: add rows to the `test_decisions` table:
  `('git -C repo symbolic-ref refs/remotes/origin/HEAD', 0, '')`,
  `('git describe --tags', 0, '')`, `('git show-ref', 0, '')`,
  `('git rev-parse HEAD', 0, '')`, `('git config --get remote.origin.url', 0, '')`,
  `('git ls-remote origin', 0, '')`, `('git remote get-url origin', 0, '')`,
  `('for r in a b; do git -C $r remote get-url origin; done', 0, '')`,
  `('git -C "$(cat repo.txt)" log -1 | head -5', 0, '')`,
  `('for r in a b; do git -C $r push origin main; done', 2, 'control flow')`,
  `('x=$(cat f); gh pr merge $x', 2, 'substitution')`. Run
  `python -m pytest -q tests/test_deploy.py -k test_decisions`: the `symbolic-ref`,
  `describe` and `show-ref` rows fail (exit 2, unknown git command).
- [X] T005 [US1] Implement plan change 2 in `cli/wuwei/guards/deploy.py`. Rerun T004;
  passes.

## Phase 4: the PR guard's parse-failure relevance (FR-003)

- [X] T006 [US1] [US2] Test, `tests/test_pr_guards.py`: add rows to
  `test_bypasses_and_relevance`: `('for r in a b; do gh -R $r issue list; done', 0)`,
  `('for r in a b; do gh -R $r pr list; done', 2)`,
  `('for r in a b; do gh api -X POST repos/$r/x; done', 2)`,
  `('for a in x; do gh alias set $a "pr merge"; done', 2)`. Run
  `python -m pytest -q tests/test_pr_guards.py -k bypasses_and_relevance`: the
  `gh issue list` row fails (exit 2).
- [X] T007 [US1] Implement plan change 3 in `cli/wuwei/guards/pr.py`. Rerun T006; passes,
  including the existing `sh push.sh` and `bash push.sh` rows (exit 2).

## Phase 5: acceptance and regression

- [X] T008 [US1] [US2] Rerun T001:
  `python -m pytest -q tests/test_seat_command_forms.py`; all pass.
- [X] T009 [US3] Run `python -m pytest -q tests/test_shell.py tests/test_deploy.py
  tests/test_commit_push.py tests/test_pr_guards.py tests/test_guard_mutation.py
  tests/test_seat_command_forms.py tests/test_shadow.py tests/test_hooks.py`; all pass
  with no existing row changed (`git diff` on these files shows additions only).
## Phase 6: review fixes

- [X] T011 Test, `tests/test_pr_guards.py`: add rows
  `('for i in 1; do gh issue comment 1 --body-file body.txt; done', 2)` and
  `('if true; then gh issue comment 1 -F body.txt; fi', 2)` to
  `test_bypasses_and_relevance`; they fail (exit 0). In `cli/wuwei/guards/pr.py` keep the
  parse failure fatal when the text carries `--body-file` or `-F`, so the outbound body
  scan is never skipped. Rerun; passes.
- [X] T012 Test, `tests/test_shell.py`: add True rows `read v < f; git -C -C $v origin main`,
  `read v < f; git --work-tree -C $v origin main`,
  `read v < f; git --git-dir -C $v origin main` and False row `git -C a -C $r status` to
  `test_command_mentions_ignores_directory_values`; the True rows fail. In
  `cli/wuwei/shell.py` skip a value word only when the flag before it is not itself a
  value. Rerun; passes.

- [X] T010 Run the full suite, `python -m pytest -q`; everything passes. Check every
  changed file for em-dashes, emojis and absolute local paths and remove any.
