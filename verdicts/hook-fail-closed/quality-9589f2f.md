Verdict: PASS
Gate: quality
Item: hook-fail-closed
PR: taoq-ai/wuwei#1175
Head: 9589f2f9241faa2afba9820ad2dae2f2c667cd76
Confidence: medium

## Findings
- [medium] docs/design.md:195 blocks: no. The change makes a PreToolUse call that is not a door (Read, a plain Bash command, any tool) exit 2 when the install is broken, because the launcher fails before it can classify the call. design section 7 says "Every other hook fails open" and a door is refused only when "an error while PreToolUse judges a door call"; constitution III says "Everything else passes". Neither text was changed in the diff (git diff 89e7064e 9589f2f touches no docs). The promise asks for exactly this (owner-approved item), so it is a note, not a defect. Failure if left: the docs promise fail-open for non-door calls while a broken install (for example a uid with no passwd entry, #1172) now refuses every tool call in every project that has the plugin, including the Bash call an agent would use to repair it. Suggested: one sentence in design section 7 and constitution III naming the launcher exception, and in the PR body that repair happens outside the session.
- [low] blocks: no. The same exit 2 now reaches a working install when the hook payload is valid JSON but not an object, or has a non-string cwd. Run at main and head with the real launchers (probe.py, 9 payloads): `[]`, `"x"`, `null`, `{"cwd": 5}`, `{"cwd": ["a"]}` exit 1 at main and exit 2 at head (AttributeError/TypeError from `payload.get` and `ws.find` in hook.main, hook.py:480). The harness never sends these, so the harm is theoretical. Acceptance 2 ("hook exit codes as on main for a working install") holds for every well-formed payload. Not covered by a test; accepted as fail closed.
- [low] bin/wuwei:9 blocks: no. The `[:300]` truncation of the stderr reason has no test (mutant no-truncation survives). The traceback is also gone for the PreToolUse hook (only type and message are kept), so the failing module is not named in the reason. Neither is a safety gap.

## Probes
- Suite at head in a `git archive` copy: `/root/.local/bin/pytest -q` gives 2156 passed, 2 skipped. The skips are not in the new tests (`-k` selects 3 tests, 3 collected, 0 skipped).
- Red at main: the 3 new tests from the head's tests/test_hook.py run against main's launcher. The two broken-install cases fail (`assert 1 == 2` for both no-plugin-json and import-error). The working-install test passes at main, as intended (a regression guard for acceptance 2). All 3 pass at head.
- Assertions: exit code, empty stdout, stderr prefix `wuwei hook PreToolUse: ` and the exception class are asserted for the real launcher run as a subprocess from a plugin copy in tmp_path. They test the real consumer; none depends on wall-clock time, the network or a shared file. The `Stop` hook still exits 1 and `--version` exits 1 on a broken install (fail-open and other-command cases).
- Mutants on bin/wuwei, one at a time, in a fresh copy each, run with the 3 new tests only (behavioural kills):
  - exit 1 instead of 2: KILLED (no-plugin-json).
  - except ValueError: KILLED (no-plugin-json raises FileNotFoundError).
  - except OSError: KILLED (import-error raises KeyError).
  - argv check dropped (always exit 2): KILLED (the `Stop` and `--version` asserts).
  - argv widened to any `hook` event: KILLED (the `hook Stop` == 1 assert).
  - argv comparison inverted: KILLED.
  - except BaseException (SystemExit swallowed): KILLED by test_a_working_install_keeps_its_hook_exit_codes (a clean SystemExit(0) from hook.main is turned into exit 2).
  - stderr write dropped: KILLED.
  - always re-raise: KILLED.
  - `[:300]` removed: SURVIVED (untested, finding 3).
- The same 10 mutants on the vendored .claude/wuwei/bin/wuwei: no behavioural test runs the vendored launcher (all 10 survive the 3 hook tests). All 10 are killed by `test_the_vendored_plugin_matches_the_tree_it_was_copied_from` (byte drift). That is acceptable because the vendored file is a generated copy of the tested one. `diff bin/wuwei .claude/wuwei/bin/wuwei` shows no difference at head.
- Real invocation: hooks/hooks.json and .claude/settings.json invoke `bin/wuwei hook PreToolUse`, a fixed string with no extra arguments. Codex loads the same plugin hooks (setup.codex_files writes only agents and exec rules, not hook commands), and its event name is the same `PreToolUse`. Exact argv matching `["hook", "PreToolUse"]` therefore matches both harnesses. The doctor's hook-seen row and `hook.main` take the same event string. No miss found.
- design/constitution: see finding 1. Docs do not state the new behaviour.
- Probes (parser/guard route corpus): not run; the diff does not touch guards.py or hook.py (0 routes can move). The guard parser probe is not applicable.
- Simplicity: none to delete. The try/except is the shortest place to catch a failure before hook.handle (the launcher is the only code that runs before import and argparse). The vendored copy is generated and is not a second implementation. Trust-boundary fail-closed handling is kept.

## Residual risk
A broken install now refuses every tool call, so an agent cannot repair it in-session; this is by promise but contradicts design section 7 text until the docs are updated. A BaseException that is not an Exception (KeyboardInterrupt, MemoryError subclasses aside) still exits as on main.
