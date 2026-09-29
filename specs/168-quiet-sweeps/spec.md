# Feature 168: Quiet sweeps, nudges, watch installer

## User scenarios and acceptance

1. Given traces and no configured scanner, `sweep watch` exits 0, records `not configured`, and emits at most one scanner notice per day.
2. Given three open obligations, `wuwei nudges` lists three sourced entries, matching the status line count. Once an obligation clears, its entry disappears.
3. A steward brief is produced only when a steward seat is launched.
4. An owner can install and uninstall the watch service for the active workspace on macOS or Linux, carrying the workspace path and PATH.
5. A killed watch has no fresh clock. The next sweep records `watch_dead: 1` using configurable `watch.dead_seconds`.

## Requirements

- Discovery names the reason for each unavailable source. An intentionally absent adapter or inapplicable source does not make a sweep fail.
- The open attention list and status count share one calculation. Unreadable input reports exit 2 with a reason.
- Watch service installation renders the shipped platform template, loads it, and reverses the operation on uninstall.
- Runtime error bodies and failed service commands are exit 2.

## Edge cases

- A failed configured scanner remains unmeasured and fails the sweep with a reason.
- Corrupt or unreadable status records fail closed instead of showing an empty list.
- Installing on an unsupported operating system or failing to load a user service reports why it could not run.
- Repeated manual sweeps within one sweep interval do not produce duplicate steward launch briefs.

## Success criteria

- A configured `none` scanner produces zero scanner read failures for a trace-bearing day.
- Three current obligations produce three listed entries, and clearing a cause reduces both the list and status count.
- One stale clock produces `watch_dead: 1` at the next sweep using the configured threshold.
- Both supported platforms install and remove one workspace-specific user service with the active workspace and PATH.

## Assumptions

- `scanner = none` means an intentional operator choice; no trace measurement is claimed.
- Open nudges are current conditions, not a historical count of event notifications.
- Service names are stable per workspace and installed in the current user's service directory.
- A sweep called outside the running watch diagnoses clock health; a newly installed watch writes its first clock on start.

## Deferred

- Tracker backlog listing and other discovery sources without ports remain unavailable with explicit reasons.
