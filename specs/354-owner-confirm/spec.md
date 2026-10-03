# Feature Specification: owner confirmations are a yes or no at the terminal or a question in the session, never a typed digest, and a decision is one command

**Feature Branch**: `354-owner-confirm`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #354, "feat(owner): owner confirmations are a yes or no at the
terminal or a question in the session, never a typed digest, and a decision is one
command". Owner, 2026-10-03, after the second trial: "This is also awful, should be
smoother, or prompt the owner, instead of having to copy a hash for integrity. In the end,
the workflow is there to bring structure, not to block the development... until now it has
been a hassle even to start."

## Root cause (read and reproduced on main, 89b577e)

Three separate frictions, each with one shared spot:

1. **The typed digest.** `cli/wuwei/integrity.py:288-304` (`_host_confirm`) writes the
   prompt and the full digest to `/dev/tty` and returns `readline().strip() == fingerprint`,
   so the owner must copy a 64 (or 12) character hex string. Nine callers route through
   it: `integrity.reconfirm` (`integrity.py:312`), `mcp._proceed_unmeasured`
   (`mcp.py:590-592`), `mcp.decide` (`mcp.py:650-653`), `drafts` approve (`drafts.py:146-148`),
   `remote.acknowledge` (`remote.py:131-132`), `config.offer` (`commands/config.py:198-199`,
   used by `config set`, `config add-repo`, `config promote`, `setup`), `state recover`
   (`commands/state.py:33-34`), `doctor --fix` (`commands/doctor.py:661-662`) and
   `decision outcome` (`commands/decision.py:114`). Every prompt ends in "type:". Spec 9.1
   calls the host terminal a local friction boundary, not proof against a same-uid process,
   so the digest adds copying and no protection.
2. **No session path for decisions.** `cli/wuwei/guards/protect_state.py:46-67` lists
   `('mcp', 'decide')` and `('decision', 'outcome')` as owner-only for every session. The
   #357 allowance (`_GATE_EDITS`, `_gate_edits`, `protect_state.py:110-125`, fed by
   `guards/decision.py:119-150` `record_gate`) covers only `goals edit` and `voice edit`. So
   the planner can ask the owner a D-n question with AskUserQuestion (the #359 widget, whose
   `record` is `wuwei mcp decide D-n <label>`, `mcp.py:365`) but cannot record the answer:
   the hook refuses, and the CLI would then need `/dev/tty`, which a Claude Code Bash call
   does not have.
3. **Workspace discovery.** `cli/wuwei/commands/mcp.py:29-31` uses `workspace.guard_scope`,
   which treats `WUWEI_WORKSPACE` as context, not membership (`workspace.py:255-288`), and
   returns 0 silently when the cwd is outside. Reproduced read-only in a scratch workspace
   created with `python3 -P -m wuwei init`: from a sibling directory with `WUWEI_WORKSPACE`
   set to the workspace, `wuwei mcp decide D-1 proceed` and `wuwei mcp check` both exit 0
   and print nothing (the owner believes it worked), while `wuwei decision outcome D-1
   proceed` (which uses `find_workspace`) finds the day. Without the variable, the
   no-workspace reason (`workspace.py:232`) says only "run wuwei init", naming neither way
   to point at an existing workspace. No `--workspace` flag exists.

Also: `mcp.decide` and `_proceed_unmeasured` call the helper inside the outer
`except (OSError, ...)` of `mcp.decide` (`mcp.py:675-676`), so without a terminal the owner
reads `MCP registry unmeasured: OSError; check configuration and scanner reports` instead
of the host-terminal reason. And `wuwei decide` does not exist; the owner command is `decision outcome D-n <option>`
for routed decisions and `mcp decide D-n <option>` for the MCP one, and only the MCP path
writes a timestamp (`mcp.py:658-660`); neither rewrites `Decided-by:` in the record.

## User Scenarios & Testing

### User Story 1 - y/N at the host terminal (Priority: P1)

Every host confirmation shows what is being confirmed and asks `Confirm? [y/N]`. `y` (or
`yes`, any case) confirms; anything else, an empty line or end of input declines. The
digest is still computed, compared and recorded by each caller exactly as today; it is never
shown in full and never typed.

**Why this priority**: it is the step the owner called awful, and one helper covers nine
commands.

**Independent Test**: `python -m pytest -q tests/test_integrity.py -k host_confirm` and
`tests/test_mcp.py -k confirm_prompt`.

**Acceptance Scenarios**:

1. **Given** a pending MCP decision D-1 with a critical finding, **When** the owner runs
   `wuwei mcp decide D-1 proceed` at a host terminal, **Then** the prompt shows `D-1`, the
   option and the findings table from the record's `Context:` and ends with
   `Confirm? [y/N] `; no 64-character digest appears; `y` records `Outcome: proceed`,
   `Decided-by: owner` and a `Notes:` timestamp, writes the baseline and re-runs the check;
   `n` leaves `Outcome: pending` and exits 1 with `MCP registry owner confirmation declined`.
2. **Given** `integrity reconfirm`, **When** it asks, **Then** the prompt names the
   installation by the first 12 characters of its fingerprint, `y` confirms, and
   `.wuwei/integrity/confirmation.json` still records the full fingerprint.
3. **Given** draft sending (`drafts approve`), **When** it asks, **Then** the prompt shows
   the destination and the draft text, `y` sends.
4. **Given** `remote ack`, **When** it asks, **Then** the prompt shows the refused message
   ids, `y` records `remote.acknowledged`.
5. **Given** the real helper on a pseudo-terminal, **When** the owner types the full
   fingerprint instead of `y`, **Then** it declines.
6. **Given** no terminal, **Then** the helper still raises `this is an owner action: run it
   in a host terminal` (unchanged).

---

### User Story 2 - A decision is one command (Priority: P1)

`wuwei decide <D-n> <option> [--note <text>]` answers any of today's owner decisions:
when `D-n` is the pending MCP decision it runs the MCP decide path (records, writes the
baseline on `proceed`, re-runs the check so the launch gate opens); otherwise it runs the
existing routed-decision path (state outcome, event, parked items resume). Both write
`Outcome: <option>`, `Decided-by: owner` and `Notes: Decided at <time> <where>.` (plus the
note) into the record. `wuwei mcp decide [<D-n>] <option>` keeps working and takes the
pending decision when `D-n` is left out. No step asks the owner to edit a record.

**Why this priority**: the owner edited a Markdown table by hand, then with `sed -i`, to
answer one decision.

**Independent Test**: `python -m pytest -q tests/test_decision.py -k decide_command` and
`tests/test_mcp.py -k decide_command`.

**Acceptance Scenarios**:

1. **Given** a routed owner decision D-3 with options A and B, **When** the owner runs
   `wuwei decide D-3 B --note "phone answer"` and confirms, **Then** it exits 0, the record
   has `Outcome: B`, `Decided-by: owner` and a `Notes:` line with the time and the note,
   state `decision_outcomes.D-3.decided_by` is `owner`, and a `decision.decided` event is
   appended.
2. **Given** the pending MCP decision D-1, **When** the owner runs `wuwei decide D-1
   proceed` and confirms, **Then** the result equals `wuwei mcp decide D-1 proceed`: the
   check re-runs and `mcp.cached` exits 0.
3. **Given** a pending MCP decision, **When** the owner runs `wuwei mcp decide proceed`,
   **Then** it answers that decision.
4. **Given** `--note` with a line break, **Then** the command exits 2 with a usage reason and
   writes nothing.

---

### User Story 3 - The planner records the owner's answer in the session (Priority: P1)

Under `observe` and `guarded`, the planner asks the D-n question through AskUserQuestion
(the widget from `wuwei mcp check --widget` or `decision show D-n --widget`, header `D-n`,
citing the record, linted by the existing question guard). The PostToolUse gate recorder
notes `D-n` on the planner's session row. The planner then runs the widget's `record`
command (`wuwei decide D-n <label>` or `wuwei mcp decide D-n <label>`) from the same
session: the hook allows it, and the CLI records the decision without a terminal prompt,
noting `in the planner session`. Under `strict` the hook refuses with the existing
host-terminal line and the exact command to paste, and the CLI keeps the y/N prompt.

**Why this priority**: the issue's second and third acceptance items; #359 built the widget
and left the recording to this issue.

**Independent Test**: `python -m pytest -q tests/test_owner_edits.py -k decide` and
`tests/test_mcp.py -k session`.

**Acceptance Scenarios**:

1. **Given** guarded posture, `scanner.mcp.block = ["critical"]`, a pending D-1 with a
   critical finding, and the planner session `planner-1` that asked D-1 through
   AskUserQuestion, **When** the planner runs `bin/wuwei mcp decide D-1 proceed` from that
   session, **Then** the hook returns 0 and the command (with `WUWEI_SESSION_ID=planner-1`
   and no terminal) exits 0, the record notes `in the planner session`, and `mcp.cached`
   exits 0 (the launch gate opens).
2. **Given** strict posture and the same question asked, **When** the planner runs the same
   command, **Then** the hook returns 1 with `MCP decisions require the owner terminal,
   outside agent tools. Run it in a host terminal: bin/wuwei mcp decide D-1 proceed`; run
   without a terminal, the CLI exits 2 with the host-terminal reason.
3. **Given** observe or guarded, **When** the planner runs `wuwei decide D-2 B` for a D-2
   it never asked, or a seat (payload with `agent_id`) runs `wuwei decide D-1 proceed`,
   **Then** the hook refuses.
4. **Given** a command naming any `D-n` word the session did not ask (for example
   `--note D-2`), **Then** the hook refuses.

---

### User Story 4 - Owner commands find the workspace from anywhere (Priority: P2)

Owner commands read the workspace from the cwd, from `WUWEI_WORKSPACE`, or from a leading
`--workspace <path>` (`wuwei --workspace <path> mcp decide D-1 proceed`). When none finds
one, the reason names both. `setup` prints the one `export WUWEI_WORKSPACE=<path>` line when
it creates the workspace.

**Why this priority**: the owner had to `cd` into the workspace for `mcp decide`; with the
variable set it silently did nothing.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k workspace_from_outside`,
`tests/test_owner_actions.py -k workspace` and `tests/test_setup.py -k export`.

**Acceptance Scenarios**:

1. **Given** a run from outside the workspace with `WUWEI_WORKSPACE` set, **When** the owner
   runs `wuwei mcp decide D-1 proceed`, **Then** the command finds the day and records the
   decision.
2. **Given** no `WUWEI_WORKSPACE`, **When** the owner runs `wuwei --workspace <path> mcp
   decide D-1 proceed` from outside, **Then** the same happens.
3. **Given** neither, from outside any workspace, **Then** `mcp decide` and `decide` exit 2
   with one line naming `WUWEI_WORKSPACE` and `--workspace`; `mcp check` stays a silent
   exit 0 (spec 035: outside a workspace the check is a no-op).
4. **Given** a seat running `bin/wuwei --workspace <path> mcp decide D-1 proceed`, **Then**
   the hook still refuses it as an owner action.
5. **Given** `setup` in a directory without a workspace, **Then** its output carries exactly
   one `export WUWEI_WORKSPACE=` line; a second `setup` in the created workspace prints none.

---

### User Story 5 - Texts say the command, fit a phone screen (Priority: P2)

Docs, skills and reason texts no longer tell the owner to type a digest or to set
`Outcome:` or `Decided-by:` by hand; they name the one command. The widget `record` for a
routed decision is `wuwei decide {id} <label>`. Prompts and refusal reasons are what, why
and the one command.

**Independent Test**: `python -m pytest -q tests/test_owner_records_lint.py tests/test_docs.py`.

**Acceptance Scenarios**:

1. **Given** the #357 hand-edit lint, **When** it also matches "type the (displayed) digest"
   and "To confirm, type", **Then** it finds nothing in `skills/`, `docs/site/`,
   `templates/` or CLI string constants, and the `PENDING_354` exception set is gone.
2. **Given** `decision show D-n --widget`, **Then** `record` is `wuwei decide D-n <label>`.
3. **Given** a phone answer awaiting confirmation, **Then** the status reason reads
   `confirm with wuwei decide D-n <option>`.

### Edge Cases

- `y` answered while the record or registry changed during the prompt: the existing
  re-read checks still refuse (`decision changed during confirmation`, `integrity changed
  during confirmation`); unchanged.
- The session allowance is recorded only for a question whose `header` is exactly a
  `D-n` id that the question text cites and whose record exists today; questions from a
  seat (`agent_id`) or another session record nothing.
- The CLI skips the terminal prompt only when `WUWEI_SESSION_ID` is today's planner session,
  the posture is not strict, and the `D-n` is on that session's `gate_asked` list. A host
  terminal (no `WUWEI_SESSION_ID`) always gets y/N. A seat subagent shares the planner's
  environment; the hook is what refuses it (spec 9.1: a friction boundary).
- `mcp decide proceed-unmeasured <server>` names no `D-n`, so it stays host-terminal only in
  every posture (y/N there).
- `--workspace` is honoured only as the first two words; later it is an argparse error.
  `--workspace` naming a directory without `.wuwei/` fails with the existing
  `WUWEI_WORKSPACE=... must name a root containing .wuwei/` reason.
- `mcp decide` with no `D-n` and no pending decision: unchanged `MCP registry has no pending
  decision` (exit 1).
- `wuwei decide D-n` for a record that is neither the pending MCP decision nor routed:
  unchanged `decision: route this pending owner decision first` (exit 1).

## Requirements

### Functional Requirements

- **FR-001**: `integrity._host_confirm(value, *, prompt=None)` writes the prompt (default:
  the plugin installation named by `value[:12]`) and `Confirm? [y/N] ` to `/dev/tty` and
  returns True only for `y` or `yes` (case-insensitive, stripped). It never writes the full
  `value`. The no-terminal behaviour is unchanged.
- **FR-002**: Each of the nine callers passes a prompt that states what is confirmed (the
  findings table, the installation short form, the draft text, the message ids, the diff or
  fixes already printed above) and no "type:" instruction. Each keeps computing, comparing
  and recording its digest as today.
- **FR-003**: `wuwei decide <D-n> <option> [--note <text>]` dispatches to `mcp.decide` when
  `D-n` is the pending MCP decision, else to the routed-decision owner outcome. A note with
  a line break exits 2.
- **FR-004**: Both decide paths write the record through one shared function that sets
  `Outcome:`, sets `Decided-by: owner` and appends `Notes: Decided at <time> <where>.`
  followed by the note when given; `<where>` is `at the host terminal` or `in the planner
  session`.
- **FR-005**: `wuwei mcp decide <option>` (one word, not `proceed-unmeasured`) answers the
  pending MCP decision.
- **FR-006**: `record_gate` adds a `D-n` header to the planner session's `gate_asked` list
  under the conditions in Edge Cases.
- **FR-007**: The hook allows `decide` and `mcp decide` from the planner session, outside
  strict, when every standalone `D-n` word in the command is on the session's `gate_asked`
  list and there is at least one; otherwise the planner gets the existing
  `<reason> Run it in a host terminal: <command>` line and seats the plain reason.
- **FR-008**: One shared function answers "which records did the planner gate ask in this
  session, and is the caller the planner" for both the hook and the CLI; strict returns no
  records.
- **FR-009**: `wuwei --workspace <path> <command> ...` sets `WUWEI_WORKSPACE` for that run
  before anything else reads the workspace. The hook's owner-action pair skips the
  `--workspace` value.
- **FR-010**: `wuwei mcp` uses the explicit `WUWEI_WORKSPACE` selection when the cwd scope
  finds no workspace; `decide` without any workspace exits 2 with the no-workspace reason;
  `check` without any stays exit 0.
- **FR-011**: The no-workspace reason names `WUWEI_WORKSPACE` and `--workspace` on one line.
- **FR-012**: `setup` prints `export WUWEI_WORKSPACE=<quoted root>` once, when it creates
  the workspace.
- **FR-013**: Owner-facing texts name `wuwei decide` (or `mcp decide`) and y/N; the hand-edit
  lint covers digest typing.

### Key Entities

- **`sessions.<id>.gate_asked`** (day state, existing list, #357): now also holds `D-n`
  ids. Written only by `record_gate` (`gate.asked` event, existing reserved producer).
- **Decision record** (existing): `Outcome:`, `Decided-by:` and an appended `Notes:` line
  written by the decide commands.

## Success Criteria

- **SC-001**: No owner command prints or reads a digest at the terminal; the y/N prompt is
  the only terminal input (tests on the real helper over a pty).
- **SC-002**: The planner records an asked MCP decision from its session in one command
  under guarded, and the launch gate opens (one end-to-end test through the hook and CLI).
- **SC-003**: `wuwei mcp decide` from outside the workspace with `WUWEI_WORKSPACE` set
  records the decision (today it silently exits 0).
- **SC-004**: The full suite passes with `python -m pytest -q`.

## Assumptions

- "The remote pairing" in the issue is `remote ack` (`remote.acknowledge`), the only remote
  host confirmation on main; no other pairing confirmation exists to change.
- The helper keeps its name and `(value, *, prompt)` signature so the about twenty test
  fakes (`lambda value, prompt: True`, `lambda value, **kwargs: True`) keep working.
- The session allowance binds the record id, not the answered option: the hook cannot read
  the owner's choice reliably from the PostToolUse payload, and the planner runs the
  widget's `record` command with the label the owner picked. Binding the option is left
  for a later issue if retro shows a mismatch.
- `decision outcome` stays as is (host terminal, owner-only, event producer names); `wuwei
  decide` delegates to it for routed decisions and becomes the documented command.
  `decision outcome` is not session-allowed.
- `integrity reconfirm`, `state recover`, `config` edits, `setup`, `doctor --fix`,
  `drafts approve` and `remote ack` stay host-terminal only in every posture; this issue
  changes only their prompt to y/N.
- `--workspace` is a leading global option only (pre-parsed before command discovery so the
  workspace's `.wuwei/env` loads); it sets `WUWEI_WORKSPACE` for the process.
- The MCP waiting line (`mcp._waiting`) and the doctor MCP row keep "in a host terminal":
  the host terminal works in every posture, and the session path is the planner's, not the
  owner's.
- "Fit one screen on a phone" is met by keeping each prompt and refusal to what, why and one
  command; the findings table is the record's own `Context:`, already cut to 60 characters a
  snippet. No line-count limit is enforced in code.
- The dry-run workspace named by the pipeline was not available; the reproduction above used
  a scratch workspace created with `wuwei init`.
- The design spec is not amended: 5.2 (#357) already says the owner answers "in the
  session, in the DM, or y/N at a terminal" and that the host terminal remains for strict
  and credentials.
