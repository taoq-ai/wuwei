# Implementation Plan: outward control is one owner-configured tier table

**Branch**: `496-outward-tiers` | **Spec**: `specs/496-outward-tiers/spec.md` | **Contract**:
`contracts/outbound-tiers.md`

## Summary

`classify` stays the one decision function. It gains three small helpers in
`cli/wuwei/outward.py`: `table(config)` (the effective rows: connector modes, owner rows,
defaults), `_parties(...)` (who reads the call, each with a class and the evidence) and
`decide(...)` (first match per party, strictest party wins). The audience branches of
`classify` (topics first, DM, external, unknown mention, `recipient_org`, external board,
unknown destination, code-host external) are replaced by those helpers; the kind rules after
them stay. `classify` gets a third outcome, `block`. The guard drops its connector mode
branches and `check_send` and passes the tool name to `check_tier`. Two read-only commands
(`outbound tiers`, `outbound explain`), two `doctor` rows, the learn card's classes, and docs.

## Technical Context

Python 3.11+, stdlib only. No new module, no new dependency, no new hook-path import (`json`
for row rendering is imported inside the render function, which only the commands and the
explain trace call). Config schema changes, so `CONFIG_CACHE_VERSION` goes from 8 to 9.

Files changed:

- `cli/wuwei/workspace.py`: `AUDIENCES`, `TOPICS`; `SCHEMA['outbound']` (`people.*.class`,
  `channel_classes`, `tiers`), `SCHEMA['outward']['classes']`; `load_config` row checks;
  `CONFIG_CACHE_VERSION`.
- `cli/wuwei/outward.py`: `DEFAULT_TIERS`, `MODE_TIERS`, `DEFAULT_CLASS`, `table`, `render`,
  `_owner_ids`, `_default`, `_person`, `_parties`, `_matches`, `decide`, `blocked`; `_flagged`
  becomes `_topics`; `classify` (signature `tool=None, trace=None`, the audience branches,
  `block`); `check_tier` (`tool=None`, block reason); `check_send` deleted.
- `cli/wuwei/guards/outward.py`: `DM_TOOL` constant; `_check` mode branches (lines 181-194).
- `cli/wuwei/drafts.py`: `widget` rule checks (lines 165, 168, 178).
- `cli/wuwei/commands/outbound.py`: `tiers`, `explain`; `run` (block); `propose`, `record`,
  `apply`, `MODE_TEXT['send']`.
- `cli/wuwei/commands/doctor.py`: `_outbound(config)` rows from `_workspace`.
- `cli/wuwei/commands/__init__.py`: `READ_ONLY` gains `outbound tiers`, `outbound explain`.
- `cli/wuwei/pr_actions.py`: `block` at line 422-424.
- `cli/wuwei/profiles.py`: `PRIVATE` gains `outbound.tiers`, `outbound.channel_classes`.
- Docs: `docs/site/concepts.md`, `docs/site/configuration.md`, `docs/site/security.md`,
  `docs/site/reference.md`, `templates/workspace/config.toml`.
- Tests: `tests/test_outward.py`, `tests/test_outbound.py`, `tests/test_outbound_learn.py`,
  `tests/test_drafts.py`, `tests/test_doctor.py`, `tests/test_pr_actions.py`,
  `tests/test_hooks.py`, `tests/test_protect_state.py`, `tests/test_profiles.py`,
  `tests/test_cli_known_command.py`, `tests/test_docs.py`.

## Constitution Check

- I stdlib only: yes.
- II exits: `block` is exit 1 with a reason; a malformed payload, an invalid row or an
  unreadable PR still fails closed as exit 2 (`UNRUN, 'draft'` from `classify`, as today).
  `outbound tiers` and `explain` exit 0, 1 (unknown id) or 2.
- III one behaviour, one function: the tier is decided in `classify` only; `check_send` and the
  guard's mode branches (a second path) are deleted. Party classes live in `_parties` only.
- IV test first: every behaviour has a failing test task before its implementation task.
- V ponytail: three helpers in the module that already decides; no new module, no rule
  object, no per-row class. Classes reuse the existing lists (A4). Explain recomputes instead
  of storing a trace (A11). Card row options are deferred (A7).
- VII security: unknown row keys and bad patterns refuse to load in every posture (a typo must
  not widen a row to match everything); seats cannot write the table (`GUARD_KEYS` already
  covers `outbound` and `outward`); strict ignores `send` for client and public; the headless
  seat, owner, `security.outbound` and lint floors are unchanged; with no owner rows the
  defaults loosen nothing except A5 (an owner-set mode `send` now skips topics).

## Design

### 1. Config (`cli/wuwei/workspace.py`)

```python
AUDIENCES = ('owner', 'team', 'company', 'client', 'public')
TOPICS = ('sensitive', 'commitment', 'disagreement')
```

In `SCHEMA['outbound']` (line 154):

```python
"people": {"*": {"email": (str, ""), "org": (str, ""), "class": (str, "", ("", *AUDIENCES))}},
"channel_classes": {"*": (str, None, AUDIENCES)},
"tiers": [{"tool": (str, ""), "person": (str, ""), "channel": (str, ""),
           "audience": (str, "", ("", *AUDIENCES)), "topic": (str, "", ("", *TOPICS)),
           "tier": (str, None, ("send", "ask", "block"))}, []],
```

In `SCHEMA['outward']` (line 179): `"classes": {"*": (str, None, AUDIENCES)}` (a connector's
default class, by server id).

In `load_config`, after the `deploy.deny` loop (line 640):

```python
if bad := next((text for text in unknown if text.startswith('unknown key outbound.tiers.')), None):
    raise ConfigError(bad)  # #496: a typo would widen the row to match everything.
for index, row in enumerate(config['outbound']['tiers']):
    try:
        re.compile(row['tool'])
    except re.error:
        raise ConfigError(f'outbound.tiers.{index}.tool: not a regular expression; ...') from None
```

`CONFIG_CACHE_VERSION = 9`.

### 2. The table (`cli/wuwei/outward.py`, next to `_flagged`)

```python
DEFAULT_TIERS = (  # #496: owner, 2026-10-04; contracts/outbound-tiers.md
    {'audience': 'owner', 'tier': 'send'},
    {'audience': 'public', 'tier': 'block'},
    {'audience': 'client', 'topic': 'commitment', 'tier': 'block'},
    {'audience': 'client', 'topic': 'disagreement', 'tier': 'block'},
    {'audience': 'client', 'tier': 'ask'},
    {'topic': 'sensitive', 'tier': 'ask'},
    {'topic': 'commitment', 'tier': 'ask'},
    {'topic': 'disagreement', 'tier': 'ask'},
    {'audience': 'company', 'tier': 'ask'},
    {'tool': 'other', 'tier': 'send'},  # #492: a monitoring write sends after the topics.
)
MODE_TIERS = {'send': 'send', 'draft': 'ask', 'refuse': 'block'}
KEYS = ('tool', 'person', 'channel', 'audience', 'topic', 'tier')


def table(config):
    """#496: the effective rows, first match wins: [(row, source, note)], set keys only."""
    rows = [({'tool': f'mcp__{re.escape(server)}__.*', 'tier': MODE_TIERS[mode]}, 'owner', ' (outward.modes)')
            for server, mode in config['outward']['modes'].items()]
    rows += [({key: row[key] for key in KEYS if row.get(key)}, 'owner', '') for row in config['outbound']['tiers']]
    return rows + [(dict(row), 'default', '') for row in DEFAULT_TIERS]


def render(row):
    import json  # Commands and explain only.
    return '{ ' + ', '.join(f'{key} = {json.dumps(row[key])}' for key in KEYS if key in row) + ' }'
```

`_flagged` (lines 317-328) becomes `_topics(normalized, rules)`: a dict `{topic: config key}`
of every topic that matches (sensitive keywords first, then `sensitive_patterns`, then
commitment, disagreement), same normalisation.

### 3. Parties (`cli/wuwei/outward.py`)

- `_owner_ids(config, kind)`: the casefolded identity set `owner_only` computes today
  (lines 196-198), extracted so `owner_only` and `_parties` share it.
- `DEFAULT_CLASS = {'tracker': 'team', 'docs': 'team', 'other': 'team'}`;
  `_default(config, kind, tool)` returns `(class, evidence)`: `outward.classes` for the tool's
  server (casefold match, as `guards.outward.mode` does), else `DEFAULT_CLASS.get(kind,
  'company')`; evidence per the contract.
- `_person(person, namespace, rules, mine, fallback, dm=False)`: `(label, key, class, why)`:
  owner identity, else `outbound.people[<ns>:<id>].class`, else `team` when today's
  `_internal(person, rules, namespace)` holds, else the connector default with the `unknown
  mention` (or `unknown DM recipient` when `dm`) evidence.
- `_parties(context, destinations, mention_text, kind, tool, config, pr)` returns a list of
  party dicts `{'id', 'label', 'kind': 'channel'|'person'|'connector', 'key', 'class', 'why'}`
  built from what `classify` reads today, in this order:
  1. Each destination: owner identity; a `[UW][A-Z0-9]+` id is a person (`dm=True`); else a
     channel: `channel_classes`, `work_channels`, `external_channels`, else the default
     (`unknown DM recipient` evidence when the call is a DM or the id starts with `D`,
     `unknown destination` otherwise). The client flags (`is_external`, `is_shared`,
     `is_connected`, `is_client` true, or a `channel_type` other than `channel`, `im`, `mpim`)
     override every destination to `client`.
  2. `recipients`, `recipient`, the `MENTION` matches of `mention_text` and the email addresses
     in it (as lines 399-408 do today), namespace `email`, else `github` for `code_host`, else
     `slack`; deduplicated by key.
  3. `recipient_org` outside `outbound.code_host_orgs`: a `client` party.
  4. `kind == 'tracker'` and `_external_tracker(config)`: a `client` party `board`.
  5. `kind == 'code_host'`: `pr` is the `_pr_context` exit: 0 adds a `team` party for the ref,
     1 a default-class party.
  6. No party yet: one `connector` party (id the server, else the kind) with the default.
  The client flags with no destination add one `client` party.

### 4. `decide` and `blocked`

```python
def decide(parties, topics, names, config, trace=None):
    """#496: (tier, fragment) of the strictest party, or None when a party has no row."""
```

For each party, walk `table(config)` with `_matches(row, party, topics, names)` (contract
Matching); under `workspace.posture(config)[0] == 'strict'` a `send` row is skipped for a
`client` or `public` party. With `trace` (a list), append the party line and one line per row
walked (`passed`, `matched`, `ignored under strict`). Combination: the lowest-numbered `block`,
else the lowest-numbered `ask`, else `send` when every party matched, else `None`. The fragment
is built per the contract (no `; `).

`blocked(fragment)` returns `f'outward: {fragment}; the owner decides: bin/wuwei outbound
tiers'`, shared by `check_tier`, `outbound tier` and `pr act`.

### 5. `classify` (`cli/wuwei/outward.py:353-494`)

Signature: `classify(text, root, config, context=None, *, kind='chat', port=False, why=None,
tool=None, trace=None)`; returns `(code, 'send'|'draft'|'block')`.

Order after the change:

1. Headless shepherd floor (unchanged, line 367).
2. `text` must be a `str` and `kind` a `str` (empty text no longer returns here).
3. `_text(context)`, `owner_only` floor (unchanged, lines 372-374), nested draft merge
   (unchanged, lines 376-383).
4. `topics = _topics(normalized, rules)`; `review_match` and `mention_text` (moved up from
   lines 402-404, unchanged).
5. `kind == 'code_host'`: `code, discussion = _pr_context(...)` (moved up from line 434);
   exit 2 returns `(code, 'draft')` as today.
6. `found = decide(_parties(...), topics, [tool, kind], config, trace)`: `send` returns
   `(0, 'send')`; `ask` returns `held(fragment)`; `block` appends the fragment to `why` and
   returns `(1, 'block')`.
7. `if not text.strip(): return UNRUN, 'draft'` (today's empty-text rule, now after the table
   so a textless write a row decides is not refused).
8. The kind rules, unchanged except:
   - the DM and external branch (lines 388-398) becomes only `if <DM>: return tier('direct
     message', 'every direct message drafts')` (DM: `is_dm`, `channel_type` `im`/`mpim`, or a
     `D`/`U` destination);
   - the unknown mention rule (lines 399-415) and the `recipient_org` rule (lines 416-418) are
     deleted (parties);
   - the tracker rule drops `and not _external_tracker(config)` (a party now);
   - the code-host `_pr_context` call (lines 433-438) is gone (step 5; a non-team PR is a party
     the table asks);
   - the chat destination rule (lines 439-446) keeps `not destinations or len(set(destinations))
     != 1` as `tier('unclassified', 'one destination per chat send')` for chat and today's
     `tier('unclassified', f'no auto-send rule for channel {kind}')` for other kinds; the
     `work_channels` membership test is deleted (the table classed every destination).
   - the review gate, the reply shapes and the commit resolve stay as they are.

### 6. `check_tier` and the guard

- `check_tier(inputs, root, config, channels, *, port=False, tool=None)` passes `tool` to
  `classify`; `decision == 'block'` returns `(FINDINGS, blocked(why[0]))`. `check_call` is
  unchanged: a block is a finding that is not a draft, so it returns before the lint.
- `cli/wuwei/guards/outward.py`: `DM_TOOL = r'(?:^|_)(?:dm|direct_message)(?:_|$)'` replaces the
  inline pattern at line 178. Lines 181-194 become:

  ```python
  if policy is outward.check_tier:
      result = outward.check_tier(inputs, root, config, channels, tool=tool)
  elif (tool.startswith('mcp__') and tool_kind(tool) != 'read'
        and mode(tool, config, channel) == 'send' and not outward._text(inputs)[0]):
      result = (CLEAN, '')  # Nothing to lint in a write without text.
  else:
      result = policy(inputs, root, config, channels)
  ```

  `mode` and `CLASS_MODES` stay for that lint branch. The hold and spend lines (195-199) are
  unchanged; a block reason never starts with `APPROVAL_REQUIRED`, so it never imports
  `wuwei.drafts`.
- `outward.check_send` (lines 331-350) is deleted.

### 7. Draft card (`cli/wuwei/drafts.py:156-183`)

- Line 165: `'unknown destination' in rule or 'unknown mention' in rule`; the hint says `to
  record the channel or person for later sends`.
- Line 168: `'unknown DM recipient' in rule`.
- Line 178: `rule.startswith(('approval tier', 'ask by rule'))`.

### 8. Commands (`cli/wuwei/commands/outbound.py`)

- `register`: `actions.add_parser('tiers', help='print the effective outbound tier table')`
  with `func=tiers`; `explain = actions.add_parser('explain', help='print the rows a draft
  passed and the row that held it')`, positional `draft`, `func=explain`.
- `tiers(args)`: load the config (exit 2 with the reason when it does not load), print the
  header and one line per `outward.table(config)` row (contract), mark owner `send` rows for a
  client or public audience or channel ` (ignored under strict)` under strict, then the kind
  rules line. Exit 0.
- `explain(args)`: `drafts.read(state.read_state(root))[args.draft]` (exit 1 when absent);
  `inputs` is the row's inputs plus `is_dm = True` when `row['operation'] == 'dm'` or the tool
  matches `guards.outward.DM_TOOL`; `outward.classify(row['text'], root, config, inputs,
  kind=row['channel'], port=row['adapter'] != 'mcp', why=why, tool=row.get('tool'),
  trace=trace)`; print the stored rule, the trace, and the `now:` line. Exit 0.
  `# ponytail: recomputed with today's config; store the trace on the draft row if the owner
  needs the table as it was.`
- `run` (`outbound tier`): a `block` decision prints `{"tier": "block", "exit": 1}` and the
  blocked reason on stderr.
- `MODE_TEXT['send']`: `Every write through this connector goes out after the lint (rule 1 of
  bin/wuwei outbound tiers).`; `MODE_TEXT['other']`: `writes go out after the lint and the
  sensitive, commitment and disagreement rows.`
- `propose`: shared channels are proposed with `'class': 'client', 'why': 'shared with an
  external org'`, the rest `'class': 'team'` (the `not row['shared']` filter at line 123 goes);
  each person `entry` gains `'class': 'team'`.
- `record`: channel lines end `: <class>` (plus `, shared with an external org` for client);
  person lines end `: team`; the question counts `work channels` (team) and `client channels`
  separately; Reasoning: `The listing names these channels and the people are the day's
  reviewers or named in its records; a channel shared with another organisation is client, so
  its sends ask and its commitments are blocked.`
- `apply`: channel ids split by class: team ids through `setup.merged` into `work_channels`,
  client ids into `external_channels`; people entries carry `class`. The `outbound.learned`
  payload is unchanged (ids only).

### 9. `doctor` (`cli/wuwei/commands/doctor.py`)

`_outbound(config)` returns the two rows of the contract (section `workspace`), called at the
end of `_workspace` before `_calibration` when the config loaded. It reads `outward.table` for
the rule numbers. Warn rows are information: nothing refuses on them.

### 10. Other callers

- `cli/wuwei/pr_actions.py:422-424`: `why = []`; pass it; accept `'block'`; on block print
  `outward.blocked(why[0])` to stderr and return 1 before any draft.
- `cli/wuwei/commands/__init__.py`: `READ_ONLY` gains `'outbound explain'`, `'outbound tiers'`.
- `cli/wuwei/profiles.py`: `PRIVATE` gains `'outbound.tiers'`, `'outbound.channel_classes'`.
- `cli/wuwei/registry.py`: no change (a block is `Result(1, ..., reason)`).
- `cli/wuwei/guards/protect_state.py`: no change; a test pins that `config set outbound.tiers`
  from an agent gets `GUARD_CONFIG`.

### 11. Docs

- `docs/site/concepts.md`: a new `## Outbound tiers` section after `## Drafts and cards`: the
  three tiers, the five classes in plain words, the client example (a commitment to a client
  channel is blocked, the same line to the team asks, a status line to you sends), owner rows
  first, and `outbound tiers` / `outbound explain`. The Drafts paragraph's example rule
  becomes the new fragment.
- `docs/site/configuration.md`: rows for `outbound.tiers`, `outbound.channel_classes`,
  `outbound.people` (`class`), `outward.classes`; `outward.modes` text (the first rows of the
  table, `send` is always send); `work_channels` (class team) and `external_channels` (class
  client); the section index line 16 gains `[outbound.channel_classes]` and `[outward.classes]`.
- `docs/site/security.md`: in Floors, one bullet: above the outbound table, in every posture:
  `security.outbound` (canary and honeytoken), the headless seat, a message only you read, a
  seat never writes the table (`config set` on `outbound` is refused), `publish` stays yours;
  under strict a `send` row never reaches a client or public audience. Line 63's mode sentence
  becomes the table.
- `docs/site/reference.md` line 48: `tiers` prints the table, `explain <draft id>` the trace.
- `templates/workspace/config.toml` `[outbound]`: commented `tiers` example with two rows,
  `class` in the people example, a commented `[outbound.channel_classes]` and
  `[outward.classes]`; line 194-197 say the table decides and the kind rules follow.

## What must not change

- `security.outbound` before `classify`, the outward lint after it, `humanize_lint`.
- The headless shepherd floor and the #495 owner floor, first in `classify`.
- `guards.outward.resolve`, `_unmatched`, `tool_kind`, the learn flow, `OWNER_ONLY`.
- #493: `drafts.hold`, `drafts.spend`, `drafts.reason`, `drafts.approve`; a held call is the
  only one that imports `wuwei.drafts`.
- The kind rules' texts and order after the table; `_pr_context` and `_internal`.
- The `(code, 'send'|'draft')` meaning of existing outcomes for every caller; `block` is new.

## Tests

- `tests/test_outward.py`:
  - `test_tiers_acceptance` (US1 1-3: client block, team ask, owner send; through the guard,
    no draft row on block).
  - `test_tiers_defaults` (table: public block, client disagreement block, client sensitive
    ask, company unknown mention ask, `other` send, `other` with a disagreement ask).
  - `test_tiers_mixed_parties` (client plus team blocks; owner plus unknown asks; send only when
    every party sends).
  - `test_owner_row_person` (US2 1-3), `test_mode_rows` (US2 4, replacing the mode asserts in
    `test_class_modes` and `test_guard_to_owner_floor`), `test_tier_row_validation` (US2 5),
    `test_tier_floor_strict` (US3 1-2), `test_tier_classes` (`channel_classes`,
    `people.class`, `outward.classes`, `is_shared`, `recipient_org`, external board, PR).
  - Update the `RULES` table, `test_check_tier_appends_the_rule`,
    `test_hook_refusal_names_draft_and_why_reads_it`, `test_draft_names_unknown_audience`,
    `test_dm_recipient_rule`, `test_tracker_github_outside_code_host_orgs_drafts` to the
    contract texts.
- `tests/test_outbound.py`: `test_outbound_tiers_prints_table`, `test_outbound_explain`,
  `test_outbound_tier_block`.
- `tests/test_outbound_learn.py`: shared channel proposed as client; approve writes
  `external_channels` and `class = "team"`; card text.
- `tests/test_drafts.py`: the card hints with the new fragments.
- `tests/test_doctor.py`: the two `doctor` rows.
- `tests/test_pr_actions.py`: a blocked reply prints the reason, exits 1, creates no draft.
- `tests/test_hooks.py`: a blocked call does not import `wuwei.drafts`.
- `tests/test_protect_state.py`: an agent's `config set outbound.tiers` gets `GUARD_CONFIG`.
- `tests/test_profiles.py`: the two keys are private.
- `tests/test_cli_known_command.py`: the two paths are registered and read-only.
- `tests/test_docs.py`: the docs and template name the new keys and commands.
