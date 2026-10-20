# Implementation Plan: the gate charter shows each finding shape

**Branch**: `fix/1179-verdict-shape-examples` | **Spec**: `specs/verdict-shape-examples/spec.md`

## Technical Context

Python 3.11 stdlib. Tests in tests/test_charters.py, tests/test_evidence.py and tests/test_hook.py.
Runtime budget for the item: 5 lines.

## Constitution Check

- Stdlib only: yes.
- Test first: the evidence test ran red on main (the refused security file was listed), the charter
  test ran red (one example line in the charter, three wanted).
- Budgets: runtime 3,208 to 3,211 lines; every generated agent at or under 2,250 words.

## Design

- `uncounted(root, item_id, gates=REQUIRED['full'])` skips a file whose `Gate:` is a known gate not
  in `gates`. `gate_gaps` passes `missing` for the missing-gates gap and `[gate]` for the delta
  review gap. board.py keeps the default, so an item with no PR still lists every refused file.
- `charters/_gate.md`: the paragraph after the verdict block gains the three rules with an example
  line each. Words come back from rules 1 and 3 and The verdict paragraph, so sentinel-arch goes
  from 2,250 to 2,249.
- Agents rebuilt with `bin/wuwei agents build`; `.claude/` re-vendored with `setup.vendor('.')`.

## Evidence

- `route_diff.py`: every route in tests/fixtures/routes.json through guards.bash at main and at the
  head, in four workspaces with an approved exception on the quality gap of o/r#5.
