# Feature Specification: Plain tone

**Feature Branch**: `522-plain-tone`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #522: WUWEI reads too heavily. A plain-language pass over reasons,
cards, skills, charters and docs, with a measurable rule (short sentences, plain words, no
stacked nominalisations) and a lint that keeps it.

Owner, 2026-10-05: "I have been noticing the framework tone in general overly formal. I like
that it is very professional, but it reads too heavily."

## Root cause

Nothing in WUWEI measures how heavy a text is, so nothing stops it growing:

- `charters/_common-authoring.md:15-28` (Writing for a person) bans the mechanical tells and
  names the humanizer. It says nothing about sentence length, one idea per sentence, verbs
  over nouns or plain words, and seats follow the checklist they are given.
- `cli/wuwei/outward.py:29-46` (`TELLS`, `tells`) is the only text lint. It matches fixed
  phrases. It never counts words per sentence or nominalisations.
- `tests/test_reasons.py` (#362) checks that every reason names a next step and uses the
  right pronoun, but not its length. `cli/wuwei/guards/protect_state.py:81-84`
  (`('config', 'set')`) is one 46-word sentence and passes.
- There is no `wuwei lint` command (`cli/wuwei/commands/` has only `decision lint`,
  `memory lint` and `verdict lint`), so neither the owner nor the suite has a number to hold.
- The texts grew one feature at a time, mostly as semicolon chains. A rough count on the base
  (a sentence ends at `.`, `!` or `?`, and at a list item, table cell or blank line) finds 112
  sentences over 35 words in `docs/site/*.md` and `README.md`, 9 in the charters, 8 in the
  four skills and 1 in the reason literals. The morning gate card's Approve text is one
  semicolon-joined sentence (`cli/wuwei/plan.py:257-265`).

## User Scenarios and Testing

### User Story 1: The lint reports the numbers (Priority: P1)

A maintainer runs `bin/wuwei lint tone docs/site README.md`. Each file gets one line with its
average and longest sentence, its count of sentences over 35 words and its nominalisation
count. The command exits 1 when a file breaks the rule, so a heavy text shows up before
review.

**Independent Test**: markdown files in `tmp_path`, `main(['lint', 'tone', ...])`, no
workspace.

**Acceptance Scenarios**:

1. **Given** a markdown file whose sentences average 12 words with none over 35, **When**
   `wuwei lint tone <file>` runs, **Then** it exits 0 and prints
   `<file>: average 12.0 words, longest <n>, 0 over 35, <s> sentences, <k> nominalisations (<r> per 100 words), at the rule`.
2. **Given** a file with one 36-word sentence, **When** the lint runs, **Then** it exits 1,
   and that file's line says `1 over 35` and ends `over the rule`.
3. **Given** a directory, **When** the lint runs on it, **Then** it measures every `*.md`
   file under it in sorted order and prints a `total:` line over all of them.
4. **Given** a path that does not exist, or a directory with no `*.md` file, **When** the
   lint runs, **Then** it exits 2 and the reason names the path and says to pass a markdown
   file or a directory of them.
5. **Given** the base before the pass, **When** the lint runs over the skills, charters,
   `docs/site` and `README.md`, **Then** it reports the numbers, and they become the before
   column of the table in `research.md`.

### User Story 2: The suite holds every text class to a budget (Priority: P1)

A later feature adds a 40-word sentence to a charter. The suite fails and names the class and
its numbers. One existing long sentence in the reference pages does not fail it while that
class stays within its count.

**Independent Test**: `tests/test_tone.py` measures five classes with the lint's own
`measure` function.

**Acceptance Scenarios**:

1. **Given** the classes reasons (every reason literal `tests/test_reasons.py` collects),
   cards (the literal questions and option descriptions of every `widget(` call, plus the
   questions and choice descriptions in `interview.QUESTIONS`), skills
   (`skills/*/SKILL.md`), charters (`charters/*.md`) and docs (`docs/site/*.md` and
   `README.md`), **When** the budget test runs after the pass, **Then** each class averages
   under 20 words a sentence, has no more sentences over 35 words than its budget, and has
   no more nominalisations per 100 words than its budget.
2. **Given** a 40-word sentence added to any charter, **When** the budget test runs,
   **Then** it fails and the message names `charters` and its numbers.

### User Story 3: What the owner reads is at the rule (Priority: P1)

The owner asks why something was refused and answers cards. Each text is short and plain.

**Independent Test**: a fixture day in `tmp_path`, real guard and card functions, each text
measured with `measure`.

**Acceptance Scenarios**:

1. **Given** a seat's Write to the day's `state.json` refused through the PreToolUse hook (the
   records floor, refused under every posture), **When** `wuwei why last refusal` runs,
   **Then** no output line is over 35 words and the lines average under 20.
2. **Given** a fixture day with a proposal, an open item and the calibration interview,
   **When** the morning gate card (`plan.gate_widget`), the close card
   (`commands/close.widget`) and the first interview card (`interview.widgets`) are
   rendered, **Then** in each card the question and every option description have no
   sentence over 35 words and average under 20, and none says "the owner".

### User Story 4: The pass rewrites the texts to the rule (Priority: P1)

The texts named in the issue read at the rule with their meaning unchanged.

**Acceptance Scenarios**:

1. **Given** the pass, **When** the lint runs on `docs/site/concepts.md`,
   `docs/site/daily.md`, `README.md`, each `skills/*/SKILL.md` and each `charters/*.md`,
   **Then** each exits 0 (at the rule).
2. **Given** the pass, **When** the full suite runs, **Then** it passes. Every test that
   asserted a rewritten text asserts the new text with the same meaning, and no assertion is
   deleted to make room.
3. **Given** a changed charter, **When** `bin/wuwei agents check` runs, **Then** it reports no
   drift (agents regenerated), and the charter's patch version is bumped.
4. **Given** a rewritten reason, **When** it is read, **Then** it keeps the #362 shape (what
   happened, then `; ` and the next step) and the pronoun rule (seat-facing reasons say "the
   owner", person-facing ones say "you").

### Edge Cases

- Front matter, fenced code blocks, HTML comments and headings are not prose and are not
  measured. Inline code counts as one word. A link counts as its text.
- A table cell and a list item each end a sentence, so a reference table does not read as one
  sentence. The separator row is skipped.
- A semicolon does not end a sentence (A1).
- A `{}` placeholder in a reason or card literal counts as one word.
- A file named directly is measured whatever its suffix; a directory yields only its `*.md`
  files.
- Outside a WUWEI workspace the lint runs the same: it reads only the paths it is given.

## Requirements

### Functional Requirements

- **FR-001**: `charters/_common-authoring.md` gains a `## Plain tone` section: one line that
  names `bin/wuwei lint tone <path>`, then five numbered rules: sentences under 20 words on
  average and none over 35; one idea per sentence; verbs over nouns ("close measures it", not
  "the measurement by close"); the plain word (use, run, send, ask) and no qualifier chains;
  the owner is "you" in docs and cards and "the owner" in seat-facing reasons (#362).
- **FR-002**: `cli/wuwei/commands/lint.py` provides `measure(*texts)`, measuring each text on
  its own and returning the totals: sentences, words, average, longest, over (the count over
  35) and nominalisations. The command `wuwei lint tone <path>...` prints one line per file
  and a `total:` line when it measures more than one file. Exit 0 when every file is at the
  rule (average under 20, none over 35); 1 when any file averages 20 words or more or has a
  sentence over 35; 2 with a reason when a path is unreadable or yields no file.
- **FR-003**: `lint tone` is read-only. It is in `commands.READ_ONLY`, in the Plumbing help
  group and in the `docs/site/reference.md` command table.
- **FR-004**: `tests/test_tone.py` holds the five class budgets as constants. The docs class
  over-35 budget is the count the docs pages outside the pass carry on the base; every other
  class's over-35 budget is 0. Each nominalisation budget is the after-pass rate rounded up to
  one decimal and is not above the before rate.
- **FR-005**: The pass rewrites, meaning unchanged: every reason with a sentence over 25 words
  and every guard reason under `cli/wuwei/guards/`; the card questions and descriptions in
  `widget(` calls and `interview.QUESTIONS`, with the gate card's Approve text as short
  sentences; the four skills; every charter (patch version bumped, agents regenerated);
  `docs/site/concepts.md`, `docs/site/daily.md` and `README.md`.
- **FR-006**: `specs/522-plain-tone/research.md` holds the before and after table (average,
  longest, over 35 and nominalisations per 100 words for each class) for the pull request.

## Success Criteria

- **SC-001**: After the pass every class is within its budget. Reasons, cards, skills and
  charters have no sentence over 35 words.
- **SC-002**: concepts.md, daily.md and README.md average lower than before and have no
  sentence over 35 words.
- **SC-003**: The full suite passes with no assertion removed.

## Assumptions

- **A1**: A semicolon is not a sentence boundary. Most of WUWEI's long sentences are
  semicolon chains, and splitting on them would hide the weight the owner named.
- **A2**: A nominalisation is a word of at least seven letters ending in `tion`, `sion`,
  `ment`, `ance`, `ence`, `ness` or `ity` (plural allowed). The suffix heuristic has false
  hits ("comment", "decision"), but it is only compared with itself over time, so the budget
  is a rate per 100 words, not a ban. The code marks it with a `ponytail:` comment.
- **A3**: Stacked nominalisations are not counted separately. The count per file plus the
  written rule covers them; a stacking metric waits for evidence that the count misses them.
- **A4**: The docs class budget allows the long sentences in docs pages outside the pass
  (reference, configuration, security and the rest) at their base count. The suite catches
  growth without failing on one existing long sentence. Bringing those pages to zero is a
  follow-up.
- **A5**: The reasons pass covers reasons with a sentence over 25 words (about 40 on the
  base) and the guard reasons (about 200), which are the refusals the owner reads through
  `wuwei why`. The other reason literals are held by the budget, not rewritten one by one.
- **A6**: The card class measures literal text. Card text built from records (a decision's
  Question) is written by seats under the new charter rule, so the rule covers it, not the
  budget.
- **A7**: The lint lives in the command module (`commands/lint.py`) with no new core module:
  the command and one test are its only callers.
- **A8**: `lint tone` goes in the Plumbing help group: the suite and maintainers run it, and
  it stays out of the owner's default help.
- **A9**: A changed charter gets a patch version bump (meaning unchanged), so
  `init --upgrade --dry-run` flags local overrides for review as it does for any charter
  change.
- **A10**: No guard, refusal or posture behaviour changes (#530 unaffected), and no planner
  path changes (#551 unaffected). The lint never refuses anything; it is a read-only report.
- **A11**: The rule's numbers (20 average, 35 longest) are constants in `commands/lint.py`,
  not config: they never change per workspace.

## Deferred

- Bringing `docs/site/reference.md`, `configuration.md`, `security.md` and the other pages
  outside the pass to zero sentences over 35 words (follow-up issue linked to #522).
- Running the tone measure on drafts or outward text in the humanizer lint.
