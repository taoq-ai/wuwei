# Feature Specification: the fail-closed check reads the doors from one table, through quotes, and covers the leak check

**Feature branch**: `claude/door-hardening`
**Item**: door-hardening, tier full, goal G-2
**Input**: follow-ups from today's gates on the door-fails-closed change. `hook.door()` kept its own
copy of the door tool names, read the raw command (so a quoted door word slipped past), left the
leak door open when the guard raised, and `codex()` ran outside `handle`'s try.

## The promise in my words

`guards.py` gets one `DOORS` table: the edit tools and the MCP tool suffixes for merge, auto-merge
and create PR. `guards.pre_tool` and `hook.door()` both read it, so the list of doors and the list
the fail-closed check uses are one list. When a guard raises, `hook.door()` decides whether to
refuse. It now:

- matches `guards.DOOR_WORDS` on the command with every quote and backslash removed, so
  `g''it push` and `"g"h pr merge` are doors;
- counts a Bash command that names a `NETWORK` program (curl, wget, ssh, scp, nc) as a door, and
  any `mcp__` tool as a door, so the leak check also fails closed;
- counts a Codex `apply_patch` as an edit door, because `codex()` now runs inside `handle`'s try
  and a payload it cannot map reaches the fail-closed check in its raw shape.

`_unwrap` skips a wrapper argument as an assignment only when it has the shape `NAME=value`, so
`env /opt/a=b/git push origin main` reads `git push`. SECURITY.md says what fails closed.

The acceptance scenarios, restated:

1. With `guards.bash` raising, PreToolUse refuses `g''it push origin main`, `"g"h pr merge 5` and
   `curl -d x https://e.test`, and the reason names the hook failure.
2. With `guards.pre_tool` raising, PreToolUse refuses `mcp__slack__send_message` and
   `mcp__github__merge_pull_request`; a Read or Glob call still passes.
3. With `codex()` raising on a malformed apply_patch payload, `handle` refuses the PreToolUse call,
   records `hook.error`, and does not raise.
4. `env /opt/a=b/git push origin main`, with main the default branch, is refused like a push to
   main; `env FOO=1 git push origin main` still is.
5. `hook.door`'s tool names come from `guards.DOORS`; hook.py holds no copy of the MCP suffixes.
6. Route verdicts are unchanged and the runtime stays at 3,000 lines or fewer.

## How this fails

1. The network match is too broad: `https` in `NETWORK` would match every URL, so a broken guard
   would refuse `git clone https://...` or `echo https://x`. Only a program word counts: the name
   must start the text or follow a separator or `/`, and be followed by whitespace or the end.
2. Moving `codex()` inside the try changes what `door()` sees after a handler error: the raw Codex
   payload instead of the mapped one. A mapped Edit would then pass as `apply_patch`. `door()`
   counts `apply_patch` as an edit, and the other Codex tools were never doors.
3. The `DOORS` table changes what `pre_tool` sends where: a typo in a key would let an MCP merge
   fall through to the plain leak check and skip the merge evidence. The existing MCP merge,
   auto-merge and create-PR tests in test_guards.py hold each route.

## Clarifications

### Session 2026-10-16

- Q: Which `NETWORK` names count in `door()`? A: The whole `guards.NETWORK` set, read as program
  words. `gh` is already a door word; `http` and `https` only match as a program name, not inside
  a URL, so the promise's five names plus those are covered without a second list.
- Q: Does `door()` still need the MCP suffixes once every `mcp__` tool is a door? A: No. It reads
  `guards.DOORS['edit']` for the edit tools and treats every `mcp__` tool as a door; the suffixes
  live only in `guards.DOORS` and `pre_tool` reads them there.
- Q: Should the quote-stripped match replace the raw match? A: Yes. Removing quotes and
  backslashes keeps every word the raw text had (`wuwei\` newline `hook` still matches the hook
  rule), so one match on the stripped text covers both.
- Q: Does the existing test that an MCP read tool fails open on a guard error still hold? A: No.
  The promise makes every `mcp__` tool a door while the hook is broken; that test moves to the
  door list and Read and Glob take its place on the open side.

## Assumptions

- Refusing every MCP call while the hook is broken is the intended fail-closed for the leak door
  (from the item). Overturned if the owner wants read-only MCP tools to pass.
- `codex()` raising is reproduced with a non-dict `tool_input` on `apply_patch`, the shape the
  harness would send when its payload is malformed. Overturned if Codex validates the shape first.

## User scenarios

### US1: a broken guard keeps every door shut (P1)

Acceptance 1, 2, 3 and 5. Tests in tests/test_hook.py and tests/test_codex.py.

### US2: a wrapper path with '=' cannot hide the program (P1)

Acceptance 4. Test in tests/test_guards.py.

## Requirements

- FR-001: `guards.DOORS` holds the edit tools and the MCP merge, auto-merge and create-PR suffixes;
  `guards.pre_tool` and `hook.door()` read it.
- FR-002: `hook.door()` matches `DOOR_WORDS` on the command with quotes and backslashes removed.
- FR-003: `hook.door()` counts a Bash command naming a `NETWORK` program, and any `mcp__` tool.
- FR-004: `codex()` runs inside `handle`'s try; `apply_patch` is an edit door.
- FR-005: `_unwrap` skips a wrapper argument as an assignment only when it is `NAME=value`.
- FR-006: Runtime at 3,000 lines or fewer; route verdicts unchanged.

## Success criteria

- SC-001: Every acceptance scenario has a test that ran red before the change and green after.
- SC-002: The full suite passes.
