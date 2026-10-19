# Feature Specification: the forged-hook door reads a hook call made through Python

**Feature branch**: `fix/forge-door`
**Item**: forge-door, tier full, goal G-2
**Input**: the security gate on goal-met (#1145, verdict security-0039ce2.md) ran 13 forge shapes under
real bash at main 8c1939e. 7 got past the guard and wrote a valid ruling row, an owner review
approval among them. guards.py refused a hand-made hook call only when the program was named wuwei
and its next word was `hook`.

## The promise in my words

Only the harness calls `wuwei hook`; a seat that calls it by hand can write any ruling row,
an owner review approval included. The guard now refuses a seat command that reaches the hook entry,
a hook function or `ws.record` by a route it can read in the command text:

1. `python -m wuwei hook <event>` in any python spelling (`python3`, `python`, `python3.12`,
   `pypy3`, a path), any option cluster (`-Im`, `-mwuwei`), `wuwei.__main__`, `-- hook`, with
   PYTHONPATH set and under the wrappers the guard already unwraps (env, nice, timeout, sudo).
   Also the package or its `__main__.py` run by path (`python3 cli/wuwei hook`).
2. Python code that names the wuwei module next to a `hook` or `record` word, given by `-c`, a
   pipe, a here-string or a here-document.
3. The CLI's subcommand reached through a word sh fills in at run time (`x=hook; bin/wuwei $x`,
   `"$SUB"`, `$(echo hook)`, `{hook,}`). Also a program word sh fills in followed by `hook`
   (`"$W" hook`, `.claude/wuwei/bin/$x hook`), and the CLI with no subcommand, which only xargs
   can complete.

What keeps passing: `pytest -q`, `python3 -m pytest`, `wuwei status`, `wuwei evidence`,
`bin/wuwei agents build`, `python3 -I specs/<item>/probe.py ...` runs, `python3 -c` code that does
not name the wuwei module, and the harness's own call of `bin/wuwei hook` (it reaches the hook
directly; the guard never reads it).

Out of scope, kept open: a script file run by path (`python3 forge.py`, `sh forge.sh`). The
repository's own probes under `specs/` import wuwei and call `hook.handle` or `ws.record` in scratch
workspaces. A command-string guard cannot tell such a probe from a forge by the command alone.

Runtime lines: +8, the item's budget of 8 (3,026 at 5fe8347, 3,034 at the head).

The acceptance scenarios, restated:

1. Each readable shape of the 7 the security verdict found passing is refused, so no ruling row
   is written. That is 5 of the 7: `python3 -m wuwei hook` with PYTHONPATH, the same under env,
   `python3 -c` calling `hook.main`, `python3 -c` calling `ws.record`, and `x=hook; <bin> $x`. The
   other 2 are the script-file case, which the lead's scope keeps open.
2. A generated probe of runner x spelling x position classes runs under real bash with a stub
   wuwei and a stub python3. Every command that reached the stub's hook entry is refused (0 holes),
   and `wuwei status`, `wuwei evidence` and `python3 -m pytest` still pass.

## How this fails

1. A legitimate seat command trips the code rule. Examples: `cd wuwei && python3 x.py --hook`
   (a relative folder named wuwei), `python3 -m pytest -k "wuwei and hook"`, or
   `python3 -m compileall cli/wuwei tests/*` (a glob after the package path). The seat gets a
   refusal and rewords the call. The pass list in tests/test_guards.py holds the shapes this
   repository runs (pytest, the CLI, specs probes, `python3 -c 'import json; ...'`,
   `python3 -m compileall -q cli/wuwei`, `--cov=cli/wuwei`). The route corpus and the full suite
   show no legitimate route moving.
2. A forge in a shape the rule does not read. It can build the module name
   (`__import__('wu' + 'wei.hook')`), take code from a variable (`python3 -c "$CODE"`), or run a
   script file. It can also use `eval` or a runner outside the guards' list (`setsid`,
   `find -exec`). The ledger stays hash-chained, and the transcript check (hook-transcript) is the
   item that can tie a ruling to an owner answer. SECURITY.md lists these shapes as open.
3. A heredoc or other multi-line command that only mentions the module beside hook or record
   (for example a PR body written by `cat <<EOF`) is now refused by the raw-text rule. The refusal
   gives the hint to write the text with Write, which the charters already require.

## Clarifications

### Session 2026-10-19

- Q: What counts as naming the module? A: `wuwei` with no word character, `/` or `.` before it
  and no word character, `/` or `-` after it; `-mwuwei hook` meets the CLI rule instead. A path
  (`.claude/wuwei/cli`, `/w/wuwei/specs/...`, `.wuwei`) is not the module.
- Q: Which programs are read as runners? A: A program word sh fills in, a shell, or any argv word
  whose name starts with `python` or `pypy`. The wrapper rule stays as it is. Reading any argv word
  also covers `uv run python`, `ionice python3` and `setsid python3`.
- Q: Does the code rule read the segment or the whole command? A: The whole command, so code fed by
  `echo ... | python3`, a here-string or a here-document is read with it.
- Q: Why refuse `wuwei` with no subcommand? A: The CLI requires one, so a bare call only runs
  when xargs or a pipe gives it the words. The rule matches only at the start of the command or
  after `-m`, so `python3 -m compileall cli/wuwei` passes.
- Q: Does the route corpus move? A: Only the routes this item adds. The 5 acceptance shapes are
  refused at the head and passed at main. The 4 pass rows pass at both.
- Q: What about a program and a subcommand that are both filled (`x=hook; "$W" $x`)? A: Refused when
  the command text names `hook`. When it names neither wuwei nor hook (`"$W" "$SUB"` with both
  from the environment), it passes: the guard lets through a command that names no door, and
  refusing every `"$EDITOR" "$FILE"` would cost more than it holds. The probe counts this
  nameless class on its own.
- Q: Does a filled word cost time? A: A first draft read `[$...]\S*` at every position, which
  took 1.3 s on a 20,000-character word and grows with its square. `FILLED` now starts at a word's
  start and reads it once with a possessive quantifier; a test holds three 100,000-character
  words under 5 s. A later draft read FORGE once per segment, and the suite's 500 KB `true;` test
  stalled on it. The read now happens once per command: 5.5 s on that input, the same as main
  under the same load.
- Q: Is this a breaking change? A: No. It closes a bypass in a guard; no CLI, config or record
  shape changes. The title has no `!`.

## User Scenarios & Testing

### US1: the readable forge shapes are refused (P1)

Acceptance 1: the 5 readable shapes, as route corpus rows citing this item and as tests. Spellings
around them are tests too: `-Im`, `-mwuwei.__main__`, `-- hook`, `"$EVENT"`, `$PY`, `"$W"`,
`.claude/wuwei/bin/$x`, `sh "$W"`, `cli/wuwei`, `__main__.py`, `pypy3`, a pipe, a here-string, a
here-document, an unreadable comment, `uv run python`, `bash -c`, `{hook,}`, xargs and a glob.

### US2: legitimate commands pass (P1)

The pass list: pytest in both spellings, the CLI's status, evidence, agents build and plan show,
specs probes, `python3 -c` without the module, `python3 -m http.server "$PORT"`,
`"$PYTHON" -m pytest`, `python3 -m compileall -q cli/wuwei`, `--cov=cli/wuwei`, `ls cli/wuwei`,
`git diff -- cli/wuwei` and `grep "wuwei hook"`.

### US3: the harness's hook entry still runs (P1)

The real `bin/wuwei hook PreToolUse`, run with a payload that has no agent_type, answers nothing for
`python3 -m pytest -q` and refuses `python3 -m wuwei hook Stop` with the forge reason.

### US4: a generated probe under real bash (P1)

Acceptance 2: specs/forge-door/probe.py.

## Requirements

- FR-001: guards.bash refuses the shapes in the promise (US1).
- FR-002: the pass list passes (US2), and every route in tests/fixtures/routes.json keeps its
  verdict except the rows this item adds.
- FR-003: the generated probe has 0 holes at the head.
- FR-004: SECURITY.md names the script-file case as open; design.md and the doors page name the
  new shapes.
- FR-005: runtime +8 or fewer; `.claude/wuwei/cli` matches `cli/`; no agent gains words.

## Assumptions

- The lead's scope keeps the script-file case open, because the repository's probes run the same
  way. Overturned by an owner scope decision or by hook-transcript tying rulings to answers.
- A runner outside the guards' wrapper list running the CLI (`setsid bin/wuwei hook`) stays open,
  and so does a wrapper whose program is a variable (`env "$W" hook Stop`), as SECURITY.md already
  lists for every door. Overturned if the wrapper rule changes.
- A refused legitimate command costs one reworded call. Overturned if a charter tells a seat to
  run a shape on the misfit list.

Rollback: revert the commit. The rule only refuses, so a revert restores the old door with no data
to migrate.
