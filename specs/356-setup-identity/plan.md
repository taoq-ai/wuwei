# Implementation Plan: setup identity, adapter interview and the doctor PR flow section

**Branch**: `356-setup-identity` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

Four small changes at the spots everything already routes through:

1. setup measures the code-host login (one new read on the code_host port) and the bot
   authors (two more fields on the merged-PR read the calibration already makes), and adds
   them to the `extra` settings it already passes to `config.proposal`.
2. Three rows in the interview table (`interview.QUESTIONS`).
3. One doctor section built from config alone, plus `--section pr-flow`.
4. One sweep line in `plan.propose` and one paragraph in the planner skill.

No new module, no new config key, no new state key or event kind, no new guard.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. The core never imports `subprocess`: the login
and the PR authors come through the code_host adapter. TOML is written through the
existing `calibrate.settle` / `calibrate.apply` path and checked by `workspace._validate`
before the owner digest, as every setup proposal is.

## Constitution Check

- I stdlib: yes.
- II three-state exits: `viewer_login` fails closed to exit 2 through the existing
  `_operation` wrapper; doctor PR flow rows are `ok` or `warn` (config is local, nothing to
  be unmeasured) and one `unmeasured` row when the config does not load; `outcome` unchanged.
- III one behaviour, one function: `doctor.pr_flow(config)` builds the rows, used by
  doctor and by `plan.propose`; `setup.identity(...)` builds the settings.
- IV test first: tasks.md puts each test before its code.
- V ponytail: reuse `obligations._owner_login`, `config.requirements`/`missing`,
  `interview` effects, `doctor._row`/`render`/`outcome`, `calibrate.settle`/`apply`.
- VII security: everything setup proposes still goes through the one owner digest
  (`config.offer`); no value is written without it. Logins and emails are validated before
  they reach TOML; instruction-like identity text is already dropped by `discover`.

## Changes, file by file

### `cli/wuwei/registry.py`

- `PARAMETERS['code_host']`: add `'viewer_login': ()`.

### `adapters/code_host/github.py`

- `_run`: new `case ['api', 'user']: allowed = payload is None and json_output` placed
  before the generic `case ['api', endpoint, *options]`.
- New `@_operation def viewer_login(root=None)`: `value = _run(['api', 'user'])`;
  `login = _login(value)`; raise `ValueError('invalid login')` unless it fully matches
  `[A-Za-z0-9][A-Za-z0-9-]*`; return `{'login': login}`. A `null` body gives `None` and
  fails the match.
- `_MERGED`: `first:30` becomes `first:50`; nodes add
  `author{__typename login ...on Bot{databaseId}}`.
- `merged_prs`: each row adds `author` and `author_email`. For `author is None`: both
  `None`. For `__typename == 'Bot'` with an int `databaseId`: `author = login + '[bot]'`,
  `author_email = f'{databaseId}+{login}[bot]@users.noreply.github.com'`. Otherwise
  `author = login`, `author_email = None`. Use `_field` for every read so malformed nodes
  fail closed. Keep the GitHub noreply format here: it is GitHub's convention, not the
  core's.

### `adapters/code_host/none.py`

- `def viewer_login(root=None): return record_none('code_host', 'viewer_login', root,
  measurement=True)`.

### `cli/wuwei/calibrate.py`

- New pure `bot_authors(prs)`: `{row['author_email'].casefold(): row['author'] for row in
  prs if row['author_email']}`.
- `survey` (`:573-594`): call `host.merged_prs` once into a local, then
  `result['baseline'] = _port(prs, baseline)` and `result['bots'] = _port(prs,
  bot_authors)`. `baseline` and the calibration snapshot are unchanged.
- `apply` (`:493`, line `:499`): render the key quoted (`json.dumps(key)`) also when
  `path == ('shepherd', 'authors')`, and render a dict value as a TOML inline table
  (`{login = "x"}`: `'{' + ', '.join(f'{k} = {json.dumps(v)}' ...) + '}'`); every other
  value stays `json.dumps`. The existing post-write checks (`_preserves_values`, the value
  round trip, `workspace._validate`) cover the new forms.

### `cli/wuwei/workspace.py`

- `:121`: `"mention": (str, None)` becomes `"mention": (str, "")`. `shepherd._mentions`
  (`cli/wuwei/shepherd.py:165-170`) already refuses a reviewer whose mention is not
  `[A-Z0-9]+`, and `outward.py:320` only matches mentions that exist, so an empty mention
  fails closed at the ping, never earlier.

### `cli/wuwei/commands/setup.py`

- `discover` (`:118-169`): after `auth` (`:122`), `login = hub.viewer_login() if auth == 0
  else None`; append `f'code host login: {login.data["login"]}'` when `login` has exit 0,
  else `'code host login: unmeasured'`; return `'login'` (str or `None`) in the dict.
- New `identity(config, login, results)` returning calibrate settings
  `[(path, key, value)]`:
  - `owner.handles`: when `login` and `obligations._owner_login(config)` raises and
    `obligations._owner_login` accepts the handles with `login` appended (that is, no
    code-host login is there yet), `(('owner',), 'handles', [*handles, login])`.
  - `shepherd.lead_login`: when `login` and the key is empty, `(('shepherd',),
    'lead_login', login)`.
  - `shepherd.authors`: `{email.casefold(): login for each nonblank
    repos[*].identity.email}` when `login`, plus `{email: bot}` from every
    `result['bots']` that is not `None`; one `(('shepherd', 'authors'), email,
    {'login': value})` per email not already a key of `config['shepherd']['authors']`
    (compare casefolded), in sorted order.
- `_setup`: after `results = calibrate.survey(...)` (`:234`), `extra += identity(staged_cfg,
  found['login'], results)` before `config.proposal(...)`. The digest diff then shows each
  value as one line. `config.proposal` already lets interview answers and a profile win
  over `extra`.

### `cli/wuwei/interview.py`

- New `_channel(text)`: strip; `ValueError('expected a Slack channel ID such as C0123ABCD')`
  unless it fully matches `[A-Z0-9]+` (the same rule as `shepherd.py:203`); return
  `{'adapters.chat': 'slack', 'shepherd.review_channel': text}`.
- Three rows appended to `QUESTIONS`, scope `workspace`, after `posture`:
  - `tracker`, header `Tracker`, "Where does your backlog live?": `None` (discovery reads
    no tracker backlog) `{'adapters.tracker': 'none'}`; `Linear` (discovery reads the
    Linear backlog; set LINEAR_API_KEY in .wuwei/env) `{'adapters.tracker': 'linear'}`;
    free `None`.
  - `chat`, header `Chat`, "Where should review pings go?": `None` (reviewers are requested
    on the code host only) `{'adapters.chat': 'none'}`; `Slack` (set SLACK_BOT_TOKEN and
    SLACK_OWNER_DM_CHANNEL in .wuwei/env; type the review channel ID to set it too)
    `{'adapters.chat': 'slack'}`; free `(_channel, 'the Slack review channel ID, for
    example C0123ABCD')`.
  - `review_bot`, header `Review bot`, "Which review bot reads your pull requests?":
    `None` `{'adapters.review_bot': 'none'}`; `Greptile` (set GREPTILE_API_KEY in
    .wuwei/env) `{'adapters.review_bot': 'greptile'}`; free `None`.
- Nothing else: `settings`, `describe`, `ask`, `parse`, `widgets` and `record` pick the rows
  up as they are.

### `cli/wuwei/commands/doctor.py`

- `SECTIONS`: insert `'pr-flow': 'PR flow'` after `'gates'`; `DOCS['pr-flow'] =
  'docs/site/configuration.md#host-build-and-memory'` (where the shepherd keys are listed).
- New `pr_flow(config)` returning rows via `_row('pr-flow', ...)`:

  | Row | ok | warn value | fix |
  | --- | --- | --- | --- |
  | `owner.handles` | `_owner_login(config)` returns: the login | `<_owner_login error>; will block: reviewer selection, review replies and obligations at pr raise` | `bin/wuwei config set owner.handles '["<code-host login>"]'` |
  | `shepherd.lead_login` | set, or `not applicable: shepherd.min_reviewers = 0` | `empty; will block: the lead review request at pr raise` | `bin/wuwei config set shepherd.lead_login '"<lead login>"'` |
  | `shepherd.authors` | `N mapped`, or not applicable as above | `empty; will block: reviewer mentions in the review ping at pr ping` | `bin/wuwei setup (maps your git email and the bot authors), or add "<email>" = {login = "<login>", mention = "<chat id>"} under [shepherd.authors]` |
  | `shepherd.review_channel` (only when `adapters.chat != "none"`) | matches `[A-Z0-9]+`, or not applicable as above | `empty; will block: the review ping at pr ping` | `bin/wuwei config set shepherd.review_channel '"<channel id>"'` |
  | `adapters.tracker` | always; `none: discovery reads no tracker backlog` or the name | | |
  | `adapters.chat` | always; `none: no review pings or chat posts; reviewers are requested on the code host only` or the name | | |
  | `adapters.review_bot` | always; `none: discovery reads no review-bot findings` or the name | | |

  Credentials for a non-`none` adapter stay in the Gates section's `config check` row.
- `diagnose(section=None)`: after loading root and config as today, when `section ==
  'pr-flow'` return `pr_flow(config)` if config loaded, else one
  `_row('pr-flow', 'config', 'unmeasured', error or UNLOADED or 'no workspace', 'fix
  config.toml first')`, before any other measurement (no heartbeat, no probes, no
  `config check`). Without a section, add `*pr_flow(config)` right after `*_gates(...)`.
- `register`: `parser.add_argument('--section', choices=['pr-flow'], help='print one
  section only')`, outside the `--fix`/`--json` group. `run`: `rows =
  diagnose(args.section)`; the rest unchanged. `fix()` re-diagnoses with no section.
  `FIXES` unchanged (pinned by `test_fix_allow_list_is_pinned`).

### `cli/wuwei/plan.py`

- `propose`, next to `data['sweep']['mcp']` (`:118`): `from wuwei.commands.doctor import
  pr_flow`; `warned = [r['name'] for r in pr_flow(workspace.load_config(root)) if
  r['status'] != 'ok']`; `data['sweep']['pr-flow'] = 'measured: ok' if not warned else
  f"measured: {len(warned)} warn ({', '.join(warned)}); wuwei doctor --section pr-flow"`.
  (Core importing a command module has precedent: `discovery.intake` imports
  `wuwei.commands.build`.)

### `skills/wuwei-plan/SKILL.md`

- Before step 1: run `wuwei doctor --section pr-flow` once at the start of the day; on exit
  1 show its output unchanged in your first message to the owner, once, and do not write
  your own list of settings that will bite later; exit 0 says nothing; exit 2 shows the
  reason.

### Docs

- `docs/site/reference.md` Doctor: seven sections including PR flow, and `--section
  pr-flow`.
- `docs/site/configuration.md`: interview table rows for `tracker`, `chat`, `review_bot`;
  `shepherd.authors` row says `mention` is optional and needed for review pings.
- `docs/site/daily.md` Configure: setup also fills `owner.handles`,
  `shepherd.lead_login` and `shepherd.authors` from `gh` and the merged PRs, and the
  interview asks tracker, chat and review bot.

## Test fixtures that must change with the code

- `tests/fakes/code_host.py`: add `viewer_login`.
- `tests/test_adapters.py` `CALLS`: add `('code_host', 'viewer_login', (), True)`.
- `tests/fixtures/code_host/recordings.json`: the `merged_prs` recording gets the new query
  string and one User node plus one Bot node in stdout and `data`; add a `viewer_login`
  recording; `tests/test_code_host.py` `CASES` adds `'viewer_login'` so the fail-closed
  matrix covers it.
- `tests/test_setup.py` (`host` fixture, `:206-215`) and `tests/test_interview.py`
  (`:386`, `:422`) SimpleNamespace fakes: add `viewer_login`; any digest or diff assertion
  that changes because setup now proposes identity lines is updated, not weakened.
- `tests/test_doctor.py` `CONFIG`: add a filled `owner.handles`, `shepherd.lead_login` and
  one `[shepherd.authors]` entry (neutral `example.com` values) so the healthy and trial
  tests stay exit 0.

## Must not change

- `obligations._owner_login` and its single-login rule; `shepherd._rank`, `_mentions`,
  `post_review_request`.
- `config.requirements`, `config.missing` and `config check` output (the credential names
  come from there already).
- The interview mechanics (`ask`, `parse`, `widgets`, `record`, `load`) and existing
  question ids and labels.
- `doctor.FIXES`, the existing six sections' rows, `render`, `outcome`, the `--fix` and
  `--json` exclusivity.
- `calibrate.baseline` semantics apart from the sample size; the calibration snapshot keys.
- Guards, hooks, state keys, event kinds.

## Deferred

- A GitHub Issues tracker adapter (the issue lists `github` as a tracker choice).
- Measuring the owner's chat mention for `shepherd.authors`.

## Build notes

- `merged_prs` treats every non-`Bot` author type (`User`, `Mannequin`, `Organization`) as a
  plain login, so an unusual author never fails the calibration baseline closed.
- `shepherd.review_channel` is ok in doctor when non-empty; the ID form is already checked
  by the interview and by the review ping.
- `tests/test_interview.py` fakes needed no `viewer_login`: only `setup` reads the login,
  `config promote` does not.
