# Implementation Plan: the status line counts items in words

**Branch**: `641-status-counts` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

One renderer, one change: `_groups` in `cli/wuwei/commands/status.py` stops dividing phase
counts by CAP and renders `<count> <word>` with plain words. Every surface (status line,
`wuwei status`, remote `status` reply, cockpit board) already reads `_groups`, so nothing
else in the code changes. Tests and owner docs that pin the old tokens are updated.

## Technical Context

Python 3.11+, stdlib only; pytest for tests. `status --line` runs on every Claude Code
refresh and carries the hook latency budget: the change adds a module-level dict and a loop
over at most ten phases, no import and no read.

## Constitution Check

- I (stdlib), II (exits): unchanged; no new failure path.
- III (one behaviour, one function): the counts stay in `_groups`, the one source (#521).
- IV (test first): every behaviour below has its test task before its implementation task.
- V (ponytail): one dict and three lines at the shared spot; no option, no config.
- Design spec conflict: 5.9 says "items per phase against CAP"; the owner's issue supersedes
  it, so this feature amends that sentence (FR-006), as #631 and #633 did for theirs.

## Design

In `cli/wuwei/commands/status.py`, next to `WIDTH`:

```python
# #641: what the line calls each phase; CAP is shown on seats only.
WORDS = {'planned': 'planned', **dict.fromkeys(state.BUILD_PHASES, 'building'),
         'gate': 'in review', 'delta': 'in review', 'raised': 'in review',
         'merged': 'shipped', 'parked': 'parked', 'escalated': 'escalated'}
```

In `_groups`, replace line 367 with:

```python
counts = dict.fromkeys(WORDS.values(), 0)
for phase, count in data['phases'].items():
    counts[WORDS.get(phase, phase)] = counts.get(WORDS.get(phase, phase), 0) + count
work = [f'{count} {word}' for word, count in counts.items() if count]
```

`dict.fromkeys(WORDS.values(), 0)` fixes the order (planned, building, in review, shipped,
parked, escalated) independent of `state.PHASES` order. `WORDS.get(phase, phase)` keeps an
unknown phase visible under its own name rather than raising from the board or remote paths,
which call `line` outside `run`'s exception handler. The builder may write the loop body
with a local `word = WORDS.get(phase, phase)`; the shape is free, the behaviour is not.

Reused, not re-implemented: `state.BUILD_PHASES` (the building set `next` and dispatch count
against CAP), `snapshot`'s per-phase `phases` dict (unchanged), `line`'s width cutting
(unchanged).

## Must not change

- `snapshot` and `status --json` (`phases` stays per phase; dashboard and SwiftBar read it).
- The seats token `seats N/CAP (roles, +N more)` and its cutting in `line`.
- `templates/dashboard.html` (its `WIP n` and `CAP running/cap` already name their nouns).
- `heartbeat.py`, `remote.py`, `commands/board.py`, `metrics.py` (they reuse `status.line`
  or render no counts).

## Files

| File | Change |
|---|---|
| `cli/wuwei/commands/status.py` | `WORDS` constant; `_groups` work tokens |
| `tests/test_signal_status.py` | new sample-day test; old `phase n/cap` assertions updated |
| `tests/test_e2e_day.py` | line 176 `merged 1/4` becomes `1 shipped` |
| `tests/test_docs.py` | line 106 marker `planned 1/1` becomes `1 planned` |
| `docs/site/daily.md` | lines 248, 253 to 256, 295 to 296: new tokens |
| `docs/site/remote.md` | line 270: the reply as `line` prints it today |
| `docs/specs/2026-09-24-wuwei-design.md` | 5.9 Status line, line 1022: counts in words, CAP on seats |

## Old assertions to update (tests/test_signal_status.py)

The `four_seats` fixture has phases `{'implement': 1}`, cap 1: `implement 1/1` (13 columns)
becomes `1 building` (10 columns). The narrow-line test
(`test_a_narrow_line_cuts_the_roles_then_drops_whole_tokens`) keeps its cut sequence with
each width reduced by 3: 81 full, 72 `(lead, arch, +2 more)`, 67 `(lead, +3 more)`, 52 and
42 `| pages 0 · nudges 0`, 27 `| pages 0`, 22 and 5 `WUWEI 1 building`. Recompute each
expected string by length rather than trusting these numbers blindly. Other sites: lines
135 (`spec 1/2`, `implement 1/2` become `2 building`), 192 (`delta 1/2`, `merged 1/2` become
`1 in review`, `1 shipped`; the JSON assertion on `phases` stays), 963, 979, 1015, 1021,
1038.

## Docs

- `daily.md` 248: `WUWEI 1 planned · seats 0/1 | pages 0 · nudges 0 · observe`; 253 to 256:
  "the status line shows `1 planned`" and "has no `planned` count"; 295 to 296: "The status
  line counts items in words, for example `1 building`, and later `1 shipped`."
- `remote.md` 270: replace the stale reply with the current shape, for example
  `1 building · seats 1/1 (builder) | pages 0 · nudges 1`.
- Design spec 5.9 line 1022: replace "then items per phase against CAP and the running
  seats by role" with "then the day's items counted in words (`5 planned · 2 building ·
  1 in review · 3 shipped`, CAP only on the seats token) and the running seats by role".
