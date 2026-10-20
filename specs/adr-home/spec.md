# Feature Specification: the one-way ADR note follows the repository's own ADR home

**Feature branch**: `fix/adr-home`
**Item**: 1171, tier full, goal G-2
**Input**: on WUWEI 4.2.2 the PostToolUse note after a `one-way:` answer said to record the ADR in
the repository's `docs/adr/`. The repository had no `docs/adr/`; its ADRs live per feature under
`specs/<feature>/adr-NNN-*.md`, and the answer re-confirmed one of them. Following the note would
have started a second ADR home.

## The promise in my words

Three texts name `docs/adr/` as the one place for an ADR: the PostToolUse note in `hook.py`, the
planner charter's one-way bullet, and the arch charter's opening line. After this item:

1. The note and the planner charter say: record the ADR where the repository keeps its ADRs, an
   existing `docs/adr/` or `docs/decisions/`, else the item's spec folder.
2. Both say: when the answer re-confirms an existing ADR, amend that ADR instead of adding a file.
3. The arch charter reads "the repository's ADRs", one word shorter, so the generated arch agent
   stays under its 2,250-word ceiling.

WUWEI does not look for the ADR folder itself. The planner reads the repository and picks the home.

The acceptance scenarios, restated:

1. An owner answers a `one-way:` question. The PostToolUse note names the repository's own ADR
   location (an existing `docs/adr/`, `docs/decisions/` or the item's spec folder). It no longer
   says the repository's `docs/adr/` as the one place.
2. The same note says that an answer re-confirming an existing ADR amends that ADR, not a new file.
3. After `bin/wuwei agents build`, the planner and arch charters state the same rule, and every
   generated agent is at or under 2,250 words.

## How this fails

1. A repository keeps ADRs somewhere the list does not name (`architecture/decisions/`, a wiki).
   The note says "where the repository keeps its ADRs" before the examples, so the planner follows
   the repository; the examples are not a closed list.
2. A repository has both `docs/adr/` and per-spec ADRs. The note puts an existing folder first, so
   the planner adds to the folder the repository already has instead of a third home.
3. The planner cannot tell whether the answer re-confirms an existing ADR and adds a duplicate. The
   note names the case; finding the ADR stays the planner's reading of the repository, out of scope
   here.

## Clarifications

### Session 2026-10-20

- Q: Does WUWEI search the repository for an ADR folder and name the path? A: No. The item puts
  that out of scope; the note states the rule and the planner reads the repository.
- Q: Does the note name the specific ADR to amend (ADR-003 in the report)? A: No. The hook sees
  only the question and the answer, so it cannot know which ADR. The note says to amend the one
  the answer re-confirms.
- Q: Which order when several homes exist? A: An existing `docs/adr/` or `docs/decisions/` first,
  else the item's spec folder.
- Q: Do the user docs change? A: Yes. `docs/site/concepts/decisions.md` and `index.md` named
  `docs/adr/` the same way and would contradict the charter.

## User Scenarios & Testing

### US1: the note names the repository's own ADR home (P1)

Acceptance 1. The note holds `docs/adr/`, `docs/decisions/` and "the item's spec folder", and not
"repository's docs/adr/".

### US2: a re-confirmed ADR is amended (P1)

Acceptance 2. The note holds "amend that ADR".

### US3: the charters state the same rule (P2)

Acceptance 3. The planner charter holds the three homes and "amend that ADR"; the arch charter
reads "the repository's ADRs" and names no `docs/adr/`. The word-ceiling test holds.

## Requirements

- FR-001: `hook._answers` appends the note naming the three homes and the amend rule.
- FR-002: `charters/planner.md` states the same rule in the "What goes to the owner" list.
- FR-003: `charters/sentinel-arch.md` reads "the repository's ADRs"; `agents/` is rebuilt and
  `.claude/` re-vendored.
- FR-004: the runtime grows by at most one line.

## Assumptions

- `docs/adr/` and `docs/decisions/` are the two common folder names (adr-tools and MADR). Overturned
  if a retro shows a third one recurring; the note's lead phrase already covers it.
- The docs pages under `docs/site/concepts/` are in scope as the user-facing copy of the rule.
  Overturned if the owner wants docs in their own PR.

## Rollback

Revert the commit, rebuild `agents/` and re-vendor `.claude/`. No config key, ledger kind or file
format changes; only note and charter text.
