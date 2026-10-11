# Feature Specification: the planner may run any wuwei command

**Feature Branch**: `800-any-wuwei-command`

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #800, part 3 of the deletion pass #789: "chore(guards): the planner may run any
wuwei command: the owner-only table, the command sets, grouped help and guide go".

## Why

The state guard keeps a table of 25 owner-only `wuwei` verbs and about 300 lines of parsing that
exist only to spot those verbs in any shell form. Around it sit the read-only and write command
sets, a grouped `--help` that sorts commands by who runs them, and a `guide` command whose text
tells every session which commands are the owner's. All of it makes the model reason about who
may run what, which is process. The owner's rule for this pass (2026-10-11): models reason only
about building, reviewing and fixing; process control lives in code, and a check that stops a
real process error stays or moves.

## User Scenarios and Testing

### User Story 1: a session runs any wuwei command (Priority: P1)

The planner, or a seat, runs a `wuwei` subcommand. The state guard no longer reads the group and
verb, so no call is refused or turned into a card because of the command's name. The command
itself decides, from its own arguments and records.

**Independent Test**: `protect_state.check_bash` on `bin/wuwei decide D-1 A`,
`bin/wuwei watch uninstall`, `bin/wuwei tracker create A` and `W=watch; bin/wuwei $W uninstall`
in a workspace returns `(0, '')`.

**Acceptance Scenarios**:

1. **Given** a workspace, **When** a session runs any `bin/wuwei <group> <verb>` as a plain
   command, **Then** the state guard returns `(0, '')`.
2. **Given** a workspace, **When** a call writes `.wuwei/days/<date>/state.json` with a redirect,
   `cp`, `rm` or `Write`, **Then** the guard refuses it exactly as before.
3. **Given** a session in the workspace, **When** it runs `cd` to a directory outside the
   workspace root, **Then** the guard refuses it exactly as before.

### User Story 2: plain help and no guide (Priority: P1)

`bin/wuwei --help` prints argparse's own help with every command. `wuwei guide` is gone, the
SessionStart orientation points at `wuwei --help` instead, the skills and charters do not mention
`guide`, and `init --upgrade` removes the stale guide block an older `init` wrote into the
`memory.export_to` file.

**Independent Test**: `main(['--help'])` exits 0 and lists every command module; `main(['guide'])`
is an argparse error; `init.upgrade` on a workspace whose `CLAUDE.md` holds the guide block
removes it and keeps the other text.

**Acceptance Scenarios**:

1. **Given** the plugin, **When** the owner runs `bin/wuwei --help`, **Then** argparse help lists
   every registered command and exits 0.
2. **Given** a `CLAUDE.md` with `<!-- wuwei:guide:start -->` ... `<!-- wuwei:guide:end -->`,
   **When** `init --upgrade --dry-run` runs, **Then** it prints
   `Would upgrade CLAUDE.md: remove the guide block` and changes nothing; **When**
   `init --upgrade` runs, **Then** the block is gone, the rest of the file is unchanged, and a
   second run reports no change.

### User Story 3: the process checks the table carried keep working (Priority: P1)

Three rows of the deleted table were the only thing stopping a real process error. Their job
moves into the command they guarded, so deleting the table opens no hole.

**Independent Test**: with no terminal (an agent's Bash), whether or not `WUWEI_SESSION_ID` is
set, `wuwei drafts approve <id>` without the owner's recorded Send answer exits 2 and sends
nothing; `wuwei plan set A spec=skipped --reason x` and `wuwei plan set A owner_merge=false` exit 1.
The environment never decides (fix round: an agent can unset it): each asks the owner's y/N at the
host terminal (`integrity._host_confirm`), and a confirmed prompt passes.

**Acceptance Scenarios**:

1. **Given** a pending draft and no owner answer on its card, **When** a session runs
   `wuwei drafts approve <id>` with no terminal, **Then** it exits 2 naming
   `bin/wuwei drafts show <id> --widget` and the owner's host-terminal command, and nothing is sent.
2. **Given** the owner answered Send on the draft's card in the planner session, **When** the
   session runs `wuwei drafts approve <id>`, **Then** it sends as today.
3. **Given** an item, **When** `plan set <item> spec=skipped` runs with no terminal, **Then** it
   exits 1 and the item's spec is unchanged; the owner's y at the host records it; `spec=required`
   still records with no prompt.
4. **Given** an item with `owner_merge` true, **When** `plan set <item> owner_merge=false` runs
   with no terminal, **Then** it exits 1 and the hold stays; the owner's y at the host releases it;
   `owner_merge=true` still records from anywhere.

### Edge Cases

- A Bash call that fails to parse and names state files: still refused exactly as before; only
  the owner-relevance branch of that path goes.
- A CLI call stays exempt from the write-target check (`_wuwei_action` stays, used by
  `_write_targets`): its arguments are data.
- A loop of CLI calls that fails to parse is no longer classified read-only by `shell.classify`
  (the command sets are gone). Guards fall back to their state and publish checks; a loop that
  names neither passes as before.
- `shell.reads` keeps every non-CLI read form (`cat`, `sed -n Np`, `find` without an action,
  `python -c` reads, `json.tool`).
- `plan.approve` calls `drafts.approve` itself after the owner's gate Approve (#636); that library
  path is unchanged, the new check sits in the `drafts approve` command.

## Requirements

### Functional Requirements

- **FR-001**: `protect_state.check_bash` MUST NOT refuse, warn or card a call because it names a
  `wuwei` group or verb. The owner table, its helpers, the owner-script reading and the opaque,
  input-driven and non-literal owner-action refusals are deleted.
- **FR-002**: Protection of the workspace state files (`check_file`, `check_scratch`, and in
  `check_bash` the write targets, `git apply`, interpreter snippets naming state, and the
  workspace-root `cd` containment) MUST be unchanged.
- **FR-003**: `cli/wuwei/commands/__init__.py` keeps only its docstring: `READ_ONLY`, `_NEEDS`,
  `WRITES` and `read_only` are deleted, and `shell.reads` no longer consults them.
- **FR-004**: `bin/wuwei --help` MUST print argparse's help; `GROUPS`, `_help` and the `--all`
  flag are deleted.
- **FR-005**: `cli/wuwei/guide.py` and `cli/wuwei/commands/guide.py` are deleted. The SessionStart
  orientation's `Reference:` line names `wuwei --help` and the owner guide. No skill, charter or
  generated agent file mentions `wuwei guide`.
- **FR-006**: `init` MUST NOT write a guide block; `init --upgrade` MUST remove an existing guide
  block from the `memory.export_to` file and report it (dry run included); a file without the
  block is unchanged.
- **FR-007**: `_cd_target`, `_cwd` and their helper `_text` MUST live in `cli/wuwei/shell.py`;
  `guards/pr.py`, `guards/commit_push.py`, `security.py` and `guards/protect_state.py` import them
  from there.
- **FR-008**: `wuwei drafts approve <id>` MUST ask the owner's host y/N unless the owner's Send
  answer (`<id>:send`, or `<id>:edit` with `--edit` or `--file`) is recorded on the calling
  planner session; with no terminal it exits 2 and sends nothing. A host-terminal approve with no
  card answer now prompts (it sent without one before).
- **FR-009**: `plan set <item> spec=skipped` and `plan set <item> owner_merge=false` MUST ask the
  owner's host y/N; with no terminal or a No they exit 1 with the item unchanged, naming the
  owner's host-terminal form. From a host terminal they now prompt (they did not before).
- **FR-010**: Every test that covers only a deleted unit is deleted with it; a test that also
  covers kept behaviour keeps those assertions. No test, budget or floor is loosened.

### Key Entities

- **State guard** (`guards/protect_state.py`): after this change, file and directory protection
  only.
- **Owner answer topics**: the planner session's `gate_asked` list, written by
  `guards/decision.record_gate`, read through `sessions.gate_topics`.

## Success Criteria

- **SC-001**: `git grep -nE "_OWNER_ACTIONS|GUARD_CONFIG|CARD_FIRST|commands\.READ_ONLY|read_only\(|__main__ import GROUPS|wuwei guide|import guide"`
  over `cli`, `tests`, `skills`, `charters`, `agents`, `docs/site` and `README.md` finds nothing.
- **SC-002**: `guards/protect_state.py` shrinks by at least 300 lines.
- **SC-003**: the touched test files pass, including `tests/test_tone.py` and the reason corpus
  test in `tests/test_invariants.py`, with no budget or floor changed.

## Assumptions

- The three owner checks here (`drafts approve`, `plan set spec=skipped`, `plan set
  owner_merge=false`), and `config set`, `integrity reconfirm` and `decide`, now rest on the
  `/dev/tty` y/N prompt (`integrity._host_confirm`); the guard's text table no longer stands in
  front of them. A pty wrapper (for example `script` fed a `y`) defeats that prompt. Per design 9.1
  the prompt is a local friction boundary, not proof against a same-uid process, so no pty guard
  is added (lead decision, fix round); the guarantees for the edges stay with the code host,
  credentials and the merge policy.
- Precondition: parts 1 and 2 of #789 (#798, #799) are merged first. Part 1 deletes the invariant
  walk, the 9.2 rows that drive `protect_state` owner behaviour (I8, I16, I36 and others), and
  the constitution bullet that asks each guard change for an invariant row. The builder rebases
  on main before starting. If #798 has not merged, the invariant cases that test a deleted rule
  are deleted here with it.
- The acceptance "no subcommand is refused or carded because of who runs it" is read against the
  guard table, the command sets and the help groups, which is the issue's scope. The three checks
  in User Story 3 are process controls the pass keeps (the owner's (b) rule): an outward send
  without the owner, skipping the spec before gates, and releasing an owner merge hold. They move
  into the command they guarded, as an owner-answer requirement, not a table of verbs.
- Commands that already confirm with the owner themselves keep doing so and need no move:
  `decide`, `decision outcome` and `mcp decide` (`decision.owner_confirm`: the card answer or y/N
  at the host), `config set` (`setup.set_value`: card or host), `config promote` and
  `config add-repo` (`config.offer`), `integrity reconfirm`, `state recover`, `telemetry send`,
  `memory forget`, `remote ack` (host y/N), `setup` (needs a terminal). Later parts delete most of
  these commands.
- `goals edit`, `voice edit`, `watch uninstall`, `listen uninstall`, `grants revoke`,
  `drafts drop`, `tracker create <item>`, `plan set ticket=`, `plan set pace=` and
  `outbound learn` from a seat become runnable from any session. None stops one of the process
  errors the owner listed; later parts delete or rework most of them (#789 parts 7, 8, 11, 13,
  16, 20, 23).
- `init --upgrade` removing the guide block is in scope: an older `init` wrote it into
  `CLAUDE.md`, which every session reads, so leaving it would keep telling sessions about a
  deleted command and the owner-only list.
- The owner disposition marker refusal (`security.gh_outbound`, `RECORDS_FLOOR`) is not part of
  the owner table; it is a `gh` outward check and stays for the edges work (#789 part 17).
- Docs: only pages that describe the deleted command or that a test reads are edited
  (`agent.md`, `reference.md`, `configuration.md`); the site is rewritten in #789 part 24. The
  design spec is the owner's and is not edited here.
- In-command refusals: `state.StateError` in `plan.py`, which `commands/plan.py` maps to 1;
  `drafts approve` keeps its existing exit 2 for a missing host terminal.

## Deferred

- The `goals` and `voice` gate topics that `record_gate` writes have no reader after this change
  (the guard was it); they go with owner edits in #789 part 13.
