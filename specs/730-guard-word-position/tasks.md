# Tasks: the command guard judges words by position

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process (`check_bash`, `shell.normalize`, `shell.mentions`, and the hook's
`run` through the `hook` helper of `tests/test_owner_actions.py`), in the `places` fixture
workspace, with an outside directory for the scope rule. Neutral fixtures only. Run the
touched test files after each pair, then the full suite (`python -m pytest -q`).

## Phase 1: a variable that holds the CLI path (FR-001, FR-002, FR-003, US2)

- [X] T001 Test in `tests/test_shell.py`: `leading_variables` returns `{'x': 'bin/wuwei'}` for
  `x=bin/wuwei; $x state set a b`, `x=bin/wuwei && $x status`, `x="bin/wuwei"; $x status` and
  `x=bin/wuwei\n$x status`; `{'a': '1', 'b': 'c/d'}` for `a=1 b=c/d; ls`; and `{}` for
  `ls; x=bin/wuwei; $x status` (not leading), `x=bin/wuwei; x=ls; $x` (assigned twice),
  `x=bin/wuwei | true; $x` (a pipe stage), `x='a b'; $x` (two words), `x=~/bin/wuwei; $x`,
  `x=$(pwd); $x push` and `x=bin/wuwei $x status` (a prefix, no separator).
- [X] T002 Implement `_VARIABLE` and `leading_variables` in `cli/wuwei/shell.py`.
- [X] T003 Test in `tests/test_shell.py`:
  - `normalize` gives argv `['bin/wuwei', 'state', 'set', 'a', 'b']` for
    `x=bin/wuwei; $x state set a b`, the same for `"$x"` and `${x}`, and `['bin/wuwei',
    'status']` for `x=bin/wuwei; timeout 5 $x status`;
  - `normalize` still raises `ParseError` for `$y foo`, `ls; x=bin/wuwei; $x status`,
    `G=git; $G push origin main`, `G=/usr/bin/git; $G status`, `x=gh; $x pr list` and
    `x=bin/wuwei; sh -c '$x status'`;
  - the `$y foo` error text contains `$y` and `in stage $y foo`;
  - `mentions('x=bin/wuwei; $x state set a b', ('git', 'gh', 'rm'))` is False;
    `mentions('G=git; $G push origin main', ('git', 'gh'))`,
    `mentions('$x push', ('git',))` and `mentions('ls; x=bin/wuwei; $x push', ('git',))` stay
    True.
- [X] T004 Implement the `mentions` clause, the `variables` keyword through `normalize`,
  `_parse`, `group`'s `_unwrap` call and the `xargs` recursion, and the resolution and new
  refusal text at `_unwrap` lines 442-443 in `cli/wuwei/shell.py`.
- [X] T005 Test in `tests/test_owner_actions.py`: through `hook` in the `places` workspace,
  `x=bin/wuwei; $x state set a b`, `grep -n wuwei tests/test_x.py` and
  `d=/path/to/tree; ls $d` exit 0 (the issue's acceptance rows); `bash(root, ...)` on
  `x=bin/wuwei; $x decide D-1 a`, `x=bin/wuwei; "$x" decide D-1 a` and
  `x=bin/wuwei; timeout 5 $x decide D-1 a` returns 1 with the owner reason of
  `bin/wuwei decide` (`_OWNER_ACTIONS[('decide', '')]`); `x=bin/wuwei; echo D-1 | xargs $x
  decide`, `x=bin/wuwei; x=ls; $x decide D-1 a` and `ls; x=bin/wuwei; $x decide D-1 a`
  return 2; every row returns `(0, '')` from the outside directory. Expected to pass after
  T004 with no change in `protect_state.py`; if it fails, fix the cause in `shell.py`.

## Phase 2: argument words judged by the stage's program (FR-004, FR-005, US1)

- [X] T006 Test in `tests/test_owner_actions.py`: a `SEARCH_FORMS` list, parametrized, each
  `bash(root, cmd) == (0, '')` and `bash(outside, cmd) == (0, '')`:
  `d=tests; grep -rn wuwei $d | sort | head -3`, `grep -n "wuwei decide" t.py | sort`,
  `grep -n "wuwei decide" t.py | cut -c1-5 | sort`,
  `grep -n "wuwei decide" t.py > out.txt; python3 -m pytest -q`,
  `grep -rn "wuwei decide" tests | sort > out.txt && ls`,
  `grep -n "wuwei decide" t.py | sed s/a/b/`, `grep -n "wuwei decide" t.py | awk 1`,
  `awk '/wuwei decide/' t.py`, `awk "/wuwei decide/ {print}" t.py | head`,
  `sed -n '/wuwei decide/p' t.py`, `sed 's/wuwei decide/x/' t.py`,
  `echo 'bin/wuwei decide D-1 a' | sed 's/a/b/'`, `git grep -n 'wuwei decide'`.
- [X] T007 Test in `tests/test_owner_actions.py`: append to `EXECUTOR_PROBES` (exit 2 inside,
  `(0, '')` outside):
  `awk 'BEGIN{print "bin/wuwei decision outcome x" | "sh"}'`,
  `awk 'BEGIN{print "exec bin/wuwei decision outcome x" > "x.tcl"}'; tclsh x.tcl`,
  `awk -f prog.awk 'wuwei decision outcome'`,
  `sed 's/.*/bin\/wuwei decision outcome x/e' t.py`,
  `sed 's/.*/bin\/wuwei decision outcome x/ge' t.py`,
  `sed '1e bin/wuwei decision outcome x' t.py`,
  `sed -n 's/^/exec bin\/wuwei decision outcome x/w x.tcl' t.py; tclsh x.tcl`,
  `sed -i 's/^/exec bin\/wuwei decision outcome x;/' x.tcl; tclsh x.tcl`,
  `sed 's/^/exec bin\/wuwei decision outcome x/' t.py | tclsh`,
  `echo 'exec bin/wuwei decision outcome x' | sed 's/x/y/' | tclsh`,
  `rg -r 'exec bin/wuwei decision outcome x' . t.py | tclsh`,
  `grep -H --label='exec bin/wuwei decision outcome x' . - < t.py | tclsh`,
  `git grep -O'bin/wuwei decision outcome' x`. The existing
  `awk 'BEGIN { system("bin/wuwei decision outcome x") }'` regression row stays 2.
- [X] T008 Implement `_SCRIPT_EFFECT`, `_text_script` and `_pattern_args`, and use them in
  `_owner_action`'s `readers` predicate and mention accounting, in
  `cli/wuwei/guards/protect_state.py`.

## Phase 3: a refusal names the stage and the word (FR-006, US3)

- [X] T009 Test in `tests/test_owner_actions.py`: `bash(root, 'perl -ne "print if /wuwei
  decision outcome/" t.py')` is 2 and the reason contains `Stage: perl -ne` and
  `word: wuwei`; `bash(root, "echo 'exec bin/wuwei decision outcome x' | sed 's/x/y/' |
  tclsh")` is 2 and the reason contains `Stage: echo` and `word: wuwei`;
  `bash(root, "tclsh <<'EOF'\nexec bin/wuwei decision outcome x\nEOF")` is 2 and the reason
  contains `no stage shows`. `test_owner_action_reasons_name_the_command` stays unchanged and
  green.
- [X] T010 Implement the `kept` stage and both reason suffixes in `_owner_action`
  (`cli/wuwei/guards/protect_state.py`).

## Phase 4: invariant and wrap-up

- [X] T011 Test in `tests/test_invariants.py`: `i51(case, rules)` per posture: through
  `rules.hook`, `grep -n "wuwei decide" notes.txt | sort` and `x=bin/wuwei; $x state set a b`
  exit 0; `check_bash` for a seat (`agent_id`; the fixture planner session asked D-1) on `awk 'BEGIN{system("bin/wuwei decide D-1 a")}'` returns 2 and on
  `x=bin/wuwei; $x decide D-1 a` returns 1; memoized per posture (`rules.memo`, as `i52`).
  Register `'I51': i51` at the end of `INVARIANTS` and `'I51': (0,)` in `READS`.
  `test_table_matches_the_checks` fails until T012.
- [X] T012 Add the I51 row after the I44 row of the 9.2 table in
  `docs/specs/2026-09-24-wuwei-design.md` (text in plan.md).
- [X] T013 Run `python -m pytest -q`; all green. Check every file written for em-dashes and
  emojis.
- [X] T014 Review F1: `leading_variables` keeps a name only when it appears once as a bare
  word, so `x+=`, `read x` and `getopts g x` leave `$x` unresolved and the guard fails
  closed. Rows in `tests/test_shell.py` and a hook row in `tests/test_commit_push.py`.
