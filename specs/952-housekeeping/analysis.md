# Cross-artifact Analysis

Spec, assumptions, plan, tasks and quality checklist updated before implementing
this owner-requested design reconsideration. The owner design spec is unchanged.
Coverage: FR-001 -> T003/T004/T006/T010; FR-002/003 -> T003/T004/T011/T012;
FR-004/005 -> T005/T011/T012; FR-006 -> T006/T011; FR-007 -> T007/T008/T013.

## Root causes and resolutions
- H1: watch.background delegated arbitrary WUWEI argv while protect_state checked
  only the outer next argv. The guard now unwraps; runtime accepts only exact PR
  wait and integer sleep commands. Forged PostToolUse input is refused.
- H2: watch.housekeeping included active trees as orphan roots without excluding
  ancestors. Both are now excluded from orphan findings.
- H3: host.processes let one cwd error abort the snapshot; next.step raised on
  unmeasured results. Errors now belong to individual PIDs and remain findings.
- M1: snapshot PR sets disagreed with pr_actions.wait's dynamic workspace polling.
  All live waits now share one key; new records contain no snapshot.
- M2: resolve wrapped one-shot set entries that could become terminal mid-write.
  Only waits/timers are wrapped or eligible for automatic cleanup.
- M3: failed KILL checks produced the same duty forever. A cleanup_failed receipt
  now makes that identity one finding without another automatic duty.
- M4: every check and every signal reread cwd for the whole user process table.
  Cwd probes now run only on explicit inspection; signals check ps -p. Process
  history is filtered before JSON decoding; ps always runs with LC_ALL=C.
- L1/L2: signalled zombies are reported as signalled, and identities use C locale.
- L3: duplicate lifecycle prior-seat reporting was deleted.
- L4: next rejects unexpected positional arguments again.
- L5: seat stop --day and all WUWEI_NOW overrides were removed.
- L6: external cleanup is a plain listing with commands, never an approval card.
- Ponytail: native git exec, prior-day Codex-only recovery rows, PR snapshots and
  the prior-day seat command extension were removed. Current recovery paths remain.

No open CRITICAL or HIGH findings after the fixes and focused executable checks.
The owner explicitly authorized the narrower design in the review follow-up.

## Verification
Initial follow-up regressions: `30 failed, 29 passed in 0.72s`.
Duplicate lifecycle regression: `1 failed, 59 deselected in 0.18s`.
Focused integration: `653 passed in 31.33s`.
The prescribed interpreter, explicit file arguments and disabled cacheprovider were
used. Fake OS tables, signals and adapter boundaries prevent real process cleanup
and network calls. The impacted-file run includes hooks and signal status.
Production diff baseline (cli and adapters): +379/-13, 392 changed lines, net +366.
Current production diff: +354/-27, 381 changed lines, net +327.
Final message and housekeeping checks: `76 passed in 2.74s`.
Final impacted run, 88 explicit files: `6949 passed in 330.53s (0:05:30)`.
This includes every test importing a changed module plus tests/test_hooks.py and
tests/test_signal_status.py. One wording failure in the initial broad run was
corrected before rerunning the entire selection. All final checks passed.
Production changes are 11 fewer changed lines and 39 fewer net added lines.
Git diff whitespace checks pass; the owner design spec is unchanged. All tasks are
complete, with no outstanding review findings. Changes remain uncommitted.

## Round 2 pre-implementation analysis
FR-008 -> T015/T016: H1 resolved in planned shared scan output consumed by next.
FR-009 -> T015/T016: M1 resolved by explicit inspection scope.
FR-010 -> T015/T016: L1/L2 resolved by runtime-only validation and flag simplification.
FR-011 -> T015/T016: L3/L4 resolved by pure formatting and optional-check skip.
FR-012 -> T015/T016: L5 resolved by workspace containment and per-day identity receipts.
No CRITICAL/HIGH specification gaps remain. H1 runtime fix awaits implementation and tests.
Earlier verification above belongs to round 1 and is not evidence for round 2.

## Round 2 implementation and focused evidence
- H1 fixed: next consumes live PR wait identities from housekeeping and returns a passive status row. The four-round field reproduction never offers or kills another wait while the original lives; it offers a new wait after that process exits.
- M1 fixed: historical seats and finished worktrees are only listed by doctor processes and close. Neither ordinary next, explicit next housekeeping, nor SessionStart prints them or fails because of them.
- L1 fixed: deleted the guard unwrap entirely. The exact runtime allowlist refuses forged PostToolUse payloads through the real CLI, including abbreviated background flags, without workspace file changes.
- L2 fixed: background is a flag; purpose is derived from argv. New process records omit the constant item, while old item-bound timer records remain readable.
- L3 fixed: orientation and resolved next rows share pure wrapper formatting, without resolving seats or writing state from SessionStart.
- L4 fixed: host none skips optional fast inspection before loading/calling the adapter. Explicit inspection and reaping still report unmeasured.
- L5 fixed: orphan cwd must resolve inside the workspace, including symlink resolution. General workspace orphan listings share daily identity receipts across doctor and close; worktree orphans retain explicit inspection. Receipts are silent signal events and confer no signal authority.

Initial regression run: `19 failed, 48 passed in 19.32s`. This included fixture setup failures that were corrected before implementation.
Corrected orientation/noise regressions: `4 failed, 63 deselected in 1.21s`.
Explicit housekeeping scope regression: `1 failed, 66 deselected in 0.20s`.
Silent receipt regression: `1 failed, 96 deselected in 2.50s`.
Final housekeeping: `67 passed in 0.79s`.
Final housekeeping/hooks/signal status: `454 passed in 28.20s`.
The broader intermediate run exposed the obsolete historical-seat assertion and missing receipt classification. Both were corrected for the next 73-file selection. A subsequent receipt-key refinement is covered by the final focused run and a separate 17-file run of every watch importer plus lifecycle callers.

Daily receipt identity regression: `1 failed, 66 deselected in 32.07s`.
A process title can change without a new process start. Receipts therefore key only
on PID and OS start identity, avoiding both repeated listings and unnecessary
persistent command text. Exact command checks remain mandatory before signals.
Final focused run after that refinement: `454 passed in 27.66s`.

Intermediate 73-file result: `3 failed, 6024 passed in 603.26s (0:10:03)`.
The third failure was the doctor header contract: default doctor intentionally omits
Processes after M1, while explicit doctor processes still prints it. The test now
expects the default sections only. This was a test expectation correction, with no
additional production change.

The concurrent intermediate selections had collected the old doctor header
assertion before it was corrected: `1 failed, 6026 passed in 623.47s (0:10:23)`
and `1 failed, 2239 passed in 76.68s (0:01:16)`. The corrected doctor case passed:
`1 passed, 105 deselected in 2.11s`. The final 73-file run starts after all code
and test corrections and supersedes these intermediate results.

## Round 2 final verification
Final 73 explicit impacted files, including every test importing a changed runtime
module plus hooks and signal status: `6027 passed in 495.47s (0:08:15)`.
The prescribed interpreter and `-p no:cacheprovider` were used. No bare suite was run.
Final production diff against HEAD: 10 files, +371/-27, 398 changed lines, net +344.
The incoming production diff was +354/-27, so round 2 adds 17 net runtime lines.
No new runtime module or dependency was introduced. The partial protect_state change
is entirely removed from the working diff. All H1, M1 and L1-L5 findings are fixed.
Whitespace and added-content checks pass. The owner design spec is unchanged, the
branch remains 952-housekeeping, and all changes are uncommitted. No work remains.

## Round 3 pre-implementation analysis
- H1 / FR-013 -> T019/T020: close conflates optional inspection exit 2 with current cleanup failure. Separate the current reap failure on its finding and gate close on actionable blockers only.
- M1 / FR-014 -> T019/T020: workspace-wide oldest-wait selection ignores notification recipient and day. Record both and classify out-of-scope waits as obsolete before duplicate selection.
- L1 / FR-015 -> T019/T020: background exempts argv before housekeeping wins dispatch. Include housekeeping in the refusal condition.
No CRITICAL/HIGH specification gaps remain. The owner explicitly authorized the optional-inspection exception and additional fix round; runtime fixes await red/green checks. Earlier verification is evidence for earlier rounds only.

## Round 3 focused verification
Initial regression run: `9 failed, 1 passed, 181 deselected in 0.31s`.
Failures reproduced all three findings before production changes, including host none,
ps/lsof failures, both wait scopes, missing metadata and historical reap failures.
Focused housekeeping and all close files: `201 passed in 1.11s`.
The final impacted selection includes static imports, literal dynamic imports and
monkeypatch targets for every changed runtime module, all changed tests, hooks,
all close files and signal status. Final selection results follow below.

## Round 3 final verification
- H1 fixed: close prints unmeasured host-none, ps and lsof findings and reaches the steward and closing.check. Current reap failures still stop close; historical failure receipts do not.
- M1 fixed: background records include session_id and day. Other-session and prior-day waits are obsolete before live-wait/duplicate selection. Only matching recorded process identities authorize cleanup; the current session's live wait survives.
- L1 fixed: combined background/housekeeping flags reject positional argv before any process inspection, event write or cleanup.

Final impacted run, 75 explicit files: `5458 passed in 234.58s (0:03:54)`.
This includes every test importing a changed runtime module or the changed host fake,
all changed test files, hooks, all close test files and signal status. The prescribed
interpreter and `-p no:cacheprovider` were used from the worktree root.
Documentation verification after the wording update: `9 passed in 0.59s`.
The earlier focused result was `201 passed in 1.11s`.

Delta review: no open findings. Session/day classification occurs only after the
existing PID/command/start-identity checks. The failed-reap flag is transient and
adds no persistent schema. Runtime changes remain in the three existing modules;
no dependencies, new subsystem or design-spec edits were introduced.
Whitespace and authored path/style checks pass. All round 3 tasks are complete.
Changes remain in the working tree, uncommitted.
