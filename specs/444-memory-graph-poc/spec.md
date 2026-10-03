# Feature Specification: Memory graph proof of concept

**Feature Branch**: `444-memory-graph-poc`

**Created**: 2026-10-03

**Status**: Ready

**Input**: GitHub issue #444, "spike(memory): proof of concept for a derived knowledge graph over the records: four hypotheses measured on a seeded corpus against the grep baseline and the harness memory, with a build, park or drop conclusion". Owner, 2026-10-03: "transform as a PoC: we select some hypotheses and then we make a conclusion."

## Context

The owner asked whether WUWEI memory should live in graph form so history is easier to
search and link. The answer taken was "the graph is an index, not the store", and the
owner then reframed the item as a time-boxed spike: before anything ships under `cli/`,
four hypotheses are measured on a seeded corpus and a document concludes build, park or
drop. Same shape as the Codex spike (#261, `docs/specs/2026-09-30-codex-plugin-spike.md`),
with one difference: this spike has runnable throwaway code and one test that keeps it
runnable.

No failure to reproduce: the issue is a spike, and the notes name no dry-run workspace.
What the spec author checked on `main` instead, because it shapes the corpus and the
conclusion:

- Today's records do not carry three facts the golden questions need. `pr.raised` carries
  `pr`, `item` and optionally `head` and `reviewers` (`cli/wuwei/state.py:363`), not the
  files a PR touched; there is no revert event kind; incidents exist only as merge breaker
  fingerprints in state (`cli/wuwei/merge.py:365`), not as records. The corpus adds these
  as marked synthetic extensions, and the document must say which question types depend on
  them.
- `wuwei why <item>` (#312, `cli/wuwei/commands/why.py`) already walks an item's events
  across days, including `decision.reversed`. The planner's real baseline for item-centric
  questions is therefore better than grep. The issue fixes grep as the measured baseline;
  the document names `why` where it already answers a question type.
- #443 (the CLAUDE.md export and the week digest) is not on `main`. H4 measures a
  simulated export built from the shape #443 specifies.
- #421's consolidate budget is "10 seconds of wall time per run and 20 MB per
  `events.jsonl`" (design 5.13); H3 uses exactly those two limits.

## User Scenarios & Testing

### User Story 1 - Measure the four hypotheses (Priority: P1)

The owner (or a reviewer) runs one command on a generated corpus and sees four tables, one
per hypothesis, each ending with its threshold marked supported, unsupported or
unmeasured, and the conclusion the pre-registered rule gives.

**Why this priority**: the conclusion is only as good as the numbers; without the runner
there is no evidence.

**Independent Test**: run the runner on a small corpus and read the four tables.

**Acceptance Scenarios**:

1. **Given** the runner on the generated 90-day corpus, **When** it completes, **Then**
   four tables print (H1 answers, H2 briefs, H3 cost, H4 overlap), each with its
   threshold marked supported, unsupported or unmeasured, followed by one conclusion line
   naming build, park or drop.
2. **Given** a Python build without FTS5 (or the fallback forced), **When** the runner
   runs, **Then** the tables still print, using the plain `LIKE` search, and the output
   names the search mode used.
3. **Given** an error while generating, indexing or querying, **When** the runner stops,
   **Then** it exits 2 with the reason and prints no verdict.

### User Story 2 - Decide build, park or drop (Priority: P1)

The owner reads one spike document with the method, the four tables, the threats to
validity, one conclusion and a decision record, and answers it as a decision widget
(#359).

**Why this priority**: the owner's question is answered by the decision, not the code.

**Independent Test**: read the document; evaluate its decision record with the existing
decision evaluator.

**Acceptance Scenarios**:

1. **Given** the spike document, **Then** it ends with exactly one conclusion (build,
   park or drop) and a decision record in the `wuwei decision template` shape that the
   decision evaluator accepts, recommending the option the conclusion names.
2. **Given** the diff, **Then** nothing was added or changed under `cli/`, `adapters/`,
   `hooks/`, `skills/`, `agents/`, `charters/` or `templates/`.
3. **Given** the conclusion is build, **Then** the document carries the follow-up issue
   text with the reduced scope; **given** park or drop, **Then** the document says this
   issue closes with the document linked. (Filing and closing are done by the
   orchestrator, not the builder.)

### Edge Cases

- A golden question whose expected records are only partly in the top 5 counts as not
  answered (no partial credit).
- A hypothesis that cannot be measured within the time box (H2's seat behaviour needs a
  live paid run) is printed as unmeasured and counted unsupported; it is never shown as
  supported.
- The corpus is regenerated from a fixed seed: two runs on the same machine print the
  same answer rates, token counts and verdicts (wall times differ).
- A planted answer phrase must appear only inside its expected set; if noise ever
  contains it, the generator raises and the corpus test fails.
- The rebuild check compares index contents, not file bytes, so a SQLite page layout
  difference does not count as a different index.

## Requirements

### Functional Requirements

- **FR-001**: All PoC code lives under `scripts/poc/memory-graph/` and is stdlib only
  (`sqlite3`, `re`, `random`, `json`, `time`, `hashlib`, `tempfile`). Nothing under `cli/`
  imports it. The PoC may import from `cli/wuwei` (for the token estimator and the
  decision evaluator).
- **FR-002**: A corpus generator writes a synthetic `.wuwei/` workspace of N days
  (default 90) in the record shapes on `main` (day directories with `events.jsonl`,
  `decisions/D-n.md`, `briefs/`, `retro/`, `report.md`, `proposal.json`; charter
  overrides and `memory/ledger.jsonl`), plus the three marked synthetic extensions (files
  on `pr.raised`, a `pr.reverted` event, `incidents/INC-n.md`). Volumes per 90 days: about
  120 items, 300 decisions, 400 PRs, 60 lessons, 20 incidents, 200 tickets, scaled with N.
  Names are neutral.
- **FR-003**: The generator also returns a golden set of 30 questions, six of each type
  (why a setting changed, what touched a file, which lesson applies to a symptom, who
  reverted a PR and why, which decisions on an item were reversed). Each question carries
  its words, its graph query form, its expected records (path and line) and one answer
  phrase that appears verbatim in at least one expected record and in no record outside
  the expected set.
- **FR-004**: An index builder derives a SQLite graph from the records: typed nodes
  (item, decision, pr, file, lesson, retro, incident, ticket) with a title, record path and line
  and an excerpt; typed edges (decided_in, supersedes, closed_by, touches, reverted,
  caused, learned_from, mentions) with the record path and line they came from. FTS5 when
  available, `LIKE` otherwise. Two builds from scratch hold identical contents.
- **FR-005**: Two graph queries exist: `ask(words)` (full text over titles and
  excerpts, top 5 hits with path and line) and `around(node, hops)` (the subgraph within
  N hops). No `path` query (no golden type needs it; the document says so).
- **FR-006**: A baseline simulates the planner today: a case-insensitive `grep -rn` over
  the workspace for the question's words, files ranked by hit count, the top 5 read in
  full; grep output counted up to its first 100 lines.
- **FR-007**: H1 table: per question type and in total, answer rate (all expected
  records in the top 5), tokens to read and wall time, for baseline and graph. Supported
  when the graph's answer rate is at least 25 points higher or its tokens at most half
  the baseline's.
- **FR-008**: H2 table: for 10 fixture items with prior decisions, brief length without
  and with the `around` subgraph (cut to a line budget of a fifth of the brief), prior
  decisions visible in each, and asks and re-decisions. Asks and re-decisions need a live
  seat and print as unmeasured, so H2 is unmeasured and counted unsupported.
- **FR-009**: H3 table: for a corpus four times N days, build wall time, largest
  `events.jsonl`, index size, node and edge counts, and whether a second build from
  scratch is identical. Supported when build time is at most 10 s, the largest
  `events.jsonl` at most 20 MB, the index under 50 MB and the rebuild identical.
- **FR-010**: H4 table: per question type and in total, the fraction of golden
  questions whose answer phrase appears in a simulated #443 export (charter rule lines
  plus a digest of the last 7 days: decisions with context and outcome, retro lessons,
  incident titles). Over half means the graph is not needed for a solo owner.
- **FR-011**: One pre-registered conclusion rule, printed by the runner: drop when H1 is
  not supported; park when H1 is supported but H3 is unsupported or H4 is over half;
  build otherwise. H2 changes only the build scope (briefs get the subgraph only if H2 is
  supported).
- **FR-012**: The runner (`python3 scripts/poc/memory-graph/run.py`) prints the search
  mode, the four tables and the conclusion line and exits 0; on any error it exits 2 with
  the reason. A `--days N` option sets the corpus size and `--no-fts` forces the
  fallback.
- **FR-013**: The spike document `docs/specs/2026-10-03-memory-graph-poc.md` holds the
  method, the four tables as printed (with date, Python and SQLite versions and search
  mode), the threats to validity, one conclusion with what build would be reduced to
  what the numbers support, and a decision record ending the document.
- **FR-014**: One test file keeps the PoC runnable and honest: the runner completes on a
  small corpus in both search modes and exits 2 on an index error; the golden set is
  consistent with the corpus; the graph answers planted questions and rebuilds
  identically; the threshold and conclusion rules hold on a table of cases; the spike
  document's decision record evaluates and matches its conclusion.

### Key Entities

- **Corpus**: a generated workspace; records only, no state machine. Deterministic from a
  fixed seed.
- **Golden question**: type, text, words, query form, expected records, answer phrase.
- **Graph**: nodes and edges derived from the records; deleting it loses nothing.
- **Verdict**: per hypothesis, supported, unsupported or unmeasured, from its threshold.
- **Conclusion**: build, park or drop, from the rule in FR-011.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The runner prints all four tables and a conclusion on the 90-day corpus in
  under 60 seconds on the owner's machine.
- **SC-002**: The PoC test file runs in under 5 seconds.
- **SC-003**: Every golden question's expected records exist at the expected lines and
  its answer phrase occurs only inside its expected set (30 of 30).
- **SC-004**: The spike document is under 1800 words and ends with one conclusion and a
  decision record the existing evaluator accepts.
- **SC-005**: The diff touches only `scripts/poc/memory-graph/`,
  `tests/test_memory_graph_poc.py`, `docs/specs/2026-10-03-memory-graph-poc.md` and
  `specs/444-memory-graph-poc/`; the full suite passes.

## Assumptions

- The corpus is generated by a seeded script, not by running the headless fixture day:
  that day needs a paid Claude run and yields one day. "Generated from the fixture day
  shapes" is read as using the record shapes the fixture day writes.
- The golden set and the corpus are written before the extractor and the queries (task
  order), so the questions are not tuned to the graph. They are still written by the same
  author as the graph; the document lists this as a threat.
- A question is answered only when every expected record path is in the top 5; the
  expected line is checked by the corpus test, not by the answer rate.
- Token cost uses the product's estimator (`wuwei.memory.estimated_tokens`, characters
  divided by 4). The graph pays for its printed hits plus reading its top 5 records in
  full, the same reading cost the baseline pays (conservative); an excerpts-only graph
  number is printed beside it as the optimistic bound and is not used by the threshold.
- The grep output cap of 100 lines stands for a planner narrowing a long grep; without
  a cap the baseline's tokens grow with the corpus and favour the graph.
- H2's behavioural measures (asks, re-decisions) need a live seat per item and per
  variant (20 paid runs); they are out of the time box, so H2 is unmeasured and counted
  unsupported, as the issue allows. The brief lengths and prior-decision visibility are
  measured offline and reported.
- "Fits the consolidate budget from #421 (10 s, 20 MB)" is read literally from design
  5.13: 10 s of wall time per run and 20 MB per `events.jsonl`. Peak memory is not
  measured.
- The #443 export is simulated: charter rule lines verbatim plus a digest of the last 7
  days of records. A question counts as answered when its answer phrase appears in that
  text.
- H4 over half maps to park (the graph is not needed while the owner works solo; a team
  workspace is the revisit trigger), not drop.
- Changed in build: a `retro` node type and a ledger `lesson` key were added (a lesson
  question expects its retro record, which no node could cite otherwise); a reversed
  question expects the second decision's Context line, where its answer phrase is; item
  nodes come from proposal candidates only; noise includes 10 reverts per 90 days.
- Identical rebuild means the same SQL dump (`iterdump`) hash, not the same file bytes.
- The decision record in the document uses the `wuwei decision template` fields with
  options build, park ("Defer") and drop ("Do nothing"), `Decided-by: owner` and
  `Outcome: pending`; the orchestrator presents it with `decision.record_widget` and
  records the owner's answer. The builder files and closes nothing (no `gh`).
- The constitution's strict mode adds clarify, analyze and checklist; this pipeline's
  brief assigns specify, plan and tasks to the spec author. Only the specify quality
  checklist (`checklists/requirements.md`) is written here; no `analysis.md`.
- Release packaging copies `docs/` but not `scripts/`, so the PoC code does not ship and
  the document does.

## Deferred

- Everything in the issue's "Original scope" (the `wuwei memory` commands, the brief
  integration, the board counts, the hook import test): only filed as a follow-up if the
  conclusion is build.
- Recording the files a PR touched, a revert event and incident records in real records:
  a prerequisite of any build that answers the "touched" and "revert" question types; the
  document names it in the build scope if build is concluded.
