# Tasks: Owner-only actions are refused in indirect forms too

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names.

## One shared rule for command text (US1, US2, US3)

- [X] T001 Add the failing acceptance table `tests/test_owner_actions.py` (fixture per the
  plan's test notes). `ACTIONS` = the nine (group, verb) pairs of the plan's table. Rows,
  each checked with `check_bash` inside the workspace and in `tmp_path / 'outside'`
  (outside is always `(0, '')`):
  - variable subcommand `X={group}; bin/wuwei $X {verb}`: exit 2, `host terminal` in the reason;
  - `echo {verb} | xargs bin/wuwei {group}`: exit 2;
  - `bin/wuwei {group} -- {verb}`: exit 1, `owner` in the reason;
  - allow rows inside the workspace, all `(0, '')`: `python3 -m pytest -q`,
    `for x in a b; do echo "$x"; done`, `export X=1`, `bin/wuwei state get`,
    `grep -rn uninstall docs/`, `rg 'wuwei mcp decide' cli`,
    `bin/wuwei state transition "$i" review`.
  - edge rows inside the workspace: `bin/wuwei mcp $ACTION` exit 2,
    `find . -exec bin/wuwei drafts approve {} \;` exit 2, `bin/wuwei drafts approve "$ID"`
    exit 1.
  Fails today: the variable form is 0 for decision, drafts, mcp, watch, goals and voice;
  `xargs` is 0 for drafts, watch, goals and voice; `--` is 0 for decision, goals and voice
  and 2 for drafts and mcp; `find -exec` is 0.
- [X] T002 Change the row `('python3 -mwuwei decision outcome D-3 A', 2)` to `1` in
  `tests/test_decision.py::test_agent_tool_cannot_invoke_owner_outcome`. Fails today with
  exit 2.
- [X] T003 Add `test_disabling_owner_rule_makes_its_probe_red` to
  `tests/test_guard_mutation.py`: in a `tmp_path` workspace (`.wuwei/config.toml`,
  `WUWEI_WORKSPACE` removed) `check_bash` on `W=watch; bin/wuwei $W uninstall` returns 2;
  with `protect_state._owner_action` monkeypatched to `lambda *args, **kwargs: None` the
  same assertion raises `AssertionError`. Add `('wuwei.guards.protect_state',
  '_owner_action')` to `SPECIAL_TESTS` and to the `required` set in
  `test_special_policies_have_mutation_probes`. Fails today: the probe returns 0 and
  `_owner_action` does not exist.
- [X] T004 In `cli/wuwei/guards/protect_state.py`: extend `_wuwei_action` for every python
  `-m wuwei` / `-mwuwei` form (plan change 1); add `_OWNER_ACTIONS`, `_OWNER_VERBS`,
  `_OWNER_VERB`, `_OWNER_PAIR` (change 2), `_owner_relevant` (change 3) and
  `_owner_action` (change 4); in `check_bash` delete the six per-action rules (lines 269
  to 297 and 311 to 367) and call the shared rule for command text, with the scope check
  after a finding and `owner_relevant` in the ParseError fallback (change 5, without the
  script-file block). T001, T002 and T003 pass; every existing guard
  table in `tests/test_protect_state.py`, `tests/test_decision.py`,
  `tests/test_drafts.py`, `tests/test_mcp.py`, `tests/test_integrity.py`,
  `tests/test_quiet_sweeps.py`, `tests/test_owner_edits.py` and
  `tests/test_launcher_relevance.py` still passes.

## Script files the command runs (US1)

- [X] T005 Add failing rows to `tests/test_owner_actions.py`: for each pair, `wrap.sh`
  containing `bin/wuwei {group} {verb}` in the cwd; `./wrap.sh` and `sh wrap.sh` are exit 1
  inside the workspace and `(0, '')` outside. Add `fw.sh` containing `bin/wuwei "$@"`:
  `./fw.sh drafts approve x` is exit 2 inside. Add one script with no owner action
  (`bin/wuwei state get`) that stays `(0, '')` inside. Add a hook-level test through
  `wuwei.commands.hook.run` (event PreToolUse) for `./wrap.sh` with
  `bin/wuwei watch uninstall` and for `W=watch; bin/wuwei $W uninstall`: return 2 and
  `permissionDecision == 'deny'` inside, return 0 outside. Fails today: every script row is
  0 and the variable row is allowed by the hook.
- [X] T006 Add the script-file block to `check_bash` in
  `cli/wuwei/guards/protect_state.py` (plan change 5): `shell.script_text` only when
  `root is not None`, relevance `_owner_relevant(script + '\n' + body, script=True)`,
  `_owner_action(normalize(body), body, relevant, script=True)`, a relevant ParseError is
  `2, 'Opaque owner script; use the host terminal.'`, scope checked after a finding, with
  the `ponytail:` comment on the one-level limit.

- [X] T009 Review F1: add path-segment, commit-message and interpreter rows to
  `test_ordinary_work_passes`, see them fail, then anchor the CLI test in
  `cli/wuwei/guards/protect_state.py` to `_CLI_CALL` (the CLI word followed by an owner group
  or a non-literal word, `-mwuwei`, or a python import) for both relevance and the non-CLI
  refusal.
- [X] T010 Review F5: add the interpreter argument-list probes (python `subprocess.run` for
  decision, drafts, mcp, watch and voice; python `os.execvp` for state recover; node
  `execFileSync`; perl `system` for integrity reconfirm) as rows expecting 2 inside and
  `(0, '')` outside, see them fail (0 inside), then in `_owner_relevant` fall back to the
  base's looser check when an interpreter with an inline-code flag is present: the CLI word
  plus an owner group and an owner verb anywhere in the text. A relevant interpreter is
  opaque (exit 2) through the existing `_owner_action` branch.
- [X] T011 Review F6: add `git commit -m "fix wuwei mcp decide"` to
  `test_ordinary_work_passes`, see it fail (exit 2), then drop git commit message operands
  (`-m`, `--message`) from the non-CLI `_CLI_CALL` check in `_owner_action`.
- [X] T012 Review r3 F7 and F8: add `EXECUTOR_PROBES` (stdin and heredoc interpreters,
  deno, bun, tclsh, parallel, `$(...)` subcommands, `./s.py`), the research allow rows and
  the reviewer's regression list to `tests/test_owner_actions.py`, see the probes and allow
  rows fail, then make relevance the base's loose check (the CLI word or a dotted owner call,
  plus an owner group and verb, a non-literal word after the CLI, or xargs). In
  `_owner_action` a non-CLI command is refused only when its own argv names the CLI (git
  message and pattern operands and grep, rg, echo and printf are carve-outs) or it is an
  interpreter running unseen code (stdin, heredoc, inline flag); a module run (`-m`) is not.
  A CLI mention that no argv shows (a heredoc) is exit 2. `_CLI_CALL`, `_OWNER_PAIR` and
  `_INLINE_CODE` are removed.
- [X] T013 Review r3 F9: add `test_script_without_cli_word_is_not_parsed`, see it fail, then
  parse a script body in `check_bash` only when it contains `wuwei`.
- [X] T014 Review r3 F10: add `test_renamed_launcher` (symlink 1, copy 2), see it fail, then
  treat a path-invoked program with a literal owner pair as the CLI when
  `shell._launcher` says it is the launcher.
- [X] T015 Review r3 F11: add the xargs rows (file, `-a`, stdin list, script body, a quoted
  `;` in `sh -c`), see them fail, then when the text names the CLI and xargs, refuse a CLI
  command without a literal group, or with an owner group and no literal verb.
- [X] T016 Review round 4 F13: add the reader-into-executor rows (tclsh, osascript, `at`,
  `batch`, ssh, `script`, `xargs -I{} sh -c {}`, a reader chain into tclsh) and a
  `printf ... | grep` allow row, see them fail, then count a reader's CLI mentions as seen
  only when its pipe does not reach a non-reader.
- [X] T017 Review round 4 F14: add `test_split_name_in_script_body` (`wu""wei` and `wu\wei`
  in a script body, 1 inside), see it fail, then gate the body parse on the quote-stripped
  body.
- [X] T018 Review round 4 F15: add the `cli/wuwei` directory allow rows, see them fail, then
  drop a word whose basename is `wuwei` and which is a directory from the per-command CLI
  check.
- [X] T019 Review round 5 F17 and F18: add the redirect-then-run rows (tclsh, `tclsh <`,
  perl, python3, `./x.sh`, a reader chain redirected), the piped-subshell row and
  `echo ... > notes.md` (2, as on base), see them fail, then invert the reader rule: a
  reader's CLI mentions count as seen only when it has no redirect, its pipe ends in readers
  without a redirect, and its scope is top level (depth 1, or 2 for a pipe stage).
- [X] T020 Review round 5 F19: add `test_bare_cli_word_beside_a_wuwei_directory` (bare
  `find -exec wuwei` and `parallel wuwei` with a `wuwei` directory, 2 inside), see it fail,
  then drop only a word that contains `/` as a directory.
- [X] T021 Add the `rg ... | head -5` and `grep ... | wc -l` allow rows and the `sort -o`
  and `uniq - x.tcl` block rows, see the allow rows fail, then add `head`, `tail`, `wc`,
  `cut` and `tr` to `_READERS`.
- [X] T022 Review round 6 F20: add `true && ./wrap.sh`, `(./wrap.sh)`,
  `timeout 5 ./wrap.sh`, `echo . | xargs ./wrap.sh`, `bash -c 'sh wrap.sh'` and
  `ls; sh wrap.sh` to the script-file table (1 inside, 0 outside), see them fail, then in
  `check_bash` run the script-body check for each normalized command
  (`shlex.join(command.argv)`) and, when parsing fails, for each literal word `normalize`
  collected.
- [X] T023 Review round 6 F21: add the `for`/`while` loop rows over `cli/wuwei` source
  files as allow rows, see them fail, then on the parse-failure path read only a word that
  ends in `.sh` or is executable.

## Verification

- [X] T007 Run `python -m pytest -q` from the repository root with the interpreter the task
  names; every test passes, including `tests/test_guard_mutation.py` and
  `tests/test_hooks.py`.
- [X] T008 Scan every file changed in this feature for em-dashes, emojis and absolute local
  paths, and remove any.
