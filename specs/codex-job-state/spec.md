# Feature Specification: the board shows a registered Codex job's state

**Feature branch**: `feat/1201-codex-job-state`
**Item**: 1201 (issue #1201), tier standard, goal G-2
**Input**: on 2026-10-20 nine Codex builder jobs ran. Their end, failure or design question reached
the planner only by tailing logs, and their `run:` rows stayed [waiting] until edited by hand.

## The promise in my words

The planner registers a Codex job on its item with `wuwei plan run <id> --job <job file>`, the
companion's own job JSON. WUWEI stores that path on the item and reads only that file: it never
lists or scans the companion's folders. While the item has no PR, the board's `run:` row shows the
job's state from the file: running, completed, failed, or asked a question (the job's last answer
ends in a question mark). A completed job that names a `HANDOFF.md` shows that path. A missing,
malformed or shapeless file shows `job state unreadable`, never done.

The acceptance scenarios, restated:

1. A running job file on a run item shows `job running`.
2. A completed job whose output names a HANDOFF path shows `job completed, handoff <path>`.
3. A failed job shows `job failed`; a completed job whose last answer is a question shows
   `job asked a question`.
4. A missing job file shows `job state unreadable`.

## The job file shape (read 2026-10-20)

Read only, from one real file on this machine,
`~/.claude/plugins/data/codex-openai-codex/state/<workspace>-<hash>/jobs/<job id>.json` (2,198 job
files present). The tests use a fixture copy of this shape, never the live folder.

| Key | Type | Values seen |
|---|---|---|
| `id` | str | `task-mukx4f0u-z6hz7v` |
| `kind`, `kindLabel`, `jobClass`, `title` | str | `task`, `rescue`, `task`, `Codex Task` |
| `status` | str | `completed` 2114, `cancelled` 52, `failed` 24, `running` 8 (the companion source also writes `queued`) |
| `phase` | str | `done`, `cancelled`, `failed`, `verifying`, `running` |
| `pid` | int or null | null once ended |
| `logFile`, `workspaceRoot`, `sessionId`, `threadId`, `turnId` | str | paths and ids |
| `createdAt`, `startedAt`, `completedAt`, `updatedAt`, `cancelledAt` | str | ISO times |
| `result` | object | `status` (0 or 1), `threadId`, `rawOutput` (the final answer text), `touchedFiles`, `reasoningSummary` |
| `rendered` | str | the rendered final answer |
| `errorMessage`, `note`, `summary`, `request`, `write` | mixed | |

Over all 2,198 files the reader gives: completed 2,109, cancelled 52, failed 24, running 8, asked a
question 5, and 44 with a HANDOFF path.

## Assumptions

- "Asked a question" is a `completed` job whose `result.rawOutput`, trimmed, ends in `?`. The file
  has no field for it. Overturned if the companion adds one.
- The HANDOFF path is the last word in `rawOutput` that ends in `HANDOFF.md`, with markdown link,
  backtick and quote marks stripped. Seen as `[HANDOFF.md](/abs/path/HANDOFF.md)` and bare paths.
- Statuses other than completed show as the file names them (`queued`, `cancelled`); a missing
  status shows `state unreadable`.
- A relative `--job` path is read from the workspace root; the planner passes the absolute path.
- The row stays [waiting] (not actionable) in every state, as other run rows do; the text tells
  the planner to act. A stale `running` file whose process died still reads running; liveness by
  pid is out of the 6-line budget.
- Once the item's PR opens, the PR row replaces the run row, as before; the job is then not shown.
- A later `plan run --reason` keeps the registered job; the row shows the reason and the job state.
- A job file the parser cannot read (missing, not JSON, nested past the parser's depth) reads
  `job state unreadable`.

## Out of scope

Dispatching Codex jobs through WUWEI, attaching the HANDOFF to the item automatically, and Codex
gate verdict attestation (#1181).
