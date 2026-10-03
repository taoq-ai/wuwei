# Implementation Plan: Tracker hygiene (spec amendment)

**Branch**: `416-tracker-hygiene-spec` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

Spec-only. Paste the five blocks of [contracts/design-amendment.md](contracts/design-amendment.md)
into `docs/specs/2026-09-24-wuwei-design.md` (new 5.11, one clause in the 4.1 Agent row, one
bullet in 4.9, the section 8 tracker row) and `.specify/memory/constitution.md` (one Workflow
bullet, version line). Prove the change with a throwaway phrase check run red on a `main`
export and green on the worktree, review for consistency, run the suite. No runtime code, no
test changes. The "Implementation map for #417" below records where each 5.11 rule lands so
#417 needs no design decision; it is not built here.

## Technical Context

Markdown only. The phrase check is a stdlib script kept in a scratch directory outside the
repository, never committed. The only tests that read these files are
`tests/test_docs.py::test_guard_boundaries_are_stated_once` (4.5, 9.1, section 10, a
constitution phrase; none touched) and
`tests/test_calibrate.py::test_instruction_like_passes_this_repository` (the constitution
must stay free of instruction-like text; block E is plain).

## Constitution Check

- I, II, III: no runtime code. 5.11 itself keeps them: adapters are stdlib `urllib`; every
  adapter call is three-state; one CLI function (`tracker.check`) holds the ticket rule and
  the five refusal points call it.
- IV (test first): the phrase check runs red on `main` before the paste, green after. Red is
  never produced by stashing or reverting the working tree.
- V (ponytail): no new port operation beyond `comment`; linking rides on `create`'s
  `parent`; one writer for all comment kinds, fed by events the CLI already writes; no new
  state other than `tickets` and `tracker_log`; no config for the templates or the parent
  link type.
- VII (security): every tracker write still passes the outward policy (4.9); `auto` only
  exempts mechanical, record-derived text, and anything naming a person drafts. New tokens
  stay out of seat environments (`env.CREDENTIALS`); the GitHub token has its own name so
  `gh` never picks it up.
- Governance: the design spec is amended by its owner; the owner's evidence line is in the
  issue and the owner merges.

## What changes (#416)

| File | Change |
|---|---|
| `docs/specs/2026-09-24-wuwei-design.md` | block A: `### 5.11 Tracker hygiene (owner, 2026-10-03, #416)` after the last `### 5.x` section, before `## 6. Memory` |
| same | block B: the 4.1 PreToolUse `Agent` launch row gains the ticket clause |
| same | block C: 4.9 gains the tracker-writes bullet after "Precedence:" |
| same | block D: the section 8 tracker row lists all seven operations and the three adapters |
| same | 3.1 layout: `tracker/` lists `none (default), linear, jira, github` (found in the builder's consistency review) |
| `.specify/memory/constitution.md` | block E: one Workflow bullet; version 1.2.0, Last Amended 2026-10-03 (or one minor above #411's bump if that merged first) |
| `specs/416-tracker-hygiene-spec/` | this feature's spec, plan, tasks, contract |

## Consistency review (builder)

Read 5.11 against these and edit only the design spec, only for a real conflict, keeping the
phrases the check pins: 3.5 (ports, `none` adapter, contract tests), 4.1 (Agent row, chat or
tracker row), 4.3 (outward lint words), 4.6 (merge path writes the done transition), 4.9
(auto-send and approve), 5.3 (tiers via 5.3 tracks and #280 gate tiers), 5.6 (lead time from
`claim` and `history`), 5.7 (discovery reads the tracker backlog; dedupe), 5.8.1 (`message`
ceiling, kill switch), 8 (tracker row), 9.1 (`seats` area, credentials out of seat
environments). Section numbering: if #411 or #415 has landed, 5.11 still follows the last
`### 5.x` section.

## Verification commands

Run from the repository root; `<scratch>` is any directory outside the repository.

```sh
mkdir -p <scratch>/main && git archive main docs/specs .specify/memory | tar -x -C <scratch>/main
python3 <scratch>/check_416.py <scratch>/main   # must fail: AssertionError: 5.11 section
python3 <scratch>/check_416.py .                # must print: OK: tracker hygiene stated
git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts docs/site tests README.md
python -m pytest -q
```

The `git diff --stat` line must print nothing.

`<scratch>/check_416.py`:

```python
import re, sys
from pathlib import Path
root = Path(sys.argv[1])
spec = (root / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
law = (root / '.specify/memory/constitution.md').read_text()
flat = lambda text: ' '.join(text.split())
found = re.search(r'^### 5\.11 Tracker hygiene \(owner, 2026-10-03, #416\).*?(?=^##)', spec, re.S | re.M)
assert found, '5.11 section'
hygiene = flat(found[0])
for key, default in (('required', '`true`'), ('skip_tiers', '`[]`'), ('strict_close', '`true`'),
                     ('create', '`["bugs", "triage", "follow-ups"]`'),
                     ('log', '`["decisions", "progress", "verdicts", "pr", "close"]`'),
                     ('auto', '`["progress", "pr", "close"]`'),
                     ('max_per_item_per_day', '`10`'), ('project', '`""`'), ('board', '`""`')):
    assert f'| `{key}` | {default} |' in hygiene, key
for kind in ('decisions', 'progress', 'verdicts', 'pr', 'close'):
    assert re.search(rf'\| `{kind}` \| [^|]+ \| [^|]+ \|', hygiene), kind
for adapter, credential in (('linear', 'LINEAR_API_KEY'), ('jira', 'JIRA_API_TOKEN'),
                            ('github', 'GITHUB_TRACKER_TOKEN')):
    assert re.search(rf'\| `{adapter}` \| [^|]+ \| [^|]*{credential}', hygiene), adapter
for phrase in ('`linear`, `jira`, `github`', 'The schema default stays `none`',
               'in force only when `adapters.tracker` is not `none`',
               '`tickets` in `state.json`', 'written only by the CLI', "candidate's `ticket` field",
               '`wuwei plan set <item> ticket=<id>`', '`created(item)`', "--import-yesterday` carries yesterday's tickets",
               'one CLI function, `tracker.check`', 'bin/wuwei tracker create <item>',
               'bin/wuwei plan set <item> ticket=<id>', 'bin/wuwei drafts approve <draft>',
               '`plan approve`: one refusal lists every approved item', '`plan add`',
               '`build next`, before the claim, and `dispatch next`, before the gates',
               'PreToolUse `Agent` launch', 'under the `seats` area',
               "recorded gate tier when there is one, else the lead's tier",
               'one `tracker.skipped` event', '`wuwei close` refuses',
               'bin/wuwei tracker done <item>', '`strict_close = false`',
               'class `items`', '--bug|--triage|--follow-up', 'must be in `create`',
               'Linear creates a sub-issue', 'Relates link', '`Related: <parent>`',
               'absolute path is refused', 'idempotent per class, subject and title',
               '`tracker.created` event', '`wuwei tracker log`', 'by the watch sweep (4.2)',
               '`tracker_log`', 'a second run writes nothing new', '`[<day> <item>]`',
               'passes the outward lint (4.3)', 'not retried', 'is in `auto` is sent',
               'becomes a draft', 'cruise levels do not apply', 'records it in `tickets`',
               '`max_per_item_per_day` comments a day', 'one `tracker.folded` event',
               '`comment(item, text, category)`', '`{title, description, item, category, parent}`',
               'returns `{id, url}`', 'port contract test', 'recorded fixtures',
               '`JIRA_SITE`', '`linear.app`', '`atlassian.net`', '`doctor` fails the tracker row',
               'bin/wuwei config set tracker.required false', 'board, `wuwei next` and the DM',
               '`[outward] humanize`, default true, #420',
               'whose owner is not in `outbound.code_host_orgs` is an external party'):
    assert phrase in hygiene, phrase
hooks = flat(re.search(r'^### 4\.1 .*?(?=^### )', spec, re.S | re.M)[0])
assert 'tracker hygiene requires one (5.11)' in hooks
tiers = flat(re.search(r'^### 4\.9 .*?(?=^## )', spec, re.S | re.M)[0])
assert '`tracker.auto`' in tiers and 'Tracker writes (5.11)' in tiers
assert 'not in `outbound.code_host_orgs` is an external party' in tiers
adapters = flat(re.search(r'^## 8\. .*?(?=^## )', spec, re.S | re.M)[0])
assert '`comment(item, text, category)`' in adapters and 'Jira' in adapters
assert 'tracker/         none (default), linear, jira, github' in spec, '3.1 layout'
assert 'Tracker hygiene (design 5.11)' in flat(law) and 'Last Amended**: 2026-10-03' in law
for text in (spec, law):
    assert '\N{EM DASH}' not in text
print('OK: tracker hygiene stated')
```

## What must not change

- Runtime and shipped text: `cli/`, `adapters/`, `hooks/`, `bin/`, `agents/`, `charters/`,
  `skills/`, `templates/`, `scripts/`, `docs/site/`, `README.md`. They change in #417.
- `tests/`: no file changes.
- Design 4.5, 9.1 and section 10: untouched, so `test_guard_boundaries_are_stated_once`
  keeps passing. No other design section changes except blocks B to D and the 3.1 layout line.

## Implementation map for #417 (recorded here, built there)

One shared spot per concern. Every refusal comes from one function; every write from one
writer; every adapter call through the existing port and its outward decorator.

Shared core, new `cli/wuwei/tracker.py` (stdlib and `wuwei` imports only, imported lazily by
callers so the common hook path gains nothing, #346):

- `ticket(data, item) -> str | None`: `data.get('tickets', {}).get(item, {}).get('id')`.
- `check(data, config, item, row=None) -> (status, reason)`: `off` (adapter `none` or
  `required` false), `ticket`, `skipped` (tier from `row['gates']['tier']`, else
  `row.get('tier')`, in `skip_tiers`), `missing` with the single 5.11 reason; a pending
  `items` draft for the item (`data['drafts']`, `drafts.read`) switches the reason to
  `bin/wuwei drafts approve <draft>`. Pure: no I/O, no events.
- `create(root, subject, category, title=None, evidence=())`: builds the neutral draft (for
  `items`, title and description from the proposal candidate in `proposal.json` or the
  `discovery_candidates` row), refuses a category not in `tracker.create` (except `items`)
  and any evidence line matching `profiles.ABSOLUTE`, dedupes on (category, subject,
  normalized title) through `tracker_log`, calls the port `create`, and on exit 0 writes
  `tickets[subject]` (for `items`) and a `tracker.created` event in one `state._write_state`.
- `log(root) -> exit`: reads `events.jsonl` (`watch.records`) for the kinds in 5.11's table,
  filtered by `tracker.log`, builds `[<day> <item>]` templates, skips keys already in
  `tracker_log`, applies the cap and the fold, calls the port `comment(ticket, text,
  category)`, and records each outcome (written, drafted with draft id, refused with reason,
  folded) plus one `tracker.logged` event per run and `tracker.folded` when it folds.
- `done(root, item)`: `dispatch.tracker_call(item, 'done', root)`.

Call sites (one line each, raising the caller's existing refusal type):

| File | Function | Change |
|---|---|---|
| `cli/wuwei/plan.py` | `_proposal` | optional candidate `ticket`: string matching `[A-Za-z0-9][A-Za-z0-9._/#-]{0,99}` |
| `cli/wuwei/plan.py` | `approve` | ticket per approved candidate (its `ticket`, or its id when it came from the tracker source in `proposal.json` `discovered`); `tracker.check` each; refuse with all reasons in one `StateError`; write `tickets` in the same update; carry yesterday's `tickets` for imported items; `tracker.skipped` per exempt item |
| `cli/wuwei/plan.py` | `add` | same for one candidate (`source == 'tracker'` gives the id); a refusal raises `ValueError`, which `discovery.intake` already turns into an owner proposal |
| `cli/wuwei/plan.py`, `cli/wuwei/commands/plan.py` | new `set_ticket(item, ticket, root)` and verb `plan set <item> ticket=<id>` | item must be a day item or proposal candidate; verify with the tracker port `created(ticket)`; exit 2 when it cannot be read; writes `tickets[item]` with source `set`, event `plan.set`; only the `ticket` key here (#412 and #419 add theirs) |
| `cli/wuwei/commands/build.py` | `next_action` | `tracker.check` before `_save`; missing is a refusal (exit 1) |
| `cli/wuwei/dispatch.py` | `next_step` | `tracker.check` after `_item`; missing raises `Refused` |
| `cli/wuwei/dispatch.py` | `tracker_call` | ticket id from `tracker.ticket`, else the item id |
| `cli/wuwei/guards/agent_launch.py` | `_check`, inside `reserve(data)` | missing raises `brief.Refused(reason)`; the `seats` area decides warn or block |
| `cli/wuwei/closing.py` | `unresolved` | for an approved item merged today with a ticket, while `required` is in force: no `tracker.call` event with `action == 'done'` and `exit == 0` for it today is a finding naming `bin/wuwei tracker done <item>`; with `strict_close` false, print it and do not count it |
| `cli/wuwei/commands/close.py` | `run` | after `closing.check` returns 0, `tracker.log(root)` (close entries) |
| `cli/wuwei/watch.py` | `sweep` | `tracker.log(root)` in its own try, like the steward; exit 2 counts as unreadable |
| `cli/wuwei/metrics.py` | `_lead_time` | `history` and `created` use the ticket id |
| new `cli/wuwei/commands/tracker.py` | `tracker create`, `tracker log`, `tracker done` | thin argparse over `tracker.py`; add the three paths to `WRITES` in `cli/wuwei/commands/__init__.py` (and `plan set`) |

Config, state, events:

- `cli/wuwei/workspace.py` `SCHEMA['tracker']`: the nine keys of 5.11 with the closed value
  lists; `adapters.tracker` default unchanged (`none`).
- `templates/workspace/config.toml` `[tracker]`: the keys with one comment line each.
- `cli/wuwei/commands/config.py` `requirements`: `('tracker', 'jira')`: `JIRA_SITE`,
  `JIRA_EMAIL`, `JIRA_API_TOKEN`; `('tracker', 'github')`: `GITHUB_TRACKER_TOKEN`.
- `cli/wuwei/env.py` `CREDENTIALS` adds those four; `PUBLIC` adds `JIRA_SITE`.
- `cli/wuwei/state.py` `STATE_PRODUCERS`: `tickets` (plan approve, plan add, plan set,
  tracker create, drafts approve), `tracker_log` (wuwei tracker log or create); `_validate`
  checks their shape.
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `tracker.created`, `tracker.skipped`,
  `tracker.folded`, `tracker.logged`, `plan.set`.

Port, outward, drafts:

- `cli/wuwei/registry.py` `PARAMETERS['tracker']`: add `'comment': ('item', 'text',
  'category')`.
- `cli/wuwei/outward.py`: `METADATA_FIELDS` adds `category` and `parent`; in `classify`, for
  `kind == 'tracker'` and `context.get('category') in config['tracker']['auto']` with no
  recipients, return send, placed after the sensitive, pattern, audience-flag, external and
  recipient checks and before the final non-chat draft branch.
- `cli/wuwei/drafts.py`: `OPERATIONS['tracker']` adds `comment`; `approve` keeps the send
  result's data and, for a sent tracker `create`, records the ticket (`items`) and the
  `tracker.created` event through the same writer `tracker.create` uses.
- `adapters/_http.py` `request`: add `method` (default `POST`); `payload=None` sends no body.
  The one shared HTTP helper; Jira needs GET and PUT.
- `adapters/tracker/none.py`: `comment` (`record_none`, measurement false, outward
  decorated).
- `adapters/tracker/linear.py`: `comment` (`commentCreate`); `create` accepts the neutral
  draft and the existing keys, strips `item` and `category`, maps `parent` to `parentId`
  (issue lookup by identifier), takes `teamId` from `tracker.project` or `backlog_filter`
  when absent, and returns `{'id': identifier, 'url': url}`.
- New `adapters/tracker/jira.py` and `adapters/tracker/github.py`: every port operation per
  the 5.11 table, `@operation` and `@outward_operation('tracker')` as in `linear.py`.
  `history` rows use Linear's shape (`createdAt`, `toState.name`): Jira from the status
  changelog, GitHub from Projects v2 status changes with a board, else the first assignment
  as `In Progress`.
- Fixtures: `tests/fixtures/reference_adapters/recordings.json` (or one file per adapter
  under `tests/fixtures/tracker/`) with recorded responses; `tests/test_adapters.py` module
  contract covers the new modules once `PARAMETERS` changes.

Setup, interview, doctor:

- `cli/wuwei/commands/setup.py` `discover`: read each repository's `README*`,
  `CONTRIBUTING*` and `.github/PULL_REQUEST_TEMPLATE*` for `linear.app` or `atlassian.net`;
  print `tracker links: <name> (<file>)`; no config change from detection.
- `cli/wuwei/interview.py` `QUESTIONS`: `tracker` choices Linear (first), Jira, GitHub, None,
  free text `<tracker> <project>`; new `tickets` (Every item: `tracker.required = true`,
  `skip_tiers = []`; All but light items: `skip_tiers = ["light"]`; Optional:
  `tracker.required = false`); new `updates` (Progress, PR and close: the default `auto`;
  Also new tickets: adds `items`, `bugs`, `triage`, `follow-ups`; Everything: every kind;
  Nothing: `[]`).
- `cli/wuwei/commands/doctor.py`: one `tracker` row through the existing probe path (not
  `pr_flow`, which `plan propose` calls without network): `backlog` exit 0 is ok; otherwise
  fail with the missing credential names or `bin/wuwei config set tracker.required false`.

Owner surfaces and docs:

- `cli/wuwei/commands/board.py` `read`: a Ticket column and the day's created tickets per
  item; `cli/wuwei/commands/next.py` `line`: the ticket beside the item;
  `cli/wuwei/listen.py` `notify`: the loop notice names the ticket.
- `docs/site/configuration.md` (`[tracker]` rows), `docs/site/adapters.md` (adapters and
  credentials tables), `docs/site/concepts.md` glossary (ticket, tracker hygiene, fold),
  `docs/site/daily.md` (one paragraph), `docs/site/reference.md` (four command rows). A site
  paragraph that mentions cruise must say "not built" (`test_cruise_mode_is_designed_not_built`).
- Charters: `charters/builder.md` and the sentinel charters name `tracker create --bug` for a
  bug outside the item's scope; `charters/planner.md` names `tracker create --follow-up` for
  retro follow-ups and `tracker create <item>` at the morning gate; regenerate `agents/`.

## Deferred

- `--triage` subjects that are incident ids depend on #415 (5.10); until it lands, the
  subject is a day item id.
- Renumbering 5.9 Cockpit against #411's 5.9 belongs to #411.
