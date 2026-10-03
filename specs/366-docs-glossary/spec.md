# Feature Specification: A glossary, plain-word interview options and one newcomer walkthrough

**Feature Branch**: `366-docs-glossary`

**Created**: 2026-10-03

**Status**: Draft

**Input**: Issue #366, docs(site): a glossary, plain-word interview options and one newcomer
walkthrough from install to first merge. Findings F19 and F25 of the UX adoption sweep of
2026-10-03. Depends on #340 (docs sweep, on main). Scope: `docs/site/concepts.md`,
`docs/site/daily.md`, `docs/site/index.md`, `README.md`, the option texts in
`cli/wuwei/interview.py`, and the F25 success line of `goals edit` / `voice edit`.

## Current state (read and reproduced on main at 89b577e)

- F19, docs. `docs/site/concepts.md:9` opens with `## Roles`; no page defines seat, gate,
  sentinel, shepherd, steward, CAP, envelope, tier, soak, delta, park, carry, nudge, page,
  digest, unmeasured, mandate, trust surface or host terminal. CAP and envelope first appear
  in a list at `docs/site/daily.md:88`; envelope is defined only as a JSON field at
  `docs/site/reference.md:80`. Several of these words carry two meanings in the docs:
  "gate" (a review seat, and the morning gate), "tier" (review tier at
  `concepts.md:128`, outbound approval tier at `daily.md:78`), "digest" (the code typed to
  confirm, `daily.md:65`, and the two-hourly decision summary, `interview.py:90`), "page"
  (an alert, and a web page, `daily.md:10`). A prototype of the first-use check over
  README, index and daily finds every term that appears there unlinked: 15 terms on daily,
  9 on the README, 5 on the index, some of them generic uses ("this page", "Releases carry").
- F19, interview. `cli/wuwei/interview.py:75-80`: header `Gate floor`, question
  `Lowest review tier for every change in {repo}?`, options described as "the standard gate
  set" and "the light gate set". Those descriptions are also misleading:
  `dispatch.py:87-89` takes the higher of the computed tier and the floor, so with the
  default floor `standard` every change gets three reviewers (arch, quality, security,
  `dispatch.py:11,98`), and `full` runs the same three roles as `standard`.
  `interview.py:70,72` say `Merge when every precondition holds, after 30 minutes`, with
  the jargon constant `SOAK` at `interview.py:16`; `:90` "two-hourly digest", `:93`
  "one-way-door decision", `:109` "control-plane messages", `:146` "trust surface",
  `:156,157` "deploy.deny", `:124,148` "voice profile", "lead charter". Each term comes
  before any explanation.
- F25. `cli/wuwei/commands/_owner_edit.py:34-35` calls `promotion.owner_edit` and returns
  `CLEAN` without printing. Reproduced in-process on a fixture workspace: `wuwei goals edit
  --file .wuwei/days/2026-10-03/goals.md` exits 0 with empty stdout and stderr, so neither
  the planner nor the owner can tell the goals were saved. (The other half of F25, agents
  proposing goals for approval, landed in #357.)
- Walkthrough. `daily.md` names no output for setup or the first plan. A clean run on main
  (one fixture repository `acme/widget`, `gh` signed in, first interview choice for every
  question; captured in-process with the `tests/test_setup.py` fakes) ends with
  `Applied the setup and recorded .wuwei/calibration.json`, the config check sections,
  `Still owed:` with `owner.name` and `bin/wuwei promote`, then `Next: /wuwei plan`, exit 0.
  The first plan then prints the `plan.md` path from `plan propose`, nothing from
  `goals edit` (F25), nothing from `plan approve`; `status --line` shows
  `WUWEI pages 0 | nudges 0 | observe | watch off | planned 1/1 | meeting unmeasured` and
  `bin/wuwei next` starts `dispatch: 1 planned item(s) queued, 0 of CAP 1 building`.

## User Scenarios & Testing

### User Story 1 - One glossary, linked at first use (Priority: P1)

A newcomer reads the README, the docs index or the daily path and meets a WUWEI word. The
first time each glossary word appears on that page it links to a two-line definition at the
top of the concepts page.

**Why this priority**: every other page assumes these words; without them the docs read as
a wall to anyone new.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k glossary`.

**Acceptance Scenarios**:

1. **Given** `docs/site/concepts.md`, **When** it is read, **Then** its first `##` section is
   `## Glossary` with one `###` entry for each of seat, gate, sentinel, shepherd, steward,
   CAP, envelope, tier, soak, delta, park, carry, nudge, page, digest, unmeasured, mandate,
   trust surface and host terminal, in that order, each at most two lines.
2. **Given** `README.md`, `docs/site/index.md` and `docs/site/daily.md`, **When** a glossary
   word (any of its listed forms) first appears in prose (outside code, HTML tags and link
   targets), **Then** that occurrence is the text of a link to its glossary entry
   (`concepts.html#<anchor>` on site pages, `docs/site/concepts.md#<anchor>` from the README).
3. **Given** a word with two meanings (gate, tier, digest), **When** its entry is read,
   **Then** it names both meanings.

---

### User Story 2 - Interview options say what they do (Priority: P1)

During `setup` or the first-day widgets the owner reads each question and option. Each one
leads with the effect in plain words and puts the WUWEI term, if any, in brackets at the end.

**Why this priority**: the interview runs before any page is read, so its words are the
first ones a newcomer has to decide on.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k interview_options`.

**Acceptance Scenarios**:

1. **Given** the interview table, **When** any header, question or option description is
   read, **Then** no glossary word (nor floor, control plane, deploy.deny, one-way) appears
   before its first opening bracket.
2. **Given** the gates question, **When** the Light option is shown, **Then** its
   description starts `Small low-risk changes get one reviewer agent`, and the Standard and
   Full descriptions say every change gets three reviewer agents.
3. **Given** a recorded answer such as `merge=Auto, 30 min soak`, **When** it is recorded
   or re-read, **Then** it still validates and maps to the same config keys and charter
   lines as before (labels and effects unchanged).

---

### User Story 3 - A newcomer can tell success from failure (Priority: P2)

The newcomer runs setup and the first plan and compares what they see with the daily path.
Each step shows the output of a clean run, and says which lines mean it worked and which
mean it did not.

**Why this priority**: today the only signal is an exit code; a silent `goals edit` and a
long setup report leave the newcomer guessing.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k clean_first_day` and
`python -m pytest -q tests/test_owner_edits.py -k saved`.

**Acceptance Scenarios**:

1. **Given** `daily.md` section 2, **When** it is read, **Then** it shows the output of a
   clean `setup --shadow` in a `text` block containing `plugin integrity: clean`,
   `Interview answers:`, `Applied the setup and recorded .wuwei/calibration.json`,
   `Still owed:` and `Next: /wuwei plan`, and says what a failed run shows instead.
2. **Given** `daily.md` section 3, **When** it is read, **Then** it shows the output of a
   clean first plan in a `text` block containing `goals: 1 goal saved (G-1)`,
   `planned 1/1` and `planned item(s) queued`.
3. **Given** a valid goals file, **When** `wuwei goals edit --file <file>` saves it,
   **Then** it prints `goals: 1 goal saved (G-1)` and exits 0; run again with the same file
   it prints `goals: 1 goal unchanged (G-1)`. `wuwei voice edit` prints `voice: saved` or
   `voice: unchanged`.
4. **Given** an invalid goals file, **When** `goals edit` refuses it, **Then** stdout stays
   empty and the existing stderr reason and exit 1 are unchanged.

### Edge Cases

- A glossary word used in its other meaning before its WUWEI meaning (for example "this
  page" in daily.md): reword the generic use or link it; the check takes the first prose use.
- A glossary word that does not appear on a page needs no link there.
- Labels are answer ids (`calibrate --answer merge=Auto, 30 min soak`, today's
  `interview.json`): they keep their text even where they contain a term.
- Goals with several ids print them in file order, comma separated, with `goals` plural.

## Requirements

### Functional Requirements

- **FR-001**: `concepts.md` MUST open (first `##` heading after the title) with
  `## Glossary`: one `###` heading per term in the issue's order, each followed by at most
  two lines of plain text.
- **FR-002**: The first prose use of each glossary word on `README.md`, `docs/site/index.md`
  and `docs/site/daily.md` MUST be a link to that term's anchor.
- **FR-003**: Every header, question and option description in `interview.QUESTIONS` MUST
  lead with plain words; a WUWEI term may appear only after the first `(`.
- **FR-004**: Interview labels, ids, scopes, free-text rules and effects MUST NOT change.
- **FR-005**: `goals edit` and `voice edit` MUST print one success line on stdout naming
  what was saved or that nothing changed; failure output and exit codes stay as they are.
- **FR-006**: `daily.md` MUST show the clean output of `setup --shadow` (section 2) and of
  the first plan (section 3), with machine-specific values as `<...>` placeholders, and the
  lines that mean failure.

### Key Entities

- **Glossary entry**: a `###` heading (the term) and one or two lines; its anchor is the
  heading lowercased with spaces as hyphens (`trust-surface`, `host-terminal`, `cap`).

## Success Criteria

- **SC-001**: All 19 terms defined in one place, each reachable by one click from its first
  use on the three entry pages.
- **SC-002**: No interview question or option shows a WUWEI term before its plain-word
  effect.
- **SC-003**: A newcomer can compare each setup and first-plan step with the docs and see
  `saved`, `Applied`, `Next:` or `planned 1/1` when it worked.
- **SC-004**: Full suite passes; no existing test assertion loosened.

## Assumptions

- Interview labels stay as they are. They are the recorded answer and the `--answer` value,
  and today's `interview.json` is re-validated by label (`interview.py:258-279`); renaming
  them would need aliases. The plain words go into the header, question and description,
  which is what the owner reads next to each label.
- "Two lines each" means at most two source lines per entry body; no character limit.
- "Exact output" means the real text a clean run prints today, with values that differ per
  machine or run (paths, free memory, digest, dates) as `<...>` and long repeated blocks
  (the config diff, calibration JSON, credential lines) cut with a `...` line. The markers
  listed in the acceptance scenarios are pinned verbatim and checked against the CLI source.
- The walkthrough covers install, setup and the first plan with output; the build, review
  and merge steps already in sections 4 to 6 stay as they are. "From install to first
  merge" in the title is met by that existing path.
- #356, #360 and #365 (same waves) change setup's tail lines and the morning gate. Whichever
  lands after this issue updates the daily.md output blocks; the marker test makes the drift
  fail loudly. `daily.md` lines 56-62 (the interview paragraph #356 edits) are not touched here.
- The site is still Jekyll; links use `concepts.html#<anchor>`. #392 converts `.html` links
  to `.md` after this issue; the link check accepts both.
- `plan approve` stays silent; the status line and `bin/wuwei next` are the success signal
  shown for it. Not asked for by F19 or F25.
- The terms check for the interview uses the glossary words plus `floor`, `control plane`,
  `control-plane`, `deploy.deny` and `one-way`; `owner.name` and `merge_deploys` may stay as
  config names after the plain words.
