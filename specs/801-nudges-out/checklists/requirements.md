# Requirements checklist: delete nudges

**Purpose**: check the spec and plan before implement. **Feature**: [spec.md](../spec.md)

## Completeness

- [x] CHK001 Every unit removed is named with (a) or (b) and where its job lives now (plan table).
- [x] CHK002 Every reader of the deleted helpers (`surfaced`, `_tidy`, `nudge_mode`,
  `SHADOW_NUDGE`, `scan(config=)`) is listed: status, doctor, board, init, nudges, and the
  tests `test_board_mcp`, `test_nudge_hygiene`, `test_nudges_mode`, `test_workspace`.
- [x] CHK003 Every module that writes the `nudge` tier or names `bin/wuwei nudges` is listed
  (signal, status, pr_actions, integrity, listen, decision, why, control_plane, obligations).
- [x] CHK004 Charters, skills, hooks, agents, CI workflows and scripts were searched: no
  mention.
- [x] CHK005 Template keys removed match the schema keys removed (`[nudges]` three keys,
  `owner.verbosity.nudges`).

## Clarity

- [x] CHK006 The new tier name (`warn`) is fixed in FR-004 and used the same way everywhere.
- [x] CHK007 The doctor page fix (`wuwei next`) and the new message texts are written out.
- [x] CHK008 The docs rewording rule is one sentence.

## Consistency

- [x] CHK009 The design spec is not edited (constitution); the conflict is raised.
- [x] CHK010 No test is loosened: each removed assertion covered deleted code; kept behaviour
  keeps its test (four `scan` cases moved).
- [x] CHK011 The only remaining `nudge` in `cli/wuwei` is the documented legacy read.

## Dependencies

- [x] CHK012 Order with parts 1 to 3 and the parallel parts 5 and 7 is stated, with what to
  skip after a rebase.
- [x] CHK013 Part 2 owns removing `[nudges]` from existing configs; no migration is added here.
