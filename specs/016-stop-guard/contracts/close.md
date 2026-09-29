# Stop and day-close contract

## Commands

- `bin/wuwei close`: record a reserved close request for an existing day, then recheck
  owned PR actions, reply/visibility obligations, retro and PR disposition.
  Returns 0 clean, 1 findings or 2 unmeasured. Outside workspace scope it returns 0.
- `bin/wuwei close --check retro`: inspect the ordered retro preconditions without
  requesting close.
- `bin/wuwei pr disposition owner/repo#7 parked --decision D-1 --comment 123`:
  record a disposition only after verifying an owner-routed decision and a fresh owner-authored
  code-host comment. Use `carried` to explicitly carry to tomorrow instead.

The owner comment must exactly match the marker printed in the producer's refusal:
`WUWEI <parked|carried> <PR> <decision-id> <today> <decision-fingerprint>`.
The fingerprint is the shared obligations fingerprint of the complete decision text.
The decision must route to owner, name `Decided-by: owner`, and have no entry in
`decision_outcomes`. It is not an approval until the owner posts it; PreToolUse refuses
raw markers in every tool input, including Bash and Write/Edit body files, within scope.
Editing the decision requires a new matching comment. The consumer verifies
both again, so deleting or editing the comment cannot leave a stale approval.

A carry satisfies close disposition only; an overdue turn-end action still needs resolution
or parking. There is no generic state/event path for producing a disposition or close flag.

## Stop

Registration is `Guard('Stop', None, check)`. Every planner registered today stays covered
through a handoff. Non-planner turns and unrelated projects pass. Both ordinary Stop and
retry Stop refuse outstanding correctness conditions. Only a recorded `close_requested`
triggers day-close checks; a payload `day_close` flag has no effect. The hook dispatcher
translates raw 1/2 results to exit 2 and `{"decision":"block","reason":"..."}`.

## Evidence and config

`retro.repo` defaults to `.`; `retro.charter_paths` to `[".wuwei/charters"]`;
`retro.changelog` to `.wuwei/memory/CHANGELOG.md`.
Paths inside the repository must be literal.
The retro lives at `.wuwei/days/YYYY-MM-DD/retro/YYYY-MM-DD.md` with Applied and Proposed
sections. Applied lists configured charter paths, or exactly `none`. Collected notes are
existing `retro.captured` events with matching evidence, counted once per evidence path.
With Applied set to `none`, close requires no Git history for the workspace.

When present, `watch.actions[PR]` contains observed open/closed state, action, creation time
and deadline. Stop reads it and checks fresh merged evidence. Absent actions are not
overdue; malformed records return 2. Watch neither synthesizes actions nor inherits old ones.

## Port additions

- `vcs.changes_on(repo, day, root=None)`: Result containing unique repository-relative paths
  changed in commits reachable from HEAD on the ISO local calendar day.
- `vcs.read_tree(repo, ref, paths, root=None)`: Result containing path-to-text mapping for
  committed files below literal paths. Ref is HEAD or a full commit ID. Failed reads return 2.
- `code_host.pr` additionally requires boolean `merged`, independent of open/closed state.

## Deferred to #120

Supply the complete PR state machine, action production,
completion/rearming, review windows, escalation and carry-forward scheduling. The report
feature must call `bin/wuwei close` before claiming day close.
