Verdict: PASS
Gate: arch
Item: launcher-python
PR: taoq-ai/wuwei#1241
Head: 6c194e3bd290209e6b6041f6f3b0a3bd4de66759
Confidence: medium
Breaking: no (minor: a new Windows entry bin/wuwei.cmd, a new optional WUWEI_PYTHON variable, a new commandWindows key in hooks/hooks.json, and more detail in two doctor rows; the exit 2 for no usable interpreter keeps its meaning)

## Findings
- [low] cli/wuwei/hook.py:51 blocks: no. Every PreToolUse call now does a second atomic cache write (hook-python next to hook-seen), on the hottest path, and it writes even when the value has not changed. One write holding both the stamp and the interpreter would keep a single write. The cost is small (one tmp-and-rename of a few bytes), and a failed write still never changes the guards' decision.
- [low] cli/wuwei/setup.py:59 blocks: no. vendor() copies bin/ into a user's .claude/wuwei/, so bin/wuwei.cmd ships to user repositories. The repository's .gitattributes (*.cmd -text) does not go with it, so a user's autocrlf or text=auto setting can turn its CRLF lines into LF. That is harmless today: the vendored copy runs only in cloud sessions, and merge_settings (setup.py:42) writes only the sh `command`. It is worth knowing before anyone points a Windows hook at the vendored copy.
- [low] bin/wuwei:12 blocks: no. bin/wuwei and bin/wuwei.cmd keep two candidate lists that differ on purpose (cmd has no python3.x or python3). design.md:242-244, getting-started.md and codex.md each state the order, so a change to the list has to touch four places. No test pins the sh order the way test_launcher pins the cmd order.

## Probes
- Diff read with `git diff origin/main...6c194e3b` (19 files, +465/-16). The branch tip origin/leone/launcher-python equals the reviewed head.
- Runtime budget: `cat cli/wuwei/*.py | wc -l` gives 3401 at the head and 3399 at origin/main. That is +2 lines, under both the 3,600 limit and the spec's FR-005 cap of +6.
- Vendored sync: in a `git archive` copy, `diff -r bin .claude/wuwei/bin` and `diff -r cli/wuwei .claude/wuwei/cli/wuwei` both show no difference. The vendored-tree test passes, and vendor() copies all of bin/, so the .cmd is included.
- Launcher contract: the -I -P -S flags, the PYTHONEXECUTABLE unset and the fail-closed PreToolUse bootstrap all stay in place, matching design.md:239-241. The cmd bootstrap is a single exec literal, and test_launcher compares its AST with the sh bootstrap, so the duplication has a fitness function. The new design.md lines describe both entries.
- hooks.json contract: `command` is unchanged for sh, Git Bash and the Codex login shell, and test_codex still runs it through `sh -lc`. `commandWindows` is extra, and the spec's Assumptions record that Claude Code ignoring the key is unverified on Windows, together with what would overturn it.
- Release: build-release.py SHIPPED includes bin. `*.cmd -text` in .gitattributes matches at any depth, so it also covers .claude/wuwei/bin/wuwei.cmd. `cat -A` shows CRLF on every line.
- Doctor: no code parses the hooks or python row detail (checked with grep for `fired` and `'python'` across cli, skills, charters and docs). The text is free-form, so the extra detail is not a breaking change.
- Hot-path cost: `python3 -V` takes about 3 ms per spawn here (20 runs in 0.061 s). The sh launcher adds one such spawn per hook when python3.12 or python3.13 is present. I did not time the full hook end to end: the PreToolUse door refused a hand-made `bin/wuwei hook` call, as it should.
- Tests at the head in the archive copy: `pytest -q tests/test_launcher.py tests/test_setup.py tests/test_codex.py` gave 78 passed.
- No mutants run: the diff changes no guard or validation in cli/wuwei. The launcher's version check is covered behaviourally by test_launcher (old python3 falls through, old WUWEI_PYTHON falls through, nothing usable exits 2). Mutation of the launcher was left to quality and security.
- Confidence is medium. Neither the cmd entry nor the commandWindows key has been run on a real Windows host, and the spec's assumptions record this. A failed Windows run would change this verdict.

## Residual risk
The Windows path (cmd.exe, Codex commandWindows, Claude Code ignoring the key) is checked only statically and by unit tests. Claude Code on Windows without Git Bash stays unsupported, as on main.
