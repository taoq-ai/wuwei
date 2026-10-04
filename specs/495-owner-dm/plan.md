# Implementation Plan: a message to the owner's own DM or user id is never a draft

**Branch**: `495-owner-dm` | **Spec**: `specs/495-owner-dm/spec.md`

## Summary

One predicate, `outward.owner_only(context, config, kind)`, answers "is the owner the only
audience of this call" from a new config table `outbound.owner`. `classify` uses it as one
early `send` rule; `check_tier` records `outward.to_owner` when it lets such a call through;
`check_lint` lints it with `to_owner=True`, as `remote.dm` already does. The DM rule names
`unknown DM recipient <id>`. #492's `outbound learn` takes one more listing file, `--owner`,
and its card and `apply` carry the identity. Setup fills the identity it already measures.
Two skills say where to post when `owner_channel = "dm"`.

## Technical Context

Python 3.11+, stdlib only. No new module, no new dependency, no new import on the hook path
(`state` is imported lazily inside the event branch, as `humanize_lint` does).

Dependency: #492 (`outbound learn`, `guards.outward.resolve`, `outward.unknown_audience`,
`outward.modes`) is not on main at edc10e7. Phase A below needs nothing from #492 except that
the guard-level tests use a fixture UUID connector name, which only #492 resolves; on a branch
without #492 those two tests use `mcp__slack__slack_send_message` until the rebase. Phase B
edits #492's code and starts only after the branch holds #492 (tasks.md, checkpoint).

Files changed:

- `cli/wuwei/workspace.py`: `SCHEMA['outbound']` (`owner`, `owner_channel`),
  `CONFIG_CACHE_VERSION` + 1.
- `cli/wuwei/outward.py`: `OWNER`, `owner_only()`; `classify` (one rule, the DM reason);
  `check_tier` (event); `check_lint` (`to_owner`); #492's `unknown_audience` (Phase B).
- `cli/wuwei/commands/event.py`: `EVENT_PRODUCERS['outward.to_owner']`.
- `cli/wuwei/signal.py`: `'outward.to_owner'` in `SILENT`.
- `cli/wuwei/commands/outbound.py` (#492): `--owner`, `_owner()`, `propose`, `record`,
  `apply`, `learn` (Phase B).
- `cli/wuwei/commands/setup.py`: `identity()`, `connect()`.
- Docs: `docs/site/configuration.md`, `docs/site/security.md`,
  `templates/workspace/config.toml`, `skills/wuwei-plan/SKILL.md`,
  `skills/wuwei-report/SKILL.md`.
- Tests: `tests/test_outward.py`, `tests/test_hooks.py`, `tests/test_signal_status.py`,
  `tests/test_outbound_learn.py`, `tests/test_setup.py`, `tests/test_docs.py`.

## Constitution Check

- I stdlib only: yes.
- II exits: unchanged shapes. `owner_only` raises `ValueError` on a malformed payload through
  `_text`; every caller already turns that into exit 2 and a draft. `outbound learn --owner`
  with an unreadable file exits 2, an invalid one exits 1 naming the shape.
- III one behaviour, one function: "the owner is the only audience" is `owner_only` only;
  classify, check_tier and check_lint call it. The identity write is #492's `apply` only.
- IV test first: every behaviour has a failing test task before its implementation task.
- V ponytail: one config table, one predicate, one rule; no new module, no new card type, no
  new writer, no env read on the hook path. Mail and code-host identity come from setup, not
  a second learn path (spec A4).
- VII security: the security check (`security.outbound`) still runs before `classify` and the
  outward lint still runs after it; the identity reaches config only through the owner's card
  answer (never `"auto"`) or the setup digest; the event is reserved; `SLACK_OWNER_DM_CHANNEL`
  is never recorded as the owner's DM (spec A7).

## Design

### 1. Config (`cli/wuwei/workspace.py`, `SCHEMA['outbound']`, line 154)

```python
"owner": {"slack": {"user": (str, ""), "dm": (str, "")}, "mail": (str, ""),
          "code_host": (str, "")},
"owner_channel": (str, "session", ("session", "dm")),
```

Bump `CONFIG_CACHE_VERSION` by one from whatever the branch holds (7 on edc10e7; #492 may
have bumped it).

### 2. `owner_only` (`cli/wuwei/outward.py`, after `_text`)

```python
OWNER = {'chat': 'slack', 'slack': 'slack', 'mail': 'mail'}  # #495: kinds with a private audience


def owner_only(context, config, kind):
    """#495: True when the owner alone is addressed: every destination and recipient is the
    owner's identity in outbound.owner for this kind. A nested draft wrapper never is."""
    if not isinstance(context, dict) or 'draft' in context:
        return False
    found = config['outbound']['owner'].get(OWNER.get(kind), '')
    mine = {value.casefold() for value in (found.values() if isinstance(found, dict) else [found]) if value}
    _, destinations = _text(context)
    targets = [*destinations, *context.get('recipients', []), *filter(None, [context.get('recipient')])]
    return bool(mine and targets) and all(target.casefold() in mine for target in targets)
```

`code_host` is not in `OWNER` (spec A5). `_text` validates the payload; a malformed one raises
as it does for `classify`.

### 3. `classify` (`cli/wuwei/outward.py:297-441`)

- Right after line 316 (`_, destinations = _text(context)`), before the nested-draft merge:

  ```python
  if owner_only(context, config, kind):
      return CLEAN, 'send'  # #495: only the owner reads it; security and the lint still run.
  ```

  The headless shepherd rule (line 311) stays first (spec A3).
- The DM branch (lines 342-344) becomes:

  ```python
  who = next(iter(destinations), None) or context.get('recipient')
  if who:
      return held(f"unknown DM recipient {who}: not the owner's DM or user id in outbound.owner.slack")
  return tier('direct message', 'every direct message drafts')
  ```

  The second line keeps today's reason for the adapter `chat.dm` port, whose inputs carry no
  destination (spec A6).

### 4. `check_tier` and `check_lint` (`cli/wuwei/outward.py:462-497`)

- `check_tier`, after `classify` returns `send` (line 479, before `return CLEAN, ''`):

  ```python
  if owner_only(inputs, config, kind):
      from wuwei import state  # Only a message to the owner pays for the event.
      state.append_event('outward.to_owner', {'channel': kind}, root)
  ```

  with `kind = next(iter(channels))` computed once and passed to `classify` too.
- `check_lint`, after the `len(channels) != 1` check:
  `to_owner = to_owner or owner_only(inputs, config, next(iter(channels)))`.
- The guard (`cli/wuwei/guards/outward.py`) needs no change in Phase A: `_lint` calls
  `outward.check_lint` and the tier guard calls `outward.check_tier`.

### 5. Reserved, silent event

- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `'outward.to_owner': 'the outward port and
  hook (wuwei.outward.check_tier)'`.
- `cli/wuwei/signal.py` `SILENT`: add `'outward.to_owner'` next to `'outward.ai_tells'`.

### 6. Phase B: the learn card (#492's `cli/wuwei/commands/outbound.py`)

- `register`: `learn_parser.add_argument('--owner', metavar='FILE', help="JSON {user, dm} from
  the connector's identity call (slack only)")`.
- `_owner(path)`: read a JSON object with exactly `user` and `dm`; `user` fullmatches
  `[UW][A-Z0-9]+`, `dm` is `""` or fullmatches `D[A-Z0-9]+` and is not
  `os.environ.get('SLACK_OWNER_DM_CHANNEL')` (the CLI loads `.wuwei/env` before commands).
  `OSError` propagates (exit 2); anything else raises `ValueError(f'{path}: expected a JSON
  object {{"user", "dm"}} with your Slack user id (U or W) and your own DM id (D, or empty),
  not the WUWEI app DM; write the file again')`.
- `propose(..., owner=None)`: `current = config['outbound']['owner']['slack']`;
  `new_owner = {key: value for key, value in (owner or {}).items() if value and not current[key]}`;
  nothing new also needs `not new_owner`; the proposal gains `'owner': new_owner`.
- `record(proposal)`: when `proposal.get('owner')`, the parts gain
  `your identity U01, DM D01` (only the fields present), the context gains
  `- owner U01, DM D01 from the connector's identity call`, and the `approve` rationale ends
  `and your identity`.
- `apply`: `owner = proposal.get('owner', {}) if option == 'approve' or mode else {}`; it
  counts toward "something to write"; settings gain
  `[(('outbound', 'owner', 'slack'), key, value) for key, value in owner.items()]`; the
  `outbound.learned` payload gains `'owner': bool(owner)`. `channels` and `keep` write no
  identity.
- `learn`:
  - Step 6 (listings need slack) and step 7 (no listing) count `args.owner` with
    `args.channels` and `args.people`.
  - Step 7's printed step, while `outbound.owner.slack.user` or `.dm` is empty, adds: `, and
    its identity tool (auth_test, users_me, whoami, or the tool whose name says identity or
    profile); write your user id and your own DM channel id as {"user", "dm"} in a JSON file
    and add --owner <file>`.
  - Read `owner = _owner(args.owner) if args.owner else {}` in the same try as the listings.
  - `card = ... or bool(owner)`: an owner identity always goes through the card.
- `outward.unknown_audience` (#492): a `D`/`U` destination counts as unknown while
  `not all(rules['owner']['slack'].values())`; everything else in it stays. That makes the
  guard's existing #492 suffix name `bin/wuwei outbound learn --tool <tool>` for a DM held
  because the identity is missing, and not for a DM to someone else once it is recorded.

`decision.owner_outcome` (#492) already calls `apply` with the answer; it does not change.

### 7. Setup (`cli/wuwei/commands/setup.py`)

- `identity()` (line 249), before the `authors` lines:

  ```python
  owner = config['outbound']['owner']
  if login and not owner['code_host']:
      settings.append((('outbound', 'owner'), 'code_host', login))
  email = next((found for repo in config['repos'] if (found := repo['identity']['email'].strip())), '')
  if email and not owner['mail']:
      settings.append((('outbound', 'owner'), 'mail', email))
  ```

- `connect()` (line 429): read `current = load_config(root)` once where the pin is checked;
  `pin = current['control_plane']['owner']` when it matches `remote.PIN`, else the measured
  `found.data`; then, when `not current['outbound']['owner']['slack']['user']`, append
  `(('outbound', 'owner', 'slack'), 'user', pin.split('/')[1])`. Never write
  `SLACK_OWNER_DM_CHANNEL` into `outbound.owner.slack.dm` (spec A7).

### 8. Skills and docs

- `skills/wuwei-plan/SKILL.md`, one paragraph after "Owner questions": when
  `outbound.owner_channel` in `.wuwei/config.toml` is `dm`, also post each digest and nudge
  shown to the owner to the owner's own Slack DM with the connector's send tool, addressed to
  `outbound.owner.slack.dm` (or `outbound.owner.slack.user` when `dm` is empty); a message to
  the owner goes out without a draft and still passes the outward lint, so write it in plain
  words. When `outbound.owner.slack` is empty, the first send is held and its reason names
  `bin/wuwei outbound learn`: run it, call the identity tool it names, and ask its card.
- `skills/wuwei-report/SKILL.md`, last paragraph: with `owner_channel = "dm"`, the day report
  also goes to the owner's DM the same way; any other outward post keeps its tier.
- `docs/site/configuration.md`: rows `outbound.owner` (identity table: `slack.user`,
  `slack.dm`, `mail`, `code_host`; learned on the card or proposed by setup; a message only the
  owner receives is never a draft) and `outbound.owner_channel` (`session` or `dm`); the
  sentence at line 401 becomes "Unknown destinations and direct messages to anyone but you
  draft by default."
- `docs/site/security.md` line 63: one sentence: a message only you receive (your DM or user
  id in `outbound.owner`, or a mail whose only recipient is you) passes the lint and goes with
  an `outward.to_owner` event; a DM to anyone else is held with `unknown DM recipient <id>`.
- `templates/workspace/config.toml` `[outbound]`: line 189 says every DM to anyone but you
  drafts; two commented lines,
  `# owner = {slack = {user = "U123", dm = "D123"}, mail = "you@example.test", code_host = "your-login"}`
  and `# owner_channel = "dm"` with a one-line note each.

## What must not change

- `outward.classify`'s `(code, 'send'|'draft')` contract and every other rule and its order;
  `pr_actions`, the ports and `outbound tier` depend on it.
- `security.outbound` before `classify`, and the outward lint after it, for every call.
- The adapter path: `remote.dm`, the chat port's `dm` (still a draft), `drafts.destination`
  and `drafts.approve` with `SLACK_OWNER_DM_CHANNEL`.
- `guards.OWNER_ONLY` and the posture handling; #492's resolution, modes and learn flow
  except the additions above; #493's draft card and `drafts.spend`.
- No import of `wuwei.drafts` or `hashlib` for a call that passes (#493, #346).

## Tests

- `tests/test_outward.py`: `test_owner_only` (table: DM id, user id, casefold, `recipient`,
  `recipients` with a stranger, two destinations, nested `draft`, unset identity, `mail`,
  `code_host`, `tracker`); `test_classify_to_owner` (D and U send, sensitive keyword and
  commitment still send, shepherd seat still drafts); `test_dm_recipient_rule` (the RULES row
  for `is_dm` to `C1` updated to `unknown DM recipient C1: ...`, a row for `U02` with the
  identity set, the port case with no destination keeps today's reason);
  `test_to_owner_event` (check_tier records one event, a draft records none);
  `test_lint_to_owner` (the owner's name passes, an emoji refuses);
  `test_guard_to_owner_every_posture` (the guard under observe, guarded and strict: exit 0,
  one event, no `drafts` row).
- `tests/test_hooks.py`: a row in `test_only_a_held_call_imports_the_draft_queue` for a send
  to the owner's DM (passes, no `wuwei.drafts`).
- `tests/test_signal_status.py`: `outward.to_owner` is silent and `wuwei event` refuses it.
- `tests/test_outbound_learn.py` (Phase B): the listing step names the identity tool and
  `--owner`; `--owner` validation (bad user, bad dm, app DM); the card question and context
  name the identity under `"auto"` and observe; `Approve` writes both fields and the guard
  then sends with the event; `Defer` writes nothing; a recorded identity is not proposed
  again; the guard reason for a DM with no identity names `outbound learn`, and with the
  identity recorded a DM to `U02` does not.
- `tests/test_setup.py`: `test_owner_identity` (identity settings, kept when set) and
  `test_slack_connect_owner_user` (pin to user id, never the DM channel).
- `tests/test_docs.py`: `test_owner_channel_in_skills`; the template keys test covers the new
  keys.
