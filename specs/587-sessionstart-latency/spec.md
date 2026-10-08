# Feature Specification: SessionStart under 75 ms wall on the runner

**Feature Branch**: `587-sessionstart-latency`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #587: SessionStart in a workspace under 75 ms wall on the runner with
the 20 ms margin the latency job requires, so the job is green on main; no budget, margin,
test or job changed.

Standing rule (#346, #562, owner, 2026-10-08): reduce the latency, never loosen a budget, a
margin, a test or the job. The #562 margin rule (20 ms of wall margin) caught this miss and
stays exactly as it is.

## Root cause

Run 37809011046 measured SessionStart in a workspace at 96.7 ms wall p95 against 100, so
the margin report says `margin short: SessionStart in a workspace 3.3 ms`. #562 planned a
SessionStart profiling round (its T001 and T012) and did not run it; the only SessionStart
cut it made was the shared day state and events read. Profiled on this worktree with the
latency fixture (`seeded_workspace`, 60-pair interleaved runs, host load 9 to 19 on 10 CPUs,
the CPU-starved shape the 2-CPU runner has):

- The integrity guard is most of the cost. Run alone it costs about 63 ms CPU above the
  bare hook (81 against 18 ms); the session guard alone about 11 ms (29 against 18 ms).
  The integrity guard (`cli/wuwei/guards/integrity.py:18-28`) runs `integrity.check`
  (`cli/wuwei/integrity.py:236-258`: an "incomplete" verdict record, the hash of every
  installed file at `:94-115`, the `ssh-keygen` verify at `:139-145`, the final verdict
  record) next to `integrity.workspace_check` (`:375-381`: `git status` and `git log` in
  `.wuwei`, `adapters/vcs/git.py:848-866`). That measurement is the security floor of
  design 7.1 and stays whole.
- Imports the session block does not need to print:
  - `cli/wuwei/memory.py:119-120` imports `wuwei.digest` (`latest`) and `wuwei.promotion`
    (`last_run`), two small readers. `cli/wuwei/digest.py:3` imports `calendar` (and
    `locale`) at module level; `cli/wuwei/promotion.py:6-7` imports `shutil` (with `bz2`,
    `lzma`, `zlib`, `fnmatch`) and `uuid` at module level. None of the readers uses them.
  - `adapters/integrity/ssh.py:5-6` imports `shutil` and `tempfile` (with `random`,
    `weakref`, `bisect`) for one `shutil.which` call (`:36`) and one
    `tempfile.TemporaryDirectory` (`:44`) that holds a one-line allowed-signers file.
  - `cli/wuwei/commands/next.py:8` imports `wuwei.decision` at module level, and
    `cli/wuwei/memory.py:100` imports it on every call; `decision.py:7` brings
    `wuwei.cruise` (the #283 and #558 suspect). Both callers use `answered` only for a day
    with decision routes, and the probe day has none.
  Together these are 21 of the 143 modules the SessionStart process loads; removing them
  measured 6.3 to 6.7 ms CPU median.
- `cli/wuwei/commands/hook.py:84-88` (#346) runs the two SessionStart guards on two threads.
  Their Python work (imports, hashing, the event decode) cannot run at the same time under
  the interpreter lock, so on a host with fewer free CPUs than runnable work the threads only
  take turns. The overlap that matters, child processes against hashing, already lives inside
  the integrity guard (`together` at `guards/integrity.py:26`, `integrity.py:145`,
  `git.py:860`). Running the two guards one after the other measured 5.6 to 6.4 ms CPU
  median less, with wall median 3 ms lower on this host.
- `cli/wuwei/guards/lifecycle.py:62` discards the day state the session registry write
  returns and `:69` reads `state.json` again (the "file read twice" of the issue); `stop()`
  in the same file already reuses that return (`:146`).

Suspects named in the issue that are not on the measured path, checked:

- #551: SessionStart calls `next.step` only (`lifecycle.py:52`), never `_ran`, `resolve` or
  `_record`, so it computes less than `wuwei next`; in the probe day `step` returns the setup
  row at `next.py:160-165` in 0.1 ms.
- #556: `wuwei.novelty` is not imported at SessionStart.
- #283, #558, #521: no status line, cruise level, budget state or restart read runs in
  `session_start`; the only link is the `decision` import above.
- Memory payload: 95 bytes in the probe, so `memory.budget_tokens` is not the cost.

## User Scenarios and Testing

### User Story 1: The latency job is green on main (Priority: P1)

The latency job on main shows SessionStart in a workspace under 75 ms wall p95 on the runner
and the margin report lists no probe.

**Independent Test**: the latency job on the pull request (artifact `latency`, report
against the last green main run); locally the interleaved before and after CPU of the
SessionStart probe path and the module pin in `tests/test_hooks.py`.

**Acceptance Scenarios**:

1. **Given** the latency job on main after the change, **When** it runs, **Then** every
   probe is green and the margin report lists no finding; SessionStart in a workspace p95
   wall is under 75 ms on the runner.
2. **Given** the full suite, **When** it runs, **Then** it is green and the diff changes no
   budget constant (`tests/test_hooks.py` budgets, `scripts/latency_report.py` margins, the
   latency job in `.github/workflows/tests.yml`).
3. **Given** SessionStart in the latency fixture (`seeded_workspace`, no decision routes),
   **When** it runs, **Then** the process loads none of `shutil`, `tempfile`, `bz2`, `lzma`,
   `random`, `uuid`, `calendar`, `wuwei.decision`, `wuwei.cruise`, `wuwei.novelty`.

### User Story 2: The session block and every guard result are unchanged (Priority: P1)

**Independent Test**: the existing SessionStart, memory, next, promotion, digest and
integrity tests, plus the new ones below.

**Acceptance Scenarios**:

1. **Given** the latency fixture, **When** SessionStart runs before and after the change,
   **Then** `additionalContext` is identical, line for line.
2. **Given** a day with an open decision route, **When** SessionStart runs, **Then** the
   constraints block still lists it under "Open decisions" and the orientation still names
   the decision row.
3. **Given** the ssh adapter, **When** `verify` runs with a good signature, a wrong
   signature, a missing manifest or signature, `ssh-keygen` absent (also with a missing
   manifest), a timeout, or a multi-line pinned key, **Then** it returns the same exit and
   reason as today, and no allowed-signers file or directory is left behind.
4. **Given** two SessionStart guards in a hook, **When** one raises, **Then** the output
   lists each guard's text in guard order as today.

### Edge Cases

- No `state.json` today: the registry write returns nothing and the session guard reads the
  state as today.
- `ssh-keygen` absent from `PATH`: unmeasured (exit 2) before any file check, as today.
- `TMPDIR` unset: the allowed-signers directory goes under `/tmp`.
- The verify subprocess raises (timeout, missing tool): the private directory and its file
  are removed.
- A guard that waits for another guard to run at the same time (the old barrier test) no
  longer finishes: SessionStart guards are independent reads and none may wait on another.

## Requirements

### Functional Requirements

- **FR-001**: `cli/wuwei/promotion.py` imports `shutil` and `uuid4` inside the functions that
  use them; `cli/wuwei/digest.py` imports `monthrange` inside the function that uses it.
  Every caller keeps its behaviour.
- **FR-002**: `cli/wuwei/commands/next.py` imports `answered` in `step` where the decision
  routes are read; `memory.constraints` imports it only when the day has decision routes.
- **FR-003**: `adapters/integrity/ssh.py` `verify` uses neither `shutil` nor `tempfile`:
  `ssh-keygen` presence is checked on `os.get_exec_path()` before the file checks, and the
  allowed-signers file is written in a private directory (mode 0700, unpredictable name,
  exclusive create, the pattern of `workspace.atomic_write`) and removed in a `finally`.
  Results, reasons and their order are unchanged.
- **FR-004**: `lifecycle.session_start` uses the day state the session registry write
  returns and reads `state.json` only when that write returned nothing.
- **FR-005**: `hook.run` runs the SessionStart guards one after the other in guard order;
  the integrity guard keeps its own overlap of child processes and hashing. The change is
  kept only when the interleaved local measure (plan, Method) shows a lower CPU median and
  no higher wall p95 on top of FR-001 to FR-004; otherwise it is reverted with its test and
  the pull request says why.
- **FR-006**: a test pins the module set of FR-001 to FR-003 on the SessionStart probe path.
- **FR-007**: no budget, margin, probe, run count, fixture or job setting changes;
  `docs/site/reference.md#where-hook-time-goes` says what a day without decision routes
  reads. (Build: FR-005 was reverted, so the guards still run together and the docs keep
  saying so.)
- **FR-008**: the pull request body carries the before and after figures: the latency job
  artifacts (runner, wall) and the local interleaved CPU figures (this host under load).

## Success Criteria

- **SC-001**: on the runner, SessionStart in a workspace p95 wall under 75 ms and every
  probe at least 20 ms (wall) or 10 ms (CPU) under its budget, read from the latency job of
  the pull request and of main.
- **SC-002**: locally, 60 interleaved pairs of the SessionStart probe path against the
  unchanged worktree on two plugin copies: above-floor CPU median at least 8 percent lower
  and wall p95 not higher (measured while writing this spec: 9 to 13 percent lower).
- **SC-003**: the full suite is green and `git diff` touches no budget or margin constant.

## Assumptions

- The runner cannot be run from here. SC-002 is the local gate; SC-001 is read from the
  latency job artifact on the pull request. If the job still shows SessionStart at or above
  75 ms, the builder reports the figure and stops: the rest of the cost is the integrity
  measurement (hash of every installed file, `ssh-keygen`, two Git reads, four record
  syncs), a security floor, and the next step is a design reconsideration with the owner
  (constitution, cycle budget), never a looser budget, margin, test or job.
- FR-005 was built, measured and reverted under its keep rule. Ten interleaved rounds of
  the SessionStart probe (60 runs each) on three plugin copies (base, FR-001 to FR-004, plus
  FR-005), load 12 on 10 CPUs: above-floor CPU p95 median 101.8, 88.4 and 86.8 ms; wall p95
  median 121.4, 94.7 and 107.0 ms. FR-005 cut CPU within the noise and raised wall, so the
  #346 overlap and its barrier test stay. The runner's two CPUs may favour it; that needs a
  runner measurement, not a local one.
- The local measure ran the probe test itself in the three copies, interleaved per round,
  instead of the scratch 60-pair harness of plan step 2: same fixture, same output checks,
  and the figures are the ones the job's probe reports. FR-001 to FR-004 cut the above-floor
  CPU p95 median by 13 percent (SC-002).
- The verdict records and the session registry write keep their syncs: they are records,
  and fewer syncs would trade durability of a security record for wall time.
- No guard, refusal, posture or decision rule changes (#530), and no planner action changes
  (#551), so the design 9.2 invariant table and `tests/test_invariants.py` do not change.
- The local wall figure is not trusted on this shared host; CPU and the interleaved pairs
  are (orchestrator note).
- The test-isolation hotfix for `test_latency_budget_decision` ships separately
  (hotfix-latency-compare) and is not duplicated here.
