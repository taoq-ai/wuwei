# Feature Specification: an empty ticket field is absent, not a rejected proposal

**Feature Branch**: `640-empty-ticket`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #640 (owner, 2026-10-10): "`plan propose` rejected the whole
proposal over `"ticket": ""`, while the template treats the field as optional." Deliver:
empty strings and null for the optional candidate fields `ticket`, `docs` and `tier` are
treated as absent in the plan validation; when a value is present and invalid, the error
names the item and the field with the accepted form.

## Root cause

Reproduced in-process on `main` with the `tests/test_plan.py` fixtures (a temporary
workspace, candidates `A` and `B`, no tracker):

| Candidate `A` carries | `plan.propose` today |
|---|---|
| `"ticket": ""` | `ValueError: A: invalid ticket; the plan JSON misses or misshapes this field; ...` |
| `"ticket": null` | same refusal |
| `"tier": ""` or `"tier": null` | `ValueError: A: tier must be light, standard or full; ...` |
| `"ticket": "not a ticket!"` | `ValueError: A: invalid ticket; ...` (no value, no accepted form) |

In the code, `cli/wuwei/plan.py`:

- `_proposal` (line 37) validates every candidate. Line 89 checks
  `'tier' in item and item['tier'] not in dispatch.TIERS`, and lines 91-93 check
  `'ticket' in item and not (isinstance(item['ticket'], str) and re.fullmatch(TICKET, ...))`.
  Both test key presence, so a present-but-empty value is validated as a value and fails.
  One bad candidate raises, so the whole proposal is refused.
- The ticket error at line 93 names the item and says "invalid ticket" but neither the
  value nor the accepted form `TICKET` (line 13, `ENG-1, PROJ-12, owner/repo#12`). The lead
  is pointed at `bin/wuwei plan template`, whose candidate (`commands/rank.py:22`,
  `candidate_template`) has no `ticket` field at all, so the template cannot show the form.
- Downstream readers also test presence: `approve` copies `candidates[name]['ticket']` into
  `tickets` when the key exists (lines 365-366) and copies `tier` the same way (lines
  386-387); `add` does the same for a discovery candidate (line 445). An empty value that
  slipped past validation would be recorded as ticket id `""`, so the fix must remove the
  key, not only skip the check.
- `_proposal` is the one shared spot: `propose` (line 193), `approve` (line 323, re-reading
  `proposal.json`) and `add` (line 439, for a discovery candidate) all route through it.
- `docs` is not a candidate field `_proposal` checks or any reader consumes (an item's docs
  page is assigned with `plan set <item> docs=`), so an empty `docs` is not refused today.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - an empty optional field does not refuse the proposal (Priority: P1)

The lead writes a candidate with `"ticket": ""` (or null, or an empty `tier`) because it has
no ticket to name. `plan propose` accepts the proposal and treats the item as having no
ticket; the tracker rule then decides at `plan approve` as for any item without one.

**Why this priority**: it is the owner's report; one empty field blocked the whole morning
plan.

**Independent Test**: propose two candidates carrying empty and null `ticket`, `tier` and
`docs`, then approve them with no tracker; the proposal is written without those keys and
the approved state records no ticket and no tier for them.

**Acceptance Scenarios**:

1. **Given** a candidate with `"ticket": ""` or `"ticket": null`, **When** the planner runs
   `plan propose`, **Then** the proposal is accepted with no ticket for that item.
2. **Given** a candidate with `"tier": ""` or `"tier": null` (or `"docs": ""`), **When** the
   planner runs `plan propose`, **Then** the proposal is accepted and the field is absent
   from `proposal.json`.
3. **Given** such a proposal, **When** the planner runs `plan approve`, **Then** no ticket
   with an empty id is recorded and the item carries no tier.
4. **Given** a discovery candidate with `"ticket": ""`, **When** the planner runs `plan add`,
   **Then** it is admitted as an item without a ticket.

### User Story 2 - a present, invalid value names the item, the field and the form (Priority: P2)

**Why this priority**: the lead fixes its own JSON only when the refusal says what to write.

**Independent Test**: propose a candidate with an invalid ticket and read the error.

**Acceptance Scenarios**:

1. **Given** a candidate with `"ticket": "not a ticket!"`, **When** the planner runs
   `plan propose`, **Then** the error names the item and `ticket`, quotes the value and shows
   the accepted pattern with example ids, and nothing is written.

### Edge Cases

- A whitespace-only string (`"ticket": "  "`) is treated as empty, so absent.
- A non-string, non-null value (`"ticket": 12`) stays invalid and gets the User Story 2 error.
- A candidate without the key behaves exactly as today.
- An invalid `tier` keeps its current message, which already names the item, the field and
  the accepted values (`light, standard or full`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Plan validation MUST treat `ticket`, `tier` and `docs` whose value is null or
  a string that is empty after trimming as absent, and remove the key from the candidate so
  every later reader (`proposal.json`, `approve`, `add`, `tracker`) sees it absent.
- **FR-002**: The ticket refusal MUST name the item, the field `ticket`, the given value and
  the accepted form: the `TICKET` pattern and the example ids `ENG-12, PROJ-12 or
  owner/repo#12`, and say the field can be left out.
- **FR-003**: Every other candidate check is unchanged.
- **FR-004**: The lead plan JSON reference (`docs/site/reference.md`) states that `ticket`
  is optional and that an empty or null `ticket` or `tier` counts as absent.

## Success Criteria *(mandatory)*

- **SC-001**: The issue's two acceptance cases pass as tests in `tests/test_plan.py`.
- **SC-002**: The existing suite stays green, including
  `test_invalid_candidate_ticket_is_unrun` (its `A: invalid ticket` prefix is kept).

## Assumptions

- The orchestrator notes file for this issue does not exist in the pipeline, so no dry-run
  workspace was named; the failure was reproduced in a temporary workspace with the test
  fixtures instead.
- "The template" in the report is the lead plan JSON contract: `plan template` prints no
  `ticket` field, which already makes it optional. The fix is in validation; the lead's
  charter and the template are not changed.
- `docs` is in the issue's list but nothing reads a candidate's `docs`; it joins the same
  normalisation so the record carries no empty key, at no extra cost.
- Whitespace-only counts as empty: a lead filling a field it has no value for writes `""` or
  a blank; neither is a ticket id.
- `plan set <item> ticket=` with an empty value keeps its own refusal: that is an explicit
  command, not an optional JSON field, and it is outside this issue.
- #636 (in the same wave) changes how tickets are proposed and recorded around `approve`;
  this change touches only the validation lines in `_proposal`, so the two meet at most on
  adjacent lines.
