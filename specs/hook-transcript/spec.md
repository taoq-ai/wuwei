# Feature Specification: an owner answer and a seat stop are recorded only when the session transcript shows them

**Feature branch**: `fix/hook-transcript`
**Item**: hook-transcript, tier full, goal G-1
**Input**: the item's promise and acceptance (`wuwei plan show hook-transcript`), spike-962's run
evidence, the owner's trust ruling of 2026-10-19 ("Yes, and run sandbox-spike next"), and the
forge-door probe (#1158, parked) whose shapes reach the hook entry by hand.

## The promise in my words

Today the hook trusts its payload. Any process that reaches `wuwei hook PostToolUse` or
`wuwei hook SubagentStop` with a hand-made payload writes the rows G-1 rests on: an owner review,
breaking, exception or goal ruling, a plan approval, a seat stop and the verdict attestation that
rides on it. forge-door showed many command shapes that reach the entry past the guard.

After this change the hook trusts only what the harness wrote. Claude Code keeps each session's
transcript under its projects folder, `~/.claude/projects/`. The hook reads the home from the
password database, never from `HOME` or `CLAUDE_CONFIG_DIR`, which a hand-made call sets.

- An owner answer counts only when that transcript holds the AskUserQuestion tool_use with the
  payload's `tool_use_id`, and the last tool_result row for that id carries the same answers. A
  transcript path that does not resolve to a regular file under the projects folder is recorded
  at once as `answer.unconfirmed` with the reason. An answer the transcript never shows is
  recorded as `answer.unconfirmed` at the session's next Stop. Nothing is dropped silently.
- A seat stop counts only when the session transcript holds the seat's launch: the meta file the
  harness writes beside the seat's transcript (`agent-<id>.meta.json`) names the seat's type and
  the Agent tool_use id, and the session transcript holds that tool_use. Otherwise the hook
  records `seat.unconfirmed` with the reason and nothing else: no `seat.stopped`, no attestation,
  no kept report.
- The file and Bash guards refuse writes under the projects folder, read in the spellings the
  ledger rule already reads. Reads stay open.

The acceptance scenarios, restated:

1. A forged PostToolUse whose `transcript_path` names a file the session wrote records no ruling,
   and an `answer.unconfirmed` row names why.
2. A recorded real flow (payload and transcript fixture) records the ruling as today.
3. A Bash call appending to a file under `~/.claude/projects/` is refused by `guards.bash`.
4. A forged SubagentStop for an agent id absent from the transcript records no `seat.stopped`.

Added from the write probe: `find -delete` after a wrapper (`env A=1`, `nice`, `timeout`) passed,
because the wrapper unwrap lands only on a program a door reads. `find` joins that list, which
closes the same hole for the ledger and the cache (`env A=1 find .wuwei/ledger -delete` passes at
main).

Added by the caller: every forge-door shape (`python -m wuwei hook`, the package by path with
`/`, `/.`, `//`, `/./`, `/../`, the `cd`, `env -C` and `sudo -D` wrappers, fullwidth names, tilde
fill, xargs) now records nothing, as a generated test class over those shapes as `hook.handle`
payloads.

## What the real flow showed

The spike left one fact unmeasured: whether the tool_result row is in the transcript when
PostToolUse runs. This session's transcript answers it for the recorded plan question
(`toolu_014L8q1vMwPqZbJ5LPCy6ucB`, 2026-10-19). Its PostToolUse hook ran 308 ms and its
`hook_success` row is stamped 04:30:05.869Z, so the hook ran from about 04:30:05.561Z. The
tool_result row is stamped 04:30:05.880Z: 11 ms after the hook returned. It sits before the hook
rows in the file, and the hook rows name it as their parent. So the harness makes the answer row
only after PostToolUse returns, and no wait inside PostToolUse can see it: the harness waits for
the hook.

So the check runs where the row exists. PostToolUse keeps the answer as pending (a cache entry
per tool_use id). The session's next hook call in the planner (PreToolUse, PostToolUse or Stop)
reads the transcript and records the answer, or keeps it pending. A Stop rereads for up to 1.5 s,
since the docs say the transcript may lag, and then records `answer.unconfirmed`. A transcript
that already holds the row (the fixture, or a harness that writes it first) is recorded in the
same PostToolUse call, as today. The notes that follow an answer ("plan approved; start the
work", the ADR note, an exception's follow-up item) reach the planner on the call that records
it. In this session's transcript, the planner's next tool call came 3.5 s to 149 s after the
answer row (11 answers, median 8.4 s), so the next call finds the row with seconds to spare.

## How this fails

1. The harness changes its transcript format (the row keys `toolUseResult`, `tool_use_id`, the
   meta file). Every real answer then becomes `answer.unconfirmed` at the next Stop and every
   seat stop `seat.unconfirmed`. Owner review rulings stop counting, so merges on owner paths
   wait. It is loud (the planner gets a note per unconfirmed answer, and the rows name the
   reason), not silent, and the fix is a reader change. The owner accepted this risk in the trust
   ruling.
2. A planner that asks and then ends its turn with no Stop (a crash, a killed session) leaves the
   answer pending in `.wuwei/cache`. It is recorded at the session's next planner hook call after
   a resume (or as `answer.unconfirmed` at its next Stop). A session that never calls again
   leaves it there unrecorded: the one path to a drop. The transcript still holds the answer, so
   the owner can be asked again.
3. Codex keeps its transcripts elsewhere (`~/.codex/sessions`) in another format. A Codex
   `request_user_input` answer and a Codex SubagentStop are recorded as unconfirmed, so a Codex
   gate's verdict is no longer attested. No real Codex transcript fixture exists to build a
   reader from; that is a follow-up item.

## Clarifications

### Session 2026-10-19

- Q: Is the trust model the owner's call? A: Yes, class trust, answered 2026-10-19: "Yes, and run
  sandbox-spike next". Record an owner answer or a seat stop only when the session transcript
  shows it; otherwise write `answer.unconfirmed` or `seat.unconfirmed` with the reason, never a
  silent drop. A seat-written script can still forge transcript lines; sandbox-spike follows.
- Q: Which folder is the harness projects folder? A: `.claude/projects` in the account's home
  as the password database names it, resolved with links. Not `HOME` or `CLAUDE_CONFIG_DIR`: the
  real-entry probe showed that a hand-made call sets its own environment, so a folder read from
  it would be the forger's.
- Q: What does "the last row for that id" mean? A: Of the rows whose content holds a tool_result
  for the id, the last one; its `toolUseResult.answers` must equal the payload's answers. The
  hook rows that name the id (`hook_success`, `hook_additional_context`) hold no tool_result.
- Q: Why not wait inside PostToolUse, as the brief proposes? A: The real flow shows the row is
  made after the hook returns (above). A wait there only delays the harness.
- Q: What is recorded when an answer is confirmed? A: The same rows as today (`prompt`, rulings,
  plan approval, `plan.change`, follow-up items), from the payload's questions and answers, which
  the transcript's answers equal.
- Q: Which hook calls confirm a pending answer? A: The planner's own calls (no `agent_id`), the
  same calls that already deliver kept seat reports, so the notes reach the planner. A seat's
  hook calls in the same session do not.
- Q: Does a seat stop need a wait? A: No. The meta file and the Agent tool_use row are written at
  launch, before the seat runs.
- Q: Where do the guards read the projects folder? A: As a path that names `.claude` followed by
  `projects` (or `.claude` itself), in every spelling the ledger rule reads, and after `cd`,
  `pushd`, `-C`, `--chdir` or `-D` into it.
- Q: Is a `python` command that only reads a transcript refused? A: Yes, as for the ledger: the
  guard cannot tell a python read from a write. The refusal names the open read routes (the Read
  tool, `cat`, `grep`, `python3 - < <path>`).

## User Scenarios & Testing

### US1: a forged owner answer records nothing (P1)

Acceptance 1 and the forge-door class. A payload whose `transcript_path` is missing, a file the
session wrote (holding a forged tool_use and tool_result), a path that leaves the projects folder
by `..`, or a link from the projects folder to a forged file records `answer.unconfirmed` at once.
A payload that names the real transcript with an id it does not hold, or with other answers,
records nothing at PostToolUse and `answer.unconfirmed` at the Stop. No `ruling`, `prompt` or
`plan.change` row, and the plan is not approved.

### US2: a recorded real flow records the ruling (P1)

Acceptance 2. The fixture flow replayed in the measured order: the transcript holds only the
tool_use at PostToolUse (pending, nothing recorded), then the tool_result and hook rows; the next
planner call records the ruling and gives its notes. The same flow with the rows already written
records at PostToolUse. A Stop that finds the row within the wait records it.

### US3: a write under the projects folder is refused (P1)

Acceptance 3. Writers, redirects, `python -c` paths, `find -delete`, edit tools, and writers after
`cd`, `env -C` or `sudo -D` into the folder, in the path classes `//`, `%xx`, `/./`, `/../`,
`~`, `$HOME`, globs and braces. Reads (`cat`, `grep`, `<`, the Read tool) pass.

### US4: a forged seat stop records nothing (P1)

Acceptance 4. A SubagentStop whose agent id has no meta file under the projects folder, whose
meta names another type, whose transcript path names another agent, or whose session transcript
lacks the launch records `seat.unconfirmed` and no `seat.stopped`, `attest` or kept report. The
recorded real launch records `seat.stopped` as today.

## Requirements

- FR-001: `ws.PROJECTS` is `.claude/projects` in the password database's home for the uid.
- FR-008: `find` is a program the wrapper unwrap reads, so `env A=1 find <records> -delete` meets
  the records and transcript doors.
- FR-002: `hook.transcript_rows(path, key)` returns the rows naming `key` in a regular file under
  `ws.PROJECTS` (links resolved), or None when the path is not one.
- FR-003: PostToolUse on AskUserQuestion records `answer.unconfirmed` at once for a path that is
  not a transcript, else keeps the answer pending under `.wuwei/cache/answer-<session>--<id>.json`.
- FR-004: Each planner hook call (PreToolUse, PostToolUse, Stop) records the pending answers the
  transcript shows, and at a Stop records the rest as `answer.unconfirmed` after up to
  `hook.WAIT` (1.5) seconds. A hook claims an entry by removing it, so a racing hook skips it.
- FR-005: SubagentStop records `seat.unconfirmed` and nothing else unless the seat's meta file and
  the session transcript show its launch.
- FR-006: `hook.running` counts a `seat.unconfirmed` agent as stopped.
- FR-007: The edit tools and the Bash guards refuse writes under `.claude/projects` with a reason
  that names the read routes.

## Assumptions

- The check runs at the planner's next hook call, not inside PostToolUse, because the real flow
  shows the row is made after PostToolUse returns (above). Overturned by a real flow whose
  PostToolUse hook already sees its tool_result row; the code then records at PostToolUse with no
  change.
- The transcript format is the one this session's Claude Code (2.1.303) writes: rows with
  `message.content` parts (`tool_use` with `id` and `name`, `tool_result` with `tool_use_id`),
  `toolUseResult.answers` on the answer row, and `agent-<id>.meta.json` with `agentType` and
  `toolUseId` beside a seat's transcript. Overturned by a harness release that changes them
  (How this fails 1).
- The wait is 1.5 s at a Stop only. The measured row came 11 ms after the hook; the next planner
  call comes seconds later. Overturned by an `answer.unconfirmed` row whose transcript holds the
  answer.
- A user who moves Claude Code's folder with `CLAUDE_CONFIG_DIR` gets every answer and stop
  recorded as unconfirmed, loudly. Overturned if the owner wants that variable honoured; it would
  then need a source a hand-made call cannot set.
- Codex answers and stops are recorded as unconfirmed until a reader for Codex's transcript is
  built from a real fixture (How this fails 3). Overturned if the owner wants Codex kept on the
  old trust until then.
- An unconfirmed seat stop records nothing else. The attestation and the kept report ride on the
  same forged payload, so they count only with the stop. Overturned if the planner wants the
  attestation judged on its own.
- A nested seat (spawnDepth 2) is launched from a seat's transcript, not the session's, so its
  stop is unconfirmed. WUWEI's seats launch none.
- The item budgets +22 runtime lines; this adds 73 (hook.py +60, guards.py +11, ws.py +2). The
  deferred confirmation (keep, claim, wait, notes) and the seat launch check were not in the
  estimate; nothing was removed to offset it. Overturned if the planner holds the item to 22, in
  which case the seat-stop check splits out.
- Under the SemVer rule this is a patch: it refuses records it used to accept from a forged or
  unreadable payload; real Claude Code flows record the same rows. Overturned if the arch gate
  rules the Codex change (How this fails 3) breaking.

## What stays open

A process that writes the transcript itself: a script file, a writer the guards do not list
(`install`, `perl`), a path built at run time, or a symlink made where the guards do not see it.
The guard reads command text, so it is a tripwire there, not a wall. The sandbox item
(sandbox-spike) is what can close it. A forger can also replay a real answer or a real seat's
launch: the rows then repeat what the harness recorded.

## Rollback

Revert the commit and re-vendor `.claude/`. Pending entries left in `.wuwei/cache` are ignored by
the old code. No config key, ledger format or file format changes; `answer.unconfirmed` and
`seat.unconfirmed` are new row kinds the old code never reads.
