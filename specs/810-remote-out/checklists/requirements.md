# Requirements checklist: delete the remote control plane, the listener and the inbox

**Purpose**: check the spec and plan before implement. **Feature**: [spec.md](../spec.md)

## Completeness

- [x] CHK001 Every unit removed is named with (a) or (b) and where its job lives now (plan table).
- [x] CHK002 Every importer of `control_plane`, `inbox`, `listen`, `remote` and the inbound
  port is listed: config, setup, status, doctor, lifecycle, heartbeat, watch, shepherd,
  signal, event, state, telemetry, sessions, decision, profiles, interview, registry, env.
- [x] CHK003 The units only the listener reached are named: `shepherd.pending`,
  `shepherd.headless`, `claude.headless`, `watch.listening`, the `inbox` wake count.
- [x] CHK004 Charters, skills, hooks, agents, CI workflows, scripts and templates were
  searched: one charter line, one template table and two template keys.
- [x] CHK005 Retired config keys are listed for `workspace.RETIRED` (base has none yet).

## Clarity

- [x] CHK006 New output lines are written out (`Removed the listener service (no longer
  shipped)`, the `config set` step in `setup slack`).
- [x] CHK007 The docs rule is one sentence; every page and line is named.

## Consistency

- [x] CHK008 No test is loosened: each removed assertion covered deleted code; kept wake and
  SessionStart cases move to `tests/test_watch.py`.
- [x] CHK009 Design spec and constitution edits are marked as the owner's #789 instruction.
- [x] CHK010 No emojis, no em-dashes, no absolute local paths, no names of clients,
  repositories or people.

## Dependencies

- [x] CHK011 Order with parts 1 to 6 is stated, with what to skip after a rebase.
- [x] CHK012 Upgrade path covered: leftover service unit, legacy wake marker, retired
  interview id, retired keys.
