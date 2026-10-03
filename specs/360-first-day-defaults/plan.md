# Implementation Plan: the first day works on defaults

**Branch**: `360-first-day-defaults` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

Small changes at the spots setup already routes through:

1. One local git read on the vcs port (`default_branch`), used by `setup.discover` when the
   code host cannot answer, plus a `<login>/<directory>` name for a repository with no
   remote.
2. Four y/N preference questions in `setup._setup` through one local helper `_yes`
   (scanner, measure once, status line, watch); measuring reuses `calibrate.classify`.
3. One interview row (`reviewers`), the `posture` question skipped under `--shadow`, and
   `owner.name` added to `setup.identity`.
4. The end of setup: `doctor.diagnose()` plus one pure function `ending(...)` that prints
   `Optional:` and `Ready:`/`Next:` and returns the exit code.
5. Two fix texts: doctor's empty `fast_checks` row, and `config check`'s host-protection
   rows (settings URL, one `gh api` command when nothing exists to overwrite).

No new module, no new config key, no new state key or event kind, no new guard.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. The core never imports `subprocess`: the
default-branch read goes through the vcs adapter (`adapters/vcs/git.py`, closed allowlist),
the test run through the checks port (`adapters/checks/local.py`, already used by
`config promote --measure`), the watch install through `commands/watch.service` (already
used by `doctor --fix`). Every config value setup proposes still lands only through the one
owner digest (`config.offer`).

## Constitution Check

- I stdlib: yes.
- II three-state exits: the new vcs read fails closed through `_operation` (exit 2 with the
  reason); setup's exit is 0 only when nothing required is open, 2 when a required item is
  unmeasured.
- III one behaviour, one function: `vcs.default_branch` (local answer), `setup.ending`
  (readiness), `init.status_line` (the settings write), `interview.QUESTIONS` (the
  question). Doctor stays the only diagnosis; setup reads its rows.
- IV test first: tasks.md orders each test before its code.
- V ponytail: reuse `calibrate.classify`, `calibrate.UNMEASURED`, `setup.identity`,
  `interview` effects, `doctor.diagnose`/`CODES`, `commands/watch.service`,
  `init`'s settings validation, `config.missing`, the existing mcp owed lines.
- VII security: running repository commands (the test run) and installing a persistent unit
  (the watch) each need an explicit answer; a closed stdin answers no. Writing the status
  line keeps `init`'s refusals (symlink, not an object, home directory). The printed
  `gh api` command is for the owner's own terminal; the guards still refuse branch
  protection changes from agents (`guards/pr.py`).

## Changes, file by file

### `adapters/vcs/git.py`

- `_run`: widen the existing case to `('symbolic-ref', '--quiet', '--short', 'HEAD' |
  'refs/remotes/origin/HEAD')`.
- New `@_operation def default_branch(repo, root=None)`:
  `remote = _run(repo, 'symbolic-ref', '--quiet', '--short', 'refs/remotes/origin/HEAD',
  missing=True).strip()`; when nonblank, `name, source = remote.removeprefix('origin/'),
  'origin/HEAD'`; else `name, source = _run(repo, 'symbolic-ref', '--quiet', '--short',
  'HEAD').strip(), 'the checked-out branch'`. Raise `ValueError('invalid default branch')`
  unless `name` fully matches the pattern `branch` already uses
  (`[A-Za-z0-9][A-Za-z0-9._/-]*`). Return `{'branch': name, 'source': source}`.

### `cli/wuwei/registry.py`

- `PARAMETERS['vcs']`: add `'default_branch': ('repo',)`.

### `cli/wuwei/commands/setup.py`

- New `_yes(question, default)`: `input(f"{question} [{'Y/n' if default else 'y/N'}] ")`,
  stripped and lowercased; `EOFError` returns `False`; an empty reply returns `default`;
  otherwise `reply in ('y', 'yes')`. ponytail: local prompt until #354's shared y/N lands.
- `discover` (`:147-171`), per candidate:
  - `url = remote.data['url'] if remote.exit == 0 else None`; `found = GITHUB.fullmatch(url)
    if url else None`.
  - Name: from `found` as today; when `url == ''` (no `origin`) and `login`,
    `f'{login}/{candidate.name}'`; `references.repository` validates both (invalid stays
    `None`).
  - Branch: when `found and auth == 0`, `hub.default_branch(name)` as today, keeping its
    reason; when `found` and not signed in, the reason is `gh is not signed in`; when no
    `origin`, `no GitHub remote`. When `name` is set and `branch` is not, and the candidate
    has a GitHub `origin` or none, `local = vcs.default_branch(resolved)`; on exit 0 take
    `local.data['branch']` and append one line:
    - GitHub origin: `f"{path}: default branch {branch} (from {source}; gh could not read
      it: {reason})"`;
    - no origin: `f"{path}: no GitHub remote; proposed as {name}, default branch {branch}
      (from {source})"`.
  - Everything after (`owed` when name or branch is still missing, identity, `repos`) is
    unchanged; another host's `origin` is still owed and never guessed.
- `identity(config, login, results)` (`:175-195`): when `config['owner']['name']` is blank
  and some `repo['identity']['name']` is nonblank, prepend `(('owner',), 'name', <first such
  name>)`.
- `_setup` (`:217-291`):
  - `init.run(SimpleNamespace(..., status_line=False))` at `:228`.
  - Scanner (`:245-246`): append the setting only when `_yes('ZIRAN is installed. Turn on
    its security scans (adapters.scanner = "ziran")?', False)`.
  - Interview (`:263`): `interview.ask([row['id'] for row in interview.QUESTIONS if not
    (args.shadow and row['id'] == 'posture')], names)`.
  - After `results = calibrate.survey(...)` (`:264`): collect `(result, command)` where
    `result['checks'][command][1] == calibrate.UNMEASURED`. When any: print `Test runner
    found: <repo>: <command>[; ...]`, and if `_yes('Run your tests once now to see if they
    are fast enough for every push?', True)`, set for each result `result['checks'] =
    calibrate.classify(result['checkout'], result['facts']['fast_checks'],
    registry.load('checks', staged_cfg), staged_cfg['calibrate']['fast_check_seconds'],
    root)`. The proposal, digest, snapshot and `calibration.md` then carry the measured
    notes unchanged.
  - Delete `check = config.run(SimpleNamespace())` (`:274`); doctor runs `config check`.
    Keep `gate = mcp.check(root)` and its stderr line.
  - After the digest path (applied or `Nothing to propose`; a declined digest still returns
    1 before this, as today):
    - Status line: `try: _, data = init.settings(root)`; when `'statusLine' not in data`
      and `_yes('Show the WUWEI status line in Claude Code for this project?', True)`,
      `init.status_line(root)` and print `Status line: added to .claude/settings.json`.
      On `ValueError`/`OSError` print `wuwei setup: status line not written: <exc>` to
      stderr and add `put the statusLine from bin/wuwei init into .claude/settings.json` to
      the optional list.
    - Watch: from `wuwei.commands import watch as watch_command`; when
      `watch_command.service_platform() in ('darwin', 'linux')`, `not
      workspace.watch_unit(root, watch_command.service_platform())[1].exists()` and
      `_yes('Install the watch service, which supervises the day and your pull requests in
      the background?', False)`: `watch_command.service(SimpleNamespace(watch_action=
      'install', once=False, dry_run=False), 'watch', None)`; on `ValueError`/`OSError`
      print `wuwei setup: watch install: <exc>` to stderr and continue.
    - `rows = doctor.diagnose()` (import `wuwei.commands.doctor` lazily).
    - `required` = `[f'set {name} in .wuwei/env' for name in config.missing(final)]` + the
      existing mcp lines (`:285-289`, unchanged text); `optional` = `found['owed']` + the
      `owner.name` line when still blank (`:280-281` text) + `bin/wuwei promote` when
      proposals exist (`:282-284`) + the status-line fallback when it applies.
    - `text, code = ending(rows, required, optional, gate.exit)`; print `text`; return
      `code`.
  - The no-repository early return (`:239-242`): `text, _ = ending([], owed[:1],
    owed[1:], 0)` with `owed = found['owed'] or [_owed(None, '<path>', None)]`; print it;
    return `FINDINGS`.
- New pure `ending(rows, required, optional, gate=0)` returning `(text, code)`:
  - `blocking = [row for row in rows if row['section'] in ('install', 'workspace') and
    row['status'] in ('fail', 'unmeasured')]`;
  - `steps = required + [row['fix'] for row in blocking]`;
  - `others = sum(row['status'] != 'ok' for row in rows if row not in blocking and
    row['name'] != 'mcp gate')` (setup already counts the MCP gate);
  - `parts = optional + ([f'{others} more in bin/wuwei doctor'] if others else [])`;
  - text: `'Optional: ' + '; '.join(parts) + '\n'` when `parts`, then `f'Next: {steps[0]}'`
    when `steps`, else `'Ready: run /wuwei:wuwei-plan'`;
  - code: `max([FINDINGS if steps else CLEAN, gate, *(doctor.CODES[row['status']] for row
    in blocking)])`.

### `cli/wuwei/commands/init.py`

- New `settings(root)` returning `(path, data)`: the existing checks at `:66-73` moved
  verbatim (symlink, home directory, object and `permissions` object) for
  `root / '.claude/settings.json'`; `{}` when absent. `run` uses it
  (`settings, data = settings(destination.parent)`, renaming the local to keep the diff
  small).
- New `status_line(root)`: `path, data = settings(root)`; `data['statusLine'] =
  _status_command(<plugin>/bin/wuwei)`; `path.parent.mkdir(exist_ok=True)`;
  `workspace.atomic_write(path, json.dumps(data, indent=2) + '\n')`.
- `_status_command(executable)` returns the dict `_status_line` prints today; `_status_line`
  prints `json.dumps(_status_command(executable))` and its hint line unchanged.
- `run`: call `_status_line(executable)` only when `getattr(args, 'status_line', True)`.
  Plain `bin/wuwei init` and `init --upgrade` output is unchanged (pinned by
  `tests/test_signal_status.py:182` and `tests/test_records_after_dryrun4.py:187`).

### `cli/wuwei/interview.py`

- New `_login(text)`: strip; `ValueError("expected a code-host login such as pat-dev")`
  unless it fully matches `[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})`; return
  `{'shepherd.lead_login': text, 'shepherd.min_reviewers': 1}`.
- One row appended to `QUESTIONS` after `review_bot`: id `reviewers`, scope `workspace`,
  header `Reviewers`, question `Who reviews your pull requests?`, choices
  `('Owner only', 'No second reviewer: you merge your own pull requests.',
  {'shepherd.min_reviewers': 0})` and `('Code authors', 'Whoever touched the changed code
  is asked; at least one review before merge.', {'shepherd.min_reviewers': 1})`, free
  `(_login, "a teammate's code-host login, for example pat-dev")`.
- Nothing else: `settings`, `describe`, `ask`, `parse`, `widgets`, `record` pick the row up.

### `cli/wuwei/commands/doctor.py`

- `_workspace` `fast_checks` row (`:280-284`): fix becomes
  `f"bin/wuwei config promote --measure (times the test runner once and proposes it when it
  is fast), or bin/wuwei config set repos.{index}.fast_checks '[\"<command>\"]'"`; keep
  `apply='config-promote'` (pinned by `test_fix_allow_list_is_pinned` and
  `test_workspace_repository_rows`).

### `cli/wuwei/commands/config.py`

- `_protection` (`:234-269`): after printing the rows, when any row is missing print
  `f"{label}: fix in https://github.com/{repo['name']}/settings/branches"`, and when
  `not data['classic']` also `f'{label}: or run in your own terminal: ' + shlex.join(argv)`
  with `argv = ['gh', 'api', '-X', 'PUT', f"repos/{repo['name']}/branches/{quote(branch,
  safe='')}/protection", '-F', 'enforce_admins=false', '-F', 'restrictions=null', '-F',
  'allow_force_pushes=false', '-F', 'allow_deletions=false', '-F',
  'required_pull_request_reviews=null' if solo else
  'required_pull_request_reviews[required_approving_review_count]=1', *checks]` where
  `checks` is `['-F', 'required_status_checks[strict]=false', *('-f',
  f'required_status_checks[contexts][]={name}') for each name in
  repo['review_required_checks']]` or `['-F', 'required_status_checks=null']` when empty.
  The return value is unchanged (still FINDINGS on a missing row).

### Docs

- `docs/site/daily.md` section 2: the git fallback for the default branch and the
  `<login>/<directory>` name; the y/N questions (scanner, test run, status line, watch);
  the reviewers question replaces the sentence telling a solo owner to run
  `config set shepherd.min_reviewers 0`; setup ends with `Ready:` or one `Next:` instead of
  "what is still owed".
- `docs/site/configuration.md` owner interview table: one `reviewers` row.

## Test fixtures that must change with the code

- `tests/test_adapters.py` `CALLS`: add `('vcs', 'default_branch', ('repo',), True)`.
- `tests/fakes/vcs.py`: add `default_branch` only if a test that uses the fake needs it.
- `tests/test_setup.py` `terminal` fixture: also stub `builtins.input` with scripted replies
  (a dict from a prompt keyword to a reply, default `''`, so every question takes its
  default), and stub `wuwei.commands.doctor.diagnose` with an all-ok list (settable per
  test), so existing tests stay fast and exit 0.
- `tests/test_setup.py` existing tests whose expectations change (update, never weaken):
  `test_discovery_without_host_auth_owes_every_repository` (now staged from git, `gh is not
  signed in` lines, `host.calls == []`), `test_identity_settings` (adds `owner.name`),
  `test_one_command_three_repositories` (the `Still owed`/`Next: /wuwei plan` asserts become
  the `Optional:` and `Ready:` lines), `test_ziran_on_path_is_proposed` (answers `y`),
  `test_empty_directory_owes_add_repo` (`Next: bin/wuwei config add-repo`),
  `test_pending_mcp_decision_is_owed_by_command` (`Next: bin/wuwei mcp decide D-2 proceed`),
  `test_setup_ends_with_the_restart_line` (unchanged: the RESTART line stays last).
- `tests/test_interview.py` `test_question_table_fits_widgets_and_every_choice_validates`:
  the id list gains `reviewers`.
- `tests/test_doctor.py` `test_workspace_repository_rows`: the `fast_checks` fix assertion
  becomes `startswith('bin/wuwei config promote --measure')` and contains
  `repos.0.fast_checks`.

## Must not change

- The one digest (`config.offer`), its decline path and `nothing written` guarantee; the
  interview mechanics and existing question ids and labels; `calibrate.classify`,
  `survey`, `proposal`; `doctor.diagnose` rows other than the `fast_checks` fix, `FIXES`,
  `render`, `outcome`; `config check` exit codes; plain `init` and `init --upgrade` output;
  `commands/watch.service`; guards, hooks, state keys and event kinds.
- A repository whose `origin` is another code host is still owed, never guessed.

## Deferred

- `build next`'s empty fast checks reason and doctor `fix:` lines spelled `wuwei` (#362).
- The publish guard's "no setting lowers it" text and reviewer selection without config
  (#369).
- `calibrate --questions` returning answered ids on the first day (#365).
- Proposing a slow test runner as a fast check anyway (the sweep's "if still unmeasured"
  default): not in the acceptance; doctor names the `config set` form instead.
