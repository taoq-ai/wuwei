Verdict: PASS
Gate: quality
Item: tests-offline
PR: taoq-ai/wuwei#1226
Head: 9ef3f3af79ecdb3b77739179b7c56e29c4adb461
Confidence: high

## Findings
- [low] tests/conftest.py:46 blocks: no. Clearing GH_TOKEN, GITHUB_TOKEN and pointing GH_CONFIG_DIR at an empty folder stops a gh found past the stub here, but a gh that keeps its token in the OS keyring (macOS Keychain) may still find one with no hosts.yml; unmeasured, the docstring's "has no token" claim holds only where the token lives in env or config.

## Probes
- Fresh `git archive` copy of 9ef3f3a; full suite with the counting shim directly after the stub (pytest launched with PATH=<shim>:$PATH, the fixture prepends the stub) under `strace -f -e trace=execve`: 3210 passed, 2 skipped; shim log never created: 0 calls (my count); every successful exec of a file named gh (152) was `/tmp/pytest-of-root/pytest-N/stubN/gh`, 0 of /usr/local/bin/gh or any other gh.
- Mutants, each in its own fresh copy, run one at a time with a stand-in real gh first on the launch PATH: M1 (bin/wuwei drops "/stub" from PATH) killed at tests/test_offline.py:30 (`assert not log.exists()`); M2 (gh.run resolves gh skipping the stub, applied to cli/ and .claude/wuwei/cli/) killed at :28 (message `gh exited 1` from the shim, not `offline`); M0 (offline fixture not autouse) killed at :21; M4 (GH_TOKEN and GITHUB_TOKEN not cleared) killed at :22. Unmutated head passes; the stand-in real gh logged nothing in any run.
- Real gh with GH_TOKEN and GITHUB_TOKEN unset and an empty GH_CONFIG_DIR, under `strace -e trace=connect`: prints the `gh auth login` hint, 0 connect calls, config folder left empty.
- Login-shell probe at the head: test_codex either_harness_shell with HOME/.profile setting PATH=/usr/local/bin:/usr/bin:/bin, traced for execve and connect: the real /usr/local/bin/gh ran (`gh api repos/acme/app/pulls...`) and made 0 non-unix connects; the test passed. The credential layer covers the hole the PATH stub alone left.
- fake fixture: monkeypatch.setattr(gh, 'run', ...) never consults PATH; all fake-using tests pass in the full run.
- Leak: PATH, token removal and GH_CONFIG_DIR go through monkeypatch (undone per test); the session stub folder lives under pytest's basetemp; the vendored .claude/wuwei tree holds no tests.
- AGENTS.md rewrap: changed lines 94 to 97 columns; no em dashes in the three changed files (python check).
- closed: test_offline shim after the real gh, hook bypass undetected (M1 survived) at 9ef3f3a
- closed: vacuous in-process gh.run block at 9ef3f3a (now pytest.raises match 'offline' plus the log assert; M2 killed)
- closed: login-shell test reaching the real gh at 9ef3f3a (credentials cleared; 0 connects measured)
- closed: per-test stub folder at 9ef3f3a (session-scoped)
- closed: AGENTS.md line width at 9ef3f3a
- Simplicity: none; each added line is either the offline guard or an assertion a mutant above kills.
- Confidence high: the 0 count was measured with both the shim and an execve trace, and every mutant was killed by a behavioural assertion.

## Residual risk
A keyring-held gh token on a machine whose login profile rewrites PATH is not covered by the credential clearing; unmeasured here.
