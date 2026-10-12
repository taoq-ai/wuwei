# Tasks: parallel Codex seats

- [X] T001 [US1] Test (`tests/test_runtime.py`): two threads dispatch through a fake companion
  whose job shows `threadId` only on the third status poll; the second `task` call comes after
  the first job's thread. A job that fails before a thread releases the lock at once. Run: red.
- [X] T002 [US1] Implement FR-001 in `adapters/runtime/codex.py`; T001 green.
- [X] T003 [US2] Test (`tests/test_runtime.py`): `status` of a failed job returns
  `error` = the companion's `errorMessage`. Test (`tests/test_dispatch.py`): a failed opinion
  job raises with the error text, the seat is `stopped` with `failed`, and the rerun calls
  `dispatch` again; an `unmeasured` seat relaunches too. Run: red.
- [X] T004 [US2] Implement FR-002 and FR-003 (`codex.status`, `build.wait`,
  `dispatch.opinion`); T003 green.
- [X] T005 [US2] Test (`tests/test_build.py`): a Codex builder job that fails exits 2 naming
  the error, leaves the build `ready` with a `build.failed` event, and the rerun dispatches a
  new job. Run: red.
- [X] T006 [US2] Implement FR-004 in `build.run_loop`; T005 green.
- [X] T007 [US3] Test (`tests/test_runtime.py`): the dispatch prompt ends with
  `verdict.retro_contract()`, which names `Blocked:`, `Gap:` and `Change:` from `FORMAT`.
  Run: red.
- [X] T008 [US3] Implement FR-005; T007 green.
- [X] T009 Write `quickstart.md`: the scratch-workspace smoke for the orchestrator.
- [X] T010 Run every test file that imports a changed module, under 3.12 and 3.11.
- [X] T011 [F2] Test: the parallel-start test finds `wuwei-start.lock` in `CODEX_HOME`. Move the
  lock there.
- [X] T012 [F3] Test (`tests/test_dispatch.py`): relaunching an `unmeasured` seat whose old job
  still runs calls `status`, `cancel`, then `dispatch`; a failed old job is not cancelled.
  Test (`tests/test_runtime.py`): `codex.cancel` runs the companion's `cancel <id> --json` in the
  worktree. `tests/test_adapters.py` lists `runtime.cancel`. Run: red.
- [X] T013 [F3] Implement `cancel` in the three runtime adapters and the registry, and the
  check in `opinion`; T012 green.
- [X] T014 [L1] Test (`tests/test_runtime.py`): a `sentinel-quality` dispatch prompt holds
  `verdict.section()`, says the final message is the whole verdict and to write no file
  outside the worktree. Test (`tests/test_dispatch.py`): the second-opinion brief's
  `Verdict file:` line says WUWEI writes the final message there; the lint-rejection
  continuation asks for the verdict as the final message and the file is rewritten from it.
  Run: red.
- [X] T015 [L1] Implement FR-006 (`codex.dispatch`, `brief.write`, `dispatch.opinion`); T014
  green.
- [X] T016 [L2] Test (`tests/test_vcs.py`, `tests/test_adapters.py`): `commit_all` runs `add
  --all` and `commit --quiet -m "chore(A): Codex builder changes"` with the identity as `-c`
  settings; a bad item or identity never spawns git. Test (`tests/test_runtime.py`): the
  builder prompt says WUWEI commits. Test (`tests/test_build.py`): a completed Codex job with
  changes is committed with the repo identity and reaches `gate`; a dirty tree after the build
  parks with `uncommitted changes`; HEAD still at the start head parks with `no new commit`,
  and a job that commits reaches `gate`; an unset identity refuses with the `config set` fix
  and leaves the build `running` (added after T017, green on first run). Run: red.
- [X] T017 [L2] Implement FR-007 and FR-008 (`vcs.commit_all`, registry, `build._commit`,
  `build._unbuilt`, `start` in `next_action` and `open_fix`); T016 green. Existing fakes that
  pass a build get a clean `status` (`test_commit_push.workspace_case`,
  `test_pr_actions.test_fix_round_returns_to_delta_gate`).
- [X] T018 [L3] Quickstart: the broker note in step 7, the verdict and commit expectations in
  steps 8 and 9.
