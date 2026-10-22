# Feature Specification: an owner answer the transcript shows late, or beside a differing answer in its batch, is still recorded

**Feature branch**: `leone/1211-confirm`
**Item**: 1211-confirm, tier full, goal G-2 (taoq-ai/wuwei#1211, its comments of 2026-10-21, the
owner's report of 2026-10-22, and taoq-ai/wuwei#1231, folded in by the lead on 2026-10-22)
**Input**: the item's promise and acceptance (`wuwei plan show 1211-confirm`), the lead's
reproduction of both causes on main 6828776, and two real AskUserQuestion flows of this session.

## The promise in my words

An owner answer counts only when the session transcript shows it (#962, #1172). Two things on main
drop answers the transcript does show:

1. Timing. A Stop that runs before the harness writes the tool_result row waits 1.5 s, then gives
   up for good: it removes the pending answer and records `answer.unconfirmed`. When the row lands
   later nothing records it. After this change a Stop that still finds no row leaves the answer
   pending, and every later planner hook call reads the transcript again. `answer.unconfirmed` is
   recorded only when the tool_result row holds a different answer, or when a named bound (10
   minutes, `hook.BOUND`) passes with no row.
2. Shape. Main compares the whole answers dict, so one differing answer (a free-text Other, or an
   option note) voids every labelled answer in its batch. After this change each question counts on
   its own: a question whose answer the transcript holds is recorded, and only the others are not.
3. The reason says which case held: `no tool_result row in 10 minutes`, or for each differing
   question `the transcript answers '<question>' with '<transcript value>', not '<payload value>'`,
   each cut to 60 characters. The planner's note names only the questions not recorded.

Folded in from #1231 (two label-only answers after a compaction, in a desktop session, reported as
"the transcript holds no AskUserQuestion <id> answered so" while the planner had already acted on
them across several tool calls):

4. `_shown` says which check failed: no AskUserQuestion tool_use with the id (decided at once), no
   tool_result row (pending), a tool_result whose `toolUseResult` holds no answers dict, or which
   question's answer differs. The next ledger row names the cause.
5. A tool_result row with no `toolUseResult.answers` dict is read by its own text, the harness's
   record in the same transcript row: `Your questions have been answered: "<q>"="<label>"`. A pair
   counts only when its question is one the tool_use asked and the pair is followed by the next
   asked question's `, "<q>"=`, or by `.` for the last, so no pair can stretch over its neighbour.
6. An answer that is not recorded never blocks the planner's Stop. The Stop records what it can and
   leaves the rest pending; the next tool call records `answer.unconfirmed` and gives its note as
   context.

The trust boundary stays: an answer counts only when the transcript holds that tool_use id, an
AskUserQuestion tool_use, and that question's exact answer in the last tool_result row for the id. A
replay records nothing more (each id once). Keeping an answer pending longer changes when it is read,
not what counts.

The acceptance scenarios, restated:

1. A plan answer whose tool_result row lands after the planner's Stop waited: the next hook call
   records `prompt` and `plan.approved`, and no `answer.unconfirmed` precedes them.
2. A batch of a `one-way:` question answered in free text and a `plan:` question answered Approve,
   where the transcript's free-text value differs from the payload's: the plan approval is recorded
   and the note names only the one-way question as differing.
3. No tool_result row ever: once the bound passes, one `answer.unconfirmed` with "no tool_result
   row", and the answer is not recorded.
4. A payload whose answers the transcript does not hold records nothing, as on main.
5. (#1231) An AskUserQuestion answered in the same turn after a compaction: when the turn stops,
   the answer is recorded and the stop is not blocked.

## What the real data shows

This session's transcript holds two AskUserQuestion flows answered by label (Claude Code 2.1.308,
2026-10-22): a plan question (tool_use 10:20:15.830Z, tool_result 10:20:18.815Z) and a trust question
(tool_use 10:21:16.267Z, tool_result 10:28:06.881Z). The ledger's `answer.pending` rows for both are
stamped in the same second as the tool_result row, and the `prompt` rows 7 s and 3 s later: for a
label, the payload's answers equal the transcript's, and the next call records them.
`tests/fixtures/transcripts/ask-late.jsonl` holds these four rows with the text replaced
(`specs/1211-confirm/fixtures.py`), and `claude-ask-post-plan.json` the plan payload.

No real free-text answer was recorded: no fixture and no session row holds one. The free-text shape
(`claude-ask-post-free-text.json`) stays reconstructed. The fix holds under either hypothesis for
the 2026-10-21 batch and the 2026-10-22 Re-scope report: if the row came late (cause 1), the answer
now waits for it; if the payload and transcript values differ for the free-text question (cause 2),
the labelled answers in the batch are still recorded and the reason names the one that differs.

## Compaction (#1231)

No compacted transcript was available. This machine's projects folder holds one session file and its
seat transcripts; the only `compact_boundary` text in them is this build's own search commands. So
compaction could not be reproduced from a real transcript, and no evidence shows that it moves rows to
another file; no directory scan is added. Weighing the report: the planner acted on the answers
across several tool calls before the Stop, and each planner PreToolUse rereads the transcript, so
pure timing is unlikely; a record shape or file the check did not expect is more likely. Main gave the
same reason for all of them. The pinned cases: no tool_use row for the id (the file the payload names
lacks the question), a tool_result whose `toolUseResult` is missing, a string or holds a list, the
harness text as a string or as text parts, and a `compact_boundary` row beside the answer row. The
next unrecorded answer names its check, so a real compacted session shows which one held.

## How this fails

1. A harness that writes a free-text answer differently in the payload and the transcript still
   leaves that one answer unrecorded. The note now names it with both values, so the planner can
   see the shape and re-ask only that question, and the next build can capture the row. The
   labelled answers beside it are recorded.
2. A pending answer whose row never comes (a crashed harness, a forged PostToolUse for an id that
   never gets a row) is reread on every planner call for 10 minutes, and each Stop in that window
   waits up to 1.5 s for it. One transcript read per pending entry per call; it ends at the bound
   with one `answer.unconfirmed` row.
3. A forged PostToolUse kept first for a real id while the row is not yet written (the cache keeps
   the first entry) still blocks the real answer: its answers differ, so nothing is recorded and the
   reason names each. Main has the same hole. Once the row is written a forged entry is decided at
   its own call, so the real PostToolUse after it records (the probe's forged-first class). A forged
   entry can only record answers the transcript holds, so it can suppress an answer but never invent
   one.
4. The harness text format for a batch is assumed (`"<q1>"="<a1>", "<q2>"="<a2>". You can now
   continue...`); only single-question rows were seen. If a batch is joined another way, a batch read
   by its text records nothing, loudly ("its text does not match"); a single question still records.

## Clarifications

### Session 2026-10-22

- Q: Where does the free-text shape come from? A: No real one exists (no fixture, no row in this
  session). The payload fixture is reconstructed and marked so; the fix does not depend on where the
  harness puts the typed text.
- Q: What is the bound? A: `hook.BOUND`, 600 seconds from the PostToolUse that kept the answer (the
  cache entry's modification time, which a forged repeat never refreshes). The real flows show the
  row in the same second as PostToolUse; the bound only ends a pending answer whose row never comes.
- Q: Which call records `answer.unconfirmed` for a differing answer? A: Any planner hook call that
  reads the tool_result row. A row is written once; main waited for a Stop only because the whole
  batch had to match.
- Q: What does the `prompt` row hold for a partly recorded batch? A: Only the recorded questions and
  their answers. The `answer.unconfirmed` row holds the payload's answers, the questions not
  recorded and the reason.
- Q: A payload question the transcript does not answer? A: It differs (the transcript value reads
  `None`). A payload with no answer dict, or an empty one, records `answer.unconfirmed` with "the
  payload holds no answer" instead of nothing.
- Q: Does the Stop still wait 1.5 s? A: Yes, so an answer written within it is recorded at the Stop
  with its notes; after it the answer stays pending.
- Q: Is the tool_result text a sound source? A: Yes, under #962: it is the harness's own row in the
  session transcript, never the payload. Soundness rests on anchoring each pair between the tool_use's
  questions; the forged-pairs class (a question or answer stretched over its neighbour, the next
  question's label claimed, a question not asked) records nothing in the tests and the probe.
- Q: Which wins when the row has a `toolUseResult.answers` dict and text? A: The dict; the text is
  read only when there is no dict.
- Q: Why defer the whole entry at a Stop rather than record its matched answers then? A: It keeps one
  claim per entry and costs no line. By the Stop the planner has usually made a call after the
  answer, which already decided it.

## User Scenarios & Testing

### US1: an answer whose row lands after a Stop is recorded (P1)

Acceptance 1, and the 7-minute trust flow: the row lands after the Stop or minutes later inside the
bound, and the next planner call records it.

### US2: a labelled answer beside a differing one is recorded (P1)

Acceptance 2, for a transcript value of `Other`, the typed text with a note, or no value.

### US3: an answer with no row is unconfirmed once the bound passes (P1)

Acceptance 3: pending through a Stop and a call at 9.5 minutes, one row after 10.5 minutes.

### US4: nothing the transcript does not hold is recorded (P1)

Acceptance 4: the forged-answer class (18 shapes x 7 transcript cases) on the new reasons, a forged
first PostToolUse kept past a Stop, a replayed batch, and payload answers the transcript lacks.

### US5: a record shape names its check, and an unrecorded answer never blocks the Stop (P1, #1231)

The shapes under Compaction, the text match by question, the forged-pairs class, and a Stop that
finds a differing answer returns no block while the next call carries the note once.

## Requirements

- FR-001: `hook._shown(kept)` returns None while the transcript holds no tool_result row for the id;
  else the answers it shows (each payload question whose answer equals the transcript's for that
  question) and the reason for the rest.
- FR-002: `hook._confirm` keeps an answer with no row pending until `hook.BOUND` seconds after it was
  kept, at every call including a Stop; then `answer.unconfirmed` with "no tool_result row in 10
  minutes".
- FR-003: `hook._confirm` records the shown answers through `_answers` (a `prompt` row with only
  them) and the rest as `answer.unconfirmed`, in one claim of the entry.
- FR-004: `hook._unconfirmed` names only the questions not recorded, in the row and in the note.
- FR-005: design.md section 8 and the hooks page state the per-question rule, the pending Stop and
  the bound.
- FR-006 (#1231): `_shown` names the failed check: no tool_use, no tool_result (pending), no
  `toolUseResult` answers with text that does not match, or the differing question.
- FR-007 (#1231): with no `toolUseResult.answers` dict, a pair counts when the row's text holds
  `"<q>"="<a>"` followed by the next asked question's `, "<q>"=` or by `.`, for a question the
  tool_use asked.
- FR-008 (#1231): at a Stop an answer with a reason stays pending; no Stop blocks on it.

## Assumptions

- No real free-text answer exists to capture, so the free-text payload is reconstructed (item
  promise: "record the assumed shape under Assumptions"). Assumed: the payload's `tool_response`
  carries `{question: <typed text>}` for an Other answer, as for a label; the transcript may hold
  the same or another value. Overturned by a captured row; the code needs no change for either.
- The bound is 10 minutes, measured from the cache entry's modification time. Overturned by a real
  row that lands later than that after its PostToolUse.
- The `prompt` row keeps only the recorded questions, so the report's owner prompts list only them.
  Overturned if the report should also list the unrecorded ones (they are in `answer.unconfirmed`).
- Runtime +10 lines (3,396 to 3,406): +4 for 1211 and +6 for #1231 (the tool_use check, the text
  match, the Stop deferral). Over the 3,400 cap until free-lines-6 (#1229, 23 lines) merges, so
  `test_the_runtime_holds_its_size_budget` fails on this branch alone; the lead allowed more than +5
  when stated. Overturned if the planner holds the item to +5, in which case the text match splits out.
- The harness joins a batch's pairs with `, ` (How this fails 4). Overturned by a real batch row.
- An answer whose transcript lacks the tool_use is decided at once: the harness writes the tool_use
  row before the owner answers, seconds before PostToolUse (10:20:15 and 10:20:18 in the real flow).
  Overturned by a real PostToolUse that runs before its tool_use row is written.

## What stays open

A forged PostToolUse that reaches the hook entry before the real one for the same id still
suppresses the real answer (How this fails 3). A process that writes the transcript itself stays
open, as in SECURITY.md.

## Rollback

Revert the commit and re-vendor `.claude/`. No config key, ledger kind or file format changes; old
code reads the pending cache entries as before and records at the next Stop as it did.
