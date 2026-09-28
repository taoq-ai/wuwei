# Watch and lifecycle contract

Run `bin/wuwei watch` from the workspace, or set `WUWEI_WORKSPACE` to select it.
`bin/wuwei watch --once` runs due work and returns 0 clean, 1 findings, 2 unmeasured
or unavailable. `bin/wuwei sweep watch` forces the aggregate sweep, including dead
watch detection. `bin/wuwei sweep obligations` retains its obligations-only contract.
No command shells out in core. Git and GitHub reads use `vcs` and `code_host`.

## Timing and configuration

`watch.clock_seconds=600`, `watch.stale_seconds=900`, `watch.sweep_seconds=7200`
and `pr.poll_seconds=120` are positive integers in workspace config. Activity
checks (60 seconds), dead-watch threshold (1200 seconds) and maximum consecutive
discovery failures (5) are constants.
Owner identity comes from `owner.handles`; repositories from `repos[].name`.
Repository names must be canonical code-host owner/repository references.
Running state items with `worktree` and worktrees in logged briefs of running
seats are active. Paths resolve from the workspace.
A changed HEAD resets the activity time and emits `watch: heartbeat`. An item's
`report_at` timestamp is its reported progress time. Both timestamps require a
UTC offset; future activity is unmeasured. First observation starts the timer.

The first tick writes a clock, polls PRs and sweeps. Scheduler marks persist in
day state. The loop remains alive after findings or unavailable scanner results.
An initial whole-discovery failure stops it; after a successful baseline, five
consecutive discovery failures stop it with exit 2. Failed snapshots record
`watch: read-failed` with the PR reference and preserve that fingerprint; other
PRs are still compared. Successful discovery resets the failure streak. Service managers restart failed
watches. SIGINT/SIGTERM set a threading.Event. The tick completes its writes and the loop
waits on that event between ticks, then releases the workspace lock.

## PR discovery and wake

The watch polls only the deduplicated union of raised and claimed day references.
It adds no discovery operation to the code_host port. An empty day uses the
existing empty-day evidence check. Failed reads never replace a prior snapshot.

The watch hashes head, PR state, mergeability, provider update time, requested
reviewers/teams, checks, reviews and discussion surfaces. Reordering lists is not
activity; edited bodies are activity. Bodies are never stored in watch events or
snapshots. A first successful baseline is quiet. Subsequent changes, new PRs and
references removed at day rollover emit `pr.changed` with PR reference and field names.
The previous day's snapshot is used at rollover.

The wake marker is the reserved `watch.wake` object in day `state.json`, with an
`at` timestamp and `prs` list. This reuses the protected state file and atomic
writer rather than creating another trusted file. It is saved before advancing
the baseline. A crash may repeat a notification, but cannot silently lose it.
SessionStart includes it in additionalContext. Stop returns `decision: block`
with the wake reason once per unseen marker and records `wake.at` in reserved
`watch.wake_seen_at`, with a reserved `session: wake-seen` event. Changes accumulate
PRs until seen. `stop_hook_active` bypasses the wake check; read failures print
an unmeasured message and exit 0. Each change also prints `planner wake:`.
An idle session requires M5 headless launch; no seat re-arms polling. The marker
is not proof of owner approval or resolution of PR obligations.

## Sweeps and lifecycle

Exactly one aggregate `watch: sweep` includes `prs`, `reply_owed`,
`visibility_owed`, `stale_owed`, `watch_dead`, `scanner_owed`, `unreadable`, `owed`
and `exit`. Scanner status is `measured`, `unmeasured` or `unreadable`; a missing
adapter is never clean. An absent trace file with an installed scanner is unreadable.
Watch health is sampled before refreshing a clock; nonzero health forces a
sweep in that tick, so restart cannot mask a gap.

SessionStart calls the existing memory payload producer and displays its byte and
estimated token counts, omitting reserved watch state from the rendered day.
It calls `memory.lint(root)` directly and displays its list of findings. Missing
notes raise ValueError and become an unmeasured line.
Last day's running seat reservations are reported as orphan process candidates,
with process liveness unmeasured. No process is killed and no PID proves identity.

Checks return 0/1/2. SessionStart preserves additionalContext even for findings;
findings, errors and malformed input always exit 0 at the hook boundary.
PreCompact validates state and complete event records, appends reserved
`session: compact` with the checked count, then syncs state/events under the writer
lock. Existing hook translation emits errors on stderr with exit 1, so compaction
is not refused. Stop blocks once for each unseen wake marker. All checks use
shared scope resolution; unrelated projects are untouched.

## Service templates

Copy `templates/wuwei-watch.service` for systemd or `templates/wuwei-watch.plist`
for launchd. Replace every `@...@` placeholder in the installed copy, including
workspace, executable, environment PATH and log destinations. Keep machine paths
out of repository files. Both templates invoke the safe `bin/wuwei` entry point.
Only one watch can hold `.wuwei/watch.lock` per workspace.

## Source harness mapping and deferred work

`pr-watch.sh`: initial-read refusal, persistent baseline, change detection including
in-place edits, failure reset, five-failure refusal. The amended issue requires
mergeability and continuing after wake instead of exit/re-arm. `staleness-watch.sh`:
HEAD comparison, periodic clock, immediate and two-hour sweeps, day ownership
union, failed-read findings, numeric owed counts. Neither source contains self-tests.

Memory lint and actual process inventory need their owning features. PR action
state/deadlines and parking enforcement belong to the PR ownership policy; M5
owns automatic headless dispatch. Scanner integration uses its existing port;
no scanner implementation is added here.
