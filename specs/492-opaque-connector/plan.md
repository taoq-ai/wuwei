# Implementation Plan: any connector name resolves its channel, config lists keep their defaults, unknown connectors, channels and people are learned on one card

**Branch**: `492-opaque-connector` | **Spec**: `specs/492-opaque-connector/spec.md` |
**Contract**: `specs/492-opaque-connector/contracts/outbound-learn.md` (CLI, listing files,
decision record, state and event shapes)

## Summary

One resolver in the outward guard (alias, rule, vocabulary) replaces the inline pattern
match at both call sites; the built-in rules take the brand anywhere; `_unmatched` and the
draft reason name `bin/wuwei outbound learn` instead of a config line. `config set` appends
to lists and adds table entries through one settings helper, which `outbound learn` reuses
to write what the owner approved. `outbound learn` is a planner command built from parts
that exist: the decision writer, owner routing, the #359 widget, `wuwei decide` and the
owner edit frame. The protect-state guard gets one reason for guard keys and one planner-only
rule.

## Technical Context

Python 3.11+, stdlib only. No new module under `cli/` (the learn command goes into the
existing `cli/wuwei/commands/outbound.py`), no new dependency, no new import on the hook path.

Files changed:

- `cli/wuwei/guards/outward.py`: `VOCABULARY`, `resolve()`, `_check`, `_unmatched`.
- `cli/wuwei/outward.py`: `MENTION`, `unknown_audience()`; `classify` uses `MENTION`.
- `cli/wuwei/workspace.py`: `SCHEMA` (rules, `outward.servers`, `outbound.learn`),
  `CONFIG_CACHE_VERSION`.
- `cli/wuwei/calibrate.py`: `apply` quotes keys under `outward.servers` and `outbound.people`.
- `cli/wuwei/commands/setup.py`: `schema_at()`, `effective()`, `merged()`; `set_value` uses
  `merged`.
- `cli/wuwei/commands/config.py`: `set --replace`, `show <key>`.
- `cli/wuwei/commands/outbound.py`: `learn` subcommand, `apply()`.
- `cli/wuwei/commands/decision.py`: `owner_outcome` applies a learn proposal.
- `cli/wuwei/guards/protect_state.py`: guard-key reason, `('outbound', 'learn')` planner rule.
- `cli/wuwei/state.py` (`STATE_PRODUCERS`), `cli/wuwei/commands/event.py`
  (`EVENT_PRODUCERS`).
- Docs: `docs/site/configuration.md`, `docs/site/security.md`, `docs/site/reference.md`,
  `templates/workspace/config.toml`, `skills/wuwei-plan/SKILL.md`.
- Tests: `tests/test_outward.py`, `tests/test_setup.py`, `tests/test_protect_state.py`,
  new `tests/test_outbound_learn.py`.

## Constitution Check

- I stdlib only: yes.
- II exits: guard refusals stay 1 (draft) or 2 (unknown write, strict unknown); `outbound
  learn` 0 proposed or written, 1 off, declined, nothing to learn, needs listings or an
  invalid listing, 2 unreadable file or state; `config show` 0, 1 unknown key.
- III one behaviour, one function: channel resolution is `resolve()` only; list and table
  merging is `merged()` only, used by `config set` and by the learn write; the owner's answer
  is recorded by `owner_outcome` only.
- IV test first: every behaviour has a failing test task before its implementation task.
- V ponytail: no load-time merge (spec A1), no new module, no MCP call from the hook, no
  new card type (a decision record), no new config writer (`setup._edit` with an
  always-yes confirm, since the decision answer is the confirmation).
- VII security: the approval policy (`outward.classify`) is unchanged; learned values reach
  config only through the owner's answer or `"auto"` (observe and guarded, reviewers only);
  `outbound learn` is refused for seats; `outbound_learn` and `outbound.learned` are
  reserved; listing names are validated before they reach a record or a card; events carry
  ids only.

## Design

### 1. Built-in rules, brand anywhere (`cli/wuwei/workspace.py:188-194`)

Each rule gets a lookahead for its brand and keeps its verb part after the last `__`:

```python
{"pattern": r"mcp__(?=.*slack).*__.*(send|post|reply|schedule|update|add_message|add_reaction|react|chat_post|delete|edit|upload|invite|kick|archive|pin|star).*", "channel": "slack"},
{"pattern": r"mcp__(?=.*linear).*__(?:\w*_)?(save|create|update)_(issue|comment)", "channel": "tracker"},
{"pattern": r"mcp__(?=.*github).*__(?:\w*_)?(add|create|update)_.*comment.*", "channel": "code_host"},
{"pattern": r"mcp__(?=.*notion).*__.*(create|update|append|patch|post|move|duplicate).*", "channel": "docs"},
{"pattern": r"mcp__(?=.*atlassian).*__(?:\w*_)?(create|update)Confluence.*", "channel": "docs"},
```

Matching stays `re.fullmatch(pattern, tool, re.IGNORECASE)`. Add to `SCHEMA['outward']`:
`"servers": {"*": (str, None, ("slack", "tracker", "code_host", "docs", "mail"))}`, and to
`SCHEMA['outbound']`: `"learn": (str, "card", ("card", "auto", "off"))`. Bump
`CONFIG_CACHE_VERSION` to 7.

### 2. `resolve(tool, config)` (`cli/wuwei/guards/outward.py`)

Module level, after `tool_kind`:

```python
# #492: tool vocabulary on the name words joined by '_'; used only when one channel matches.
VOCABULARY = (
    ('slack', r'(?:conversations|channels)_.*|chat_post.*|(?:.*_)?add_(?:message|reaction)s?(?:_.*)?'),
    ('tracker', r'(?:.*_)?issues?(?:_.*)?'),
    ('mail', r'(?:.*_)?(?:drafts?|labels?|threads?|spam|trash|forward|inbox|e?mails?)(?:_.*)?'),
    ('docs', r'(?:.*_)?(?:pages?|blocks?|databases?)(?:_.*)?'))


def resolve(tool, config):
    """#492: the channels of a tool: the owner alias, then the rules, then the vocabulary;
    reads skip the alias and vocabulary. config None is the schema defaults."""
```

- `rules = config['outward']['tool_patterns'] if config else SCHEMA default`; `servers =
  config['outward']['servers'] if config else {}`.
- Not an `mcp__` string: return the rule matches (today's behaviour for other names).
- `read = tool_kind(tool) == 'read'`. Server id: `tool[5:].rpartition('__')[0]`.
- Alias first when not `read`: compare server ids with `casefold()`; a hit returns `{channel}`.
- Rules: the set of matching channels, as today (two channels stay the ambiguous refusal).
- Vocabulary when not `read`: the words are split exactly as in `tool_kind` (factor the split
  into one small `_words(name)` used by both), joined by `_`; return `{channel}` only when
  exactly one entry fullmatches.
- Otherwise `set()`.

`_check` replaces both inline comprehensions (lines 108-109 and 123-124) with
`resolve(tool, config)`; everything else in `_check` keeps its order (the read pass, scope,
payload checks, ambiguity, the DM flag, the policy call).

### 3. Reasons name the learn command (`_unmatched`, the draft reason)

`_unmatched(tool, root, config, policy)` keeps its flow (#469) and builds one way out instead
of `line`:

- `learn = config['outbound']['learn'] != 'off'`.
- write: `outward: connector {server} is not known for write tool {tool}; write it as a draft
  for the owner to send` plus, when `learn`, `, and the planner runs bin/wuwei outbound learn
  --tool {tool}`.
- unknown, block: `outward: unknown MCP tool {tool} of connector {server}, not a read or a
  write by its name; ` plus the same way out.
- unknown, warn: the `outward.unknown_tool` event reason, same text with `passed under
  {name}`.

In `_check`, the draft branch (lines 133-135) keeps `outward: channel {channel} needs owner
approval; write it as a draft for the owner to send` and, for `slack` or `chat` when `learn`,
appends from `outward.unknown_audience(inputs, config)`: `; destination C01 and 2 mentions
are not known yet, so the planner runs bin/wuwei outbound learn --tool {tool}` (name only the
parts that are non-empty). `inputs` here is the payload input with the DM flag, as passed to
the policy.

### 4. `unknown_audience(inputs, config)` (`cli/wuwei/outward.py`)

```python
MENTION = r'(?<![\w@])@([\w.-]+)'  # classify uses it too (line 337)


def unknown_audience(inputs, config):
    """#492: (destinations, mentions) of a chat send that outbound config does not know yet:
    channel ids outside work_channels (DMs and external channels excluded) and @-mentions
    with no slack: entry in outbound.people. The tier itself stays in classify."""
```

Uses `_text(inputs)` for texts and destinations, `_normalize` for the text, and the
casefolded `outbound.people` keys. Returns two sorted lists. No new import.

### 5. Lists keep their defaults (`cli/wuwei/commands/setup.py`, `commands/config.py`)

In `setup.py`, next to `_settle`:

- `schema_at(parts)`: walk `workspace.SCHEMA` (dict: the name or `'*'`; list: its item rule
  for an int part); `None` when the key is not in the schema.
- `effective(config, parts)`: walk the loaded config by the same parts.
- `merged(config, parts, value, replace=False)`: the settings for one key. A list rule and a
  list value without `replace`: `[(parts[:-1], parts[-1], [*current, *(v for v in value if v
  not in current)])]`. A `'*'` table and a dict value without `replace`: one setting per entry,
  `[(tuple(parts), name, item) ...]`. `replace` on any other rule raises `ValueError`
  (`{key}: --replace applies to a list or a named-entry table; drop --replace`). Otherwise
  `[(parts[:-1], parts[-1], value)]`.

`set_value.change` computes `merged(load_config(root, raw=raw), parts, parsed['value'],
getattr(args, 'replace', False))` and passes it to `_settle`. `calibrate.apply` adds
`('outward', 'servers')` and `('outbound', 'people')` to its quoted-key paths (line 528).

In `config.py`: `set` gains `--replace` (store_true, help: write the value as given instead
of adding to the current list or table). New `show <key>` (help: print the effective value,
each row tagged default or owner): load the config, `setup.schema_at`/`effective`, default
from `workspace._default(rule)`; a list prints one row per item, a table one `name = value`
row per entry, a scalar one row; each row is `json.dumps(item)` plus two spaces and
`default` when the item is in (or equal to) the default, else `owner`. Unknown key: exit 1,
`config show: unknown key <key>; run bin/wuwei config check for the documented keys`.

### 6. `outbound learn` (`cli/wuwei/commands/outbound.py`)

The contract file holds the arguments, the listing shapes, the filters, the record text, the
state and event shapes. Functions:

- `learn(args)`: the flow in the contract, top to bottom; prints and returns the exit.
- `_rows(path, kind)`: read one listing file (JSON list of objects with exactly the contract
  keys), validate types and the id and name patterns; `ValueError` names the file and the
  shape.
- `propose(root, config, data, server, channel, channels, people, *, card)`: the filters
  (contract, Proposal) on today's state `data`; returns the proposal dict or `None` when
  there is nothing new.
- `ask(root, config, proposal)`: the record text, `decision.write`, `decision.evaluate`,
  `decision.route_owner`, then one `state._write_state(..., reserved=False,
  kind='outbound.proposed')` storing `outbound_learn[D-n] = {**proposal, 'answered': None}`,
  then print `json.dumps([decision.record_widget(id, fields, level=workspace.verbosity(config,
  'decisions'))], indent=2)`.
- `apply(root, proposal, option, decision_id=None)`: settings from the proposal for the
  option (`approve`: alias, channels, people; `channels`: alias, channels; `keep`: none),
  computed inside the `setup._edit` change callback from `load_config(root, raw=raw)` with
  `setup.merged` for `work_channels`; `setup._edit('outbound learn', 'learned connector',
  lambda *a, **k: True, change)`. On exit 0 with settings, append `outbound.learned`
  (contract, Event). Returns the exit.

Under `"auto"` in observe or guarded, `learn` calls `apply(root, proposal, 'approve')`
directly.

### 7. The owner's answer writes config (`cli/wuwei/commands/decision.py`)

In `owner_outcome`, after the record-changed check and before the state write:

```python
learned = data.get('outbound_learn', {}).get(args.id)
if learned is not None:
    from wuwei.commands import outbound  # Off every other decision path.
    if outbound.apply(root, learned, args.option, args.id):
        return 1, 'decision: the learned connector was not written; run bin/wuwei config check, then answer again'
```

and inside `update(current)`: when `args.id` is in `current.get('outbound_learn', {})`, set
its `answered` to `args.option`. The config write comes first so a failed state write leaves
an idempotent retry (the same settings write nothing the second time).

### 8. Guard config and the planner-only learn (`cli/wuwei/guards/protect_state.py`)

- Add `('outbound', 'learn'): ("Learning a connector runs in the registered planner session,
  outside seats: hand back to the planner, which runs bin/wuwei outbound learn; the owner can
  run it in a host terminal.")` to `_OWNER_ACTIONS`.
- In `_owner_action`, where a reason is found: `if (group, verb) == ('outbound', 'learn') and
  edits[1]: continue` (the registered planner, any posture; strict then asks the card).
- `GUARD_KEYS = ('outward', 'security', 'outbound', 'grants')` and `GUARD_CONFIG = ("Guard
  settings (outward, outbound, security, grants) are the owner's and never change from an
  agent tool: for an unknown connector, channel or person the planner runs bin/wuwei
  outbound learn, and the owner answers its card.")`. For `('config', 'set')`, when the first
  non-flag word after `set` splits on `.` to a first segment in `GUARD_KEYS`, return
  `GUARD_CONFIG` instead of the table reason.

### 9. Reserved producers

`state.STATE_PRODUCERS['outbound_learn'] = 'wuwei outbound learn or wuwei decide'`;
`event.EVENT_PRODUCERS['outbound.learned'] = 'wuwei outbound learn or wuwei decide'` and
`['outbound.proposed'] = 'wuwei outbound learn'`.

### 10. Docs

- `configuration.md`: the `outward.tool_patterns` row (brand anywhere; `config set` adds,
  `--replace` replaces), new rows `outward.servers` and `outbound.learn`, the
  `outbound.people` row (learned entries); a short "Lists and tables" paragraph in
  Calibration next to the `config set` bullet (append, `--replace`, `config show`), and drop
  "Lists replace yours" wording where it describes `config set`.
- `security.md` line 63: the resolution order, the vocabulary, the learn reason; drop the
  `config set outward.tool_patterns` line and "copy any you still need".
- `reference.md`: the `outbound` row names `outbound learn`.
- `templates/workspace/config.toml`: commented `# servers = {"<server id>" = "slack"}` under
  `[outward]` and commented `# learn = "card"` with a one-line note under `[outbound]`.
- `skills/wuwei-plan/SKILL.md`: one paragraph: when a refusal or nudge names `bin/wuwei
  outbound learn`, run it with the named tool, call the listing tools it prints, write the
  two listing files under today's day directory, run it again with them, ask the printed
  widget and record the answer with its `record` command; never edit config for it.

## What must not change

- `outward.classify` and its `(code, 'send'|'draft')` contract; `pr_actions` and the ports
  depend on it. `outward.APPROVAL_REQUIRED` and the port draft path.
- The #469 read rule (`tool_kind`, `READS`, `WRITES`) and the posture handling of unknown
  tools (pass under warn with one event per tool per day, refuse under block).
- `guards.OWNER_ONLY` (`outward.check_tier` blocks in every posture).
- `load_config` semantics: a list in `config.toml` is the whole list.
- Decision validation (`decision.evaluate`, `_scored`, `_explained`) and `owner_outcome`'s
  confirmation, race and reversal rules.
- The `config set` refusal for every agent tool in every posture (records floor); only its
  reason for guard keys changes.
- Hook-path imports (#346): `guards/outward.py` and `outward.py` add no import; the learn
  command, `setup` and `decision` are never imported by a hook.

## Tests

- `tests/test_outward.py`: fixture servers are UUIDs (`00000000-0000-4000-8000-00000000000n`)
  and fixture channels and people (`C01`, `U01`, `ada@example.com`).
  `test_resolve_opaque` (acceptance US1 1 to 4), `test_vocabulary` (table over the four
  entries and one ambiguous name), `test_alias_reads_still_pass`, `RECORDED_OPAQUE` and
  `test_recorded_opaque_tools` (the #469 Slack, Linear and GitHub lists plus a mail list,
  each under a UUID server, with expected `read`, `draft` or `learn`), `test_learn_reasons`
  (write and unknown in each posture name the connector and `outbound learn`; `"off"` names
  only the draft), `test_draft_names_unknown_audience`, `test_no_config_set_in_reasons`
  (every reason from the above contains no `config set`). Existing #469 tests that pin
  `config set outward.tool_patterns` or exit 2 for vocabulary names are updated (spec A12).
- `tests/test_setup.py`: `test_list_set_appends`, `test_list_set_replace`,
  `test_table_set_adds_entries`, `test_replace_refused_on_scalar`, `test_config_show_tags`.
- `tests/test_outbound_learn.py`: listings and instructions, filters, card, answers through
  `owner_outcome` and the guard afterwards, `"auto"` under guarded and strict, `"off"`,
  declined today, open card reprinted, reserved key and kinds.
- `tests/test_protect_state.py`: `test_guard_config_set_refused` (each posture, each guard
  prefix, reason names the owner and `outbound learn`, not `propose the line`),
  `test_outbound_learn_planner_only` (seat refused, registered planner passes),
  `test_config_show_outbound_learn_passes`.
- `tests/test_hooks.py`: the existing #346 import tests must keep passing unchanged.
