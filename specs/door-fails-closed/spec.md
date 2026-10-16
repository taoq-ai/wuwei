# Feature Specification: an error inside a door refuses the call instead of letting it pass

**Feature branch**: `claude/door-fails-closed`
**Item**: door-fails-closed, tier full, goal G-2
**Input**: any exception on a door path makes the PreToolUse hook fail open. Seen on the merge door:
`evidence.template_sections` caches the PR template headings, the cache write raised `OSError`,
`hook.handle` caught it, recorded `hook.error` and returned nothing, so `gh pr merge` ran unchecked.

## The promise in my words

PreToolUse never turns a door into a pass because something broke. Two changes in `cli/wuwei/hook.py`:

1. `pre_tool` returns the guards' decision (deny, ask or note) even when writing its ledger row
   fails. The failed record goes to stderr; the decision still reaches the harness.
2. When an exception escapes while PreToolUse handles a call that names a door, `handle` returns a
   deny whose reason names the error, and records `hook.error` when it can. A call names a door
   when it is a Bash command whose raw text matches `guards.DOOR_WORDS` (the rule #1077 added for
   multi-line commands, reused here, no second list), an MCP tool ending in `merge_pull_request`,
   `enable_pr_auto_merge` or `create_pull_request`, or a Write or Edit. Any other hook error, and
   any error in another hook event, fails open as today.

The size budget holds through one transcript reader: `last_text` and `tokens` each read the seat
transcript line by line; one function now reads it once and returns both.

The acceptance scenarios, restated:

1. `gh pr merge 5` while `.wuwei/cache/template-acme__app.json` is a directory: the cache write
   raises `IsADirectoryError`; PreToolUse denies, the reason names the error, a `hook.error` row is
   recorded.
2. A call the guards refuse while `ws.record` raises (a read-only ledger, a malformed last line):
   the deny still reaches the harness.
3. `ls` with an exception inside the hook: fails open as today and records `hook.error`.
4. The runtime size test still passes at 3,000 lines or fewer.

## How this fails

1. A guard bug that raises on an ordinary door call (any Write, or `gh pr view`) now blocks that
   tool for the whole session instead of letting it pass. The deny names the error so the operator
   can fix the workspace or the bug; this is the intended trade.
2. The except branch itself raises (a payload with a non-dict `tool_input` or a non-string tool
   name), the hook process exits non-zero, and the harness treats that as non-blocking: the door
   passes. `door` reads the payload defensively, and a test pins a string `tool_input`.
3. A refusal whose ledger row failed leaves no `refused` row, so the audit undercounts refusals.
   The failure is printed to stderr; the call itself stays refused.

## Clarifications

### Session 2026-10-16

- Q: The promise names `guards.DOORS (added by 1068)`; what is that? A: #1077 (item 1068) added
  `guards.DOOR_WORDS` and the raw-text rule in `guards.bash`. `hook.door` reuses `DOOR_WORDS` on the
  raw command text, the same test the multi-line rule applies, so `gh pr view 5` counts as naming a
  door. No parallel list is added.
- Q: Which edit tools count as "a Write or Edit"? A: The set `guards.pre_tool` already treats as an
  edit: Write, Edit, MultiEdit, NotebookEdit. Codex `apply_patch` arrives as Edit through `codex()`.
- Q: Does the deny for a door error also write a `refused` row? A: No. It records `hook.error` with
  the event and the error, as every hook error does; the deny is the harness output.
- Q: What if `hook.error` cannot be recorded either? A: The deny still returns; a test pins it.
- Q: How is a read-only ledger tested? A: The suite runs as root, where chmod does not stop a write,
  so the tests replace `ws.record` with one that raises `OSError` (read-only) or `ValueError`
  (malformed). A malformed last line is already skipped by `ws` (#1075) and pinned by an existing test.
- Q: A payload whose `tool_input` is not a mapping? A: Nothing can be read, so it is not a door call
  and fails open as today, without crashing the hook.
- Q: Does the combined transcript reader change behavior? A: Only at a malformed row: before, a row
  that broke the text loop still let the token loop go on, and the other way round. Now both stop at
  that row and keep what they had. Transcripts come from the harness; the existing tests hold.

## User Scenarios & Testing

### US1: a door that cannot judge stays shut (P1)

Acceptance 1, plus an injected error on each door kind (git push, gh pr merge, the ledger path,
Write, Edit, each MCP door tool), and an injected error while `hook.error` cannot be recorded.

### US2: a refusal survives a failed record (P1)

Acceptance 2, for a deny on a non-door call (an unclassed AskUserQuestion), a deny on a door (a
ledger Write) and an ask (`terraform apply`), each with `OSError` and `ValueError`.

### US3: other errors fail open (P2)

Acceptance 3 for `ls`, Read, a read-only MCP tool and an Agent launch; a PostToolUse error on a
Write; an unreadable `tool_input`.

## Requirements

- FR-001: `hook.pre_tool` returns the guards' decision when `ws.record` raises.
- FR-002: `hook.handle` returns a PreToolUse deny naming the error when the call names a door.
- FR-003: `hook.door` decides "names a door" from `guards.DOOR_WORDS`, the MCP door tool names and
  the edit tools.
- FR-004: Other PreToolUse errors and errors in other events fail open and record `hook.error`.
- FR-005: The runtime stays at 3,000 lines or fewer.

## Assumptions

- MultiEdit and NotebookEdit count as edits, as in `guards.pre_tool`. Overturned if the owner wants
  the narrower "Write or Edit" literally.
- `ws.cache_put` stays as it is (outside the promise); the deny names the cause.

## Rollback

Revert the commit. No config key, ledger kind or file format changes.
