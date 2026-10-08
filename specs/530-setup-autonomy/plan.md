# Implementation Plan: One setup question for autonomy, the interview on upgrade, and the harness allowlist card

**Branch**: `530-setup-autonomy` | **Spec**: `spec.md`

## Summary

Three small changes at the shared spots, no new module, no new config key, no new state key or
event kind:

1. The interview table (`cli/wuwei/interview.py`) gains the `autonomy` row first and the
   `allowlist` row last and loses `posture`, `tier` and `learn`. The existing #529 card path
   (`calibrate --answer`, `sessions.card_answered`, `setup.card_write`) writes the five keys of
   the autonomy answer at once; nothing new on that path.
2. `merge.default_tier` gains `today`, read in the one shared grant lookup `grants.active`, so
   `grants.gate` (deploy guard and `merge.by_grant`) and `grants.plan` stop asking a merge card
   on a configured repository below strict.
3. `interview.unanswered` is the one count, printed by `init --upgrade` and doctor; `next.py`
   drops the day-one condition. `init.allow_rules` and `init.allow` write the allowlist the
   `allowlist` answer confirms.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only; in-process tests. Fixtures and helpers to reuse
(import them, do not copy them): `tests/test_card_confirms.py` (`ws`, `interview_card`,
`answer`, `no_terminal`, `strict`, `events`, `config`), `tests/test_interview.py` (`ONE`,
`PLANE`, `root`, `offline`), `tests/test_grants.py` (`CONFIG`, `root`, `run`),
`tests/test_next.py` (`calibrated`, `planned`, `day`, `row`, `ran`, `seen`),
`tests/test_doctor.py` (its workspace fixture and row lookup), `tests/test_setup.py`
(`project`, `host`, `terminal`, `run_setup`, `Confirm`), `tests/test_invariants.py`
(`INVARIANTS`, `READS`, `default_has_no_grant`). Neutral names only: `example/project`,
`other/elsewhere`.

## Constitution Check

- Stdlib only; exits 0/1/2 unchanged. Pass.
- One behaviour, one function: the merge default lives only in `grants.active`; the
  unanswered count only in `interview.unanswered`; the rules only in `init.allow_rules`. Pass.
- Records floor: config is written only through `setup.card_write` (card answer) or the host
  terminal; `settings.local.json` only after the card answer or a terminal answer. No seat or
  default creates a grant: the shipped `merge.default_tier` stays `""` (I5). Pass.
- No new refusal in any posture (#530). Pass.
- New rules get I18 in design 9.2 and `tests/test_invariants.py`. Pass.
- Test first: each behaviour below has its test task before its implementation task.

## Changes

### `cli/wuwei/workspace.py`

`SCHEMA['merge']['default_tier']`: add `"today"` to the allowed values (line 81) and to its
comment.

### `cli/wuwei/grants.py`

- `DEFAULT = 'merge.default_tier'` beside `ACTIONS`.
- `active(config, data, name, found, standing=True)`: after the recorded `hits`, when there is
  no hit, return `('today', DEFAULT)` if `name == 'merge'`, `config['merge']['default_tier'] ==
  'today'`, the posture is not strict, `not data.get('close_requested')`, no row in
  `data['grants']` with `(action, target) == (name, found)` is answered `keep`, and the
  repository of `found` (`repo:<r>` or `pr:<r>#<n>`) is a configured `[[repos]]` name. One
  `re.fullmatch(rf'(?:repo|pr):({REPO})(?:#[0-9]+)?', found)` gives the name. Nothing else
  changes in `gate` (its `used` event records `decision: merge.default_tier`, `scope: today`)
  or in `merge.by_grant` (`merge_tier` returns `today`, which is not `owner_only`).
- `plan(root, config, candidates)`: before looking for a reusable planned card, `hit =
  active(config, state.read_state(root), name, repo_target)`; when `hit and hit[1] ==
  DEFAULT`, append `(name, repo_target, DEFAULT)` and `continue`. `plan.md` then prints
  `Owner-only: merge <target> (merge.default_tier)` through the existing line in
  `cli/wuwei/plan.py`.

### `cli/wuwei/interview.py`

- New first row:

  ```python
  {'id': 'autonomy', 'scope': 'workspace', 'header': 'Autonomy',
   'question': 'How much should WUWEI run without asking you?',
   'choices': (
       ('Autonomous', '<plain description, recommended> (observe posture, autonomy.mode)', AUTONOMOUS),
       ('Supervised', '<plain description> (guarded posture, autonomy.mode)', SUPERVISED)),
   'free': None}
  ```

  with the effects of FR-001. Descriptions start with plain words: the leading text before
  `(` must not use a glossary word (`tests/test_docs.py::test_interview_options_lead_with_plain_words`),
  and labels never use I or me. Autonomous: guards warn, messages no rule holds go out, merges
  on your own repositories run once checks and reviews pass, connectors are learned without
  asking, decisions WUWEI can take are taken and reported; recommended. Supervised: each
  owner-only action, held message and decision beyond the item asks you on a card.
- Remove the `posture`, `tier` and `learn` rows (`:222-232`, `:335-348`).
- New last row `allowlist`, header `Permissions`, question `Let Claude Code run the WUWEI
  commands and the adapter reads without a permission prompt? (settings.local.json)`, choices
  `Allow` (`{'allowlist': True}`; description names the rule classes of FR-011, says it never
  allows a push, merge, deploy or release, and ends with the one line: production reads of
  your projects stay your decision, and Claude Code keeps asking for them) and `Not now`
  (`{}`; Claude Code keeps asking for each command).
- `_setting(name)`: also exclude `'allowlist'`. `describe`: for `allowlist` print
  `.claude/settings.local.json allow rules`.
- `settings`: delete the two `shadow_since` lines (`:409-410`).
- `card_for`: skip `row['id'] == 'autonomy'`.
- `HOW = 'bin/wuwei setup, or the planner asks them on cards'` and
  `unanswered(root, repos)`: `done = _recorded(root)`; return `[(row, repo) for row in
  QUESTIONS for repo in (repos if row['scope'] == 'repo' else [None]) if (row['id'], repo) not
  in done]`. `widgets(root, repos, ids=())`: with ids, `_selected(ids, repos)` as today;
  without, `unanswered(root, repos)`.

### `cli/wuwei/commands/calibrate.py` (`_interview`)

In the per-answer loop: when `interview.effects(qid, answer).get('allowlist')`, confirmed is
`args.interview is not None or sessions.card_answered(<same card text>, answer)`; if confirmed,
`init.allow(root)` and print `Wrote .claude/settings.local.json: <rule>` per added rule (or `No
settings.local.json changes`); else print the `Next: run bin/wuwei calibrate --interview
allowlist in a host terminal.` line. An `allowlist` answer never sets `pending` (it has no
config key); `Not now` does nothing. An OSError or ValueError from `init.allow` exits 2 with
the reason, as other errors there do.

### `cli/wuwei/commands/init.py`

- `settings(root, name='settings.json')`: the same checks for `.claude/<name>`.
- `ALLOW = {('vcs', 'git'): (...), ('code_host', 'github'): (...)}` with the patterns listed
  under Assumptions in `spec.md`, written as `git status*`, `git diff*`, `git log*`,
  `git show*`, `git rev-parse*`, `git fetch` (exact), `git add *`, `git commit *`,
  `git worktree list*`, `gh pr view*`, `gh pr list*`, `gh pr checks*`, `gh pr diff*`,
  `gh pr status*`, `gh issue view*`, `gh issue list*`, `gh run view*`, `gh run list*`.
  No `gh auth status` rule: `--show-token` would print the token unprompted.
- `allow_rules(config, executable)`: `[f'Bash({executable} *)', *(f'Bash({p})' for (key,
  value), patterns in ALLOW.items() if config['adapters'][key] == value for p in patterns)]`.
- `allow(root)`: read `.wuwei/executable` (refuse a symlink like `upgrade` does), load the
  config, `path, data = settings(root, 'settings.local.json')`, validate
  `permissions.allow` is a list of strings (same message shape as `deny` at `:69-70`), append
  the missing rules in order, `atomic_write`, return the added rules.
- `upgrade`: after the `Undo not rehearsed` line (not counted as a change), `from wuwei import
  interview`; `n = len(interview.unanswered(root, [r['name'] for r in config['repos']]))`
  from the migrated config; print `setup: {n} questions unanswered: {interview.HOW}` when n >
  0; on `ValueError` print `setup: unanswered questions unmeasured: <reason>`. It is a read,
  so it prints under `--dry-run` too, like the undo line; the two exact-output asserts in
  `tests/test_workspace.py` (`test_upgrade_retires_shadow_mode`,
  `test_upgrade_removes_enforce_mode`) also filter lines starting `setup:`.

### `cli/wuwei/commands/doctor.py` (`_calibration`)

Replace the `interview` row body: `n = len(interview.unanswered(root, names))`; `ok` with `all
setup questions answered` when 0, else `warn` with `f'{n} questions unanswered'` and fix
`interview.HOW`. The `unmeasured` branch stays. `interview.load` is no longer called here.

### `cli/wuwei/commands/next.py` (`step`)

Delete `earlier` (`:202`); the row is due while `('calibrate', '') not in returned`; why reads
`Ask the setup questions not answered yet; the list is empty when all are.` `THEN['calibrate']`
says to show the owner the printed `Next:` line for a host terminal (it names `config promote`
for config keys and `calibrate --interview allowlist` for the allowlist), not only `config
promote`. No new import.

### `cli/wuwei/commands/setup.py` (`_setup`)

- Replace `'posture'` with `'autonomy'` at `:471` and `picked['posture'] = 'Observe'` with
  `picked['autonomy'] = 'Autonomous'` at `:476` (comment: the flag answered it).
- After the config offer succeeds: when `picked.get('allowlist')` effects allow, call
  `init.allow(root)` and print the rules written; an error prints `wuwei setup: allowlist not
  written: <reason>; run bin/wuwei calibrate --interview allowlist` and joins `optional`, like
  the status line block.

### Docs and spec text

- `docs/specs/2026-09-24-wuwei-design.md`: only row I18 in 9.2 and the I5 note `the shipped
  merge.default_tier is empty; today is written only by the owner's autonomy answer` (the
  constitution's Workflow rule requires the invariant row; the design spec is otherwise the
  owner's). If another item took I18 on the base, use the next free id.
- `docs/site/configuration.md`: the `merge.default_tier` row gains `today`; line 3 names the
  autonomy card instead of `outbound.default_tier` and `outbound.learn`; the calibration
  paragraph (`:379`) says what the autonomy answer writes (the five keys; strict only by hand),
  that the planner asks unanswered questions at every plan and init --upgrade and doctor count
  them, and what the `allowlist` answer writes (never a push, merge, deploy or release;
  production reads stay the owner's).
- `docs/site/reference.md`, `docs/site/agent.md`, skills and charters: no change unless a
  touched docs test names the removed rows.

## What must not change

- The #529 card confirmation (`sessions.card_answered`, never under strict) and
  `setup.card_write`; the records floor; every refusal and its text.
- `merge.check` preconditions (`granted=True` skips only eligibility and pacing;
  `merge_deploys` must be `false`), the `merge_tier` meaning of `""`, `ask`, `owner_only`.
- Grant behaviour for `deploy`, `release`, `publish`, `evidence`, for repositories outside
  `[[repos]]` and under strict; standing grants and the #556 novelty rule.
- `next.py`, `hook.py` and every guard never import `interview` or `calibrate`
  (`tests/test_hooks.py::test_calibrate_is_off_every_hook_path`).
- `.claude/settings.json` (deny rules, status line) is not touched by the allowlist.
- The `cap` and `seats` rows.

## Test files to run

`tests/test_interview.py tests/test_card_confirms.py tests/test_grants.py tests/test_merge.py
tests/test_next.py tests/test_doctor.py tests/test_setup.py tests/test_workspace.py
tests/test_invariants.py tests/test_docs.py tests/test_hooks.py tests/test_plan.py` (those that
exist on the base; `ls tests` first). Never the full suite.
