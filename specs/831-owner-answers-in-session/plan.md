# Implementation Plan: the owner answers in the session, never in a terminal

**Branch**: `b3-decision-framework` | **Spec**: [spec.md](spec.md) | **Issue**: #831

Built after part 9 (#814) and before parts 10 (#815) and 11 (#816) on the same branch. Part 9
edits some of the same files (`commands/decision.py`, `plan.py`, `commands/next.py`,
`commands/doctor.py`, `workspace.py`); locate every edit below by function name and text, not by
line. Line numbers given are from the worktree when this plan was written.

## Summary

One card, one helper, one hook branch, one guard line, then every remaining terminal caller and
text moves onto them.

- `sessions.needs_owner(root, command, detail, token='')` is the only owner confirmation for
  code that stays. It reads today's `events.jsonl` for the owner's recorded `Yes` on the step's
  Owner step card and otherwise returns the refusal that names the card.
- `guards/decision.record_gate` records answered Owner step questions from any main session as
  a `gate.asked` event, before it reads state.
- `guards/protect_state.check_bash` refuses a Bash call that runs `wuwei hook`, so a session
  cannot feed the hook a forged answer.
- Seven `_host_confirm` call sites switch to the helper. Every terminal text in code that
  stays loses the terminal. A test pins both, with a LEFT list for code later parts delete.

## Technical Context

Python 3.11+, stdlib only; pytest dev-only. Run only the touched test files with
`python3 -m pytest -q <files>`; CI runs the suite. No new dependency, command or config key.
One new test helper file (`tests/fakes/owner.py`); no new runtime module.

## Constitution Check

- Test first: every behaviour change below has a failing test task before its code task.
- Stdlib only, shortest diff: the helper reuses `sessions.card_topic`, the existing
  `gate.asked` event kind and `record_gate`; no new store, command or guard module.
- Process control in code: the confirmation stays in code; only its channel moves from a
  terminal to a recorded card answer. The model asks the card the command prints and reruns
  the command; it reasons about nothing else.
- No test is loosened: tests that pinned a terminal prompt for a converted step are rewritten
  to pin the card; the wall lint loses only rows whose text is no longer a wall.
- Generated agents: `charters/planner.md` changes, then `bin/wuwei agents build`.

## Design

### The helper (`cli/wuwei/sessions.py`)

```python
OWNER_STEP = 'Owner step'


def needs_owner(root, command, detail, token=''):
    """#831: None when the owner answered Yes on this step's card today (recorded by the hook),
    else the refusal naming the card to ask."""
    question = f'{OWNER_STEP}: {command}' + (f' ({token})' if token else '')
    topic = card_topic(OWNER_STEP, f'{question}\nYes')
    path = workspace.day_dir(root) / 'events.jsonl'
    rows = path.read_text(encoding='utf-8').splitlines() if path.is_file() else []
    if any('"gate.asked"' in line and topic in json.loads(line)['payload'].get('topics', ())
           for line in rows):
        return None
    card = {'question': question, 'header': OWNER_STEP, 'multiSelect': False,
            'options': [{'label': 'Yes', 'description': detail},
                        {'label': 'No', 'description': 'Nothing changes.'}],
            'record': command}
    return (f'{command}: waits for the owner; ask this Owner step card with AskUserQuestion, '
            f'then run the command again on Yes: {json.dumps(card)}')
```

- The topic hashes the question and the reply, so no command text (a config value, a reason)
  is written to the log, and redaction never changes it.
- Today's log only, read-only, no state read: it works while `state.json` is unreadable.
- `gate.asked` is a reserved event kind (`commands/event.EVENT_PRODUCERS`), and
  `events.jsonl` is protected from tool writes, so only the hook writes it.
- No posture check: the card counts under strict too (spec Edge Cases).
- `sessions.py` is deleted by part 23; that part moves `card_topic`, `OWNER_STEP` and
  `needs_owner` to the module that keeps them (Handoff).

### The hook (`cli/wuwei/guards/decision.py`)

- `record_gate`: right after the `scope` and `agent_id` checks and before
  `state.read_state`, collect `card_topic(OWNER_STEP, f'{question}\n{reply}')` for every
  question whose `header` is `OWNER_STEP`, whose text starts with `OWNER_STEP + ': '`, and
  that has a reply in `tool_response.answers` (`_answer`). When any were found, call
  `state.append_event('gate.asked', {'session_id': session, 'topics': sorted(found)}, root)`.
  When every question was an Owner step question, return `(0, '')` there, so an unreadable
  state does not turn the record into an error. Other questions keep today's planner-only path.
- `check_question`: next to the `gate_question` skip, `continue` for an Owner step question
  (header `OWNER_STEP`), so the PreToolUse citation check does not ask for a D-n record.
- Part 14 deletes the decision guard; it must keep these two branches (Handoff).

### The forged-payload guard (`cli/wuwei/guards/protect_state.py`)

In `check_bash`, inside the `for command in commands` loop, before the interpreter check:

```python
if (_wuwei_action(command.argv) or [''])[0] == 'hook':
    return 2, ('wuwei hook runs only from Claude Code hooks, never from a tool call; '
               'run the command the hook guards instead')
```

`protect_state` is a records-area guard, so it blocks in every posture. The heartbeat probes
call the hook as a subprocess of `status --line`, not as a tool call, so they are unaffected.

## Process control: what each changed unit was

| Unit | Kind | Where its job goes |
|---|---|---|
| `_host_confirm` y/N at `/dev/tty` for the seven call sites below | (b) stops an unconfirmed owner step (spec skip, merge hold release, config write, integrity confirm, state restore, strict seat stop, doctor fix, telemetry send) | kept: `sessions.needs_owner`, the owner's recorded Owner step answer |
| `config set` session branch (redirect to `calibrate --questions` or a decision record with Value rows) and strict branch ("run it in a host terminal") | (a) made the model route a config change through a decision record | deleted: `config set` asks its own Owner step card |
| "in a host terminal" in refusal and help texts | (a) sent the owner outside the session | deleted: the text names the command, which asks its own card |
| Bash `wuwei hook` | (b) new check: a session could feed the hook a forged owner answer | `protect_state.check_bash` |

No unit is deleted without its job moving. No config key is retired.

## Callers converted (code that stays)

Each uses `reason = sessions.needs_owner(...)` and refuses with `reason` (exit 1) when it is
not None. Import `sessions` inside the function where the module is on the hook path
(`integrity.py`, `state.py`).

| Call site | Command (card question) | Token | Detail (the Yes description) |
|---|---|---|---|
| `plan.py:_owner_confirm`, from `set_spec` (spec=skipped) | `shlex.join(['bin/wuwei', 'plan', 'set', item, 'spec=skipped', '--reason', reason])` | none | `Skip the spec for <item>: <reason>` |
| `plan.py:_owner_confirm`, from `set_owner_merge` (false) | `bin/wuwei plan set <item> owner_merge=false` | none | `Release the owner merge hold on <item>` |
| `commands/config.py:offer` (config set, add-repo, promote; setup's own call too) | new kw `command`, default `f'bin/wuwei {label}'` | the existing 12-character summary digest | `Apply the <what>:` plus the printed summary |
| `integrity.py:reconfirm` (when `confirm` is None) | `bin/wuwei integrity reconfirm` | `fingerprint[:12]` | `Confirm plugin installation <fp12> on this host.` |
| `commands/state.py` to `state.recover` | `bin/wuwei state recover` | snapshot `digest[:12]` | `Restore today's state from its snapshot.` |
| `commands/seat.py:run` under strict | `bin/wuwei seat stop <name>` | none | `Stop seat <name>.` |
| `commands/doctor.py:fix` (when `confirm` is None) | `bin/wuwei doctor --fix`, plus ` --apply <labels>` when `only` is set | the 12-character text digest | the printed fix preview |
| `commands/telemetry.py:_send` | `bin/wuwei telemetry send <week>` | `sha256(title\nbody)[:12]` | today's prompt text (repository, title, body) |

Details per file:

- `plan.py:_owner_confirm(command, prompt)` becomes `_owner_confirm(root, argv, detail)`:
  `if reason := sessions.needs_owner(root, shlex.join(['bin/wuwei', 'plan', 'set', *argv]),
  detail): raise state.StateError(reason)`. Both callers pass their real argv (the reason
  text, not `<why>`). The `integrity` import goes.
- `commands/config.py:offer`: `if confirm is None:` use the helper and print its reason to
  stderr, return `FINDINGS`; else keep `confirm(digest)` with the declined text
  `wuwei <label>: declined; nothing written; run it again`. Docstring: "confirm on the owner's
  Owner step card". Help strings for `promote`, `set` and `add-repo` drop "host terminal"
  (`(owner, asks on a card)`).
- `commands/setup.py:set_value`: delete `session`, the strict branch and the session branch
  (from `session = sessions.current() ...` to the session `return FINDINGS`); keep the
  `--from-card` branch (outside strict, part 14 deletes it) and the final `_edit` call, with
  `command=shlex.join(['bin/wuwei', 'config', 'set', *given])` passed through `_edit` to
  `offer`. `add_repo` passes `command='bin/wuwei config add-repo'`. Drop imports that become
  unused (`interview` here).
- `integrity.py:reconfirm`: `if confirm is None:` use the helper, return
  `Result(1, reason=reason)`; else `if not confirm(result.data)` returns
  `Result(1, reason='integrity re-confirmation declined; run bin/wuwei integrity reconfirm again')`.
  The comment "after the terminal interaction" becomes "after the owner's answer".
  `_host_confirm` and `HOST_TERMINAL` stay for the left callers.
- `state.py:recover(root, *, confirm)`: `confirm(token)` now returns None to proceed or a
  refusal; `if (reason := confirm(digest[:12])): raise StateError(reason)`. The two
  `read_state` texts become `run bin/wuwei state recover` (it asks the owner on its card).
- `commands/state.py`: `confirm=lambda token: sessions.needs_owner(root, 'bin/wuwei state
  recover', "Restore today's state from its snapshot.", token)` with
  `root = workspace.find_workspace()`; help text `(owner, asks on a card)`.
- `commands/seat.py:run`: the strict branch uses the helper (`refuse(FINDINGS, reason)`); the
  non-strict refusal becomes `seat stop runs from the planner session; run it there`.
- `commands/doctor.py:fix`: `if confirm is None:` use the helper, print the reason, return 1;
  else keep `confirm(digest)`. The `OSError` branch goes with the terminal. The `--widget`
  error text becomes `... run wuwei doctor --fix, which asks on its Owner step card`.
- `commands/telemetry.py:_send`: helper instead of `_host_confirm`; the declined text goes;
  help text `(owner, asks on a card)`.

## Callers and texts left (code a later part deletes)

These keep `_host_confirm` or their terminal text until the named part deletes the code. Each
is a LEFT row `(file, substring, part)` in the new test; the deleting part deletes the row.

| File: unit | Why left | Part |
|---|---|---|
| `undo.py` (whole), `commands/decision.py:undo` | undo door | 10 (#815, this batch) |
| `grants.py`, `commands/grants.py` (whole) | grants | 11 (#816, this batch) |
| `merge.py:by_grant`; `merge.check` texts "allows no merge method", "does not allow the ... method" and the owner_paths `Routed` text | grant merge path and owner block, which part 11 rewrites | 11 (#816) |
| `commands/setup.py` interview (`_setup`, the `setup` parser help, `raise OSError(integrity.HOST_TERMINAL)` sites), `interview.py:HOW`, `commands/calibrate.py`, `commands/next.py` setup rows in `step` and `THEN['calibrate']` | setup interview and calibration cards | 12 |
| `consolidation.py:forget`, `commands/memory.py` forget help, `commands/next.py:THEN['goals']` | consolidation and owner edits | 13 |
| `decision.py:owner_confirm`, `decision.py:no_card` strict suffix, `commands/decision.py` (`outcome` help, `owner_outcome` declined text), `commands/doctor.py:_day` "under strict you run it in a host terminal" | decision cards and decide | 14 |
| `drafts.py:approve`, `commands/drafts.py` help, `commands/outbound.py:learn` (outward.servers), `tracker.py:check` and `tracker.py:_held` strict branches | drafts, learning cards, held tickets | 16 |
| `mcp.py` (whole), `commands/doctor.py:_gates` MCP row, `guards/protect_state.py:_hint` registry (ziran) row | MCP registry gate | 18 |
| `integrity.py:HOST_TERMINAL`, `integrity.py:_host_confirm` (`/dev/tty`) | still called by the rows above | the part that deletes the last caller (18) |
| `tracker.py:relabel` ("init --upgrade in a host terminal") and the `sys.stdin.isatty()` label condition in `commands/init.py` (not a text; not caught by the test) | lifecycle labels | 20 |
| `watch.py:health` ("watch install in a host terminal"), `commands/setup.py` watch install text | the watch | 23 (setup text: 12) |

`scripts/headless_e2e.py` drives a D-1 answer through `/dev/tty`; it is not CLI text and goes
with decide in part 14.

## Texts rewritten (code that stays)

One rule for the common case: "with bin/wuwei config set ... in a host terminal" and "with
bin/wuwei config add-repo in a host terminal" lose " in a host terminal"; those commands now
ask their own card. Hand edits lose the terminal ("the owner edits the baseline"; "the owner
removes the duplicate [[repos]] entry in config.toml"). "run wuwei state recover in a host
terminal" and "integrity reconfirm in a host terminal" or "on the host" become the plain
command. Files:

- `cli/wuwei/workspace.py`: `zone`, `_validate` (3), `load_config` (6).
- `cli/wuwei/commands/doctor.py`: `_calibration`, `_day` (6 of 7; the strict clause is left),
  `fix`.
- `cli/wuwei/dispatch.py`: `tracker_call`, `opinion` (3).
- `cli/wuwei/tracker.py`: `full_id`, `create` (2); the strict branches and `relabel` are left.
- `cli/wuwei/merge.py`: `bot_evidence`, the `check` typo text ("the owner fixes it in
  config.toml"), `baseline` ("ask the owner to add that line to the baseline").
- `cli/wuwei/integrity.py`: `measure` (2), `check`, `confirmed`, `cached` (2), `fresh`,
  `reconfirm` (2).
- `cli/wuwei/guards/commit_push.py` (3), `cli/wuwei/guards/pr.py:api_check`,
  `cli/wuwei/guards/stop.py:check` (`run bin/wuwei state recover; it asks the owner on its
  card`), `cli/wuwei/guards/deploy.py:git` (`if it publishes, run it as a plain literal
  command`, no terminal), `cli/wuwei/guards/protect_state.py:_hint` config.toml and integrity
  rows (the command; "outside agent tools" goes).
- `cli/wuwei/commands/build.py` (`wait`, `run_loop`), `cli/wuwei/commands/worktree.py:add`,
  `cli/wuwei/registry.py:validate`, `cli/wuwei/security.py:honeytoken_path`,
  `cli/wuwei/outward.py:lint`, `cli/wuwei/pr_actions.py:_rebase`,
  `cli/wuwei/promotion.py` (`_target`, `_ensure_clean`), `cli/wuwei/shepherd.py` (6; the two
  "bin/wuwei setup" ones become `bin/wuwei config set shepherd.authors`).
- The same suffix drop in code later parts delete but whose text has no terminal flow:
  `closing.py` (2), `obligations.py:_owner_login`, `voice.py:learn` (2),
  `commands/note.py:run_add`, `calibrate.py` (`drift`, `host`, `propose_checks`, `report`,
  `survey`: "config promote" and "config set" now ask their own card; "on the host" goes).

Docstrings are not owner text; the test skips them, and they are not edited.

The existing reason lints in `tests/test_reasons.py` still apply to every rewrite: each reason
names a next step; seat-facing reasons have no pronoun; person-facing text
(`commands/doctor.py`, `commands/setup.py`, `next.step`, widget text) never says "the owner"
(say "you" there, for example "run wuwei state recover; it asks you on a card").

## Files to edit, tests (TDD order in tasks.md)

- `tests/fakes/owner.py` (new): `answer(root, command, token='', reply='Yes',
  session='planner-session')` calls `guards.decision.record_gate` with a PostToolUse
  AskUserQuestion payload for the Owner step question and asserts `(0, '')`.
- `tests/test_card_confirms.py`: new cases for the helper and the hook (FR-001, FR-002, US2);
  the config set session and strict cases (`test_strict_session_names_the_host_terminal`,
  `test_strict_host_terminal_ignores_the_card_and_prompts`,
  `test_config_set_in_a_session_without_a_card_names_the_card`,
  `test_config_set_in_a_host_terminal_prompts_as_today`,
  `test_session_hint_names_value_rows_and_the_previous_line`) become: no answer names the
  Owner step card and writes nothing, in a session, outside one and under strict; the answer
  writes the value. The decide cases stay.
- `tests/test_protect_state.py`: `bin/wuwei hook PostToolUse`, `wuwei hook SubagentStop` and
  `python3 -P -m wuwei hook PreToolUse` refuse with exit 2; `bin/wuwei next` passes.
- `tests/test_plan.py` (the `no_terminal` cases near 485-562), `tests/test_merge.py`
  (owner_merge=false near 1370), `tests/test_state.py` (recover near 650-681),
  `tests/test_integrity.py` (reconfirm and reconfirm texts near 778, 864, 901, 1115; the two
  `_host_confirm` unit tests stay), `tests/test_doctor.py` (654, 879, 927, 936, 952, 1082,
  1214-1217, 1283), `tests/test_telemetry.py` (near 448), `tests/test_handback.py` (near
  365-375): replace `_host_confirm` monkeypatches with no answer (refusal names the card) and
  `owner.answer(...)` (proceeds).
- `tests/test_reasons.py`: `test_no_text_sends_the_owner_to_a_terminal` and its LEFT rows.
- `tests/test_invariants.py`: delete the OWNED rows whose text is no longer a wall
  (`guards/commit_push.py` x3, `guards/pr.py`, `integrity.py` "page: plugin integrity"); keep
  the EXEMPT rows whose substring still matches (`guards/stop.py`, `guards/deploy.py`).
- Any other touched test that asserts a rewritten text (`tests/test_workspace.py`,
  `tests/test_dispatch.py`, `tests/test_commit_push.py`, `tests/test_pr_guards.py`,
  `tests/test_shepherd.py`, `tests/test_build.py`): update the expected text only.

## Files to edit, governance and docs

- `charters/planner.md`: rule 4 ends "Only the owner skips one item's spec:
  `wuwei plan set <item> spec=skipped --reason <why>` asks the owner on its Owner step card."
  Add one sentence to the same list: "A command that refuses with an Owner step card: ask that
  card with AskUserQuestion as printed; on Yes run the same command again; on No leave it."
  Then `bin/wuwei agents build`.
- `skills/wuwei-retro/SKILL.md`: "When that command says it runs in a host terminal, show the
  owner that line" becomes the Owner step sentence above. `skills/wuwei-consolidate` goes with
  part 13.
- `docs/specs/2026-09-24-wuwei-design.md` 9.1: one paragraph "Owner answers (owner,
  2026-10-11, #831)": nothing runs in a terminal; an owner step refuses with its Owner step
  card, the hook records the owner's reply from a main session, the command reads it from
  today's event log; seats' questions and Bash `wuwei hook` never count; the boundary is the
  one the terminal prompt had. The strict sentence about the host terminal in 9.1 and the
  merge and grant lines (356, 370) are left to part 11, which rewrites them.
- `docs/site/*`: no edit unless a test forces one; the site is rewritten in part 24.

## Handoff

- Part 11 (#816), next on this branch. Its plan adds "the owner runs it in a host terminal"
  to the deploy guard, the merge owner-block row in `next`, the charters and constitution VII.
  The new test refuses those texts. Part 11 must instead:
  - let `merge.execute` merge a PR the policy routes to the owner when
    `needs_owner(root, f'bin/wuwei merge {ref}', <why>, head[:12])` is None, and name that card
    when it is not; the `next` row asks the card;
  - let the deploy guard allow a deploy, release or publish command when
    `needs_owner(root, <the exact command>, ...)` is None, refusing with the card otherwise;
  - word the constitution VII amendment as "runs only on the owner's recorded Owner step
    answer", not "from the owner's host terminal";
  - delete the LEFT rows for `grants.py`, `commands/grants.py` and `merge.py`.
- Part 10 (#815): delete the `undo.py` and `commands/decision.py:undo` LEFT rows.
- Part 14 (decision guard): keep the Owner step branches of `record_gate` and
  `check_question` (move them with the gate record they live in).
- Part 17 (edges) and part 23 (state guard): carry the Bash `wuwei hook` refusal into the edge
  guard.
- Part 23 (sessions): move `card_topic`, `OWNER_STEP` and `needs_owner` to the module that
  stays.
- The part that deletes the last `_host_confirm` caller deletes `_host_confirm`,
  `HOST_TERMINAL`, their tests in `tests/test_integrity.py` and their LEFT rows.

## RETIRED at rebase

None. This part retires no config key or table.

## Risks

- Part 11 conflict (above): if its builder follows its plan as written, the new test fails.
  The lead should point part 11's builder at the Handoff before it starts.
- A seat runs in the planner's session environment and could rerun an owner step the owner
  approved. It can only run exactly what the card showed (same command and token); this is
  the same reach the planner has.
- Owner steps answered from an adhoc main session count. That is the owner's reply; a
  workspace with several open sessions has several places to answer.
- Agents are generated files and part 9's builder is editing them now: rebuild with
  `bin/wuwei agents build` after part 9 is done, never by hand.
