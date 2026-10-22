Verdict: FIX
Gate: quality
Item: tests-offline
PR: taoq-ai/wuwei#1226
Head: 626c521190082ee39cf5ce4418532ffb6f77ea3a
Confidence: high

## Findings
- [medium] tests/test_offline.py:17 blocks: yes. Failure: a hook subprocess that drops the stub folder from PATH calls the real gh (mutant M1: bin/wuwei filters "/stub" out of PATH; the hook ran `gh api repos/acme/app/pulls?state=open&per_page=100` on the stand-in real gh) and test_offline still passes, because the counting shim is appended after the whole PATH, behind any real gh, so `assert not log.exists()` cannot fail on a machine with gh installed (requirement: promise "a test asserts a full hook subprocess run makes no real gh call"; acceptance 2)
- [low] tests/test_offline.py:26 blocks: no. The in-process `gh.run(['api', 'rate_limit'])` block and the assert after it are vacuous: the shim is only in the subprocess env, never on os.environ PATH, so the log cannot be written by this call; with the fixture removed it would make a real network call from the test itself.
- [low] tests/test_codex.py:29 blocks: no. Existing gap the PATH stub cannot close: `sh -lc` runs a login profile; where the profile sets or reorders PATH (stock Debian root /etc/profile, macOS path_helper with Intel Homebrew gh in /usr/local/bin) SessionStart reaches the real gh. Shown with HOME/.profile setting PATH to a stand-in real gh: one call logged. Unsetting GH_TOKEN/GITHUB_TOKEN and pointing GH_CONFIG_DIR at an empty folder in the fixture would make even a real gh fail before the network.
- [low] tests/conftest.py:30 blocks: no. The stub is rewritten into a new mktemp folder for every test (about 3,200 folders a run); a session-scoped folder with a per-test monkeypatch of PATH does the same.
- [low] AGENTS.md:9 blocks: no. The added line runs to about 112 columns where its neighbours wrap near 100.

## Probes
- Full suite at head, counting shim (logs to an absolute path, exits 1) placed before the original PATH, so after the fixture's stub: `TAG=head PATH=<shim>:$PATH /root/.local/bin/pytest -q`: 3210 passed, 2 skipped; shim log never created: 0 calls (my count).
- Same shim on base 6828776: 3209 passed, 2 skipped, 150 calls logged; the shim works.
- Full suite at head under `strace -f -e trace=execve`: 86,973 execs; every successful exec of a file named gh (152) was `/tmp/pytest-of-root/pytest-N/stubN/gh`; 0 execs of /usr/local/bin/gh or any other gh. 152 = 150 + the new test's hook call + its in-process call. This also covers subprocesses with their own env: all tests that build env (test_codex, test_hook broken_install and line 1527, test_setup, test_guards bash stub) spread os.environ, so they keep the stub; no test calls gh by absolute path (grep of tests and cli for gh invocations: only gh.run spawns gh); no test deletes PATH or overrides the fixture.
- Mutant M0 (offline fixture made non-autouse): test_offline fails at the `wuwei-test-stub` which-assert. Killed.
- Mutant M0b (M0 plus the which-assert removed), stand-in real gh first on PATH: test passes while the stand-in logged `api repos/acme/app/pulls...` and `api rate_limit`. The hook and in-process assertions alone pin nothing.
- Mutant M1 (bin/wuwei drops "/stub" from PATH), stand-in real gh first on PATH: test_offline passes, stand-in logged the hook's call. Survives. Re-run in a fresh copy: same.
- Fix check: with the shim inserted right after the stub (`[parts[0], shim, *parts[1:]]`), M1 fails at `assert not log.exists()` and the unmutated head passes.
- fake fixture: monkeypatch.setattr(gh, 'run', ...) replaces the function, so PATH is never consulted; all fake-using tests pass in the full run (3210 passed).
- Leak: the stub is set with monkeypatch.setenv (undone per test) in tests/conftest.py only; the vendored .claude/wuwei tree holds no tests (git ls-tree: 0 entries under .claude/wuwei/tests).
- Login-shell probe: test_codex either_harness_shell under strace runs `gh api repos/acme/app/pulls...` from the `sh -lc` SessionStart (stub here); with HOME/.profile resetting PATH the stand-in real gh logged that call.
- Simplicity: the try/except gh.run block and its assert in test_offline.py can be deleted (vacuous), or made real by setting the shim-after-stub PATH in-process; the per-test mktemp can become one session folder. Nothing else is deletable.
- Confidence high: the 0 count is measured two ways (shim and execve trace) and each mutant was run and re-run.

## Residual risk
On machines whose login profile rewrites PATH, the one `sh -lc` test can still reach the real gh; the PATH stub alone cannot cover that.
