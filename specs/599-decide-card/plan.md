# Implementation Plan: A card answer confirms the record command without the session id in the environment

**Branch**: `599-decide-card` | **Date**: 2026-10-10 | **Spec**: `specs/599-decide-card/spec.md`

## Summary

One shared fix: the CLI resolves the calling session from state when `WUWEI_SESSION_ID` is
missing and the caller has no terminal on stdin (or passes `--card`). Both card readers,
`decision.owner_confirm` and `sessions.card_answered`, go through it, so `decide`, `mcp
decide`, `decision undo`, `config set --from-card` and `calibrate --answer` accept the card
again. Then: the widget's record command carries `--card <hash>`, a 12-character hash of the
card's Question and Options that `owner_confirm` checks against the record as it stands; an
`env_file` flag on the SessionStart `session.seen` payload with one doctor row; the rerun rule
in the planner skill and the guide; invariants I29 and I30.

## Starting point

- Line numbers below are on current `main` (0.24.1). The branch base `6627e24` is older;
  work against main.
- The working tree holds an earlier attempt of this item with `--card` as a bare flag and
  invariant I25. Reuse the pieces this plan keeps unchanged (`sessions.caller`, the
  `env_file` payload flag and `_seen` keyword pass, the doctor row, `no_card`, the seat hook
  test, the `Terminal` stdin helper in the tests); replace the flag with the hash, and use
  I29 and I30 (I25 belongs to #605 on main).

## Technical Context

Python 3.11+, stdlib only (`os`, `sys`, `hashlib` through `sessions.card_topic`); pytest for
tests. Run the touched files while building, then the full suite once:
`python -m pytest -q tests/test_card_confirms.py tests/test_decision.py tests/test_mcp.py
tests/test_sessions.py tests/test_doctor.py tests/test_guide.py tests/test_charters.py
tests/test_docs.py tests/test_outbound_learn.py tests/test_invariants.py`.

## Constitution Check

- I stdlib: yes.
- II exits: `--card` without a confirmation is exit 1 with a reason (the existing decline
  exit); no new exit 2.
- III one behaviour, one function: session resolution lives in `sessions.caller`; the card
  rule (hash, asked topic, no prompt) lives in `decision.owner_confirm`; the hash in
  `decision.card_hash`. Nothing re-implements `gate_topics` or `card_topic`.
- IV test first: every task pair in `tasks.md`.
- V ponytail: no new module, state key, event kind or config; the hash is computed, never
  stored.
- VII security and #530: no wall added below strict (a mismatched or unasked `--card` exits 1
  pointing at the card); strict unchanged (hook refusal, I8); seats refused by the hook before
  the CLI (I8, plus an explicit test). Rows I29 and I30 in design 9.2 and
  `tests/test_invariants.py`.
- Hook path: SessionStart puts one bool on an event it already writes; no read, write,
  import or event is added (#346, #587 latency). `protect_state` and `record_gate` do not
  change: `--card <hash>` is not a `D-n` word, so the hook's asked-id check reads the command
  as today.

## Changes, by file

1. `cli/wuwei/sessions.py` (`current` at line 22, `card_answered` at 48, `touch` at 89,
   `export` at 180)
   - New `caller(root, card=False)` next to `current()` (`import sys` at the top):
     ```python
     def caller(root, card=False):
         """#599: the exported session id, else today's planner for a caller with no terminal
         on stdin or a --card record command; None for a host terminal."""
         if (session := current()) or (sys.stdin is not None and sys.stdin.isatty() and not card):
             return session
         return state.read_state(root).get('planner_session_id')
     ```
     `current()` stays as is; its other callers (`merge`, `shepherd`, `brief`, `seat`,
     `setup.set_value`, `claim_item`, `next`) keep the environment meaning.
   - `card_answered`: `gate_topics(root, caller(root))`.
   - `export`: `return bool(path)`.
   - `touch(..., env_file=None)`: the `session.seen` payload gains `'env_file': env_file`
     only when it is not None.
2. `cli/wuwei/decision.py`
   - New `card_hash(identifier, fields)`, next to `record_widget` (line 246):
     ```python
     def card_hash(identifier, fields):
         """#599: the card the owner saw, as the widget's record command carries it."""
         from wuwei.sessions import card_topic
         return card_topic(identifier, f'{fields["Question"]}\n{fields["Options"]}').split('=', 1)[1][:12]
     ```
   - `RECORD = 'wuwei decide {id} "<label>" --card {card}'`; in `record_widget` (line 260)
     `record.format(id=identifier, card=card_hash(identifier, fields))`. `str.format`
     ignores the unused keyword, so `mcp.RECORD` and `CONFIG_RECORD` print as today.
   - `owner_confirm(root, identifier, digest, prompt, card=None, fields=None)` (line 520):
     ```python
     from wuwei import sessions
     if card is not None and card != card_hash(identifier, fields):
         return ''  # the record changed since its card, or not a card hash
     if identifier in sessions.gate_topics(root, sessions.caller(root, card is not None))[0]:
         return 'in the planner session'
     if card is not None:
         return ''
     from wuwei.integrity import _host_confirm
     return 'at the host terminal' if _host_confirm(digest, prompt=prompt) else ''
     ```
   - New `no_card(root, identifier, option)` (the working tree has it; its reason gains
     `for this record`): `decision:
     {identifier} has no card answer for this record from the planner session; ask it with
     bin/wuwei decision show {identifier} --widget and run its record command`, plus under
     strict `; under strict the owner runs bin/wuwei decide {identifier} {option} in a host
     terminal`.
3. `cli/wuwei/commands/decide.py`: `parser.add_argument('--card', metavar='HASH',
   help='the card hash from the widget record command; the owner answered it in the planner
   session, so it never prompts')`; pass `card=args.card` to `mcp.decide`.
4. `cli/wuwei/commands/decision.py` `owner_outcome` (line 178, call at 204): `card =
   getattr(args, 'card', None)`; `owner_confirm(..., card, fields)`; when `not where and card
   is not None` return `1, no_card(root, args.id, args.option)` before the existing decline.
   Namespace callers without `card` (`config set --from-card`, `outbound`, the DM listener)
   are unaffected. `undo` keeps its call (no `card`).
5. `cli/wuwei/mcp.py` `decide(..., card=None)`: pass `card, fields` to `owner_confirm`; with
   `card` and no `where`, `Result(1, reason=decision.no_card(root, identifier, option))`;
   otherwise `DECLINED` as today.
6. `cli/wuwei/guards/lifecycle.py` (`_seen` at 34, export at 62): `env_file =
   sessions.export(...)` when the payload has a session id, and `_seen(root, payload,
   'SessionStart', env_file=env_file)`; `_seen(root, payload, event, **extra)` passes the
   keywords to `sessions.touch`.
7. `cli/wuwei/commands/doctor.py` `_day` (line 576, after the `traces` row at 621): one row
   `('day', 'session id', ...)` from `watch.records(workspace.day_dir(root) /
   'events.jsonl')`, the last `session.seen` whose payload has `env_file`. True or none: ok
   (`SessionStart exported it` / `not recorded today`). False: warn `SessionStart had no
   CLAUDE_ENV_FILE, so Bash calls do not carry WUWEI_SESSION_ID; record commands for asked
   cards confirm through the planner in state`, fix `update Claude Code so SessionStart gets
   CLAUDE_ENV_FILE, then start a new session`. `watch.ERRORS`: an unmeasured row. If `_day`
   already reads today's events, reuse that list instead of a second read.
8. `cli/wuwei/guide.py` Records and questions paragraph (line 75) and
   `skills/wuwei-plan/SKILL.md` `card` bullet: one sentence each, after "Record each answer
   with its `record` command": "A decision record command that exits non-zero on the
   confirmation: run the `record` command `wuwei decision show D-n --widget` prints (`wuwei
   decide D-n "<label>" --card <hash>`) without asking the card again; below strict never
   show the owner a host-terminal command for a card they answered." Regenerate
   `docs/site/agent.md` if a test compares it with the guide.
9. `docs/site/reference.md`: the `decide` command row and the Host terminal actions row
   gain `[--card <hash>]`; the `--widget` sentence of Decision record names `wuwei decide
   D-<n> <label> --card <hash>` and says the hash is the card's (Question and Options), so a
   record changed after the card does not record from it.
10. `docs/specs/2026-09-24-wuwei-design.md` 9.2, after I28 (keep the id order; I31 follows):
    ```
    | I29 | A decision record command for a card the planner asked never prompts below strict, with and without `WUWEI_SESSION_ID`; under strict it never records from the card | per posture, `decision.owner_confirm` on the planner's asked D-99 with the variable set and unset x no card and the record's card hash, stdin not a terminal, `_host_confirm` recording each call | #599; the seat refusal stays in `tests/test_card_confirms.py` |
    | I30 | A `--card` record command confirms only the card of the record as it stands: a hash from an edited record never records and never prompts | per posture, `decision.owner_confirm` on the asked D-99 with the hash of the record with its Options changed | #599 |
    ```
11. `tests/test_invariants.py`: `i29` and `i30` reading one memo per posture, `compute`
    built once (no `main()`, no doctor or test-module import, no guard run inside the walk):
    configure the posture; add `D-99` to `planner-1`'s `gate_asked` and restore it after (D-1 is the world's deploy card that other rows read); `fields =
    {'Question': 'q', 'Options': 'o'}`, `changed = {**fields, 'Options': 'p'}`; replace
    `integrity._host_confirm` with a recorder returning False and `sys.stdin` with
    `io.StringIO()`; for `WUWEI_SESSION_ID` in (`planner-1`, unset) x card in (None,
    `card_hash('D-99', fields)`) call `owner_confirm(root, 'D-99', 'x' * 64, 'p', card,
    fields)`; then once with `card_hash('D-99', changed)`; restore everything in `finally`.
    I29 below strict: all four results `in the planner session`, no prompt; strict: none
    `in the planner session`, prompts only for the two calls without a card. I30: the
    changed-hash call returns `''` with no prompt in every posture. `INVARIANTS` and
    `READS` (`(0,)` each). `BROKEN`: `'session id only from the environment'` patching
    `wuwei.sessions.caller` to `lambda root, card=False: sessions.current()` (fails I29);
    `'card hash ignored'` patching `wuwei.decision.card_hash` to a constant (fails I30).

## Shared helpers reused

`sessions.gate_topics` (strict and planner checks), `sessions.current`,
`sessions.card_topic` (the #529 hash), `state.read_state`, `watch.records` (doctor event
read), `decision.record_widget`, `decision.option_id`, `integrity._host_confirm` (terminal
path unchanged), the `ws`, `answer()`, `config_card()`, `no_terminal()` and `hook()` helpers
in `tests/test_card_confirms.py`.

## What must not change

- `sessions.current()` and every caller of it except `card_answered` and `owner_confirm`.
- `sessions.gate_topics`, `guards/protect_state.py`, `guards/decision.py` (`record_gate`):
  no hook logic changes; I8 holds as is.
- `integrity._host_confirm`, `drafts.approve`, `consolidation.forget`,
  `setup.set_value`'s own session check, `decision.undo`'s identifier.
- The non-card decline messages and exits of `decide`, `decision undo`, `mcp decide`.
- `mcp.RECORD` and `CONFIG_RECORD`.
- Strict: no card is ever a confirmation.

## Test updates the builder expects

- Record pins: `tests/test_card_confirms.py:354`, `tests/test_decision.py:1236`,
  `tests/test_outbound_learn.py:170` become `wuwei decide D-n "<label>" --card <hash>` with
  the hash from `decision.card_hash` of that record (grep `'record'` for any other pin, for
  example in cruise and grants tests).
- `test_card_answered_only_for_the_planner_outside_strict` and any test that meant "no
  variable is a host terminal" while a topic was asked: pytest's stdin is not a terminal, so
  give it a `Terminal()` stdin; never change the rule to fit a test.
- Doctor tests that pin the list of Day rows gain the `session id` row.
