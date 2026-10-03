# Implementation Plan: every refusal says what happened, why, and the one command to run, with real values and one reason per refusal

**Branch**: `362-refusals-coach` | **Spec**: `specs/362-refusals-coach/spec.md` |
**Catalogue**: `specs/362-refusals-coach/research.md`

## Summary

Fix each finding once, at the spot every caller routes through, then rewrite the remaining
walls string by string with an AST test as the ratchet:

1. `cli/wuwei/exits.py`: six d2 family constants. Internal invariants append one.
2. `tests/test_reasons.py` (new): the collector, the next-step test, the two voice tests and
   the before-a-plan tests.
3. `cli/wuwei/commands/hook.py` `run`: sort refusals by specificity, print the first only.
4. `cli/wuwei/guards/commit_push.py`: one helper for the worktree's item, used by the bare
   push, fast-check, commit-and-push and default-branch reasons.
5. `adapters/vcs/git.py` `_run` and `adapters/code_host/github.py` `_run`: the first stderr
   line, the repository and one hint, in the one line each that raises `exited`.
6. F12: `commands/close.py`, `commands/report.py`, `commands/decision.py` `show`,
   `commands/goals.py`, and the texts in `commands/build.py` `check`, `dispatch.py`,
   `plan.py` `approve`.
7. `cli/wuwei/integrity.py`: record the plugin path; name both paths in `cached` and
   `check`.
8. `cli/wuwei/commands/doctor.py`: capture stderr in `run`, launcher path in `_row`,
   `setup --shadow`, identity without a workspace.
9. The catalogue: every remaining wall under `cli/wuwei`, plus the docs pages' voice.

No new module under `cli/`, no new state key, no new event kind, no new command.

## Technical Context

Python 3.11+, stdlib only (`ast`, `re` in the test). Tests: pytest, in process. Reuse
`tests/test_posture.py` `stub`, the `workspace_case` fixture and `payload` of
`tests/test_commit_push.py`, `install_replay` and `adapter` of `tests/test_vcs.py` and
`tests/test_code_host.py`, the `workspace_root` helper of `tests/test_integrity.py`, the
doctor fixtures of `tests/test_doctor.py`, `fakes.integrity.seed`, and `ROOT`/`SITE` of
`tests/test_docs.py`. No network, no real `git` or `gh`.

## Constitution Check

- I stdlib only: yes; adapters import `wuwei.redact`, already a core module.
- II three-state exits: no guard changes its decision. Exit codes change only where the
  spec says: `close`, `report` (no day state), `decision show` (missing id) and bare
  `goals` become 0; a bare `git push` in commit_push becomes 1 (a finding) instead of 2.
  Both block; posture handling is unchanged.
- III one behaviour, one function: the reason choice lives in `hook.run`; the item and
  branch in one commit_push helper; the stderr line in each adapter's `_run`; the family
  texts in `exits.py`; the launcher substitution in doctor `_row`.
- IV test first: every task pair in `tasks.md`; the AST test is written first and fails on
  about 940 walls until the rewrites land.
- V ponytail: appending a constant beats a family exception hierarchy (six classes, the
  same edits); the hint table is two regexes, not a framework; no shim on PATH.
- VII security: redaction of the stderr line (`wuwei.redact.redact`, 200 characters), no gh
  stdout body, no search endpoint (it can carry an email). No trust is added: the plugin
  path in the integrity records only feeds message text.

## Design

### 1. `cli/wuwei/exits.py`: d2 family constants

Add after the exit statuses (exact text; no "you", no em-dash):

```python
# d2 families (#362): an internal invariant names its family's next step after its own text,
# for example raise ValueError(f'invalid decision ledger; {DAMAGED}').
DAMAGED = ('a WUWEI record failed its consistency check, so nothing was written; run '
           'bin/wuwei doctor, which names the file and its fix (bin/wuwei state recover for state.json)')
PLAN_JSON = ('the plan JSON misses or misshapes this field; compare it with bin/wuwei plan '
             'template, which shows every field, and fix the one named here')
ADAPTER_DATA = ('an adapter or seat runtime returned data WUWEI cannot read, so the step is '
                'unmeasured and nothing was recorded; retry once, then run bin/wuwei doctor, '
                'which tests the adapter')
PAYLOAD = ('Claude Code sent a hook payload this WUWEI version cannot read, so nothing was '
           'done; run bin/wuwei doctor, then update Claude Code or WUWEI')
RACE = ('another session changed this record while the command ran, so nothing was '
        'written; run the same command again')
SYMLINK = ('links are refused so a write cannot be redirected; replace the link with a '
           'regular file (bin/wuwei doctor names it)')
FAMILIES = ('DAMAGED', 'PLAN_JSON', 'ADAPTER_DATA', 'PAYLOAD', 'RACE', 'SYMLINK')
```

Each d2 row in research.md keeps its text and gains `; {FAMILY}` (f-string with the
imported name, `from wuwei.exits import DAMAGED`, or `exits.DAMAGED`). The `rank.py` row
(`candidates must be a list`) takes `PLAN_JSON`. Where a d2 string is a guard return
(`return 2, 'missing or invalid tool_input'`), the same applies.

### 2. `tests/test_reasons.py` (new): collector and tests

Collector, over every `cli/wuwei/**/*.py` (`ast.parse`, no import):

- Reason sites: `raise X(<arg0>)`; `print(<arg0>, file=sys.stderr)`; `Result(1|2, data,
  <reason>)` and `Result(1|2, ..., reason=<reason>)`; `return (<1|2|FINDINGS|UNRUN>,
  <text>)`; the values of `_OWNER_ACTIONS` in `guards/protect_state.py`.
- Text of a node: a `str` constant; a `JoinedStr` (its constant parts joined); a `+`
  concatenation of those; each branch of an `IfExp`. Anything else (a variable, `str(exc)`)
  is not a reason literal and is skipped. Empty text is skipped.
- Pass-through: a `JoinedStr` that is only `{value}`, or a label matching
  `[\w ./{}-]+: ` followed by one `{value}` (`f'build: {exc}'`, `f'wuwei {name} edit:
  {exc}'`). Exempt: the wrapped reason is checked where it is made.
- Family: a `JoinedStr` with a `FormattedValue` that is a `Name` or `Attribute` whose name
  is in `exits.FAMILIES`. Passes the next-step test and is skipped by the voice test (the
  constants are checked once, directly).
- Next step:
  `re.compile(r'\bwuwei [a-z][\w-]*\b(?!:)|/wuwei:wuwei-|\bconfig set\b|\b(?:run|rerun|use|set|add|pass|retry|remove|replace|restore|create|write|answer|install|fetch|start|split|ask|wait)\b', re.I)`.
  `wuwei hook:` (a label) does not count; `bin/wuwei build next DIV-1` does.
- Person-facing (voice set P): non-docstring string constants and f-string constant parts
  in `commands/doctor.py`, `commands/setup.py`, `commands/nudges.py`; in
  `commands/next.py` function `step`; in `control_plane.py` the `HELP` assignment and the
  functions `render`, `escalate`, `notify`; the first argument and the option description
  strings of every `widget(...)` call (`decision.widget` and the module-local name) under
  `cli/wuwei`.
- Seat-facing: every collected reason string not located in the four person-facing files.

Tests:

- `test_every_reason_names_a_next_step`: no wall; the assertion message is the list of
  `relative/path.py:line: text`.
- `test_collector_finds_a_new_bare_wall`: the collector run on a source string with the
  three cases of spec US7 scenario 2.
- `test_seat_facing_reasons_have_no_pronoun`: no `\b(?:you|your)\b` (case-insensitive) in
  seat-facing text, and none in the six family constants.
- `test_person_facing_text_never_says_the_owner`: no `\bthe owner\b` (case-insensitive) in
  P.
- KEEP rows: two are the hook's own `print(reason)` of a variable (not collected); the third,
  `workspace.py` `time component required`, is caught and replaced before anyone sees it.
  The test holds it in a one-entry allowlist, `KEEP = {('workspace.py', 'time component
  required')}`, which `test_every_reason_names_a_next_step` skips and
  `test_keep_rows_unchanged` asserts is still present in that file.
- `test_before_plan_*` (spec US4): `wuwei.__main__.main([...])` in a `tmp_path`
  workspace made with `main(['init', str(root)])`, `WUWEI_WORKSPACE` and `WUWEI_NOW`
  set, `fakes.integrity.seed` where needed; assert exit codes and `capsys` text.

`tests/test_docs.py` gains `test_pages_address_the_reader` (spec US7 scenario 5).

### 3. `cli/wuwei/commands/hook.py` `run`: one reason

- Keep the code with each refusal: `refusals.append((guard.check, message, code))` and
  adapt the two readers in `run` (`enforced` default and the `posture` call) to the triple,
  or sort before `posture` and drop the code: sort `refusals` stably by
  `(code, module(check) == 'integrity')`, then call `posture(payload, [(check, message)
  for check, message, _ in refusals], root)` unchanged. `posture` keeps input order, so
  `enforced[0]` is the most specific enforced refusal.
- `reasons = [...]` stays for SessionStart. For every other event print only
  `enforced[0]`: `reason, line = enforced[0][1], enforced[0][2]`; text `f'{reason}\n{line}'
  if line else reason`. `refuse(...)` gets that text and `refusals=` all of `enforced`
  (unchanged), so `hook.refusal` keeps every guard.
- `posture()`, `level()`, `refuse()` unchanged.

### 4. `cli/wuwei/guards/commit_push.py`: the guard's own values

- Helper, next to `push_options`:

```python
def _item(path, root):
    """The item of an item worktree (<root>/worktrees/<ITEM>), else None."""
    try:
        return Path(path).resolve().relative_to(Path(root).resolve() / 'worktrees').parts[0]
    except (ValueError, IndexError):
        return None
```

  Branch: `item.lower()` (the `commands/worktree.py` convention), else `<branch>`.
- `push_options(args, branch='<branch>')`: fewer than two operands returns `((1, f'name the
  remote and the branch: run git push origin HEAD:refs/heads/{branch}'), None, [])`
  instead of raising. The unsupported-option message also names that command. The early
  call (`:402`) passes no branch; the real call (`:426`) passes the branch from
  `_item(actual['path'], root)`.
- `push_check(repo, actual, push, root, vcs)`: compute `item = _item(actual['path'],
  root)` once. Fast-check refusal (`:140`, `:145`): `f'fast check "{check}" has not passed
  for HEAD {sha[:12]}; run bin/wuwei build check {item}'`, or `...; run bin/wuwei
  fast-checks in this worktree` without an item. Default branch (`:117`): name
  `repo['default_branch']` and the item branch push. `push_check` is also used by
  `commands/git_hook.py`; the text change is shared and correct there too.
- Commit then push (`:374`): `run the commit alone, then bin/wuwei build check {item},
  then git push origin HEAD:refs/heads/{branch} as its own command` (without an item:
  `bin/wuwei fast-checks`). Compute item and branch from `directory` and `root` at that
  point (no vcs call: `_item(directory, root)`).
- Decisions unchanged: same calls refused, same exits, except the bare push 2 to 1.

### 5. `guards/deploy.py` and `guards/protect_state.py`

- `deploy.py:115`: `push destination is unresolved; name it: git push origin
  HEAD:refs/heads/<branch>`; the other `unknown(...)` texts per research.md. Exit and the
  owner-only floor unchanged.
- `_OWNER_ACTIONS`: each value names its command and the host terminal, seat-facing, for
  example `('decision', 'outcome')`: `Recording a decision outcome is the owner's answer:
  show it with bin/wuwei decision show <id> --widget, and the owner runs bin/wuwei decision
  outcome <id> <option> in a host terminal.` `('config', 'set')`: `Config edits are the
  owner's: propose the line, and the owner runs bin/wuwei config set <key> <value> in a
  host terminal.` Keep every value a single sentence that names `bin/wuwei <group>
  <verb>`.
- `:171`, `:190`: `Opaque owner action: write bin/wuwei <group> <verb> as a plain command
  so the guard can read it; owner actions run in a host terminal.`

### 6. Adapters: first stderr line, repository, hint

`adapters/vcs/git.py` `_run`, replace the final `raise ValueError(f'git exited
{result.returncode}')` (`:183`):

```python
line = next((text.strip() for text in result.stderr.decode('utf-8', errors='replace').splitlines()
             if text.strip()), '')
reason = f'git exited {result.returncode} ({args[0]} in {os.fspath(repo)})'
if line:
    reason += ': ' + redact(line)[:200]
if re.search(r'origin/\S+|unknown revision|bad revision|not a valid object name', line, re.I):
    reason += f'; run git -C {os.fspath(repo)} fetch origin, then retry'
raise ValueError(reason)
```

`from wuwei.redact import redact` at the top. The `not a git repository` branch and the
rebase branch stay. `_operation` keeps printing (callers rely on it); doctor captures it.

`adapters/code_host/github.py` `_run`, replace `raise ValueError(f'gh exited
{result.returncode}')` (`:110`): the same first-line, redaction and cap; the subject is the
repository when `args[1]` matches `repos/<owner>/<name>` or a pull URL gives it, `search`
for a `search/` endpoint, else `args[0]`; the hint `; run gh auth login` when the line
matches `auth login|not logged|authentication`. The `branch protection absent` 404 branch
and `_errors` (stdout bodies) stay.

### 7. F12 commands

- `commands/close.py` `run`: replace the `raise ValueError('day state missing; ...')` with
  `print('Nothing to close today: no day has started. Start one with /wuwei:wuwei-plan.')`
  and `return 0`.
- `commands/report.py` `run`: before `report.write()`, if `workspace.day_dir(root) /
  'state.json'` is not a file, print `No report today: no day has started. Start one with
  /wuwei:wuwei-plan.` and return 0 (root from the existing `guard_scope` call). `report.py`
  keeps raising for its other callers, with its catalogue rewrite.
- `commands/decision.py` `show`: catch `FileNotFoundError` before `OSError` and return `0,
  f'No {args.id} today; bin/wuwei nudges lists open decisions.'`. Other read errors keep
  exit 2 with the path made workspace-relative.
- `commands/goals.py`: `required=False` on the action subparsers and
  `goals.set_defaults(func=show)`; `show` reads `.wuwei/memory/goals.md` (through
  `promotion.safe_path`, as `_owner_edit.run` does), prints the no-goals line when
  `goals.defined(text)` is false, else one line per goal from `goals.parse(text)`:
  `G-1 (priority 1): <outcome>; measure: <measure>; target: <target> by <date>`. A parse
  error is exit 1 with the error and `bin/wuwei goals edit`. `voice` is untouched.
- `commands/build.py` `check` (`:373`): `f'{item} is not waiting for checks ({state}); run
  bin/wuwei build next {item} for its current step'`, where state is `no build yet` or
  `build {record["status"]}`. Exit stays 2 (the command's `except ValueError`).
- `dispatch.py:140`: `f'{item} is not approved at the morning gate; approve it there
  (/wuwei:wuwei-plan) or admit it with bin/wuwei plan add {item}'`; `:161`: `f'{item} is in
  {phase}, not at a gate; run bin/wuwei build next {item}'`. Exit stays 1.
- `plan.py:172`: `No plan for today yet, so there is nothing to approve; run
  /wuwei:wuwei-plan (or bin/wuwei plan propose) first.` Exit stays 1.

### 8. `cli/wuwei/integrity.py`: both paths

- `check`: add `'plugin': str(PLUGIN)` to the final `verdict.json` record (not to the
  incomplete placeholder). When `result.exit == 1`, a confirmation exists, and its
  `plugin` is a string that differs from `str(PLUGIN)`, replace the reason with
  `confirmed(record['plugin'])`.
- `reconfirm`: add `'plugin': str(PLUGIN)` to `confirmation.json`.
- `cached`: after validation, before the checkout comparison, `if
  isinstance(record.get('plugin'), str) and record['plugin'] != str(PLUGIN): return
  Result(2, reason=confirmed(record['plugin']))`.
- One helper builds the text:

```python
def confirmed(other):
    return (f'plugin integrity: this workspace confirmed the plugin at {other}, but this '
            f'session runs {PLUGIN}; start Claude Code with that copy (claude --plugin-dir '
            f'{other}), or run bin/wuwei integrity reconfirm in a host terminal to confirm this one')
```

  `PLUGIN` is already resolved; compare strings of resolved paths.
- Old records without `plugin` behave as today.

### 9. `cli/wuwei/commands/doctor.py`

- `run`: `with redirect_stderr(io.StringIO()): rows = diagnose(args.section)` (both names
  are imported already).
- `_row`: when `fix` is set, substitute the launcher:
  `re.sub(r'(?<![\w/@:.-])(?:bin/)?wuwei(?= [a-z-])', str(integrity.PLUGIN / 'bin/wuwei'),
  fix)`. One place covers `render`, `--json`, the `held` list and setup's `Next:` line
  (`commands/setup.py` `ending` reads `row['fix']`).
- `_workspace` (`:218`): fix `bin/wuwei setup --shadow in the directory that holds your
  repositories`.
- `_host` (`:171`): `own = root is None or (config['repos'] and all(...))`; the `ok` text
  for the no-workspace case is `not set globally; setup reads each repository's own
  identity`.
- Doctor texts are person-facing: "you", never "the owner".

### 10. Rewrite rules for the rest of the catalogue

Work file by file through the failure list of `test_every_reason_names_a_next_step`:

- A row in research.md d1: take its rewrite, then apply the voice rule of the file (seat:
  drop "you"/"your", rephrase imperative; person: "you", never "the owner"). Keep the
  `{...}` values the code had; replace `{...}` in the drafted text with the real
  expression. Fill in a value the code has (item, key, path relative to the workspace)
  where the draft says `<item>`.
- A row in d2: keep the text, append `; {FAMILY}`.
- A string with no row (added after the sweep): what happened, why if not obvious, and one
  command with real values, in the file's voice.
- Usage strings (`usage: build next ...`): name the right form as a full `bin/wuwei`
  command.
- Keep the leading words of a message where tests or `wuwei why` match on them, unless the
  draft replaces a wall; update an existing test assertion to the new text without
  weakening what it checks.
- Rewrites stay one line (no `\n`), no em-dash, no emoji, no absolute path literal.
- As built: the leading text stays and the step is appended after `; ` (see spec
  Assumptions); a one-word string is a token and `raise AttributeError` is the
  `__getattr__` protocol, so the collector skips both.
- A throwaway listing script, if useful, lives outside the repository.

Docs: rewrite each `the owner` in `docs/site/*.md` (about 55 lines; not `agent.md`,
`charter-overrides.md` or the Glossary section) to address the reader ("you", "your
interview"), keeping every phrase an existing `tests/test_docs.py` assertion pins; where a
pinned phrase contains "the owner", change the page and the assertion together.

## What must not change

- Which calls each guard refuses, every guard's exit code except the bare-push 2 to 1, the
  posture levels and floors, `guard.would_refuse` and `hook.refusal` event shapes.
- SessionStart output; hook behaviour outside a workspace.
- Exit codes of every command except the four F12 state answers.
- Adapter result shapes and allowlists; gh stdout bodies never in a reason; the
  `branch protection absent` and `not a git repository` texts.
- `Decided-by: owner` in records, config keys, event kinds and state keys.
- `next.orientation`, `next.POSTURES`, the charters, the skills, `README.md`, `SECURITY.md`.
- Hook latency: no new import on the hook path (`exits.py` constants are plain strings;
  commit_push's helper uses `Path` only).

## Risks for the builder

- Volume: about 940 strings across most modules. Do it file by file and run that file's
  tests after each; the AST test's list shrinks as you go.
- Existing tests pin old texts (for example `tests/test_vcs.py::test_git_exit_is_explained`,
  `tests/test_doctor.py:279`, the `('git push', 2)` row of `tests/test_commit_push.py`
  `test_bash_table`, `tests/test_cli_known_command.py:147`). Change the assertion to the
  new text; keep its intent.
- `tests/test_hooks.py` pins the hook's imports and latency; `exits.py` must stay
  import-free.
- `commands/next.py` `step` rows become person-facing ("you"); the SessionStart block
  shows them through `line(row)`, which is intended (the planner shows them unchanged).
- The verb regex is generous on purpose (the sweep's own test). Do not satisfy it with a
  token verb; the d1 rewrite is the bar.
