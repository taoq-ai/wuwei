# Feature Specification: Worktree command, watch install safety and operator docs

**Feature Branch**: `210-worktree-watch-docs`
**Created**: 2026-09-30
**Status**: Draft
**Input**: GitHub issue #210, "feat(team): worktree command, watch install safety and operator docs". Evidence: the v0.5.0 operator dry run of 2026-09-30, rows 11, 17, 20, 40, 41 and 42.

## Root causes (reproduced read-only in the dry-run workspace)

- **Row 11, unguarded item worktree.** `workspace.create_worktree` (`cli/wuwei/workspace.py:415`) creates the worktree through the vcs port and installs the pre-push anchor (`commands/git_hook.install`), but no CLI command calls it. The operator therefore ran `git -C repos/demo worktree add -b divide-1 worktrees/DIVIDE-1 main`. In the dry-run workspace that worktree's Git directory has no `wuwei-workspace` anchor, `core.hooksPath` is unset and `.wuwei/git-hooks/` does not exist. The native pre-push guard never runs, so a push made outside the Claude Bash hook (a terminal, a script) is unguarded unless `WUWEI_WORKSPACE` happens to be set.
- **Row 40, failed install blocks retry.** `commands/watch.py:72` writes the unit file before loading it (`:74` launchd, `:76-77` systemd). When the load fails, the unit stays, and the retry refuses at `:52-53` with "watch already installed; run watch uninstall first".
- **Row 41, uninstall cannot clean up.** `commands/watch.py:44` and `:46` stop the service and raise before `path.unlink()` at `:47`. A unit whose service never loaded cannot be removed, so install and uninstall deadlock (dry run: install exit 2, retry exit 2, uninstall exit 2).
- **Row 42, dead watch hidden.** `commands/status.attention` (`cli/wuwei/commands/status.py:58-77`) learns about a dead watch only from the latest `watch: sweep` event. (a) `obligations.sweep` (`cli/wuwei/obligations.py:256`) writes a `watch: sweep` event without `watch_dead`, which clears the full sweep's watch page (`status.py:59`) and leaves one generic `watch: sweep` nudge (`status.py:75-77`). (b) A watch that dies after its last sweep writes no further sweep, so nothing records the death. In the dry run SessionStart (`guards/lifecycle.py:34`, live `watch.health`) said "watch dead: no clock line within deadline" while `status --line` showed `pages 0` and `wuwei nudges` had no watch entry.
- **Rows 17 and 20, brief input.** The legal phase order (`state.PHASES`, `cli/wuwei/state.py:26-37`) appears only in a refusal (`planned -> gate: legal next phases: ...`). The verdict finding layout accepted by `verdict.finding_blocks` (`cli/wuwei/verdict.py:56`) is undocumented; the quality seat's first verdict was rejected with "no finding with severity" and its retro said "Gap: verdict finding layout undocumented". `wuwei brief` reads the body from stdin (`commands/brief.py:30`) and takes a charter name as its role (`brief arch ...` failed with "unknown charter: arch"); neither is documented.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Anchored item worktree (Priority: P1)

After the morning gate the planner creates each item's worktree with `wuwei worktree add <item>`. The worktree carries the pre-push anchor, so every push from it runs the push guard regardless of the caller's environment.

**Independent Test**: In a temporary workspace with one configured Git repository and gate approval, run `wuwei worktree add X`, commit in the worktree, then run `git push` from the worktree with `WUWEI_WORKSPACE` removed from the environment. The managed pre-push hook runs the recorded executable with the workspace selected.

**Acceptance Scenarios**:

1. **Given** `wuwei worktree add X`, **when** a push runs from that worktree without `WUWEI_WORKSPACE` in the environment, **then** the push is guarded (the pre-push shim runs `<executable> git-hook pre-push` with `WUWEI_WORKSPACE` set to the workspace from the anchor, and a refusing guard stops the push).
2. **Given** an approved gate and one configured repository, **when** `wuwei worktree add X` runs, **then** it exits 0, creates `worktrees/X` in the workspace on branch `x`, and prints JSON with `branch` and `path`.
3. **Given** no morning gate approval, **when** `wuwei worktree add X` runs, **then** it exits 1 with the gate reason and the vcs port is not called.
4. **Given** two configured repositories and no `--repo`, **when** `wuwei worktree add X` runs, **then** it exits 2 naming `--repo`; with `--repo <name>` it uses that repository; an unknown name exits 2.

### User Story 2 - Safe watch install and uninstall (Priority: P1)

The owner can preview the watch service, and a failed install never leaves a unit behind that blocks the next attempt.

**Independent Test**: Patch the watch service adapter to fail on load, run `watch install`, check no unit file remains, then install again with a working adapter.

**Acceptance Scenarios**:

1. **Given** a failed `watch install`, **when** the owner retries, **then** the retry works and no unit file remains from the failed attempt.
2. **Given** `watch install --dry-run`, **then** it prints the unit path, the rendered unit and the service commands it would run, exits 0, writes no file and calls no service command.
3. **Given** an installed unit whose stop command fails, **when** `watch uninstall` runs, **then** it removes the unit, prints the stop failure as a warning on stderr and exits 0.
4. **Given** no installed unit, **when** `watch uninstall` runs, **then** it exits 0.

### User Story 3 - Dead watch is visible (Priority: P2)

A dead watch shows in the status line and in `wuwei nudges` from live clock health, not only from the last recorded sweep.

**Independent Test**: With a clock line today older than `watch.dead_seconds`, `status --line` contains `watch dead` and `wuwei nudges` lists a page with source `watch: health`; after a fresh clock event both clear.

**Acceptance Scenarios**:

1. **Given** today's latest clock line older than `watch.dead_seconds`, **then** `wuwei nudges` includes one page with source `watch: health` and the health reason, and `status --line` shows `watch dead` and counts that page.
2. **Given** a later partial `sweep obligations` event, **then** the dead watch is still shown.
3. **Given** a fresh clock line, **then** no watch entry appears even if an earlier sweep recorded `watch_dead: 1`.
4. **Given** unreadable clock health, **then** a `watch: health` nudge carries the unmeasured reason and the status line shows `watch unmeasured`.

### User Story 4 - Operator reference (Priority: P3)

`docs/site/reference.md` lets an operator write a brief, a verdict and phase transitions without reading source.

**Acceptance Scenarios**:

1. The page shows an example gate verdict that passes `verdict.lint` with quality and class-sweep rules, and lists the finding rules (severity, file:line, blocks yes/no, failure scenario).
2. The page lists every active phase with its legal next phases exactly as in `state.PHASES`.
3. The page documents `wuwei brief <charter> <item> <name>` with the body on stdin, charter names versus gate role names, and the `--worktree`, `--gate`, `--track`, `--pr` options.
4. The page and the plan skill document `wuwei worktree add <item> [--repo <name>]` as the only way to create item worktrees.

### Edge Cases

- The target path `worktrees/<item>` already exists or the branch exists: the vcs port fails and the command exits 2 with its reason.
- An item ID that is not a plain identifier (`brief.identifier`) exits 2 before any vcs call.
- Hook installation fails after the worktree is created: the command exits 2 with the reason (existing `create_worktree` behaviour, unchanged).
- On Linux, `enable --now` fails after `daemon-reload`: the installer runs the same best-effort teardown as uninstall, removes the unit and exits 2 with the original reason.
- `watch install --dry-run` with a unit already present exits 2 with "already installed", like the real install.
- The watch is expected when `watch install` has installed its unit for the workspace (the unit file at the path install and uninstall share exists). Expected with no fresh clock line (none today, or today's older than `watch.dead_seconds`) is dead, including the morning after an overnight death; it clears at a fresh clock line or after `watch uninstall`. Not expected with no clock line today is `watch off`, neither a page nor a nudge. Not expected with a stale clock line today is dead. The same rule applies to the status line, `wuwei nudges`, sweeps and SessionStart.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `wuwei worktree add <item> [--repo <name>]` MUST call the existing `workspace.create_worktree` with the configured repository path, branch `item.lower()` (the naming `brief.prior_branch_pattern` already matches), path `<workspace>/worktrees/<item>` and the configured vcs adapter, and print the port result as JSON.
- **FR-002**: A missing gate approval MUST exit 1; other failures MUST exit 2 with the reason.
- **FR-003**: `--repo` MUST be optional with exactly one configured repository and required otherwise.
- **FR-004**: `wuwei watch install --dry-run` MUST print the unit path, rendered unit and service commands and MUST NOT write files or call the service adapter.
- **FR-005**: A failed service load during install MUST remove the unit (best-effort teardown) and exit 2 with the load failure.
- **FR-006**: `wuwei watch uninstall` MUST remove an existing unit and exit 0 even when a service command fails, printing each failure as a warning on stderr.
- **FR-007**: `status.attention` MUST add live watch health from `watch.health`: a page for dead, a nudge for unmeasured, source `watch: health`, replacing any sweep-recorded watch row. `status --line` MUST show `watch off`, `watch dead` or `watch unmeasured`; `status --json` MUST carry `watch` as `alive`, `off`, `dead` or `unmeasured`. An installed unit with no fresh clock line is `dead`; no installed unit and no clock line today is `off` and adds no row.
- **FR-008**: `docs/site/reference.md` MUST document the verdict layout, phase order, brief body input and worktree command; `docs/site/configuration.md` MUST document the dry run, failure cleanup, idempotent uninstall and the dead watch surfaces; `skills/wuwei-plan/SKILL.md` MUST use `wuwei worktree add`.
- **FR-009**: Documentation tests MUST lint the documented example verdict and compare the documented phase table with `state.PHASES`.

### Key Entities

- **Anchor**: `<git dir>/wuwei-workspace` plus per-worktree `core.hooksPath` to `.wuwei/git-hooks`, written only by `git_hook.install`. Unchanged.
- **`watch: health` attention row**: `{"tier": "page"|"nudge", "source": "watch: health", "lane": "Work", "reason": <health message>}`. Derived live, never stored.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A push from a worktree made by `wuwei worktree add` runs the pre-push guard with the environment cleared of `WUWEI_WORKSPACE` (one end-to-end Git test).
- **SC-002**: After a failed install zero unit files remain, and the next install exits 0.
- **SC-003**: `watch uninstall` exits 0 in 100% of tested states (absent unit, failing stop, working stop).
- **SC-004**: With a stale clock, the status line and `wuwei nudges` both show the dead watch, including after a partial obligations sweep.
- **SC-005**: The documented verdict example passes lint and the documented phase table equals `state.PHASES`.

## Assumptions

- Branch naming reuses the existing configuration: the item ID lowercased, which `brief.prior_branch_pattern = "*{item}*"` (lowercased item) already matches. No new configuration key.
- The worktree path is fixed at `<workspace>/worktrees/<item>`, as in the dry run. No configuration key; add one only when an operator needs another layout.
- The new branch starts from the configured repository's checked-out HEAD, which is how the existing `vcs.worktree_add(repo, branch, path)` port works. Choosing a base ref would change the port contract and recordings; the brief already reports the merge-base against the remote default branch.
- `worktree add` does not record the worktree in day state; `wuwei brief ... --worktree` remains the producer of the item's `worktree` field.
- `watch uninstall` succeeds even when the stop command fails, as the issue states. The warning names the failure so the owner can stop a still-loaded job by hand; the unit file is removed so it is not reloaded at the next login.
- Live watch health is the authority for the watch row in attention; a sweep's `watch_dead` count no longer produces its own row. A workspace with no clock line today reports `watch off` unless its watch unit is installed, in which case it is dead.
- Existing tests that expect an empty attention list or exact page counts gain a fresh `watch: clock` event in their fixtures; the existing uninstall-failure assertion (exit 2, unit kept) is replaced by the new behaviour.

## Deferred

- A partial `sweep obligations` event still clears full-sweep stale, scanner and integrity rows in `status.attention` (`status.py:58-77`). Only the watch row is fixed here, by live health; the other rows belong to a separate issue.
- Row 11 guidance in `charters/planner.md` and generated agent files is not changed; the plan skill carries the instruction.
