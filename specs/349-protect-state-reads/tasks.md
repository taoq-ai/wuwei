# Tasks: protect_state blocks writes, never reads

**Input**: `specs/349-protect-state-reads/` (spec.md, plan.md)

Test first, always: write each test task, run it with the command given, see it fail for the
stated reason, then do the implementation task that follows. Run from the repository root
with the interpreter your task names. No absolute local paths, client or repository names,
emojis or em-dashes in any file. Fixture names stay neutral. Do not edit or remove an
existing test row; if an existing test goes red, the change is wrong (plan, "What must not
change").

Fixture for the new tests in `tests/test_protect_state.py` (reuse the file's `workspace`
fixture and `payload` helper; day `2026-09-28`): add `.wuwei/days/2026-09-28/decisions/D-1.md`,
`.wuwei/days/2026-09-28/events.jsonl`, `.wuwei/ziran/a/report.json`, `.wuwei/charters/a.md`,
`.wuwei/charters/b.md`, `.wuwei/memory/goals.md`, `.wuwei/integrity/verdict.json` (already
seeded), and `read_reports.py` at the workspace root that only reads
`.wuwei/ziran/*/report.json`. A `posture(root, name)` helper writes
`[security]\nposture = "<name>"\n` to `.wuwei/config.toml`. Events come from
`.wuwei/days/*/events.jsonl`, kinds `hook.refusal` and `guard.would_refuse`, as in
`tests/test_cli_known_command.py`.

## Phase 1: the shared predicates (FR-001, FR-002, FR-006)

- [X] T001 [US1] Test, `tests/test_protect_state.py`: `test_issue_349_shared_read_predicate`,
  a table over `shell.reads(argv)`: true for `['cat', 'x']`, `['less', 'x']`, `['ls', 'd']`,
  `['find', 'd', '-name', 'x']`, `['diff', 'a', 'b']`, `['sed', '-n', '1,5p', 'x']`,
  `['jq', '.', 'x']`, `['wuwei', 'status']`; false for `[]`, `['sed', '-i', 's/a/b/', 'x']`,
  `['find', 'd', '-delete']`, `['awk', '1', 'x']`, `['python3', 'x.py']`,
  `['wuwei', 'config', 'set', 'k', 'v']`. Plus `shell.classify('less x').readonly` is true and
  `shell.classify('for f in a; do cat $f; done > out.txt')` returns a `Shape` with `readonly`
  false (no exception). Then `test_issue_349_inline_code`, a table over
  `shell.inline_code(argv)`: true for `['python3', '-c', 'x']`, `['python3', '-Bc', 'x']`,
  `['node', '-e', 'x']`, `['node', '--eval=x']`, `['perl', '-pe', 'x']`; false for
  `['python3', 'x.py']`, `['python3', '-m', 'json.tool', 'f']`, `['python3', '-P', 'x.py']`,
  `['cat', '-c']`, `[]`. Run `python -m pytest -q tests/test_protect_state.py -k issue_349`:
  fails with `AttributeError` (no `shell.reads`, no `shell.inline_code`).
- [X] T002 [US1] Implement in `cli/wuwei/shell.py` (plan 1): add `'less'` to `READ_ONLY`; add
  `reads(argv, cwd=None)` and `inline_code(argv)` above `_classify`, moving the existing code;
  `_classify` calls them and loses its `sed` and `find` branches. Run T001: green. Run
  `python -m pytest -q tests/test_cli_known_command.py tests/test_protect_state.py
  tests/test_scope_first.py tests/test_hooks.py`: green.

## Phase 2: reads pass in every posture (FR-001, FR-003, FR-004, US1)

- [X] T003 [US1] Test, `tests/test_protect_state.py`: `test_issue_349_reads_pass`,
  parametrized over posture (`observe`, `guarded`, `strict`) and these (cwd, command) rows,
  each piped through `wuwei.commands.hook.run` with `event='PreToolUse'`; assert return 0 and
  no new `hook.refusal` or `guard.would_refuse` event:
  - root: `grep posture .wuwei/config.toml`, `grep -n posture .wuwei/config.toml`,
    `cat .wuwei/days/2026-09-28/decisions/D-1.md`, `python3 read_reports.py`,
    `python3 -m json.tool .wuwei/ziran/a/report.json`, `head -5 .wuwei/config.toml`,
    `tail -5 .wuwei/days/2026-09-28/events.jsonl`, `sed -n 1,5p .wuwei/config.toml`,
    `less .wuwei/config.toml`, `wc -l .wuwei/days/2026-09-28/state.json`,
    `jq . .wuwei/ziran/a/report.json`, `ls .wuwei/ziran`,
    `find .wuwei/ziran -name report.json`, `diff .wuwei/charters/a.md .wuwei/charters/b.md`,
    `cat .wuwei/memory/goals.md`;
  - cwd `.wuwei`: `ls ziran`, `find ziran -name report.json`,
    `for f in ziran/*/report.json; do cat $f 2>/dev/null; done`.
  Also `test_issue_349_read_tools_pass`: Read, Grep and Glob on `.wuwei/config.toml` through
  the hook return 0 with no event (passes today; pins it). Run
  `python -m pytest -q tests/test_protect_state.py -k issue_349`: the python operand, json.tool,
  `ls`, `find`, `diff` and the `.wuwei` glob loop rows fail (hook returns 2); the others pass.
- [X] T004 [US1] Implement in `cli/wuwei/guards/protect_state.py` (plan 2a, 2b, 2c):
  `_write_targets` reader line uses `_READERS` (with the `rg --pre` exception) or
  `shell.reads(argv, cwd)`; `shell.reads` is true for `python3 -m json.tool <one file>` (a
  second operand is the outfile); the `check_bash` interpreter rule keeps its main form
  (state named in argv, not `-P -m wuwei`) and skips commands `shell.reads` accepts; the
  unparsed refusal condition is prefixed with `not shape.readonly and`. Run T003: green.
- [X] T004a [US2] Review fix F1. Test `test_issue_349_interpreter_operands_stay_refused`: in
  `observe` and `strict`, the hook returns 2 for `python3 -m json.tool /tmp/x.json
  .wuwei/config.toml`, the same into day `state.json`, `python3 -m zipfile -e a.zip .wuwei`,
  `python3 -m tarfile -e a.tar .wuwei/days`, `python3 w.py .wuwei/config.toml`,
  `node w.js .wuwei/config.toml` and `python3 read_reports.py .wuwei/ziran/a/report.json`.
  A script run with no protected operand still passes.

## Phase 3: writes refused with the command to use (FR-005, FR-007, US2, US3)

- [X] T005 [US2] [US3] Test, `tests/test_protect_state.py`:
  `test_issue_349_write_reasons`, a table of (tool, target or command, expected substring):
  - `.wuwei/config.toml`: Edit, `sed -i 's/a/b/' .wuwei/config.toml`,
    `echo x | tee .wuwei/config.toml`, `echo x > .wuwei/config.toml`: `wuwei config set`;
  - `.wuwei/days/2026-09-28/state.json`: Write, `echo x >> <it>`: `wuwei state set`;
  - `.wuwei/days/2026-09-28/events.jsonl`: Write, `echo x >> <it>`: `wuwei event`;
  - `.wuwei/ziran/a/report.json`: Edit, `echo x >> <it>`: `wuwei mcp decide`;
  - `.wuwei/memory/goals.md`: Edit, `cp /dev/null <it>`: `wuwei goals edit --file`;
  - `.wuwei/integrity/verdict.json`: Write: `wuwei integrity reconfirm`;
  - `.wuwei/charters/a.md`: Write: `use the wuwei CLI` (generic);
  - `.wuwei/credentials/backup.env` after `security.initialize(root / '.wuwei',
    security.DEFAULT_HONEYTOKEN_PATH)`: Write and `echo x > <it>`: `use the wuwei CLI`.
  Assert `check_file` or `check_bash` returns code 1, the substring is in the reason, and
  `'\n' not in reason`. Plus `test_issue_349_writes_refused_in_every_posture`: for each
  posture, `sed -i 's/a/b/' .wuwei/config.toml`, `echo x > .wuwei/config.toml` and Edit on
  `.wuwei/config.toml` through the hook return 2 with one new `hook.refusal` event, and
  `python3 -c 'open(".wuwei/days/2026-09-28/state.json", "w")'` through `check_bash` is still
  `(2, 'Opaque interpreter; use the wuwei CLI for state changes.')` and
  `python3 tool.py > .wuwei/config.toml` is still code 1. Run
  `python -m pytest -q tests/test_protect_state.py -k issue_349`: the reason rows fail (the
  generic two-sentence hint has no command); the posture rows pass (pins today).
- [X] T006 [US2] Implement in `cli/wuwei/guards/protect_state.py` (plan 2d): one-line
  `_STATE_HINT`, `_hint(path)`, `check_file` and the `check_bash` target loop return the
  hint of the resolved protected target; `git apply` keeps `_STATE_HINT`. Run T005: green.

## Phase 4: seat guide and full suite

- [X] T007 Docs, `docs/site/agent.md`: add to the bullet on records under `.wuwei/` that
  reading them (Read, Grep, `cat`, `grep`, `jq`, `ls`) is always allowed. Keep the page at
  or under 100 lines. Run `python -m pytest -q tests/test_docs.py`: green.
- [X] T008 Run the full suite, `python -m pytest -q`: everything passes with no existing test
  edited. Grep the files you touched for em-dashes, emojis and absolute local paths and
  remove any.
