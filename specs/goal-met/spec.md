# Feature Specification: a plan pass offers a goal as met when its date passed

**Feature branch**: `feat/goal-met`
**Item**: goal-met (issue #975), tier full, goal G-1
**Input**: a dated goal with a stale target is what the 2026-10-18 pass found. The plan should
surface it at each pass, not leave it to the lead by chance.

## The promise in my words

1. `wuwei plan pass` reads `.wuwei/goals.md`. For each goal block named `G-n` whose `Date:` is an
   ISO date before today, and which the owner has not ruled met, it prints one line:
   `goal G-n dated <d>: ask the owner 'goal: G-n met? <evidence>'`. The planner replaces
   `<evidence>` with what the measure shows; WUWEI does not read the measure.
2. When the owner answers a question that starts `goal: G-n met?`, the PostToolUse hook records a
   `ruling` row with `kind: goal.met`, the goal id, the goal's Outcome as goals.md holds it then,
   `approved` (the yes words the hook already reads), the question and the answer. A ruling counts
   only while goals.md still holds that Outcome under that id, so a goal the owner rewrites in place
   is a new goal and is offered again. A no keeps the goal open. The pass does not offer it again
   until the owner moves its date past the day of the no.
3. The day report prints `Met goals: <ids>` (or `none`). The lead charter says a met goal gets no
   new candidates. Nothing this change adds writes `goals.md`; only the owner changes it.

Runtime lines: +13, within the item's budget of 13 (2,986 at 3d2eb29, 2,999 at the head, the
same after arch round 1).

The acceptance scenarios, restated:

1. goals.md holds a goal dated yesterday with no ruling; `wuwei plan pass` prints the goal: line once
   for it.
2. The owner answers yes to `goal: G-2 met? ...`; PostToolUse records a ruling goal.met G-2 and the
   report lists G-2 as met.
3. The owner answered no; the next plan pass on the same date does not offer G-2 again.

## How this fails

1. The planner writes `goal: G-2 met?` and then proposes the opposite in the evidence ("Not yet;
   move the date to 11-01?"). A yes then records the goal as met. The ruling keeps the question and
   the answer, so the audit shows what the owner read; the hook's note names what was recorded, so
   the planner sees a misread at once and can re-ask.
2. The owner answers in free text such as "Met" or "Done", which the hook's yes words do not cover.
   The goal is recorded as open and held until its date moves. The note says "recorded as open";
   the skill tells the planner to offer Yes and No.
3. A goal's Date is not ISO ("23 Oct 2026", "end of Q4"). The pass never offers it. The setup
   template and every goal in this repository use ISO dates; a non-ISO date stays silent rather
   than being offered on a wrong day.

## Clarifications

### Session 2026-10-18

- Q: Which question shape does the hook read? A: `\s*goal: *(G-[0-9]+) met\?` at the start, any
  case. The goal id is the one the owner reads first; later text (`and G-3 met?`) records nothing
  for G-3. ASCII digits only, so an Arabic-Indic digit after `G-` records nothing.
- Q: Does the guard change? A: No. `goal:` takes any wording; a goal question in another shape is
  recorded as a prompt only, and the pass offers the goal again. Refusing near shapes would also
  refuse real goal questions that mention "met" (a target change).
- Q: What does "after its date moves" mean in the ledger? A: The no's ruling carries its day (the
  row's UTC timestamp). The pass holds a goal while a no was given on or after its date. When the
  owner moves the date past the day of the no, and that date passes, the pass offers it again.
- Q: A no given before the date (an early ask the pass did not make)? A: It does not hold the goal
  once the date passes, because the owner has not yet answered for that date.
- Q: Which ruling counts when there are several? A: The latest per goal, so a later no reopens a
  goal once ruled met.
- Q: The owner rewrites the G-1 block in place with a new outcome and date. Is the new G-1 met?
  A: No. The ruling keeps the Outcome it answered, and a ruling counts only while goals.md holds
  that Outcome under that id (arch round 1). The report's `Met goals:` line reads the goals in
  goals.md, so a goal removed from the file or rewritten no longer shows as met. A no recorded
  against the old Outcome does not hold the new goal either.
- Q: Which goal names are offered? A: Only `G-n` headings, the shape the hook records. Another
  heading would be asked every pass and never recorded.
- Q: Does any other consumer read a goal.met ruling? A: `evidence.py` reads rulings with
  `kind == 'breaking'`, `kind == 'exception'` or no kind with a `pr`; `report.learning` reads
  `kind == 'exception'`. A goal.met row has a kind and no `pr`, so none of them picks it up.

## User Scenarios & Testing

### US1: the pass offers a goal past its date (P1)

Acceptance 1, plus: a goal dated today or tomorrow, an empty or non-ISO date, a non-`G-n` heading,
a goal ruled met before or after its date, a no on the goal's own date, a lowercase heading
(`## g-10`) ruled met and a month-only date (`Date: 2026-10`) are each not offered. A lowercase
heading with no ruling is offered under its upper-case id.

### US2: a yes records the goal as met and the report lists it (P1)

Acceptance 2, through Claude's AskUserQuestion and Codex's request_user_input. Two goals ruled met
are both listed. A goal the owner rewrites in place (new Outcome and date) is offered again, and
the report no longer lists it as met.

### US3: a no holds the goal until its date moves (P1)

Acceptance 3, plus: the owner moves the date to the day of the no (still held), then past it
(offered again).

### US4: the hook records exactly what was asked (P1)

A generated set of questions (prefixes x ids x joins x tails x answers), each asked through
`guards.pre_tool` and answered through the hook: no question is refused, and each records exactly
the goal id and yes or no asked, or nothing when it is not in the shape.

### US5: no route moves (P1)

Every route in `tests/fixtures/routes.json` reads the same through `guards.bash` and the PreToolUse
hook at main and at the head.

## Requirements

- FR-001: `wuwei plan pass` prints the goal: line for each `G-n` goal past its ISO date with no
  latest ruling of met and no no on or after its date.
- FR-002: `hook._answers` records `ruling {kind: goal.met, goal, outcome, approved, question,
  answer}` for a non-empty answer to a question in the shape, and adds a note naming what it
  recorded.
- FR-003: `report.day` prints `Met goals:` with the goals in goals.md whose latest ruling for their
  current Outcome is met, in goals.md order, or `none`.
- FR-004: The lead charter gives a met goal no new candidates; the run skill tells the planner to ask
  the printed question.
- FR-005: Nothing this change adds writes goals.md (init and upgrade keep their existing writes).
- FR-006: No route in `tests/fixtures/routes.json` changes verdict or reason.
- FR-007: Runtime grows by at most 13 lines; `.claude/` matches the tree.

## Assumptions

- The yes words stay the hook's shared ones (yes, approve, accept, proceed). Overturned if owners
  answer goal questions in free text often; then "met" could join them for this class.
- The guard stays as it is for `goal:` (any wording). Overturned if a near-shape goal question
  reaches the owner and is lost in practice.
- A no before the goal's date does not hold it after the date. Overturned if the owner wants an
  early no to hold until the date moves.
- The report lists met goals from every day's rulings, not only today's, since a goal outlives a
  day. Overturned if the owner wants only today's.
- A goal is its id and its Outcome text: a ruling holds only while goals.md keeps both. An edit to
  the Outcome text alone (a typo fix) makes the goal due again, and the owner answers once more.
  This fails toward asking. Overturned if owners often reword outcomes without changing the goal.
- Goal ids are not normalised: `goal: G-02 met?` records `G-02`, which matches no `## G-2` heading,
  so G-2 stays offered (under-records, never forges). The pass prints `G-2`, so the planner asks in
  that shape. Overturned if a planner writes padded ids in practice.

## Rollback

Revert the commits. Rulings of kind goal.met already in the ledger stay and nothing else reads
them; goals.md is never touched.
