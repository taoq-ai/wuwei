# Feature Specification: Decision lint and question guard

**Feature Branch**: `078-decision-lint`
**Created**: 2026-09-28
**Status**: Ready
**Input**: Issue #78, M1 Guards, design sections 5.8 and 5.4.

## User Scenarios & Testing

### User Story 1 - Trust the recommendation (Priority: P1)

A seat records its alternatives and evidence before acting or asking the owner.
The evaluation filters by musts and recomputes weighted wants.

**Independent Test**: Lint a saved decision with known scores.
**Acceptance Scenarios**:
1. Given a recommendation scoring 20 and another passing option scoring 80,
   when lint runs, then it refuses and names both options and scores.
2. Given a complete record recommending a top passing option, lint accepts it.
3. Given a missing field or fewer than two options, lint refuses with reasons.
4. Given a decision write through any supported file tool or relevant Bash command,
   an invalid record is returned to the seat. A rejection event is appended for a file
   tool or a normalized Bash target naming that file; day scans only give feedback.

### User Story 2 - Ground owner questions (Priority: P1)

An owner decision question must cite a valid decision for today. Morning gates and
clarifications use the narrower forms below (G1, owner may overrule).

**Independent Test**: Submit question hook payloads with and without valid citations.
**Acceptance Scenarios**:
1. Given AskUserQuestion without a valid citation or morning-gate exemption inside a
   workspace, it is refused.
2. Given a cited record that exists today and passes lint, the question is accepted.
3. Given a missing, stale, unreadable or invalid cited record, the question is refused.
4. Given an unrelated project, questions and writes pass untouched.
5. Given a question whose header or text starts with `Morning gate` and whose text cites
   today's existing plan file, it is accepted without a decision record.
6. Given a cited `C-<n>` record for today with Question, Context and at least two Options
   lines, and no scoring table or other fields, it is accepted as a clarification.
7. Each question in a batch must independently qualify; `D-<n>` still requires the full
   Kepner-Tregoe record.

### User Story 3 - Decide at the right level (Priority: P2)

Seats decide reversible changes confined to their own item and log the outcome.

**Independent Test**: Route saved decisions with different reversibility and blast radius.
**Acceptance Scenarios**:
1. Given a two-way door inside the item's branch or PR, routing returns seat and logs it.
2. Given scope agreed with others, routing returns owner.
3. Given uncertainty, a one-way door or a wider blast radius, routing returns owner.
4. Generic state writes cannot change recorded decision outcomes, and generic event
   writes cannot append any `decision.` event kind. No outcome subcommand exists.

### Edge Cases

Duplicate fields, malformed matrices, invalid weights or scores, unknown option ids,
no passing options, ties, missing cells, commented or fenced examples, symlink targets,
Bash wrappers and opaque snippets, unavailable event persistence, and multiple questions.

## Requirements

### Functional Requirements

- FR-001: Require Question, Context, Options, Musts, Wants, Recommendation, Confidence,
  Reversibility, Blast radius, Pre-mortem, Revisit, Decided-by and Outcome.
- FR-002: Require two distinct options including doing nothing or deferring, complete
  pass/fail must evaluations and complete integer wants with weights 1..10, scores 0..10.
- FR-003: Recommend only an option passing every must with the maximal weighted sum.
- FR-004: Lint saved decision writes and append decision.rejected events on attributable
  rejection only. Bash day scans and citation checks give feedback without events.
- FR-005: Require valid current-day citations for each owner question. Expose this
  validation for future control-plane escalations. Allow the morning-gate and clarification
  forms described above.
- FR-006: Scope file guards by resolved target, and questions by cwd. Include configured
  repositories and their worktrees when a workspace anchor is available.
- FR-007: Only `decision route` produces seat outcomes; reserve decision_outcomes for
  that path and every `decision.` event kind for dedicated writers.

### Key Entities

Decision: daily id, evidence, alternatives, evaluations, recommendation and routing fields.
Outcome: decision id, selected option, deciding actor, outcome, date in the day state.
Rejection: event with file and reasons.

## Success Criteria

- All acceptance scenarios are automated and pass without network or real external tools.
- Every lower-scoring recommendation is refused with both computed scores.
- Every ungrounded in-scope owner question is refused; unrelated projects pass.

## Assumptions

- Markdown field labels and tables form the canonical shape, documented in contracts.
  Question, Recommendation, Confidence, Reversibility and Decided-by occupy one line.
  Prose fields (Context, Blast radius, Pre-mortem, Revisit, Outcome) may continue across
  lines. Trailing Consequences and Notes sections are allowed. Tables may omit outer
  pipes; must pass/fail values are case-insensitive.
- Clarifications use `days/<date>/decisions/C-<n>.md` under `.wuwei`, with one-line Question,
  nonempty Context and two or more distinct Options lines. Repeated `Options:` labels or
  a list under `Options:` are accepted. No musts, wants or scoring table are required or
  allowed. Missing, stale, unreadable or symlink-escaped records are refused.
- Morning gates cite `days/<date>/plan.md`, `.wuwei/days/<date>/plan.md` or the absolute
  current-day plan path in the question text. The plan must exist without a symlink escape.
- Ties allow any maximal passing option. At least one must and want are required.
- Outcome may be `pending` before a decision; Decided-by names its intended actor.
- `unsure` reversibility is accepted but routes to owner. Only exact `own branch` or
  `own PR` blast-radius declarations qualify for seat routing; other prose routes owner.
- Workspace discovery uses ancestors or WUWEI_WORKSPACE, as existing guards do.
- Bash mentions of D- trigger today's decision scan; normalized targets establish
  workspace scope and identify files eligible for rejection events. Unsupported relevant
  commands fail closed with a decision-record hint; irrelevant commands pass before parsing.
- Existing hooks (#6), verdict text filtering (#13), state and VCS ports are reused.

## Deferred

M5 control-plane wiring, digests, steward metrics and sampling. The shared citation check
is available for M5. Owner outcomes must come from a hook-produced source, the
AskUserQuestion PostToolUse answer or the M5 control plane. That producer is out of scope;
agent-supplied outcome commands cannot stand in for owner answers. No global workspace
registry is introduced.
