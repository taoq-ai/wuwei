# Feature Specification: a gate's verdict is linted before its hand-back

**Feature branch**: `claude/verdict-handback`
**Item**: verdict-handback, tier full, goal G-1
**Input**: two quality verdicts on 1068 failed the strict shape (a finding without file:line) and were
never attested. The block came from SubagentStop after SubagentHandback had ended the seat's run, so
no seat saw it and no `verdict.missing` row was written. The X-1 security verdicts written while the
hooks were down were also left unattested without a record.

## The promise in my words

The lint is already one check (`verdict.parse`, called by `_verdict_problem` and by evidence). The
gap is when it runs. Three changes:

1. PreToolUse on `SubagentHandback` from a sentinel seat runs `_verdict_problem` on the hand-back
   message. A problem denies the hand-back with the shape errors and the format, so the seat fixes
   the file while it can still act. A well-formed verdict is attested there.
2. SubagentStop records `verdict.missing` with the problem whenever a block cannot reach the seat:
   on `stop_hook_active` as today, or when the seat's transcript shows its run ended with a
   `SubagentHandback` call.
3. `verdict.parse` accepts a note without a place: `- [low] blocks: no. <note>`. A blocking finding
   still needs `<file>:<line>` and `Failure:`. FORMAT and the shared gate charter say so, so no seat
   pads a `:1` anchor.

The anti-forgery rule stays: an attest is recorded only for a sentinel seat whose role, taken from
the harness's `agent_type` and never from the message, matches the verdict's `Gate:`.

The line budget holds: post_tool's re-read of the Agent tool's response goes, because the hand-back
check reads the same message earlier and from the seat's own call.

The acceptance scenarios, restated:

1. A sentinel hands back naming `.wuwei/verdicts/1067/quality-3fb3f40.md`, which holds a finding
   with no file:line and no `blocks:`. PreToolUse denies it, and the reason lists the shape errors
   and the format.
2. The same hand-back with a well-formed verdict: PreToolUse then SubagentStop leave exactly one
   attest row for the file.
3. A seat whose run ended by hand-back, with a verdict problem found at SubagentStop: a
   `verdict.missing` row holds the problem.
4. `- [low] blocks: no. a note on the design` parses as a note; `- [high] blocks: yes. Failure: x` is
   rejected for its missing file:line.
5. The runtime size test passes at 3,000 lines or fewer.

## How this fails

1. The harness does not send `agent_type` on a subagent's PreToolUse. Then the hand-back is not
   linted, and SubagentStop does the work: it attests a good verdict as before and records
   `verdict.missing` for a bad one instead of losing it. Nothing gets worse than today.
2. A hook error inside the hand-back check (an unreadable ledger) lets the hand-back pass, since
   SubagentHandback is not a door. SubagentStop runs the same check and records what it finds.
3. A seat that cannot fix its verdict loops on a denied hand-back. Each deny names the exact errors
   and the format; the seat can still end with plain text, and the stop then records
   `verdict.missing`.

## Clarifications

### Session 2026-10-16

- Q: Where does the role come from at PreToolUse? A: `payload['agent_type']`, the harness field
  SubagentStop already reads, with the plugin prefix stripped. The message text is never consulted
  for the role.
- Q: Is a hand-back from a seat that is not a sentinel linted? A: No. A builder's or the lead's
  hand-back passes untouched; only `sentinel-*` seats are checked.
- Q: How does SubagentStop know the hand-back ended the run? A: The transcript reader already takes
  the last report from a `tool_use` whose input has a `message`. It now also reports whether that
  last part was a `SubagentHandback` call.
- Q: Does SubagentStop still return a block when the run already ended? A: No. It records
  `verdict.missing` and returns nothing, the same as on `stop_hook_active`.
- Q: Is the deny recorded? A: Yes, as a `refused` row through the existing pre_tool path, which
  holds the tool and the reason.
- Q: What happens to the #1039 case (the stop could not read the transcript)? A: The hand-back
  message reaches PreToolUse in the tool input, so the attest happens there. A seat that ends with
  plain text is read from `last_assistant_message` as before.
- Q: What does a note without a place store as its location? A: `None` under `where`; nothing in
  the runtime reads `where`.

## User Scenarios & Testing

### US1: a malformed verdict is fixed before the run ends (P1)

Acceptance 1. The deny reason holds the bad finding line and `verdict.FORMAT`; no attest row.

### US2: a good verdict is attested once (P1)

Acceptance 2, plus: a builder, a seat of another gate, and a seat with no `agent_type` attest
nothing; the builder and the unknown seat are not denied.

### US3: a problem no block can reach is recorded (P1)

Acceptance 3, with a transcript whose last part is a SubagentHandback call.

### US4: notes need no place (P2)

Acceptance 4.

## Requirements

- FR-001: `hook.pre_tool` denies a sentinel seat's SubagentHandback when `_verdict_problem` finds a
  problem, with that problem as the reason.
- FR-002: A well-formed verdict is attested at that hand-back; the SubagentStop that follows adds no
  second row.
- FR-003: `hook.subagent_stop` records `verdict.missing` instead of blocking when the run ended by
  hand-back.
- FR-004: `verdict.FINDING` makes `<file>:<line>` optional; a blocking finding without it is an
  error. FORMAT and `charters/_gate.md` say so; `agents/` is rebuilt.
- FR-005: post_tool's Agent hand-back re-read is removed; the runtime stays at 3,000 lines or fewer.

## Assumptions

- The harness sends `agent_type` and `agent_id` on PreToolUse inside a subagent, as on SubagentStop.
  Overturned if a live trace shows it missing; the stop path then still records the problem.
- The deny counts as a `refused` row in the audit. Overturned if the retro wants hand-back denials
  apart from door refusals.
- "The sentinel charters" means `charters/_gate.md`, the gate rules every sentinel charter is built
  from. Overturned if the owner wants the line repeated in each role charter.

## Rollback

Revert the commit and rebuild `agents/`. No config key, ledger kind or file format changes; verdicts
with notes that carry a file:line still parse.
