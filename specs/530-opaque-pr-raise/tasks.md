# Tasks: Opaque commands warn, and a branch push, a PR raise and a local merge are never owner-only

Test first: each test task is written, run and seen failing for the expected reason before
its implementation task. Fixtures are neutral (`example/project`, item `9` or `DIV-1`, branch
`div-1`, reviewer `alice`); no real `git` or `gh`.

## Phase 1: local merge (US4)

- [X] T001 Test in `tests/test_deploy.py`: change the `('git merge topic', 2, 'branch')` row
  to `0`; add `git merge origin/main` and `git -C <worktree> merge main` rows expecting 0.
- [X] T002 Implement in `cli/wuwei/guards/deploy.py` (`git`): delete the `merge` branch
  (`:133-135`).
- [X] T003 Test in `tests/test_commit_push.py` (moved: the parser_warns fixture has no configured
  repository, so a merge there is refused as unconfigured; the item worktree fixture is used): through the hook, `git merge main` in a
  configured item worktree exits 0 under observe, guarded and strict, and a following
  `git push origin main` is still refused (deploy or commit_push in the refusals).

## Phase 2: opaque calls warn below strict (US1)

- [X] T004 Test in `tests/test_shell.py`: `shell.unreadable` returns `script loop.sh` for
  `bash loop.sh` and `./loop.sh`, `command substitution is unsupported` for `gh pr view
  $(git rev-parse --abbrev-ref HEAD)`, `inline interpreter code` for `python3 -c 'print(1)'`,
  for `python3 -c "print(['gh','pr','view'])"` and for a here-doc fed `python3 -
  <<'EOF'`, `python3 code from input` for `cat x | python3`, and `''` for `gh pr view 7`,
  `git status` and `npm test`.
- [X] T005 Implement `unreadable(command, cwd=None)` in `cli/wuwei/shell.py`.
- [X] T006 Test in `tests/test_deploy.py`: `deploy.floor_named` is true for text naming
  `git push origin main`, `git push origin HEAD:refs/heads/master`, `git push -f origin x`,
  `git push --force-with-lease origin x`, `git push origin +x`, `git push --no-verify origin
  x`, `git push origin v1.2.3`, `git push origin refs/tags/a`, a configured default branch,
  an `environments` match (`release/next` for `release/*`), `kubectl apply`, a `deploy.deny`
  program, `gh release create`, `gh pr merge 7`, `gh api repos/o/r/pulls/7/merge`, `gh pr
  review 7 --approve`, `gh api repos/o/r/pulls/7/reviews -f event=APPROVE`, `gh pr merge 7
  --admin`, `gh api repos/o/r/branches/main/protection`, `gh alias set`, `gh workflow run
  build.yml`, `gh pr comment 7 --body x`, `gh pr create`, `git config core.hooksPath x`;
  false for `gh api repos/o/r/pulls/7/comments`, `gh pr view 7 --json
  mergeable,reviewRequests`, `gh pr checks 7`, `gh run list`, `git push origin
  HEAD:refs/heads/div-1`, `git merge main`.
- [X] T007 Implement `GH_FLOOR` and `floor_named(text, config)` in
  `cli/wuwei/guards/deploy.py`.
- [X] T008 Test in `tests/test_parser_warns.py` (US1.1, US1.2): with a script `loop.sh`
  running `gh api repos/o/r/pulls/7/comments`, for `bash loop.sh`, `gh pr view $(git
  rev-parse --abbrev-ref HEAD)` and `python3 -c "import subprocess;
  print(subprocess.run(['gh','pr','view','7']).stdout)"`: under observe and guarded the hook
  exits 0 and `guard.would_refuse` holds exactly one event, reason starting `opaque:` and
  naming `loop.sh`, `substitution` or `python3`, area `publish`, level `warn`; under strict
  the hook exits 2 with today's reason and no `guard.would_refuse`.
- [X] T009 Test in `tests/test_parser_warns.py` (US1.3, US1.4): a script running `git push
  origin main`, a script running `kubectl apply -f x`, a script running `gh release create
  v1`, a script running `gh pr review 7 --approve`, `python3 -c "import subprocess;
  subprocess.run(['gh','pr','comment','7','--body','x'])"`, `python3 -c "import os;
  os.system('git push --force origin x')"`, and the existing
  `test_publish_forms_still_refuse` rows that name `main` or `gh pr merge` are refused in
  every posture; `test_state_writes_still_refuse` stays green. Move `for f in a b; do git
  push origin $f; done` and `for f in a b; do git commit -m $f; done` to a new parametrized
  test asserting a warning below strict and a refusal under strict; update
  `test_issue_470_commit_substitution` so guarded warns.
- [X] T010 Test in `tests/test_posture.py`: with stub guards, a `deploy` exit 2 on an opaque
  command (`bash loop.sh`) and a `pr` exit 2 on the same call give one event under guarded;
  an exception inside the opaque computation (monkeypatch `shell.unreadable` to raise)
  enforces the refusal; a `protect_state` exit 2 on an opaque call still blocks.
- [X] T011 Implement in `cli/wuwei/commands/hook.py` (`posture`): keep `config`, add the
  `opaque_reason()` closure and the `elif` branch after the `UNPARSED` branch.

## Phase 3: PR create is levelled as publish (US2.7, FR-004)

- [X] T012 Test in `tests/test_posture.py`: with a stub `pr` guard, a refusal starting with
  `guards.RAISE` warns under observe and blocks under guarded and strict with `posture:
  publish = block (set security.areas.publish)`; `NO_REVIEWER` warns under observe and blocks
  without a posture line under guarded; a stub `pr` merge-policy refusal still blocks under
  observe with the owner-only line; a `publish:` reason from a stub `commit_push` has no
  posture line.
- [X] T013 Implement `RAISE` in `cli/wuwei/guards/__init__.py` and the two levelling edits in
  `cli/wuwei/commands/hook.py` (`posture`).

## Phase 4: the evidence card (US2.3 to US2.6, FR-005, FR-006)

- [X] T014 Test in `tests/test_grants.py`: `grants.evidence` under observe returns `(1,
  reason)`; with `record=True` it appends one `guard.would_refuse` (guard `pr`, level `warn`)
  and returns `(0, None)`; under strict `(1, reason)` and no card; under guarded it writes a
  card whose options are `keep` (`Defer until the check passes`), `once`, `today` (no `always`),
  whose context names the check, and the reason starts `publish:`, names the check and the
  card, and does not contain `host terminal`; answered `once` it returns `(0, use)` and
  `use()` spends it; answered `today` it passes until close; answered `keep` it refuses
  naming the check; an `evidence` grant on `repo:example/project` does not let a `deploy`,
  `release` or `deploy.deny` publish on the same repository through.
- [X] T015 Implement in `cli/wuwei/grants.py`: `ACTIONS['evidence']`, `action()`, the
  `evidence` branches in `gate()`, and `evidence()`.
- [X] T016 Test in `tests/test_commit_push.py`: `fast_evidence` returns the old reason;
  `check()` with no fast-check record under guarded returns 1 with a `publish:` card reason
  naming `bin/wuwei build check`; under observe returns `(1, 'fast check ...')`; under strict
  the same `(1, reason)`; with an answered `once` grant it returns 0 and the grant is spent
  only once the whole call passes.
- [X] T017 Implement in `cli/wuwei/guards/commit_push.py`: extract `fast_evidence`, call it and
  `grants.evidence` in `check()`, collect and call `use`.
- [X] T018 Test in `tests/test_git_hook.py`: the pre-push hook with no fast-check evidence
  exits 0 with a `warning:` line under observe and guarded and exits 1 under strict; a push
  to the default branch exits 1 in every posture (unchanged).
- [X] T019 Implement in `cli/wuwei/commands/git_hook.py` (`run`): `fast_evidence` after
  `push_check`, refused only under strict.
- [X] T020 Test in `tests/test_shepherd.py`: `raise_pr` with a gate miss under observe
  creates the PR, prints the warning and records one `guard.would_refuse`; under guarded it
  creates no PR, exits 1 and writes a card; after `once` it creates the PR and spends the
  grant; under strict it exits 1 with today's reason and no card. Update
  `test_raise_refuses_failed_gate_without_creating` for the card reason.
- [X] T021 Implement in `cli/wuwei/shepherd.py` (`raise_pr`): `grants.evidence(...,
  record=True)` on a gate miss, `use()` after `state.record_pr`.

## Phase 5: PR create from any directory (US3, #534)

- [X] T022 Test in `tests/test_pr_guards.py` (fixture gains an item `DIV-1` with a recorded
  worktree under `worktrees/DIV-1` and the fake's `branch` result `div-1`): from the workspace
  root, `gh pr create -R example/project --head div-1 -r alice` returns 0 and reads `head` in
  the worktree; `cd <worktree> && gh pr create -r alice` returns 0; `--head other` returns 1
  `head other is not a recorded item branch of example/project`; `-R other/project --head
  div-1` returns 1 naming `other/project`; `--head div-1` alone and `-R example/project`
  alone return 2 naming both options; `cd <unrecorded dir> && gh pr create -r alice` keeps
  today's exit 2; with the security gate verdict removed, the guarded reason names `div-1`
  and the missing gate and no directory. Update the two old `--head`/`-R` rows. Every create
  refusal that is not a card starts with `pr raise:`.
- [X] T023 Implement in `cli/wuwei/guards/pr.py`: `_recorded`, the `cd` rewrite in `check()`,
  `payload` and `use` plumbing, `RAISE` prefixing in `action()`, the new `create_check`
  target and evidence path.
- [X] T024 Test in `tests/test_commit_push.py` (US3.5, US3.6): from the workspace root,
  `cd <recorded worktree> && git push origin HEAD:refs/heads/div-1` and `git -C <recorded
  worktree> push origin HEAD:refs/heads/div-1` with fast-check evidence return 0; `cd
  <unrecorded dir> && git push origin HEAD:refs/heads/x` returns today's nonzero result. If
  green on first run, no code change; if red, fix in `cli/wuwei/guards/commit_push.py` with
  the smallest change and note it here. Green on first run; no code change. The unrecorded row is not pinned: the vcs
  fake answers every path alike, so it cannot show the real unconfigured-repository refusal.
- [X] T025 Test in `tests/test_shepherd.py`: `pr raise` run with the workspace root as cwd
  and with an unrelated cwd inside the workspace raises the PR for the recorded worktree
  (pins today's behaviour).

## Phase 6: guide, producers and docs (US5)

- [X] T026 Test in `tests/test_guide.py`: the guide has a line naming `wuwei pr state` and
  `wuwei pr ping-check` and the words `reviewer list`; line count stays under 97.
- [X] T027 Implement the line in `cli/wuwei/guide.py`; regenerate the block in
  `docs/site/agent.md` from `wuwei guide` (keeps `test_agent_guide_ships_and_is_linked`
  green).
- [X] T028 Update producer descriptions in `cli/wuwei/commands/event.py` and
  `cli/wuwei/state.py`; run the state allowlist and event tests.
- [X] T029 Docs: `docs/specs/2026-09-24-wuwei-design.md` 4.1, 4.5 and 9.1 amendments,
  `docs/site/security.md:57` and `docs/site/reference.md:370`, as the plan states; run
  `tests/test_docs.py`.

## Phase 7: verification

- [X] T030 Run the full suite (`python -m pytest -q`); grep the changed files for em-dashes,
  emojis and absolute local paths.
- [X] T031 Review fixes: a chained PR create keeps the owner-only refusal (F1); `floor_named`
  strips shell quoting before matching (F2); stale expectations and reason wording updated
  so the full suite is green (F3).
- [ ] T032 Follow-up, out of scope: `bash s.sh` where `s.sh` writes into `.wuwei/` passes
  below strict (predates #530, F5).
