# Implementation Plan: an owner-only action asks the owner instead of blocking, the answer is a decision and a grant, the gate pre-approves planned deploys, and the reason names the action and the target

**Branch**: `478-publish-grants` | **Date**: 2026-10-04 | **Spec**: `spec.md` | **Issue**: #478

## Summary

One grant gate at the one spot every owner-only deploy refusal passes: `deploy.check`. `deny()`
stops building a reason and returns the rule and the repository it knows; `check` hands every
such result to `grants.gate`, which either lets the call through on a matching grant (and
appends `grant.used`) or refuses with the #362 reason naming a decision card. The card is an
ordinary decision record written with `decision.write`, routed with `decision.route_owner`,
shown with the existing `decision show D-n --widget` and answered with the existing
`wuwei decide D-n "<label>"`; `owner_outcome` stores the answer on the `grants` state row the
way #492 stores `outbound_learn` answers, and writes the `[grants]` line for `Always allow`
through the same owner edit frame #492 uses. The three former "workflow resolution" raises
become deploy refusals. `plan propose` writes the same kind of card for owner-only actions the
lead lists, and `plan gate` prints them after the gate question. No second approval mechanism,
no new port, no new store: one new core module (`grants.py`) and one new command module.

## Technical Context

Python 3.11+, stdlib only (`fnmatch`, `re`, `json`, `shlex` through existing helpers). Tests:
pytest, in process, `tmp_path` workspaces. Fixtures to reuse: `workspace` and `check()` in
`tests/test_deploy.py` (`acme/app` at `.`, `deploy.workflows = ["deploy.yml", "Production"]`);
`hook_call`, `fixed` and `events` in `tests/test_posture.py`; `proposal()`, `lead()` and `root`
in `tests/test_plan.py`; `gated()` and `edit()` in `tests/test_owner_edits.py`. The owner's
confirmation in tests: monkeypatch `wuwei.integrity._host_confirm` to return True (as
`tests/test_drafts.py` does). Day change: monkeypatch `wuwei.workspace.now`. Neutral names only
(`fixture-org/app`, `acme/app`, `Deploy Production`).

## Constitution Check

- I stdlib only: yes.
- II exits: the guard keeps 0, 1, 2. A refusal with a card, a kept action, an unresolved target
  and a host-denied command are exit 1; an unreadable state or a raced `once` spend raises
  inside `check` and is exit 2 through its existing `except`.
- III one behaviour, one function: the grant decision in `grants.gate`; the answer in
  `owner_outcome`; the standing line in `grants.standing`; the cwd repository in one helper
  shared with `merge.reference`.
- IV test first: `tasks.md` orders each test before its code.
- V ponytail: reuses the decision record, `record_widget`, `decide`, `route_owner`,
  `gate_topics`, `setup._edit` and `write_value`; one state key, three event kinds, one config
  table. Matching is on action class and target, not on argv.
- VII security: **raised conflict.** Principle VII says "nothing ever deploys (design spec 4.6
  and 4.7)" and design 4.7 says "refused always". The owner's issue changes that: the guard
  still refuses, and only the owner's recorded answer lets the same action through. This
  feature amends 4.7, the non-goal and the posture floor bullet in the design spec (dated
  owner, 2026-10-04, #478) and Principle VII (version 1.4.0). Trust: the `grants` key and the
  `grant.*` events are producer-owned; only `decide` writes `answered`; `config set grants.*`
  from an agent tool is already refused (`protect_state.GUARD_KEYS`); `grants revoke` joins the
  owner actions. The heartbeat probe never writes a card.
- Hook latency (#346): `wuwei.grants` is imported only when the deploy guard refuses.

## Contracts

### Rule to action class (FR-003)

`grants.action(rule)`: `release` for `release create`, `tag push`, `release API`, `tag or branch
ref API`; `publish` for a rule starting `deploy.deny: `; `deploy` for every other rule.
Nouns for reasons and the report: `deploy`, `release`, `publish action`; verbs for the planned
card question: `deploys`, `releases`, `publishes`.

### Target (FR-003)

`repo:<org>/<name>` where `<org>/<name>` full-matches `[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+`, taken
from, first match wins: the repository `deny()` carries (gh `-R`/`--repo`/`GH_REPO`, the
`repos/<o>/<r>/` API path, the pull request's `repo`); else the single configured repository
holding the payload cwd (`merge.configured(root, config, cwd)`, below). Otherwise `None`.

### Reasons (FR-001, FR-004, FR-012, US4)

`<command>` is `' '.join(hook.redacted_target(payload, root).split())`. `<posture>` is
`workspace.posture(config)[0]`. `<noun>` and `<rule>` as above.

| Case | Exit | Reason |
|---|---|---|
| card written or reused | 1 | `publish: <command> on <org>/<name> is a <noun> (<rule>), owner-only under <posture>; the owner decides: bin/wuwei decision show D-n --widget` |
| answered `keep` today | 1 | `publish: <command> on <org>/<name> is a <noun> (<rule>), owner-only under <posture>; the owner kept it owner-only (D-n): ask the owner to run it in a host terminal` |
| target `None` | 1 | `publish: <command> is a <noun> (<rule>), owner-only under <posture>; name the repository with -R <org>/<repo> or run it from a configured repository so the owner can decide on a card, or the owner runs it in a host terminal` |
| host permission rule | 1 | `publish: <command> is a <noun> (<rule>), owner-only under <posture>; the workspace permissions deny it, so no grant lifts it: ask the owner to run it in a host terminal` |
| heartbeat session | 1 | `publish: <command> is a <noun> (<rule>), owner-only under <posture>; ask the owner to run it in a host terminal` |

The host permission case: `fnmatchcase(' '.join([program, *args]), rule[5:-1])` for a rule in
`deploy.PERMISSIONS_DENY` (`Bash(<pattern>)`), checked before any card is written. Every reason
starts `publish: `, so the hook adds no posture line (FR-012). `wuwei why` splits on `; ` and
prints `rule: publish: ...` and `fix: the owner decides: ...` unchanged.

### Refusal card record (FR-004, FR-005)

Written by `grants.ask`. `<strict>` is posture `strict`. One line per field; the command is
already one line.

```
Question: Allow <action> on <org>/<name>?
Class: other
Context: <command> is a <noun> (<rule>). Target: repo:<org>/<name>. Item: <item or none>. Seat: <seat>.
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
| keep | Keep owner-only | Nothing runs from the session. | You run the command in a host terminal. |
| once | Allow once | The seat runs this <action> on <org>/<name> once. | The next run asks again. |
| today | Allow today | Every <action> on <org>/<name> runs until wuwei close. | Each run is recorded as grant.used. |
| always | Always allow | A standing grant in config.toml [grants]. | Later days too, until bin/wuwei grants revoke. |   (omitted under strict)
Musts:
| Criterion | keep | once | today [| always] |
| Owner decides | pass ... |
Wants:
| Criterion | Weight | keep | once | today [| always] |
| Least standing access | 10 | 9 | 7 | 5 [| 3] |
Recommendation: keep
Reasoning: A grant lets a seat run an action that cannot be undone; keep it unless this run is expected.
Confidence: medium
Reversibility: one-way
Blast radius: <noun> on <org>/<name>.
Pre-mortem: A seat runs the <action> at the wrong time or on the wrong branch.
Revisit: Revoke a standing grant with bin/wuwei grants revoke.
Decided-by: owner
Outcome: pending
```

`<item>` is `hook.claimed(root, payload['session_id'])`; `<seat>` is `payload.get('agent_type')`
or `main session`. `decision show D-n --widget` then prints labels `Keep owner-only
(Recommended)`, `Allow once`, `Allow today`[, `Always allow`] in that order.

### Planned card record (FR-011, US3)

Written by `grants.plan`, same builder. Question: `<goal> <item> <verb> <org>/<name>: allow
today, ask when it happens, or keep owner-only?`. Options `today` (`Allow today`, "The <noun>
runs without asking today.", "Each run is recorded as grant.used."), `ask` (`Ask when it
happens`, "The first run asks on a card.", "The day stops once for it."), `keep` (`Keep
owner-only`, "Nothing runs from the session.", "You run it in a host terminal."). Wants
`Day runs without interruption` weight 10: today 9, ask 5, keep 1; under strict the Wants row is
`Least standing access`: keep 9, ask 5, today 3 and the recommendation is `keep`; otherwise
`today`. Context: `Planned in days/<date>/plan.md for <item>. Target: repo:<org>/<name>.`

### Status-quo title (spec Assumptions)

`decision.STATUS_QUO = r'(?i)(?:Do nothing|Defer|Keep)\b'`, used by `decision._scored`
(`decision.py:82-83`, message "include Do nothing, Defer or Keep") and by
`control_plane` `drop it` (`control_plane.py:62`).

### `wuwei grants` output (FR-009)

```
1. deploy repo:fixture-org/app always (D-3, 2026-10-04)
today: deploy repo:fixture-org/app today (D-5)
today: release repo:fixture-org/app once (D-6)
```

Under strict, standing lines end with ` (ignored under strict)`. Nothing: `No grants.` Exit 0;
an unreadable config or state is exit 2 with the reason.

## Changes

### `cli/wuwei/guards/deploy.py` (FR-001, FR-002, FR-003)

- `deny(rule, repo=None)`: `return 1, (rule, repo)`. Only `check` ever sees this value.
- `workflow(target, config, repo=None)`: a marked match, and the case that raised `unknown(...
  'workflow name or ID requires unavailable workflow resolution')` at line 59, both `return
  deny('deploy.workflows', repo)`. The empty-target `unknown` at 52 and the clean path stay.
- `api(...)`: `repo = '/'.join(parts[1:3]) if parts[0] == 'repos' and len(parts) > 2 else
  None`; pass it to every `deny` and to `workflow`; the rerun `unknown` at 166-167 becomes
  `return deny('deploy.workflows', repo)`.
- `gh(...)`: pass `repo` to `deny('release create', repo)` and `workflow(..., repo)`; the
  `run rerun` `unknown` at 226-227 becomes `return deny('deploy.workflows', repo)`.
- `merge(...)`: `deny(..., data['repo'])`.
- `check`: move the per-command body of the loop (lines 280-316) into `command_result(argv,
  env, config, root)` returning `(0, '')`, `(1, (rule, repo))` or `(2, reason)`; the loop
  does `result = command_result(...)`, then `if result[0] == 1: from wuwei import grants;
  return grants.gate(payload, root, config, argv, *result[1])` and `if result[0]: return
  result`. The opaque-command `unknown` stays in the loop. The `except` at 318-319 is unchanged.

### `cli/wuwei/merge.py` (FR-003)

`configured(root, config, cwd)`: the repository names whose resolved path holds `cwd`, with the
existing vcs `common_dir` fallback (lines 49-56, moved unchanged). `reference` calls it and
keeps its "numeric PR requires an unambiguous configured repository" error.

### `cli/wuwei/grants.py` (new; FR-003 to FR-008, FR-011)

- `ACTIONS = {'deploy': ('deploy', 'deploys'), 'release': ('release', 'releases'), 'publish':
  ('publish action', 'publishes')}`; `REPO = r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'`.
- `action(rule)`, `target(root, config, cwd, repo)` per the contracts.
- `active(config, data, action, target)`: `('always', D)` for the first standing line with the
  same action and `fnmatchcase(target, line['target'])` unless posture is strict; then a row
  answered `today` while `not data.get('close_requested')`; then a row answered `once` and not
  `spent`. Else `None`.
- `_record(question, context, rows, recommendation, blast, premortem)`: the record text from
  `(id, title, rationale, consequence, score)` rows; used by `ask` and `plan`.
- `ask(root, row, text) -> str`: `decision.write(text, root).stem`, `decision.
  route_owner(D, fields, root)`, then `state._write_state(..., reserved=False,
  kind='grant.asked', payload={'id', 'action', 'target', 'planned'})` setting
  `data.setdefault('grants', {})[D] = {**row, 'answered': None, 'spent': False}`. Returns D.
- `gate(payload, root, config, argv, rule, repo) -> (code, reason)`: the contracts table, in
  this order: heartbeat (`payload.get('session_id') == hook.HEARTBEAT_SESSION`), host
  permission rule, target `None`, `active` (on a hit: for `once`, a `_write_state` with
  kind `grant.used` whose update raises `ValueError(f'grants: {D} changed; {RACE}')` unless
  the row is still answered `once` and not spent, then sets `spent=True`; otherwise
  `state.append_event('grant.used', ...)`; payload `{decision, action, target, scope,
  session, item}`; return `(0, '')`), a row for this action and target answered `keep`
  (keep reason), an unanswered row for this action and target (reuse its D), else `ask`.
- `plan(root, config, candidates) -> {item: [(action, target, D)]}`: per candidate
  `owner_actions` entry, reuse a planned row written today with the same item, action and
  target (answered or not, so a re-proposal keeps the owner's answer), else `ask` with the planned card and row `{action, target, item, goal, planned:
  True, rule: 'planned', command: None, seat: None}`.
- `gate_widgets(root, config) -> list`: `decision.record_widget(D, fields, level=workspace.
  verbosity(config, 'decisions'))` for each unanswered planned row today, in id order.
- `standing(root, row, D) -> int`: under strict print `decide: Always allow is not offered
  under strict; answer Allow today or Allow once` to stderr and return FINDINGS; else
  `setup._edit('decide', 'standing grant', lambda *args, **kwargs: True, change, root)` where
  `change` returns `setup.write_value(raw, 'grants.standing', [{'action', 'target', 'scope':
  'always', 'decision': D, 'date': workspace.now().date().isoformat()}], mode='append')`.

### `cli/wuwei/commands/hook.py` (FR-012)

In `posture()` after the `NO_REVIEWER` line: `if guard == 'deploy' and reason.startswith(
'publish: '): line = ''`. Nothing else changes.

### `cli/wuwei/commands/decision.py` (FR-006)

`owner_outcome`, after the `learned` block (128-132): `grant = data.get('grants', {}).get(
args.id)`; when `grant` and `args.option == 'always'`, `grants.standing(root, grant, args.id)`;
a nonzero result returns `(1, 'decision: the standing grant was not written; run bin/wuwei
config check, then answer again')`. In `update`, `if args.id in current.get('grants', {}):
current['grants'][args.id]['answered'] = args.option`.

### `cli/wuwei/commands/grants.py` (new; FR-009)

`grants` (no action) lists per the contract; `grants revoke <n>`: `n` from 1; out of range is
exit 1 `grants: no standing grant <n>; bin/wuwei grants lists them`; otherwise
`setup._edit('grants revoke', 'standing grant', None, change, root)` with `change` writing the
list without line `n` through `setup.write_value(raw, 'grants.standing', rest)`; on CLEAN
`state.append_event('grant.revoked', {'decision', 'action', 'target'}, root)`.

### `cli/wuwei/workspace.py` (FR-008)

- `SCHEMA['grants'] = {'standing': [{'action': (str, None, ('deploy', 'release', 'publish')),
  'target': (str, None), 'scope': (str, 'always', ('always',)), 'decision': (str, None),
  'date': (str, None)}]}`.
- `load_config`: each line's `target` full-matches `repo:[A-Za-z0-9_.*?-]+/[A-Za-z0-9_.*?-]+`,
  `decision` full-matches `decision.DECISION_ID`, `date` is `YYYY-MM-DD`; otherwise
  `ConfigError('grants.standing.<i>: ...; the owner fixes it with bin/wuwei grants revoke <i+1>
  in a host terminal')`.
- `CONFIG_CACHE_VERSION` 7 to 8.

### `cli/wuwei/plan.py` (FR-011)

- `_proposal`: an optional candidate `owner_actions` must be a list of objects with exactly
  `action` in `grants.ACTIONS` and `target` full-matching `repo:` + `grants.REPO`; otherwise
  `ValueError(f'{name}: owner_actions need action deploy, release or publish and target
  repo:<org>/<name>; {PLAN_JSON}')`.
- `propose`: after the gate-approved check (160-161), `planned = grants.plan(root,
  workspace.load_config(root), data['candidates'])`; each candidate block gets one line per
  entry, `Owner-only: <action> repo:<org>/<name> (D-n)`, after its `Flags:` line.

### `cli/wuwei/commands/plan.py` (FR-011)

`gate` prints `json.dumps([plan.gate_widget(...), *grants.gate_widgets(root, config)],
indent=2)`. `gate_widget` itself is unchanged.

### `cli/wuwei/decision.py`, `cli/wuwei/control_plane.py`

`STATUS_QUO` per the contract, used at both sites.

### Records and registries (FR-014, FR-009)

- `state.STATE_PRODUCERS['grants'] = 'wuwei hook PreToolUse (deploy guard), wuwei plan propose or
  wuwei decide'`.
- `commands/event.EVENT_PRODUCERS`: `grant.asked` (`wuwei hook PreToolUse or wuwei plan
  propose`), `grant.used` (`wuwei hook PreToolUse`), `grant.revoked` (`owner host wuwei grants
  revoke`).
- `signal.SILENT` gains the three kinds (the routed decision already nudges).
- `commands/__init__.py`: `'grants'` joins `READ_ONLY`, `'grants revoke'` joins `WRITES`.
- `guards/protect_state.py` `_OWNER_ACTIONS[('grants', 'revoke')]`: "Revoking a grant is the
  owner's, outside agent tools: list them with bin/wuwei grants, and the owner runs bin/wuwei
  grants revoke <n> in a host terminal."

### `cli/wuwei/commands/doctor.py` (FR-010)

In `_workspace` after the posture rows: under strict, per line `i`, `_row('workspace',
f'grant {i}', 'warn', f'{action} {target} ({decision}) is ignored under strict', f'bin/wuwei
grants revoke {i}')`.

### `cli/wuwei/report.py` (FR-013)

After the spec warnings: count `grant.used` events by `(decision, action)`; when any, add `##
Grants` with `- <verb> run under grant <D>: <n>` (for example `- deploys run under grant D-3:
3`).

### Skill, charters, docs, design (FR-015)

- `skills/wuwei-plan/SKILL.md` step 4: `wuwei plan gate` prints a list, the gate question first
  and then one `D-n` card per planned owner-only action; ask them in one AskUserQuestion (at
  most four per call), record each `D-n` answer with its `record` command before step 5. New
  paragraph "Owner-only actions": a seat's refusal that names `bin/wuwei decision show D-n
  --widget` is asked like any decision card; after the answer, continue the seat so it runs the
  same command; `Keep owner-only` means show the owner the command for a host terminal.
- `charters/_common.md` rule 2: deploy, release or promote only under the owner's grant: on a
  `publish:` refusal stop and hand back naming its `D-n`, and rerun the same command only when
  the planner says the owner allowed it. `charters/lead.md` step 4: list an item's owner-only
  steps as `owner_actions` (`action`, `target`). Bump both charters' `version`; regenerate
  `agents/` with `python3 -P -m wuwei agents build`.
- `docs/site/concepts.md` (a "Grants" section near the posture text at 163), `configuration.md`
  (`[grants]`), `security.md` (line 56 floor and 86: you decide, a grant is how you decide
  once), `daily.md` (the gate line and the refusal card), `reference.md` (`wuwei grants` and
  `grants revoke` under Host terminal actions, and the concepts.md list of them). Site pages
  address the reader ("you"), as `test_pages_address_the_reader` requires.
- `docs/specs/2026-09-24-wuwei-design.md`: non-goal "Deploying" and 4.7 gain "Amended (owner,
  2026-10-04, #478): the guard refuses and asks; only the owner's recorded answer (once, today,
  always) lets the same action through"; the floor bullet under Security posture says the same.
- `.specify/memory/constitution.md` Principle VII: "nothing deploys without the owner's recorded
  grant (design spec 4.6 and 4.7)"; version 1.4.0, Last Amended 2026-10-04.

### Tests that change with the new contract

- `tests/test_deploy.py`: rows `gh workflow run test.yml`, `gh run rerun 123`, `gh workflow run
  123`, `gh api .../runs/123/rerun -X POST` become exit 1 with `workflow`;
  `test_workflow_aliases_fail_closed` becomes exit 1 with `deploy` in the reason and
  `resolution` not in it. Rows already at exit 1 keep their substrings (the rule is in the
  reason).
- `tests/test_plan.py` `test_cli_propose_and_approve`: `plan gate` prints a list, so the gate
  widget's `record` is read from its first entry.
- `tests/test_workspace.py` defaults and `tests/test_signal_status.py` tiers gain the new key and
  the three silent kinds.

## What must not change

- `deploy.check`'s scope, relevance and parse paths, and every exit-2 reason that is not an
  owner-only rule (unparsed input, unknown git alias, unresolved push destination, opaque
  script, port errors).
- `deploy` stays in `guards.OWNER_ONLY`; no posture lowers it; only a grant passes it.
- `decision.record_widget`, `decide`, `gate_topics`, `_GATE_EDITS` and the strict rule that the
  owner records in a host terminal.
- `plan.gate_widget`'s return value and its tests; the gate still records with `plan approve`.
- `PERMISSIONS_DENY` and `wuwei init`'s settings.
- The `pr` guard, the outward tier and the #493 draft card.
- No import of `wuwei.grants` on a Bash call the deploy guard does not refuse.

## Project Structure

```
specs/478-publish-grants/
  spec.md  plan.md  data-model.md  tasks.md
cli/wuwei/grants.py  merge.py  plan.py  decision.py  control_plane.py  workspace.py  state.py  signal.py  report.py
cli/wuwei/guards/deploy.py  protect_state.py
cli/wuwei/commands/grants.py  hook.py  decision.py  plan.py  doctor.py  event.py  __init__.py
skills/wuwei-plan/SKILL.md  charters/_common.md  charters/lead.md  agents/*.md
docs/site/concepts.md  configuration.md  security.md  daily.md  reference.md
docs/specs/2026-09-24-wuwei-design.md  .specify/memory/constitution.md
tests/test_grants.py (new)  test_deploy.py  test_plan.py  test_decision.py  test_doctor.py  test_report_retro.py  test_owner_edits.py  test_cli_known_command.py  test_hooks.py
```
