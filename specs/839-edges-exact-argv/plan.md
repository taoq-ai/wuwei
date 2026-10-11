# Implementation Plan: exact argv only on the irreversible edges; one edges module; integrity warns at session start

**Branch**: `b6-edges` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at d60253b8 (main plus part 15). Part 16 (#838) lands first and changes
`guards/outward.py`, `guards/__init__.py` (`FLOOR`), `security.py` callers and several tests
named below: locate code by function name in those files.

## Summary

One guard module, `guards/edges.py`, refuses the irreversible edges by exact argv per command
segment: host merge, approve, admin (with branch protection), force push, deploy, outward send,
and a bare `gh pr create` for a recorded item. `guards/deploy.py` becomes `edges.py`;
`guards/pr.py` goes; `guards/commit_push.py` leaves `guards/` as a library. About 450 lines of
`shell.py` (the opaque-command machinery) go, with the hook's opaque warning and `resolved:`
line. An unreadable call is logged as `UNPARSED`, never refused. The PreToolUse integrity guard
goes; integrity is a SessionStart warning.

## Technical Context

Stdlib-only Python 3.11+ (`shlex`, `re`, `fnmatch`), pytest dev-only. Net deletion: about 2,000
lines of code and 2,500 lines of tests go; `edges.py` is about 350 lines (most of it the deploy
tables it already has). No config key changes. Run only the touched test files; CI runs the
suite.

## Constitution Check

- I: nothing added.
- II: an edge guard that cannot read its config or state exits 2 and blocks (fail closed). The
  one exception, an unreadable command, is logged; T019 amends II to say so.
- III: one edges module, one segment splitter (`edges.segments`), one gate check
  (`merge.gate_check`).
- IV: red tests first: `tests/test_edges.py` per edge, the integrity warning, the unparsed log.
- V: deletion of the parser defences; the code host and credential layout are the anchors (9.1).
- VII: the floor is unchanged: merge, approve, admin, branch protection, deploy and outward send
  block in both settings; canary egress and markers stay records floor.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| `shell.py` opaque machinery (`mentions`, `script_path`, `script_text`, `is_opaque`, `classify`, `unread`, `unreadable`, `constructed`), the hook's `opaque: <what>` warning, the `resolved:` line, `UNKNOWN_GIT`, `deploy.floor_named` | (a) makes the model phrase commands for a parser | nowhere; exact argv on the edges, the code host and credentials beyond them (9.1) |
| `commit_push.check`: author and committer identity at commit and push | (a) here; a duplicate of the native hooks | the native pre-commit and pre-push hooks (`wuwei git-hook`, unchanged); `worktree add` writes the identity |
| Force push refusal | (b) edge | `edges.check_bash` |
| Push to the default branch | (b) a merge outside policy | the native pre-push hook (`commit_push.push_check`, unchanged) and the protected base branch (9.1) |
| Push before fresh fast checks; push after a commit in the same call | (b) builder hands off unchecked | `build.next_action` and `dispatch.next_step` (pass plan table); the native pre-push hook warns |
| `--no-verify`, `core.hooksPath` config, hook pointer removal | (a) guards guarding other local checks, none a boundary (9.1) | nowhere |
| `GIT_*` and `GH_*` override refusals, unsupported options, compound-command refusals | (a) parser defence | nowhere |
| `gh` alias and extension refusal, unknown `gh` command, GraphQL refusal | (a) parser defence | nowhere; ceiling held by the code host |
| `gh pr create` reviewer rule (`NO_REVIEWER`) | (b) for WUWEI's PRs only | `bin/wuwei pr raise` (`shepherd.min_reviewers`, `REVIEWER_WAYS_OUT`) |
| `gh pr create` gate check at the head | (b) gate on the wrong head | `bin/wuwei pr raise --item` refuses unless every gate passed at the head; a bare create for a recorded item is refused (kept) |
| `gh pr create` `--repo`/`--head` pairing and unrecorded head refusals, the opaque create | (a) parser shape | nowhere |
| Bare `gh pr create` for a recorded item | (b) PR raised outside WUWEI | `edges.check_bash` |
| `merge.check` inside the hook on `gh pr merge` | (b) merge outside policy | the hook refuses every session merge naming `bin/wuwei merge`, which runs `merge.check` |
| `gh pr merge --admin`, approval, branch protection | (b) edges | `edges.check_bash` |
| Shepherd seat naming "merge" or `WUWEI_SEAT_ROLE` | (a) covered by the merge edge | nowhere |
| `deploy.unknown` refusals (unresolved target, unsupported host, unknown command, git override) | (a) parser defence | nowhere |
| `deploy.merge` code-host lookup of a merge's base | (b) merge into an environment or a `merge_deploys` repo | `merge.check` behind `bin/wuwei merge` |
| Deploy argv table, `deploy.deny`, workflows, releases, tags, environment pushes, deployment API | (b) edges | `edges.check_deploy` |
| `gh` body canary and marker scan (`security.gh_outbound` from `pr.action`) | (b) records floor | `edges.check_bash` |
| PreToolUse integrity gate | kept as a warning (owner, positioning) | SessionStart guard, unchanged |
| `protect_state.check_bash` refusal of an unparsed call a write may target | (b) records, but a parse refusal the issue rules out | logged as `UNPARSED`; parsed writes stay refused; state files at mode 0444; part 23 |
| Verdict guard `classify(...).readonly` fast path | not a check (a shortcut) | `normalize` plus `reads` |

Found (b) units that move rather than go: the `gh` body scan, the gate check at raise, the
reviewer rule, `merge.check` for environment merges, default-branch push and fast checks before
push. None is lost.

## Design

### `cli/wuwei/guards/edges.py` (from `git mv guards/deploy.py guards/edges.py`)

Keep from `deploy.py`: `VERBS`, `CLOUD_VERBS`, `PERMISSIONS_DENY`, `deny`, `environment`,
`workflow`, `api`, `gh`, `command_result` (deploy only). Delete `PROGRAMS`, `DEPLOY_ACTIONS`,
`GH_FLOOR`, `_FORCE`, `unknown`, `floor_named`, `merge`, the `git` override and unknown-verb
branches, the `pr merge` branch of `gh`, and `check`. Where `unknown(...)` raised, the call is
not an edge: return `(0, '')`. `api` drops its `merges` branch (the merge edge owns it).

New:

```python
SHELLS = ('sh', 'bash', 'zsh', 'dash', 'ksh')
DEPTH = 4
# Each reason starts with a guards.MERGE prefix, so the floor reads it.
MERGE_REASON = ('merge policy: a PR merges only through bin/wuwei merge {pr}; it checks the policy at '
         'the head and asks the Owner step card when the owner decides')
ADMIN = 'admin merge is refused; run bin/wuwei merge {pr}, which never uses --admin'
APPROVE = ("PR approval is the owner's; post a comment review (gh pr review --comment), and "
           'merge through bin/wuwei merge {pr}')
PROTECTION = 'branch protection changes are refused; the protected base branch is the owner\'s'
FORCE = ('force-push is refused; commit the change on top and run '
         'git push origin HEAD:refs/heads/{branch}')
```

- `segments(text, cwd, depth=0)`: returns `[(argv, env, cwd)]`. Here-doc bodies are cut first
  (a `<<`, `<<-` delimiter, quoted or not, up to the line equal to it; unterminated raises
  `ValueError`). Then `shlex.shlex(text, posix=True, punctuation_chars=';&|()<>\n')` with
  `whitespace_split = True` and `'\n'` taken out of `whitespace`; every punctuation token ends a
  segment. Per segment: leading `NAME=value` words go to `env`; `env` with `-i`, `-u NAME`,
  `--unset=NAME`, `--` and assignments is unwrapped; a program in `SHELLS` with a flag cluster
  holding `c` recurses on the script word (`depth + 1`; past `DEPTH` raises `ValueError`); a
  segment `cd <literal dir>` moves `cwd` for later segments. `shlex` `ValueError` propagates.
  `# ponytail: backticks, quoted $( ) and names built at run time are not split; the code host
  and the credential layout hold them (spec 9.1); split them here if a seat is seen using them.`
- `_git(args)`: skips `-C v`, `-c v`, `--git-dir[=v]`, `--work-tree[=v]`, `--namespace[=v]`,
  `--no-pager`; returns `(verb, rest)`.
- `_forced(rest)`: any word `--force*` or `--mirror`, a short cluster `-[a-zA-Z]*f[a-zA-Z]*`,
  or a non-option operand starting with `+`.
- `_recorded(root, config, *, path=None, repo=None, branch=None)`: moved verbatim from
  `pr.py:194-208`.
- `check_bash(payload)`: `root = workspace.guard_scope(payload)`; none: `(0, '')`. No
  `(?<![\w.-])(git|gh)(?![\w.-])` word in the raw text: `(0, '')`. `segments` raises:
  `(2, shell.UNPARSED)`. Per segment, by basename:
  - `git`: verb `push` and `_forced(rest)`: `(1, FORCE)` with the item's branch when `cwd` is an
    item worktree (`commit_push._item`), else `<branch>`;
  - `gh`: skip `-R`/`--repo` (with value) before the family; run `security.gh_outbound` exactly
    as `pr.action` computes `text_write` (`pr.py:345-350`) and `pr.api_check` does for `api`
    (`pr.py:277-284`), returning its refusal; then
    - `pr merge`: `--admin` in args: `ADMIN`, else `MERGE_REASON`, with the first operand as `{pr}`
      (else `<pr>`);
    - `pr review` with `--approve` or `-a`: `APPROVE`;
    - `pr create`: the item from `--head` with `--repo` (`_recorded(..., repo=, branch=)`) or
      from `cwd` (`_recorded(..., path=)`); an item whose state row has no `pr`:
      `(1, RAISE + <the hint text of pr.py:245-247>)`;
    - `api`: the endpoint normalisation of `pr.api_check:270-279` (`shell.operands` with its
      value and flag sets); for a write: `repos/<o>/<r>/pulls/<n>/merge` or
      `repos/<o>/<r>/merges`: `MERGE_REASON`; branch protection or rulesets (`pr.py:289-291`):
      `PROTECTION`; `repos/<o>/<r>/pulls/<n>/reviews` with a field `event=APPROVE`: `APPROVE`.
  - errors reading config or state (`OSError`, `ValueError`, `KeyError`, `TypeError`):
    `(2, f'edges: could not run: {exc}')`.
- `check_deploy(payload)`: the scope, config and relevance check of `deploy.check:314-332`
  (relevance: a word from `VERBS`, `vercel`, `vc`, `gcloud`, `aws`, `az`, `git`, `gh` or a
  `deploy.deny` first word); `segments` raises: `(2, shell.UNPARSED)`; per segment
  `command_result(argv, env, config, root)`; a `(1, (rule, repo))` asks
  `sessions.needs_owner` exactly as `deploy.check:350-356` does and returns `publish: <card>`.
- `check_send(payload)`: part 16's `guards/outward.check_send`, moved with the branches only it
  takes (the owner disposition marker branch, the Bash canary branch, and the MCP local,
  allowed and refused answers). It imports `resolve`, `tool_kind`, `NATIVE_TOOLS` and `DM_TOOL`
  from `guards/outward.py`.
- `GUARDS = [Guard('PreToolUse', 'Bash', check_bash), Guard('PreToolUse', 'Bash', check_deploy),
  Guard('PreToolUse', None, check_send)]`.

The force-push branch name helper and `git` push parsing are shared by `check_bash` and the
tag and environment rows of `command_result.git` (`_git`).

Imports: `check_send` makes `edges` load on every PreToolUse, as `outward` does today. Keep a
Write, Read or MCP call off the Bash path: import `urllib.parse`, `sessions`, `state`,
`registry` and `merge` inside the functions that use them (the #240 and #346 pattern), not at
module level.

### `cli/wuwei/guards/outward.py`

`check_send` and the `_check` branches only it takes move to `edges.py`. The module keeps
`resolve`, `tool_kind`, the vocabulary constants and `check_lint` (profile relaxable, in
`LOG_ONLY`).

### `cli/wuwei/guards/__init__.py`

- `MODULES`: delete `commit_push`, `deploy`, `pr`; add `'edges': {'PreToolUse': None}`;
  `'integrity': {'SessionStart': None}`.
- `FLOOR`: delete `'deploy'`, `'pr'` and part 16's `'outward.check_send'`; add
  `'edges.check_deploy'`, `'edges.check_send'`. The comment names the edges.
- `MERGE` (58-59): drop `'a shepherd seat never merges'`; keep `'merge policy'`,
  `'admin merge'`, `'PR approval'`, `'branch protection'`.
- Delete `NO_REVIEWER` (49-52) and its use in `floor` (77). Keep `REVIEWER_WAYS_OUT` (shepherd)
  and `RAISE`.

### `cli/wuwei/guards/integrity.py`

Delete `check` and its `owner_step_call` import; `GUARDS = [Guard('SessionStart', None,
session_start)]`; the docstring says it warns at session start.

### `cli/wuwei/commit_push.py` (from `git mv cli/wuwei/guards/commit_push.py`)

Delete `check`, `git_command`, `commit_options`, `push_options`, `GUARDS`, the `shell` and
`Guard` imports, and the constants only they read (`COMMIT_VERBS`, `IDENTITY_SETTINGS`,
`IDENTITY_ENV`, if no other reader). Keep `_identity`, `unset_identity`,
`configured_identity`, `identity_check`, `REPO_ENV`, `context`, `_context`, `push_check`,
`fast_evidence`, `_item`, and the `data` re-export. Docstring: the commit and push policy of
the native Git hooks, `pr act` and dispatch.

Importers (change `wuwei.guards.commit_push` to `wuwei.commit_push`):
`cli/wuwei/fast_checks.py:9`, `cli/wuwei/brief.py:477`, `cli/wuwei/dispatch.py:244`,
`cli/wuwei/pr_actions.py:290`, `cli/wuwei/workspace.py:839`, `cli/wuwei/commands/build.py:105`,
`cli/wuwei/commands/git_hook.py:9`, `cli/wuwei/commands/doctor.py:37`.

### `cli/wuwei/merge.py`

Move `GATES`, `_recorded_gates` and `gate_check` from `pr.py:18, 83-191` (imports `data` from
`registry`, `verdict`, `workspace`). Delete the lazy `from wuwei.guards.pr import gate_check`
(390). `cli/wuwei/shepherd.py:282` imports `gate_check` from `wuwei.merge`.

### `cli/wuwei/shell.py`

Delete (line ranges at d60253b8):

- `_VALUES` (98), `_names` (113-116), `mentions` (119-163);
- `script_path`, `script_text` (226-259);
- `is_opaque` (664-697); keep `_INTERPRETER` and `_SNIPPET` (646-648) for `inline_code`;
- `PUBLISHERS` (710), `UNKNOWN_GIT` (741-742), `_GIT_PUBLISH`, `_KEYWORDS`, `_WRAPPERS`,
  `_SHELLS` (743-748), `_OPERATOR`, `_SUBSTITUTED` (751-752); keep `_FIND_ACTIONS` (749);
- `Shape`, `_close`, `_tick`, `_cut`, `_simple`, `_strip` (755-912);
- `_names_publisher`, `_shell_script` (962-973);
- `classify`, `_classify` (1021-1106);
- `unread`, `constructed`, `unreadable` (1109-1173);
- the `lru_cache`, `product`, `prod` imports if unused.

Keep: `ParseError`, `NonliteralPathError`, `Command`, `operands`, `leading_variables`,
`PLUGIN_LAUNCHER`, `_launcher`, `_text`, `_cwd`, `_cd_target`, `known_cli`, `normalize` and its
helpers (`_TOKEN`, `_ASSIGNMENT`, `_VARIABLE`, `_WRITERS`, `_GUARDED`, `_QUOTED_PART`,
`_PATH_COMMANDS`, `_expands`, `_reject_mentions`, `_literal`, `_word`, `_heredoc`,
`_read_word`, `_parse`, `_unwrap`, `_variable_read`), `git_kind`, `git_runs`, the `_GIT_*` and
`_GH_READS` sets, `WORKSPACE_ROOT`, `UNPARSED`, `READ_ONLY`, `snippet_write`,
`_SNIPPET_WRITES`, `reads`, `inline_code`. `UNPARSED` keeps its text: it is a logged reason now.

Callers of every deleted function (all removed or edited by this plan):

| Function | Callers |
| --- | --- |
| `mentions` | `guards/commit_push.py:321,324`, `guards/deploy.py:64,324,329,331,336,347`, `guards/pr.py:395-407,420` (deleted); `security.py:171,176` (edited); `tests/test_shell.py` |
| `script_path` | `guards/pr.py:400` (deleted); `shell.script_text`; `tests/test_shell.py` |
| `script_text` | `commands/hook.py:302` (deleted branch); `guards/commit_push.py:320`, `guards/deploy.py:328`, `guards/pr.py:394,404` (deleted); `tests/test_shell.py` |
| `is_opaque` | `guards/commit_push.py:417`, `guards/deploy.py:347`, `guards/pr.py:456` (deleted); `shell.unreadable`; `tests/test_shell.py` |
| `classify` | `guards/protect_state.py:307,310` (edited); `guards/verdict.py:71` (edited); `shell.unread`, `shell.unreadable`; `tests/test_shell.py`, `tests/test_protect_state.py` |
| `unread` | `guards/commit_push.py:335,345,353,398`, `guards/deploy.py:338,341`, `guards/pr.py:424,447` (deleted); `tests/test_shell.py` |
| `unreadable` | `commands/hook.py:301` (deleted branch); `tests/test_shell.py` |
| `constructed` | `commands/hook.py:134-141` (deleted); `tests/test_shell.py` |
| `UNKNOWN_GIT` | `guards/deploy.py:168` (deleted); `commands/hook.py:292,311` (edited); `tests/test_hooks.py` |
| `PUBLISHERS`, `_names_publisher`, `_shell_script`, `_cut`, `_close`, `_tick`, `_simple`, `_strip`, `Shape` | `shell.classify`, `shell.constructed` only |

`cli/wuwei/obligations.py` and `cli/wuwei/watch.py` use `unreadable` as a counter key, not the
function: unchanged.

### Other shell callers

- `guards/protect_state.py:307-322` (`check_bash`, `except ParseError`): drop `classify`. A
  top-level `cd`, `pushd` or `popd` with `contain_cwd`: `(2, WORKSPACE_ROOT)`; a state mention
  (`_STATE_MENTION` or `_STATE_GLOB`) in the text: `(2, UNPARSED)`; else `(0, '')`. Drop
  `NonliteralPathError`, `_DYNAMIC`, `_WRITE_CONSTRUCT` and `_protected_name(...,
  directories=True)` if nothing else reads them.
- `guards/verdict.py:70-72`: delete the `classify(...).readonly` fast path. When every parsed
  command has no write and `shell.reads(argv)` without `inline_code`, return `CLEAN`; the
  existing `cli` branch (77-81) stays.
- `security.py:171-177` (`reads_honeytoken`): `if target.name not in script: return False`; on
  `ParseError` raise the same `ValueError` (the traces recorder records it; it never refuses).

### `cli/wuwei/commands/hook.py`

- `run`: delete the `constructed` block (133-141); the refusal sort (119) keys on the exit only
  (integrity no longer refuses in PreToolUse).
- Delete `PUBLISH` (274-275). `enforce`: delete `opaque_reason` (295-306), the `opaque` local
  and the `PUBLISH` branch (316-321), and the `UNKNOWN_GIT` condition (311); import only
  `UNPARSED` and `WORKSPACE_ROOT`. The docstring drops the opaque sentence.

### Other code

- `cli/wuwei/commands/init.py:16`: `from wuwei.guards.edges import PERMISSIONS_DENY`.
- `cli/wuwei/calibrate.py:16`: `from wuwei.guards.edges import VERBS`.
- `cli/wuwei/commands/doctor.py:336`: "the PreToolUse guard still checks git commit and git push"
  becomes "the PreToolUse guard still refuses a force push".
- `cli/wuwei/telemetry.py:30`: `GUARDS` stays `tuple(sorted(guards.MODULES))` (the pin in
  `tests/test_telemetry.py:130`), so it gains `edges` and loses `commit_push`, `deploy`, `pr`.
  Stored weeks name them: add `RETIRED_GUARDS = ('commit_push', 'deploy', 'pr')  # stored weeks
  (#839)` to `INNER` (46), as `cruise` is.
- `cli/wuwei/guards/agent_launch.py`: no change (the launch contract blocks; CAP, host seats,
  free memory and ticket log through `guards.CAPACITY`).

## Governance and docs

- Constitution II: append "A Bash call a guard cannot read is the one exit 2 that is logged,
  not blocked (#839)." Bump the minor version over the one part 16 leaves; dated amendment line.
- Design spec (owner-approved pass):
  - 4.1: the `git commit`, `git push` row becomes `git push` (force push in any form); the
    `gh pr create` row becomes "a recorded item that links no PR, naming `bin/wuwei pr raise
    ... --item`"; the `gh pr merge` row: "always, naming `bin/wuwei merge`"; the approve, admin
    and protection row stays; the deploy row stays; the outward row is part 16's.
  - 4.5: replace the normalisation paragraph and the #530 amendment with "Amended (owner,
    2026-10-11, #839): guards match exact argv per command segment (`shlex`), with leading
    assignments, `env` and `sh -c` unwrapped and here-doc bodies skipped. A call they cannot
    split is logged, never refused. Interpreter snippets, scripts, aliases and names built at
    run time are not read: the code host and the credential layout hold them." Keep the
    "What the normalisation guarantees" list and the narrow allowlist paragraph.
  - 4.7: one sentence: the hook matches these by exact argv (#839).
  - 9.1: "a parse failure blocks only a relevant call" becomes "a call a guard cannot read is
    logged, never refused (#839)"; in "No new walls", drop integrity and commit and push from
    the list and the sentence on the unparsed command, the deploy guard's unknown git
    subcommand and the opaque call; integrity is a SessionStart warning.
  - 9.2 table: the Guard column names `guards/edges.py` for every row (`check_bash`,
    `check_deploy`, `check_send`); the Test column names `tests/test_edges.py`; the Admin row
    keeps branch protection; the Force push row adds `+refspec`; the PR raise row drops
    `guards/pr.py`.
- `docs/site/security.md:66-68`: the unparsed paragraph appears three times (the lead's note);
  replace the three with one paragraph: the edges by exact argv, unreadable calls logged, the
  workspace root `cd` logged.

## Files to delete (2 code, 2 tests)

- `cli/wuwei/guards/pr.py` (after `gate_check`, `_recorded_gates`, `GATES` and `_recorded` move);
- `cli/wuwei/guards/deploy.py` (renamed to `edges.py`, not deleted in history);
- `tests/test_deploy.py`: its table cases become the deploy table of `tests/test_edges.py`;
  `test_floor_named` and the opaque and unknown cases go;
- `tests/test_pr_guards.py`: the gate cases (115, 141, 163, 667, 726 and the create cases that
  exercise the gate) move to `tests/test_merge.py` calling `merge.gate_check` directly; the
  recorded-item create cases (789, 800, 828) become rows of `tests/test_edges.py`; the rest go.

`cli/wuwei/guards/commit_push.py` moves to `cli/wuwei/commit_push.py`.

## Files to add

- `cli/wuwei/guards/edges.py` (from `deploy.py`), `tests/test_edges.py`.

## Files to edit, code (22)

`cli/wuwei/guards/__init__.py`, `cli/wuwei/guards/outward.py`, `cli/wuwei/guards/integrity.py`,
`cli/wuwei/guards/protect_state.py`, `cli/wuwei/guards/verdict.py`, `cli/wuwei/shell.py`,
`cli/wuwei/security.py`, `cli/wuwei/commit_push.py` (moved), `cli/wuwei/merge.py`,
`cli/wuwei/shepherd.py`, `cli/wuwei/telemetry.py`, `cli/wuwei/calibrate.py`,
`cli/wuwei/fast_checks.py`, `cli/wuwei/brief.py`, `cli/wuwei/dispatch.py`,
`cli/wuwei/pr_actions.py`, `cli/wuwei/workspace.py`, `cli/wuwei/commands/hook.py`,
`cli/wuwei/commands/init.py`, `cli/wuwei/commands/doctor.py`, `cli/wuwei/commands/build.py`,
`cli/wuwei/commands/git_hook.py`. `hooks/hooks.json` needs no change: one
`wuwei hook PreToolUse` entry serves every guard.

## Files to edit, governance and docs (3)

`.specify/memory/constitution.md`, `docs/specs/2026-09-24-wuwei-design.md`,
`docs/site/security.md`.

## Files to edit, tests

- `tests/test_edges.py` (new): one table per edge (merge, approve, admin and protection, force
  push, deploy, outward send, PR raise), each with refused rows, allowed rows and an
  enforce-off row through `hook.enforce`; the segment splitter (quotes, here-doc, `env`,
  `sh -c`, `cd`, unwrapped assignment, unbalanced quote gives `UNPARSED`); the `gh` body canary
  rows moved from `tests/test_canary.py:478,543`.
- `tests/test_commit_push.py`: delete every `guard().check(...)` case and the `UNPARSED` import;
  keep the identity, context, fast evidence and `unset_identity` cases with the helper importing
  `wuwei.commit_push`. `tests/test_vcs_guard.py`, `tests/test_fast_checks.py`,
  `tests/test_git_hook.py` import its fixtures: run them.
- `tests/test_shell.py`: delete the `mentions`, `is_opaque`, `classify`, `unread`,
  `constructed`, `script_path`, `script_text` and `unreadable` cases; keep `normalize`,
  `git_kind` and `reads`.
- `tests/test_parser_warns.py`: delete the opaque, publish-target, issue 470 and unknown git
  cases (`test_five_shapes`, `test_publish_forms_still_refuse`, `test_issue_470_*`,
  `test_opaque_*`); keep `test_state_writes_still_refuse`, `test_heartbeat_read_loop_exits_zero`
  and `test_issue_508_git_in_path`, rewritten onto `guards.enforce` if they still name a
  posture.
- `tests/test_seat_command_forms.py`: delete the opaque form rows (44, 90-91, 100, 108); keep
  the forms that run.
- `tests/test_hooks.py`: the `MODULES` pin (164); the discover assert (147) names `edges`;
  `test_hook_imports_only_needed_guards` (185-213): `BASH_GUARDS` becomes `{'edges'}` for the
  Stop and PostToolUse rows; the PreToolUse Write row goes with the three Bash-only modules it
  covered (`edges` loads on every PreToolUse for `check_send`, as `outward` does, and
  `protect_state` already loads `shell` and `shlex` on a Write); delete the `UNKNOWN_GIT`,
  opaque and `resolved:` cases; keep the `UNPARSED` and `WORKSPACE_ROOT` once-per-call cases.
- `tests/test_integrity.py`: delete the PreToolUse guard cases (659, 737 and the hook runs at
  250-260, 826-828, 1098-1107 that expect a PreToolUse refusal); add: a failing cached verdict
  produces no PreToolUse refusal; SessionStart prints the reason and exits 0; the reconfirm
  card case stays.
- `tests/test_records_after_dryrun4.py:116`: the config error case runs the SessionStart guard.
- `tests/test_protect_state.py`: rewrite the two `shell.classify` cases and the unparsed rows to
  expect `UNPARSED` (logged) instead of a refusal; parsed state writes still refuse.
- `tests/test_verdict.py`: run (the fast path change keeps its cases).
- `tests/test_enforce.py`: rows `commit_push`, `deploy`, `pr`, `integrity` become `edges`
  rows (`check_bash` force push and `pr raise:` log with enforce off; `check_deploy`,
  `check_send` and the `MERGE` prefixes block); add the launch rows of US5 (CAP, host seats,
  free memory, free memory unmeasured, ticket log; brief mismatch blocks); delete the
  `'opaque` row.
- `tests/test_invariants.py`: `CALLED` security row keys become `('edges.check_send',
  'edges.check_bash')`; delete the `integrity.py` `measure` row; `EXEMPT` rows name
  `guards/edges.py` with the four `MERGE` prefixes and drop the shepherd and deploy unknown git
  rows; lower `len(rows) > 200` to the count after this part, with a comment that the reasons
  went with their code.
- `tests/test_guard_mutation.py`: rows for `commit_push`, `deploy`, `pr` and integrity
  PreToolUse become `edges` rows (`check_bash` with `gh pr review --approve`, `check_deploy`
  with `terraform apply`, `check_send`); keep the SessionStart integrity row.
- `tests/test_telemetry.py`: run (the pin follows `MODULES`); stored rows naming `commit_push`
  and `pr` still validate.
- `tests/test_scope_first.py:35`: `GUARD_TABLES` names `test_edges` in place of
  `test_commit_push`, `test_pr_guards`, `test_deploy`.
- `tests/test_canary.py`: 478 and 543 call `edges.check_bash`.
- `tests/test_merge.py`: 507 (`guards.pr.check`) becomes an `edges.check_bash` merge row or
  goes to `tests/test_edges.py`; add the moved gate cases.
- `tests/test_shepherd.py` (289, 328, 428, 443, 957), `tests/test_templates_errors.py:106`,
  `tests/test_process_depth.py:251`: `wuwei.merge.gate_check` and `merge._recorded_gates`.
- `tests/test_dispatch.py:2229`: `edges.check_bash`.
- `tests/test_doctor.py:403`, `tests/test_vcs.py:498`, `tests/test_pr_actions.py:57-59`:
  `wuwei.commit_push`.
- Part 16's rewritten send tests (`tests/test_outward.py`, `tests/test_stop.py`,
  `tests/test_profiles.py`, `tests/test_canary.py`) import `check_send` from `guards.edges`.
- `tests/test_why.py:270`, `tests/test_shadow.py`, `tests/test_telemetry.py:55-90`: stored
  events naming old guards stay as data; run them.

## RETIRED

None: no config key or table stops being read (spec Assumption 10).

## Risks

- **Bypass ceiling.** A seat can reach an edge through a script, an interpreter snippet, a gh
  alias, GraphQL, backticks or a name built at run time. That was always cooperative (4.5,
  9.1); the code host's protected branch and required checks, and no approve or deploy token in
  seat environments, remain the anchors. `wuwei config check` verifies the layout.
- **Default-branch push** is now refused only by the native pre-push hook and branch
  protection. Part 23 deletes `wuwei git-hook`; it must keep a default-branch push refusal
  there or rely on protection, and say which.
- **Records floor on unparsed calls.** The state-file guard now logs an unparsed call that names
  a state file instead of refusing it. Parsed writes stay refused, and state files are 0444.
- **Part 16 dependency.** The move of `check_send` assumes part 16's names; if they differ,
  follow part 16's code, keep its tests, and move the floor key.
- **Test inventory.** About 230 guard tests go or move. After the deletions, grep:
  `grep -rn "guards.commit_push\|guards.pr\b\|guards import pr\|guards.deploy\|is_opaque\|shell.classify\|unreadable(\|constructed(\|script_text\|UNKNOWN_GIT\|floor_named\|NO_REVIEWER" cli tests`
  finds nothing.
- **The reason corpus floor.** `tests/test_invariants.py` asserts more than 200 reasons; this
  part deletes many. Lower the number to the new count; the wall check itself is unchanged.

## Handoff

- Part 23: the native Git hooks and the default-branch push (above).
- Part 24: `docs/site/reference.md` near 376 and 452, `docs/site/daily.md:260`.
- Part 18: `agent_launch.check_mcp`.
