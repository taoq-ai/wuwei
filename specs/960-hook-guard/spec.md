# Feature Specification: Close forged hook invocation bypasses

**Feature Branch**: `960-hook-guard`
**Created**: 2026-10-13
**Status**: Review follow-up implemented and verified
**Input**: GitHub issue #960, field reproductions from the #952 review.

## User Scenarios & Testing

### User Story 1 - Refuse model-forged hook events (Priority: P1)

The owner needs tool calls unable to impersonate hook events that record an Owner
step answer or stop a seat.

**Independent Test**: Feed recorded PreToolUse Bash payloads through the full hook
pipeline under enforce, with a forged PostToolUse input file in the test workspace.

**Acceptance Scenarios**:

1. Given enforce, `echo $(wuwei hook PostToolUse < p.json)` and
   `wuwei --workspace . hook PostToolUse < p.json` both receive deny before execution.
2. Given a launcher on PATH, in bin, in a plugin cache, or through the workspace
   executable pointer, direct and wrapped hook commands receive the same refusal.
3. Given prefix options, sh -c, env, xargs, command substitutions or backticks,
   hook invocations are refused with the hook-specific reason.

### User Story 2 - Preserve legitimate hooks and ordinary tools (Priority: P1)

Claude Code's configured hook command continues to consume recorded payloads.
Ordinary unsupported shell syntax keeps its existing allow-and-log behavior.

**Independent Test**: Replay configured hook commands; compare ordinary unparsed
calls and parsed commands which mention hook as data against existing outcomes.

**Acceptance Scenarios**:

1. A recorded legitimate hook invocation still succeeds through the shipped shim.
2. An unparseable call without both words wuwei and hook retains today's behavior.
3. Parsed `echo 'wuwei hook'` and `wuwei next` do not receive a hook refusal.

### Edge Cases

- The unparsed fallback matches both words in any order, including paths and quotes.
- Malformed quoting with both words refuses; only one word or longer identifiers do not.
- A workspace path named hook is an option value, not a hook subcommand.
- Python module launchers and wrapper combinations follow the same guard.
- The existing guard scope and enforcement floor remain authoritative.

## Requirements

### Functional Requirements

- **FR-001**: Under enforce, refuse model tool calls running wuwei hook, including
  the two reported bypasses, global prefix options, launcher paths, workspace
  pointers, substitutions, backticks, sh -c, env and xargs.
- **FR-002**: When shell parsing fails and wuwei and hook occur as words, refuse with
  a specific hook reason instead of the generic unparsed reason that is only logged.
- **FR-003**: Preserve existing behavior for other unparsed calls, parsed reader
  text and ordinary WUWEI commands.
- **FR-004**: Preserve Claude Code's configured hook invocation. Reject non-runner
  parents only if a reliable caller signal exists; otherwise document why and rely
  on the guard, as the issue permits.
- **FR-005**: Reuse the existing guard, denial output and refusal records; add no
  owner prompts, new workflow paths, dependencies or state schema.
- **FR-006**: Refuse any adjacent argv pair consisting of literal hook or a word
  containing `$`, followed by a known hook event, regardless of program name.
  Recognize mixed-case launcher names and Python short-option clusters ending in m.
- **FR-007**: Strip quotes and backslashes before the fallback word check and match
  wuwei case-insensitively. Apply the same check to inline interpreter code arguments
  and git -c alias values, while preserving the review harness's ordinary rows.

## Success Criteria

- **SC-001**: Both field reproductions and all listed invocation families receive
  deny in the full PreToolUse pipeline before executing the forged payload.
- **SC-002**: Legitimate hook replay and ordinary unparsed regression cases retain
  their prior outcomes; all affected test files pass offline.

## Assumptions

- No questions are asked per task instructions. The scope is literal hook attempts
  visible in the submitted shell text and forms supported by the existing parser;
  arbitrary encoded programs and external script contents are not a new sandbox.
- The unparsed fallback intentionally errs toward refusal when both words occur,
  including inert text within otherwise unsupported syntax. Parsed reader text stays
  data unless it contains the adjacent argv pair specified in FR-006.
- Review F6: strings built at run time, such as `printf 'wu%sei'` or
  `"$(printf ho%sk o)"`, and script files such as `bash f.sh`, `./f.sh` and
  `make -f m.mk` are a known limit of this static guard. Closing that limit requires
  a separate follow-up for hook-side checks against harness-written evidence.
- FR-006 intentionally refuses literal `hook <Event>` argv pairs even in readers.
  `W=watch; bin/wuwei $W uninstall`, `echo hook docs` and `echo 'wuwei hook'`
  remain allowed. Inline-code word checks are conservative, not language evaluation.
- `--workspace <path>` is the only global option that consumes a value and allows
  execution today; help/version exit. Prefix detection must not treat later command
  operands as subcommands. Do not add new CLI options.
- Caller authentication fallback: hooks/hooks.json invokes bin/wuwei with only
  hook and the event. bin/wuwei execs Python; commands/hook.py reads ordinary JSON
  from stdin. None provides a private runner credential. Inherited environment and
  payload fields can be supplied by a tool command. An immediate parent can be a
  shell or the harness, and a process name is not proof of the hook invocation path.
  There is no reliable authenticated distinction available in this repository, so
  retain the hook CLI and rely on PreToolUse, as FR-004 permits. Do not add a process
  name allowlist or a forgeable environment flag.
- Proposed owner-only design wording: the #839 unparsed-call exception excludes
  commands containing both wuwei and hook as words. The design and constitution
  files remain unchanged.
- Explicit affected test files replace a bare full-suite run per seat instructions.

## Clarifications

### Session 2026-10-13

Recommendations recorded without questions: retain guard scope and enforcement
floor; preserve parsed data; use the permitted parent-authentication fallback.
Review recommendations: implement F1 through F4 and the small F5 inline-code check;
retain exact event-name matching and the ordinary harness controls. The user's
explicit review follow-up authorizes this fix round.

## Deferred

F6 is a separate follow-up issue pending filing; GitHub commands are forbidden in
this task. Link it to #960 when filed. It covers runtime-built strings and script
files through authenticated harness evidence, outside this static guard's scope.
