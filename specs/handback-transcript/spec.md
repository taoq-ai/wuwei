# Feature Specification: a gate attestation is recorded only from the seat's own transcript

**Feature branch**: `leone/handback-transcript`
**Item**: handback-transcript (taoq-ai/wuwei), tier full, goal G-1
**Input**: the security gate on hook-transcript (#1172): `python3 -m wuwei hook SubagentStop` with a
forged payload passed and was counted as a quality PASS. PreToolUse on a sentinel's
SubagentHandback attested from its payload with no transcript read, and a replayed real
SubagentStop attested the text of `last_assistant_message`.

## The promise in my words

A gate's attestation has two doors into the ledger: the PreToolUse hook on the sentinel's
SubagentHandback call, and its SubagentStop. Both must take the report from the seat's own agent
transcript, the file Claude Code writes, and never from the text the hook payload carries. The
transcript path must resolve to a regular file under the harness projects folder, beside the meta
file that names the seat's type and an Agent tool_use the session transcript holds (the launch
check hook-transcript built). When the payload carries a report the transcript does not hold, the
hook records `seat.unconfirmed` with the reason, and no `attest` row, no `seat.stopped` row and no
kept report.

The acceptance scenarios, restated:

1. A forged PreToolUse SubagentHandback payload from a sentinel, naming a PASS verdict file: no
   attest row is written, and evidence still lists the gate as owed.
2. A real recorded sentinel flow (payload, session transcript and agent transcript fixtures): the
   attestation is recorded as today, once, at the hand-back.

Outside: binding an attestation to the verdict text the seat wrote (a rewritten verdict file is
re-read on a replayed real report, below); Codex seats, which have no agent transcript and were
already unconfirmed.

## How this fails

1. The harness writes the SubagentHandback tool_use row after PreToolUse runs. The hook would then
   find no hand-back, wait about 2 s, and record `seat.unconfirmed` with no attestation at the
   hand-back. The stop still attests from the transcript, so the gate is counted late, not lost.
   Measured on this machine: a Bash call found its own tool_use row in the running seat's
   transcript while it ran, so the row is written before the tool runs. Not measured: the row
   inside a PreToolUse hook itself.
2. The harness puts a text in `last_assistant_message` that is not one of the seat's text parts or
   hand-back messages (a joined multi-part message, a normalised string). Every such stop records
   `seat.unconfirmed` and loses its `seat.stopped` row and kept report. Measured: 24 of 24 reports
   kept in this workspace equal a text part of their seat's transcript byte for byte, and the
   ledger holds no `verdict.missing` row, so after a hand-back the payload text was empty or named
   the verdict.
3. A seat rewrites a verdict file a real gate named and replays that gate's real stop. The report
   is genuine, the verdict file is not, and it is attested as rewritten: `.wuwei/verdicts` is not
   a guarded path. Residual, named in SECURITY.md.

## Clarifications

- Q: The PreToolUse payload names no agent transcript. Where is the seat's? A: Beside the session
  transcript, as Claude Code lays it out: `<session>/subagents/agent-<agent_id>.jsonl`. The
  SubagentStop payload names it as `agent_transcript_path`, and the hook uses that when given.
- Q: "Never from the payload": may the payload's text be used at all? A: Only to pick which of the
  seat's own reports is meant. The text attested is one the transcript holds byte for byte; with
  no text in the payload, the transcript's last report is used, as before.
- Q: Does the hand-back check use the tool_use id? A: No. It checks that a SubagentHandback (or
  text) in the seat transcript carries the same message. The id is a documented PreToolUse field,
  but no real PreToolUse payload with it was recorded here.
- Q: Does the check apply to builders and leads too? A: Yes, at SubagentStop: one rule for every
  seat stop. A report the transcript does not hold is not kept for the planner either.
- Q: What does PreToolUse answer when the report is unconfirmed? A: Nothing: the hand-back goes
  through and the stop decides. A forged call's answer reaches no seat.

## Requirements

- FR-001: PreToolUse on a sentinel's SubagentHandback attests only a report the seat's own
  transcript holds, read under the projects folder after the launch check.
- FR-002: SubagentStop takes the seat's report from its transcript; a payload text the transcript
  does not hold records `seat.unconfirmed` and nothing more.
- FR-003: The seat transcript is read only as a regular file under the projects folder, links
  resolved.
- FR-004: A real flow records what it recorded before: the attest row at the hand-back, the stop
  with tokens and confidence, no second attest row.
- FR-005 (follow-up, branch `leone/handback-timing`): a seat or session transcript is split into
  rows on newlines only. A row whose JSON string holds a raw U+2028, U+2029, U+0085 or another
  Unicode line break reads as one row.

## Follow-up: a raw line separator in a seat transcript

Promise in my words: after #1244, three real security gates on door-words-text handed back a PASS
and none was counted. Each seat transcript held a raw U+2028 inside a JSON string (a probe class
the gate quoted). `transcript_rows` split with `str.splitlines()`, which splits there, so the
whole transcript read as unreadable. The hand-back then recorded `seat.unconfirmed`, and the
stop read an empty report and blocked for a missing verdict line. Acceptance: the real seat's
hand-back attests once, a stop alone attests from the transcript, and every forged shape still
attests nothing.

How this fails:

1. A key that is not a string (a meta `toolUseId` number) raises at `.encode()`: caught, it reads
   as no transcript, as before.
2. The session transcript holds the separator: every launch check and owner answer read fails.
   The same split fixes it; the corpus differential reads both paths.
3. Bytes split on a lone CR: JSON escapes CR inside a string, so a real row never holds one raw.

## Rollback

Revert the commit and re-vendor `.claude/`. No config key, ledger format or file format changes;
`seat.unconfirmed` already exists and gains a second reason.
