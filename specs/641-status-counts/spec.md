# Feature Specification: the status line counts items in words, not a planned N/M ratio

**Feature Branch**: `641-status-counts`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #641 (owner, 2026-10-10): the status line says `planned 12/5`, which
reads as a meaningless ratio. Deliver: the line names what it counts in words a person reads
at a glance, for example `5 planned, 2 building, 3 shipped`, with the cap only where it
applies (`2/3 seats`). The same text in `wuwei status`, the heartbeat page and the Claude
Code status line.

## Root cause

Reproduced in-process on `main` (`status.line` on a sample snapshot: cap 5, phases
`planned 12, implement 2, gate 1, raised 1, merged 3`, two builder seats):

```text
WUWEI planned 12/5 · implement 2/5 · gate 1/5 · raised 1/5 · merged 3/5 | pages 0 · nudges 1
```

`cli/wuwei/commands/status.py:367`, in `_groups`, renders every phase count against CAP:

```python
work = [f'{phase} {count}/{data["cap"]}' for phase, count in data['phases'].items()]
```

CAP limits running seats, not items in a phase, so `planned 12/5` and `merged 3/5` divide two
unrelated numbers. The phase names are internal (`delta`, `raised`, `gate`), not words the
owner reads at a glance. The tokens are also long enough that this sample day drops the
`seats` token at the default 100 columns.

`_groups` is the one source of every surface (#521): `status.line` (the Claude Code status
line through `wuwei status --line`, the remote `status` DM reply in `remote.py:316`, the
cockpit board's first line in `commands/board.py:151`) and `status.full` (`wuwei status`).
Fixing `_groups` fixes all of them. The seats token (`seats 2/3 (builder, builder)`) already
names its noun and is the only place CAP belongs. `metrics.py:606` (named in the issue) is
the time-in-phase metric; it reads `plan.approved` items, renders no status text and is not
part of this defect.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which words? A: Count first, then the word: `planned` (phase planned), `building` (the
  build phases `spec`, `implement`, `fix`, the same set `next` and dispatch count against
  CAP), `in review` (`gate`, `delta`, `raised`: a gate or a PR review), `shipped`
  (`merged`), `parked` and `escalated` (already plain words, kept so the owner sees held
  work).
- Q: Order? A: planned, building, in review, shipped, parked, escalated; a word with a zero
  count is left out, as phases with zero items are today.
- Q: Does the seats token change? A: No. `seats N/CAP (roles)` already names its noun, the
  issue's acceptance accepts it (`seats`), and it is pinned across docs and tests. Only the
  per-phase `/CAP` goes.
- Q: Does `status --json` change? A: No. `phases` stays a per-phase count: the dashboard
  draws its columns from it and the menu bar plugin reads only pages and nudges.
- Q: Does the dashboard change? A: No. Its column headers already say `WIP n` and, on build
  columns only, `CAP running/cap`, which names its noun.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The owner reads the day's items at a glance (Priority: P1)

The owner glances at the Claude Code status line (or `wuwei status`, or the phone `status`
reply) and reads how many items are planned, building, in review and shipped, with no
number divided by CAP except the seats.

**Why this priority**: the defect the owner reported; every surface shows it.

**Independent Test**: build a snapshot for a sample day and compare `status.line` and the
first line of `status.full` with the pinned text.

**Acceptance Scenarios**:

1. **Given** a day with cap 3, items in phases planned 5, spec 1, implement 1, gate 1,
   raised 1, merged 3 and one running builder seat, **When** the status line renders,
   **Then** it is exactly
   `WUWEI 5 planned · 2 building · 2 in review · 3 shipped · seats 1/3 (builder) | pages 0 · nudges 0`.
2. **Given** the same day, **Then** no `N/M` pair appears in the line or in `wuwei status`
   unless the word before it is `seats`.
3. **Given** items parked and escalated, **Then** the line shows `1 parked · 1 escalated`
   after the other counts.
4. **Given** the same snapshot, **Then** `wuwei status` (first line), the remote `status`
   reply and the cockpit board's first line show the same counts, because all read
   `status._groups`.

### Edge Cases

- No items: no count token, the line starts with the seats token as today
  (`WUWEI seats 0/1 | pages 0 · nudges 0`).
- Width cuts: `line` keeps cutting roles first, then whole tokens from the right of work;
  the count tokens are shorter, so the existing narrow-line tests keep their cut sequence at
  widths 3 columns smaller.
- Before the gate (`no plan yet`, `gate waiting`) the counts render the same way.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The status groups MUST render each nonzero item count as `<count> <word>`,
  with the words and order from the Clarifications, summing phases that share a word.
- **FR-002**: No item count MUST be rendered against CAP; `seats N/CAP` is unchanged.
- **FR-003**: `status --line`, `status`, the remote `status` reply and the cockpit board MUST
  show the same tokens (one renderer, `_groups`).
- **FR-004**: `status --json` and its `phases` key MUST stay unchanged.
- **FR-005**: The owner docs that show the line (`docs/site/daily.md`,
  `docs/site/remote.md`) MUST show the new tokens.
- **FR-006**: Design spec 5.9 (`docs/specs/2026-09-24-wuwei-design.md`, Status line) MUST
  say the line counts items in words (`5 planned, 2 building, 3 shipped`) instead of
  "items per phase against CAP"; CAP stays on the seats token. Recent features amend the
  design spec with the code (#631, #633), so this one does too.

## Success Criteria *(mandatory)*

- **SC-001**: A test pins the full status line for the sample day in scenario 1.
- **SC-002**: A test asserts no `\d+/\d+` pair in the line or in `wuwei status` for that day
  except after `seats`.
- **SC-003**: The full suite passes; `status --line` stays within its latency budget (no new
  import, no extra read).

## Assumptions

- The issue's example words (`planned`, `building`, `shipped`) are kept; `in review`,
  `parked` and `escalated` cover the remaining phases so no item disappears from the line.
- `building` means `state.BUILD_PHASES`, the set CAP is counted against elsewhere (`next`,
  dispatch), so the line and `next` agree on what building means.
- The issue's `2/3 seats` is an example of "cap only where it applies"; the existing
  `seats 2/3` form satisfies the acceptance (a noun makes it a ratio) and is kept to avoid
  churn in docs and tests.
- "The heartbeat page" means the surfaces that echo the line outside the terminal: the
  remote `status` reply and the cockpit board. `heartbeat.py` only probes that
  `status --line` exits 0 in budget and renders no counts; it needs no change.
- No orchestrator notes file exists for #641; the issue is the only input.
- The feature directory was created by an earlier run of `create-new-feature.sh` on branch
  `641-status-counts`; it was not re-run. `metrics.py:606` (named in the issue) is the
  time-in-phase metric and renders no status text, so it does not change.
