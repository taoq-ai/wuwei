# Implementation Plan: People, channels and tools register

**Branch**: `552-graph-register` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

## Summary

One JSON register, `.wuwei/graph.json`, built from the config keys that hold relations
(Assumption A4) plus the few facts no key can hold (a person seen in a channel, names from
learn cards). The guards keep reading `config.toml` unchanged. The one config writer
(`config.offer`) and `init --upgrade` write the register and the view together, register
first, from the same validated text, so there is no TOML generator. `wuwei who` walks the
register and asks `outward.classify` (the guard's own function) for the tier. `wuwei why`
cites the class or mode edge behind a held draft. `doctor` reports drift; `init --upgrade`
resolves it toward `config.toml` (the owner's hand edit).

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime
**Primary Dependencies**: none (json, re, pathlib)
**Storage**: `.wuwei/graph.json`, written with `workspace.atomic_write`
**Testing**: pytest, in-process (`run(Namespace(...))`, `diagnose()`), `tmp_path` workspaces with neutral fixtures
**Target Platform**: macOS and Linux owner machines
**Performance Goals**: no hook imports `wuwei.graph`; the hook latency budget is untouched
**Constraints**: no new refusal under observe or guarded (the records floor is the only one); no guard or reason text changes
**Scale/Scope**: tens of nodes per workspace; linear scans are fine

## Constitution Check

- I Stdlib only: json, re, pathlib. Pass.
- II Three-state exits: `who` 0 found, 1 no match or no register, 2 damaged register or unreadable config. Writers keep their exits: the register is not their input, so a damaged one is a warning with the fix and is never overwritten (A13). Pass.
- III One behaviour, one function: the model lives in `graph.py` only; `who`, `why`, `doctor`, `init` and the writer call it; the tier comes from `outward.classify`. Pass.
- IV Test first: every task below has its test before it. Pass.
- V Simplicity: no TOML generator, no tool nodes, no tier edges, no new flags; one `sync` call in the one writer. Pass.
- VII Security: the register is protected by the records floor; `who` and `why` print through the existing redacting stdout. Pass.
- Owner session never blocked: `who` is a quick read. Pass.

## The register

```json
{"version": 1,
 "nodes": {"channel:C01": {"name": "eng"},
           "person:slack:U01": {"name": "Ada", "view": "outbound.people"},
           "address:ada@example.test": {}},
 "edges": [{"from": "channel:C01", "type": "class", "to": "team", "view": "outbound.work_channels"},
           {"from": "person:slack:U01", "type": "class", "to": "team", "view": "outbound.people"},
           {"from": "person:slack:U01", "type": "maps_to", "to": "address:ada@example.test", "view": "outbound.people"},
           {"from": "person:slack:U01", "type": "member_of", "to": "channel:C01", "card": "D-1"}]}
```

- `nodes`: every edge endpoint that has a colon, plus table-entry nodes. Attributes are
  optional: `name` (from a learn card) and `view` (the node is an entry of that table, kept
  even with no edges: `outbound.people`, `voice.sources`).
- `edges`: ordered; `type` in `member_of, class, sends_through, mode, maps_to, reviews`;
  either `view` (a view edge) or optionally `card` (register-only, `D-<n>`; absent under
  `outbound.learn = "auto"`).
- Load validation (damaged, ValueError naming the fix "move .wuwei/graph.json aside and run
  bin/wuwei init --upgrade"): a symlink, unreadable JSON, keys other than exactly
  `version, nodes, edges`, version not 1, a node id without `kind:`, a node attribute other
  than `name` or `view`, an edge with a missing field, an unknown type or a view not in
  `VIEWS`.

### View mapping (`build` writes it, `views` reads it back)

| View key | Edges per entry (from, type, to) |
| --- | --- |
| `outbound.people` `<k>` = `{email, org, class}` | node `person:<k>` with `view`; `maps_to address:<email>` if email; `member_of org:<org>` if org; `class <class>` if class |
| `outbound.channel_classes` `<id>` = `c` | `channel:<id> class c` |
| `outbound.work_channels` `[id]` | `channel:<id> class team` |
| `outbound.external_channels` `[id]` | `channel:<id> class client` |
| `outbound.owner.slack.user` | `person:owner maps_to person:slack:<user>` |
| `outbound.owner.slack.dm` | `person:owner maps_to channel:<dm>` |
| `outbound.owner.mail` | `person:owner maps_to address:<mail>` |
| `outbound.owner.code_host` | `person:owner maps_to login:<login>` |
| `outward.servers` `<s>` = kind | `connector:<s> sends_through <kind>` |
| `outward.modes` `<s>` = m | `connector:<s> mode <m>` |
| `outward.classes` `<s>` = c | `connector:<s> class <c>` |
| `shepherd.authors` `<email>` = `{login, mention}` | `address:<email> maps_to login:<login>`; `address:<email> maps_to person:slack:<mention>` if mention |
| `owner.handles` `[h]` | `person:owner maps_to person:slack:<h>` when `h` fullmatches `outward.SLACK_SHAPE['user']`, else `person:owner maps_to login:<h>` |
| `voice.sources` `<a>` = `[c]` | node `voice:<a>` with `view`; `channel:<c> member_of voice:<a>` |
| `repos.<n>.shepherd.reviewers` `[l]` (view `repos.shepherd.reviewers`) | `login:<l> reviews repo:<name>`; the view is `{repo name: [logins]}` for repos with reviewers |

`views(register)` returns each key in the loaded-config shape (people entries with all three
fields, authors with `mention` defaulting to `""`, owner fields defaulting to `""`), and
`sections(config)` returns the same keys read from a loaded config, so
`views(build(config)) == sections(config)` for every valid config. That equality is the
register-or-view invariant.

## Code changes

### New: `cli/wuwei/graph.py` (the model; never imported on a hook path)

- `NAME = 'graph.json'`, `TYPES`, `VIEWS` (the keys above), `COMMENT` (the config comment
  line: `# A view of .wuwei/graph.json: bin/wuwei config set and the cards write both; bin/wuwei who walks it.`),
  `TABLES` (the TOML headers that get it: `owner`, `voice.sources`, `outward.servers`,
  `outward.modes`, `outward.classes`, `outbound`, `outbound.people`,
  `outbound.channel_classes`, `outbound.owner`, `outbound.owner.slack`, `shepherd.authors`).
- `build(config, previous=None, add=(), names=None)`: the view edges and table-entry nodes
  from `config` (table above), then the register-only edges of `previous` (no `view`), then
  `add`; node names from `previous` kept, `names` ({id: name}) applied; every endpoint is a
  node. Pure.
- `sections(config)` and `views(register)`: the `{view key: value}` maps above. Pure.
- `drift(register, config)`: the view keys where they differ. Pure.
- `load(root)`: the register, `None` when missing, `ValueError` when damaged (rules above).
- `save(root, register)`: `workspace.atomic_write(root / '.wuwei' / NAME, json.dumps(register, indent=2) + '\n')`.
- `sync(root, config, add=(), names=None)`: `load`, `build`, `save` when different; returns
  True when it wrote. A damaged register raises `ValueError` before anything is written.
- `warn(label, exc)`: prints `wuwei <label>: warning: .wuwei/graph.json not updated: <exc>;
  move it aside and run bin/wuwei init --upgrade` to stderr. The one place the warning text
  lives; `offer`, `apply` and `upgrade` call it.
- `find(register, name)`: node ids whose id, id without its kind, last segment or name
  (with or without a leading `#` or `@`) equals `name`, case-insensitive; an MCP tool name
  `mcp__<s>__<t>` or `tool:<s>/<t>` resolves to `connector:<s>`.
- `related(register, node)`: the edges from or to `node`, in register order.
- `cite(register, text, tool=None)`: the edges whose `view` key appears in `text` and whose
  `from` node is named by a token of `text` (tokens stripped of `@`, brackets and trailing
  punctuation, resolved with `find`) or is the connector of `tool` (`mcp__<s>__<t>`), in
  register order, deduplicated. The guard's reason names both the party and the key
  (`C01 in outbound.external_channels as client`, `..., outward.modes`, `connector default
  class company (outward.classes)`), so a channel in two lists cites only the list that
  decided.
- `line(edge)`: `<from> <type> <to> (<view>)`, `(card D-n)` or `(learned)`.
- `annotate(raw)`: `raw` with `COMMENT` inserted on its own line before each header whose
  table is in `TABLES`, unless the line before already is `COMMENT`; uses
  `configtext.entries` for the headers.

### `cli/wuwei/commands/config.py` `offer` (`:236-256`): the one writer

Before `workspace.atomic_write(path, text)` (`:252`), inside `if text != raw:`, call
`graph.sync(root, workspace.load_config(root, raw=text))` in a `try`; on `ValueError` or
`OSError` call `graph.warn(label, exc)` and go on to write `config.toml` (A13). Every config
write path already ends here (`setup._edit`, `setup.card_write`, `config set`,
`--from-card`, `calibrate --answer`, `config promote`, `setup`, `setup slack`, `outbound
learn` apply, `drafts approve --always`, `grants`).

### `cli/wuwei/commands/outbound.py`

- `learn` (`:434`): after `proposal = propose(...)` (`:522`), when `args.thread` set it and
  the proposal is not None, store `proposal['thread_channel'] = target` (the thread's
  channel id; the card text is unchanged).
- `apply` (`:387-431`): after `code == CLEAN` and after the `outbound.learned` event (the
  config write is the record), call `graph.sync(root, workspace.load_config(root), add=...,
  names=...)` with the approved channels' and
  people's names (`{f'channel:{id}': name}`, `{f'person:slack:{id}': name}`) and, when
  `proposal.get('thread_channel')`, one `{'from': f'person:slack:{id}', 'type':
  'member_of', 'to': f'channel:{thread_channel}', 'card': decision_id}` edge per approved
  person whose `why` starts with `in thread` (`card` omitted when `decision_id` is None).
  An `OSError` or `ValueError` calls `graph.warn('outbound learn', exc)`; `apply` still
  returns `CLEAN` (A13).

### New: `cli/wuwei/commands/who.py`

- `register(subparsers)`: `who <name> [--json]`.
- `run(args)`: `find_workspace`, `load_config`, `graph.load`; no register: exit 1 with
  `no .wuwei/graph.json; run bin/wuwei init --upgrade`; no match: exit 1 with
  `no node <name> in .wuwei/graph.json; people and channels are learned with bin/wuwei
  outbound learn`; damaged or `ConfigError`: exit 2 with the reason.
- Per match, text: the node and name; one `class <c> (<view>)` line per class edge; for a
  channel, `people:` with each `member_of` source, its name and class; the tier line; one
  `edge: <line>` per related edge. `--json`: a list of `{node, name, edges, tier, rule}`.
- Tier, through `outward.classify(ROUTINE, root, config, context, kind=..., why=why,
  tool=...)` with `ROUTINE = 'tests passed'`; `draft` prints as `ask`, the rule is `why[0]`
  or null:
  - `channel:<id>`: kind `slack`, context `{'channel': id}`; `a routine message here`.
  - `person:slack:<id>`: kind `slack`, context `{'channel': id}`; `a routine direct message`.
  - `person:email:<a>` or `address:<a>`: kind `mail`, context `{'to': [a]}`; `a routine mail`.
  - `connector:<s>`: kind its `sends_through` target or `other`, context `{}`, tool the MCP
    name given or `mcp__<s>__send`; `a routine write through it`.
  - `login:<l>` or `person:github:<l>`: through the `person:slack:` node an address maps it
    to, else `no tier here: the pull request rules decide on the code host`.
  - `person:owner`, `org:`, `voice:`, `repo:`: no tier line.

### `cli/wuwei/commands/why.py`

- `run` (`:34`): before the item fallback, `elif re.fullmatch(r'draft-[0-9a-f]{32}', target):
  steps = held(root, target)`.
- New `held(root, draft_id)`: the draft row from `drafts.read(state.read_state(root))`
  (missing: `Missing('no draft <id> today; run bin/wuwei drafts for the queued ids')`);
  steps `held: <tier_reason without the APPROVAL_REQUIRED prefix>` then `edge: <line>` per
  `graph.cite(register, tier_reason, row.get('tool'))`, or `edge: not recorded` when none
  or no register.
- `refusal` (`:170-198`): for an entry whose reason starts with `outward:` and names a
  `draft-<hex>` id, append that draft's `edge:` steps after its `fix:` line.

### `cli/wuwei/commands/init.py` `upgrade` (`:312`)

After `migrated` is final (after `_stamp`): `migrated = graph.annotate(migrated)`;
`previous = graph.load(root)`; `register = graph.build(workspace.load_config(root,
raw=migrated), previous)`; `graph_changed = register != previous`. Unless `--dry-run`,
`graph.save` runs before the `config.toml` write. Print `{prefix} .wuwei/graph.json: <n>
nodes and <m> edges from config.toml` when changed; include `graph_changed` in the "No
workspace changes needed" test. When `annotate` changed the text, print `{prefix}
config.toml: name .wuwei/graph.json above <k> sections` and include that in the same test.
A damaged register (`ValueError` from `graph.load`) calls `graph.warn('init', exc)`, skips
the register and runs the rest of the upgrade.

### Templates

- New `templates/workspace/graph.json`: `{"version": 1, "nodes": {}, "edges": []}` and a
  final newline, so a fresh `init` ships a register that matches the empty template.
- `templates/workspace/config.toml`: `COMMENT` above `[owner]`, `[voice.sources]`,
  `[outbound]` and `[shepherd.authors]`, so `annotate(template) == template`.

### `cli/wuwei/commands/doctor.py`

- New `_register(root, config)` called next to `_outbound(config)` (`:352`): `ok`
  `<n> nodes, <m> edges; matches config.toml`; `warn` `no .wuwei/graph.json` or `config.toml
  differs from graph.json in <k> keys` (detail: the keys), fix `wuwei init --upgrade`,
  `apply='init-upgrade'`; `warn` with the damage reason and fix `move .wuwei/graph.json
  aside, then wuwei init --upgrade` (no apply). Never `fail`: `setup.ending` holds a failing
  workspace row as a required step (A13).
- `_workspace` (`:217-250`): the `upgrades` list drops lines that name `graph.json`, so the
  template row does not repeat the register row.

### `cli/wuwei/guards/protect_state.py`

`_protected_name` (`:294-324`): add `('graph.json',)` to the first tail tuple. `_hint`
(`:332`): `graph.json is the register of people, channels and tools: bin/wuwei config set,
the cards and bin/wuwei init --upgrade write it; bin/wuwei who reads it.`

### Registration and docs

- `cli/wuwei/commands/__init__.py`: `who` in `READ_ONLY`.
- `cli/wuwei/__main__.py` `GROUPS`: `who` after `why` in the Recovery group.
- `docs/site/configuration.md`: new section `## People, channels and tools` (the model, the
  view table in plain words, `who`, drift and its fix); the rows for `owner.handles`,
  `shepherd.authors`, `voice.sources`, `outward.servers`, `outward.modes`,
  `outward.classes`, `outbound.work_channels`, `outbound.external_channels`,
  `outbound.channel_classes`, `outbound.people` and `outbound.owner` end with a pointer to it.
- `docs/site/reference.md`: a Commands row for `bin/wuwei who`; the Why section names the
  draft id target and the `edge:` line.

## Shared helpers reused

`workspace.atomic_write`, `workspace.load_config`, `workspace.find_workspace`,
`configtext.entries`, `outward.classify`, `outward.SLACK_SHAPE`,
`outward.APPROVAL_REQUIRED`, `drafts.read`, `state.read_state`, `why.Missing` and
`why.render`, doctor's `_row` and the `init-upgrade` fix.

## What must not change

- No new refusal or stop: the register never blocks a write, a card answer or an upgrade
  (A13); the records floor row is the only refusal this item adds.
- Every guard and its inputs: `outward.py`, `guards/outward.py`, `workspace.load_config`,
  the config cache, the reason texts. `outward.py` is not edited.
- `configtext.place`, `setup._settle`, `setup._edit`, `calibrate.apply`: the view text is
  written exactly as today.
- The learn card text (`outbound.record`) and the `outbound.learned` event payload.
- `why` output for items, decisions, target keys and non-outward refusals.
- `novelty.configured` and every other reader of the modeled keys.
- No hook imports `wuwei.graph`.

## Project Structure

### Documentation (this feature)

```text
specs/552-graph-register/
  spec.md  plan.md  tasks.md  analysis.md  checklists/requirements.md
```

### Source Code

```text
cli/wuwei/graph.py                      new: the model
cli/wuwei/commands/who.py               new: wuwei who
cli/wuwei/commands/config.py            offer writes the register first
cli/wuwei/commands/outbound.py          learn keeps the thread channel; apply adds members and names
cli/wuwei/commands/why.py               draft target, edge lines
cli/wuwei/commands/init.py              upgrade builds the register, annotates the config
cli/wuwei/commands/doctor.py            register row
cli/wuwei/guards/protect_state.py       records floor
cli/wuwei/commands/__init__.py          READ_ONLY
cli/wuwei/__main__.py                   help group
templates/workspace/graph.json          new: empty register
templates/workspace/config.toml         comment lines
docs/site/configuration.md, docs/site/reference.md
tests/test_graph.py, tests/test_who.py  new
tests/test_why.py, tests/test_doctor.py, tests/test_outbound_learn.py,
tests/test_protect_state.py, tests/test_config_writer.py, tests/test_workspace.py (upgrade),
tests/test_docs.py
```

## Complexity Tracking

None. The one judgement call (register and view written together from the view text, A2)
removes a TOML generator rather than adding a layer.
