# Implementation Plan: Novelty gate

**Branch**: `556-novelty-gate` | **Spec**: `spec.md`

## Summary

One new module, `cli/wuwei/novelty.py`, holds the seen set (`memory/targets.json`) and the
target keys. Three existing routing points consult it, each with a few lines and no second
routing path: `mandate()` in the `decision route` command, `check_tier` in the outward
policy, and `gate()` in the grant gate. Two existing owner-answer writers clear a target
(`owner_outcome`, `drafts.approve`). `init --upgrade` seeds the set from CLI-written records
of the last 30 days, and the reader seeds lazily when the file is missing. protect_state
reserves the file. Report and `why` read it.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Tests in process on neutral fixtures in
`tmp_path` (`fixture-org/...` repositories, channel ids `C1`, `C9`), reusing the existing
helpers of `tests/test_decision_classes.py` (records and routing), `tests/test_outward.py`
(workspace with `[outbound]`, guard payloads), `tests/test_grants.py` (`standing`, deploy
payloads) and `tests/test_protect_state.py`.

## Constitution Check

- III one behaviour one function: keys, configured set, seen set, seed and clear live only in
  `novelty.py`; each gate calls `novelty.novel` once. Pass.
- II exits: a damaged seen set raises `ValueError` with the fix; each caller's existing error
  path turns it into exit 2 or its could-not-validate draft. Pass.
- No forgeable trust: the seen set is a file only the CLI writes (protect_state refuses seat
  writes); clearing happens only inside the owner-answer writers (already owner or
  planner-after-card only) and the seed, which reads CLI-written records (every event kind
  but `note`, the one free kind). Config is owner-only. A seat-written key in a record can
  only add a card, never remove one. Pass.
- No new refusal under observe or guarded (#530): the new stops are a decision card, a draft
  card and a grant card. Pass.
- #551: the planner's next step is a command output (`decision route` prints `owner` and the
  reason line; the draft and grant refusals name their card command). No skill or charter
  prose is added. Pass.
- Ponytail: no event kind, no config key, no class; `by: mandate` and the level form wait for
  #283. Pass.

## Changes

### New: `cli/wuwei/novelty.py`

```python
"""#556: the seen set; a target the workspace never touched runs one level lower (design 5.8.1)."""
from wuwei.grants import REPO   # reuse; grants imports only stdlib at module level
KEY = (rf'repo:{REPO}|channel:[^\s,;]+|person:[A-Za-z0-9_-]+:[^\s,;]+'
       r'|tool:[A-Za-z0-9_-]+/[A-Za-z0-9_-]+|dependency:[A-Za-z0-9_.-]+/[^\s,;]+'
       r'|env:[^\s,;]+|workflow:[^\s,;]+')
CLEARS = 'one owner answer on a card clears it'
DAYS = 30
```

- `keys(text)`: `re.finditer(r'(?<![\w:/.-])(?:' + KEY + ')', text)`, each match stripped of
  trailing `.`, `)` and `:`, kept only if it still fullmatches `KEY` and contains no `<` or
  `>` (template placeholders); ordered, no duplicates.
- `record_keys(fields)`: `keys()` over `Question`, `Context` and `Blast radius`.
- `configured(config)`: the set the owner declared: `repo:<name>` for `repos`;
  `channel:<id>` for `outbound.work_channels`, `outbound.external_channels`,
  `outbound.channel_classes` keys, the non-empty `channel` of `outbound.tiers` rows,
  `shepherd.review_channel`, `outbound.owner.slack.dm`; `person:<key>` for
  `outbound.people` keys and `person:slack:<outbound.owner.slack.user>`; `env:<name>` for
  `environments` keys; `workflow:<name>` for `deploy.workflows`; every
  `grants.standing[].target` without `*`, `?` or `[`. Empty strings skipped.
- `_path(root)`: `Path(root) / '.wuwei/memory/targets.json'`.
- `_read(root)`: `None` when the file is missing; else the parsed dict, validated:
  `{'targets': {key: {'first_seen': 'YYYY-MM-DD', 'cleared': None | {'by': 'owner'|'seed',
  'evidence': str, 'at': str}}}}` with every key fullmatching `KEY`. A symlink, bad JSON or
  bad shape raises `ValueError('memory/targets.json is damaged (<what>); the owner moves it
  aside and runs bin/wuwei init --upgrade, which seeds it again')`.
- `_update(root, change)`: under a lock (`state.lock_ex` on `.wuwei/memory/targets.lock`,
  as `mcp._lock` does), `data = _read(root)`; when `None`, `data = {'targets':
  _history(root)}` (lazy seed); call `change(data['targets'])`; write with
  `workspace.atomic_write` when the file was missing or `change` returned true. Returns the
  `change` result.
- `novel(root, config, found)`: `found` empty returns `[]` without reading anything (hook
  fast path). Otherwise the keys not in `configured(config)` and not cleared in the set; each
  key with no row gets `{'first_seen': today, 'cleared': None}` (one `_update`). Returns the
  novel keys in input order.
- `clear(root, key, evidence)`: inside `_update`, set `cleared = {'by': 'owner', 'evidence':
  evidence, 'at': now}` unless already cleared; a missing row gets `first_seen: today` too.
- `_history(root)`: `{key: row}` from the last `DAYS` days (today back to today minus 30):
  for each date, `consolidation.day_records(root, day)` (live day, legacy archive or
  tarball; `None` skips); events parsed with `watch._rows(records.get('events.jsonl', ''))`,
  every kind but `note` (`commands.event.FREE_KINDS`): a payload `repo` that fullmatches
  `REPO` (as `repo:<repo>`), and the `target` of a `grant.used` event when it fullmatches
  `KEY` (other hook events carry a `target` that is command text a seat shapes); `state.json` drafts
  with `channel` in `('chat', 'slack')`, `status` in `('sent', 'approved')` and a keyable
  `destination` (as `channel:<destination>`). Row: `first_seen` the earliest such day,
  `cleared: {'by': 'seed', 'evidence': 'days/<that day>', 'at': now}`. A day that raises
  `ValueError`, `OSError` or `UnicodeError` prints `warning: novelty seed skipped <day>:
  <reason>` on stderr and is skipped.
- `seed(root, write=True)`: the count of `_history` keys not yet in the set; with `write`,
  adds them (existing rows untouched, so an uncleared row stays uncleared) through `_update`.
- `line(found, how=CLEARS)`: `f'first time for {", ".join(found)}; {how}'`.
- `today_lines(root)`: report lines for rows whose `first_seen` is today: `- <key>: cleared by
  owner (<evidence>)`, `- <key>: cleared by seed`, `- <key>: not cleared`; `['none']` when
  there are none or no file. Read only (`_read`, no lazy seed).
- `explain(root, config, key)`: `why` lines: `target: <key>`, then `seen: configured in
  config.toml`, or `first seen: <date>` and `cleared: by <by> on <at date> (<evidence>)`, or
  `cleared: not yet; <CLEARS>`, or `not seen yet` when there is no row.

### `cli/wuwei/commands/decision.py`

- `mandate()`: right after the two "already holds" returns (`:85-88`) and before the door
  checks:
  ```python
  novel = novelty.novel(root, workspace.load_config(root), novelty.record_keys(fields))
  if novel:
      route_owner(ident, fields, root)
      return 'owner\n' + novelty.line(novel)
  ```
  `decide()` already returns `0, decided`, so `decision route` prints both lines. This is
  the one routing change; `mandate()` runs only under autonomous.
- `show()` with `--widget`: when `state.read_state(root)['decision_routes'][id]` has `novel`,
  append ` First time for <keys>: your answer clears it.` to the widget's `question`.
- `owner_outcome()`: after the record is rewritten (`:200`), for each key in
  `data.get('decision_routes', {}).get(args.id, {}).get('novel', [])` call
  `novelty.clear(root, key, args.id)`, skipped when `grant is not None and args.option ==
  'keep'` (Keep owner-only leaves the target novel so the standing line stays off for it);
  on `ValueError` or `OSError` return `2, f'decision:
  {args.id} recorded; the seen set was not updated: {exc}'`. This covers the host, the
  planner card, `config set --from-card` and the DM listener, which all call it.
- `template()`: the Context placeholder becomes `Replace with the evidence file and reason for
  deciding; name a repository, channel, person, dependency, environment or workflow outside
  this item's repository as repo:<org>/<name>, channel:<id>, person:<ns>:<id>,
  dependency:<ecosystem>/<name>, env:<name> or workflow:<name>.` The template still lints.
  Placeholders such as `channel:<id>` would match `[^\s,;]+`, so `keys()` drops any match
  containing `<` or `>`, and a test asserts the template yields no keys.

### `cli/wuwei/decision.py`

- `route_owner()`: compute `novel = novelty.novel(root, workspace.load_config(root),
  novelty.record_keys(fields))` before the write; add `'novel': novel` to `data_row` and to
  `payload` only when non-empty. Every owner route (decision route, grant cards, `--external`,
  PR dispositions, outbound learn) records it under either mode.

### `cli/wuwei/outward.py`

- New `channel_ids(context)`: `[part[key] for part in (context, context.get('draft', {}))
  for key in ('channel', 'channel_id') if key in part]`, used by `classify` (replacing the
  inline list at its `destinations =` line) and by `check_tier`.
- `check_tier()`: after the `decision == 'draft'` return and before `owner_only`:
  ```python
  if config['autonomy']['mode'] == 'autonomous' and kind in ('chat', 'slack') \
          and not owner_only(inputs, config, kind):
      from wuwei import novelty
      found = novelty.novel(root, config, [key for key in (f'channel:{value}' for value in channel_ids(inputs)
                                                      if isinstance(value, str))
                                          if re.fullmatch(novelty.KEY, key)])
      if found:
          return FINDINGS, f'{APPROVAL_REQUIRED}: ' + novelty.line(
              found, 'approving this draft clears it, then the tier table decides')
  ```
  The MCP hook (`guards/outward._check`) already turns that result into a held draft and
  spends an approved one; the adapter port (`check_call`) already keeps it a draft. No
  change in `guards/outward.py`.

### `cli/wuwei/drafts.py`

- `approve()`: after the `claim` write, when `row['channel'] in ('chat', 'slack')` and
  `f'channel:{row["destination"]}'` fullmatches `novelty.KEY`, call `novelty.clear(root,
  key, draft_id)` (inside the existing `try`, so a damaged set returns its exit 2). `drop()`
  is unchanged.

### `cli/wuwei/grants.py`

- `active(config, data, name, found, standing=True)`: the standing loop runs only when
  `standing` (and not strict, as today).
- `gate()`: before `hit = active(...)`:
  ```python
  novel = (novelty.novel(root, config, [found])
           if name != 'evidence' and config['autonomy']['mode'] == 'autonomous' else [])
  ```
  pass `standing=not novel`, and append `f'; {novelty.line(novel)}'` to `head` when novel.
  The card text is unchanged: its Context already reads `Target: repo:<org>/<name>.`, so
  `route_owner` records it as novel and the owner's answer clears it.

### `cli/wuwei/commands/init.py`

- `upgrade()`: after the other writes, `count = novelty.seed(destination.parent,
  write=not args.dry_run)`; when `count`, print `f'{prefix} memory/targets.json: {count}
  targets seen in the last {novelty.DAYS} days'`. A fresh `init` is unchanged (the lazy
  seed covers it).

### `cli/wuwei/guards/protect_state.py`

- `_protected_name`: `if tail == ('memory', 'targets.json'): return True` next to the
  `ledger.jsonl` line.
- `_hint`: for that tail, `targets.json is the seen set (design 5.8.1 Novelty): the CLI writes
  it from owner answers, drafts approve and init --upgrade.`

### `cli/wuwei/report.py`

- `build()`: after `*class_lines(data)`, add `'', '## First time today',
  *novelty.today_lines(root)` (brief and full).

### `cli/wuwei/commands/why.py`

- `run()`: before the item branch, `elif re.fullmatch(novelty.KEY, target): steps =
  [(line, None, []) for line in novelty.explain(root, workspace.load_config(root), target)]`.
- `decided()`: when today's `decision_routes[ident]` has `novel`, add the step `novel:
  first time for <keys>` before the level line. Help text of `target` names `a target key`.

### Docs and design

- `docs/specs/2026-09-24-wuwei-design.md` 5.8.1: a paragraph `Novelty (owner, 2026-10-08,
  #556)`: the rule in the issue's words (one level lower, never below L0, never above the
  ceiling; under autonomous with no cruise levels a card; supervised unchanged), the seven
  key forms, what clears (one owner answer on a card naming it, or an action under mandate
  not reversed within the undo window, whichever first; configuration; the upgrade seed), the
  seen set `memory/targets.json` written only by the CLI, and that a novel target never
  creates a grant and never lets a standing grant pattern apply. Plain and short.
- `docs/site/concepts.md`: glossary entry `### Novel` (three sentences).
- `docs/site/daily.md`: one paragraph near the mandate paragraph (`:344`): what a first-time
  card looks like and that one answer clears it.
- `docs/site/reference.md`: in the `decision route` paragraph, the two-line `owner` output;
  `wuwei why <target key>`; `init --upgrade` seeding; `memory/targets.json` in the workspace
  files list if one exists; the draft reason for a first-time channel.
- No skill or charter text changes (#551).

## What must not change

- Supervised routing (`route()`, the seat route) and every route under supervised except the
  `novel` field on owner routes.
- The tier table, `classify`, the drafts hold and spend flow, and `drop()`.
- Grant rows, `[grants]` lines, `grants.plan`, the evidence card, and strict's handling of
  standing lines.
- `decision_outcomes` shapes, event kinds (no new kind), `EVENT_PRODUCERS`, the MCP and seat
  launch gates.
- Exit codes of every touched command except the new exit 2 for a damaged seen set.

## Existing tests at risk

- `tests/test_outward.py` and `tests/test_outbound.py` cases with `default_tier = "send"` or
  a sending tier row whose channel is not configured: allowed fix is adding the channel to
  that fixture's `work_channels` or `channel_classes` (or supervised when the test is about
  supervised); no assertion edits.
- `tests/test_grants.py` standing-pattern cases on a repository outside the fixture's
  `[[repos]]`: allowed fix is the same.
- Report tests pinning the full report: add the `## First time today` and `none` lines.
- `decision template` tests: the template still lints and its Context text is new.
