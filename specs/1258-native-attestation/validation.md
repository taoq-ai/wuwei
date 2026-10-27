# Builder validation

Source head: `b5fb247c0512bb264c2b2b8ff672341fd557e7be`.
Parent: `b6310c55f20a430110007f3050929881e8b68935`, merged normally before the final source freeze.

## Test-first evidence

- `uv run --no-project --with pytest python -m pytest -q tests/test_native_evidence.py`: initial red was 375 failed and 33 passed. The first native implementation passed 408 tests.
- Added delivery, race, notification and boundary cases. The missing child boundary failed before the explicit check; the expanded suite then passed 421 tests.
- The parent-root regression failed before requiring both native paths under SESSIONS. The latest native suite has 422 tests.
- Final native, fixture-privacy and vendor-parity recheck: 424 passed.
- Broader focused run: 1,900 passed, 1 skipped, with one initial vendor-parity failure. Supported-Python generation fixed parity; the focused recheck passed.
- `uv run --no-project --with pytest python -m pytest -q`: final full run at the source head passed 4,350 tests, with 7 skips, in 253.35 seconds.
- An earlier full run was interrupted before the native-root source fix and is superseded. It is not a pass. It also exposed the fixture policy matching canonical task identities as local paths; the fixture now uses an explicit task-root placeholder.

Logs are retained in the builder's `builder-1258` scratch evidence. No test used real GitHub credentials; the repository's autouse offline fixture remained active.

## Route differential

Command: `uv run --no-project --with pytest python .wuwei/scratch/builder-1258/run_differential.py`.
The script creates no production state and runs the repository's route test with a decision-capture plugin in separate archived trees.

Main: `3feedf5ca60ad78ac602cb1a44c165e2aade0263`, 288 routes, passed.
Head: `b5fb247c0512bb264c2b2b8ff672341fd557e7be`, 288 routes, passed.
Corpus SHA256: `de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1`.

No verdict moved. All ten reason changes are listed below. No refusal changed its PR or repository reference.

| Command | Main verdict | Head verdict | Reason movement |
| --- | --- | --- | --- |
| `cd ~/.claude/projects/-repo && printf x >> s.jsonl` | refusal | refusal | HARNESS adds `.codex/sessions` |
| `cd ~/.claude/projects/-repo/memory && echo x >> ../s.jsonl` | refusal | refusal | HARNESS adds `.codex/sessions` |
| `echo x >> ~/.claude/projects/-repo/%6demory/n.md` | refusal | refusal | HARNESS adds `.codex/sessions` |
| `echo x >> ~/.claude/projects/-repo/memory/../s.jsonl` | refusal | refusal | HARNESS adds `.codex/sessions` |
| `echo x >> ~/.claude/projects/-repo/s.jsonl` | refusal | refusal | HARNESS adds `.codex/sessions` |
| `echo x >> ~/.claude/projects/-repo/tool-results/r.txt` | refusal | refusal | HARNESS adds `.codex/sessions` |
| `env -C ~/.claude/projects/-repo tee -a s.jsonl` | refusal | refusal | HARNESS adds `.codex/sessions` |
| `ln -s ../s.jsonl ~/.claude/projects/-repo/memory/n.md` | refusal | refusal | HARNESS adds `.codex/sessions` |
| `tee -a ~/.claude/projects/-repo/s.jsonl` | refusal | refusal | HARNESS adds `.codex/sessions` |
| `tee -a ~/.claude/projects/-repo/s/subagents/agent-a.jsonl` | refusal | refusal | HARNESS adds `.codex/sessions` |

## Generated native path probe

Command: `PYTHONPATH=.wuwei/scratch/builder-1258/head-final/cli uv run --no-project --with pytest python .wuwei/scratch/builder-1258/native_root_probe.py`.

Generated 32 commands, ran the tee door stub 32 times, found 0 holes. Four path classes (`//`, `%xx`, `/./`, `/../`) crossed direct calls and `cd`, `env -C`, `sudo -D`, with plain and pipeline positions. Bash is real; env/sudo are minimal PATH wrappers that execute the tee stub in the requested directory. No privilege request was made. Eight percent-literal controls pass because percent spelling is a literal filesystem name, not URL decoding. The guard parser itself was not changed.

The tracked native tests also cover the existing writer templates, all edit tools, Windows path spellings and wrapper forms. Existing Windows behavior remains subject to platform CI; this local run used POSIX.

## Isolated behavioral mutants

Command: `uv run --no-project --with pytest python .wuwei/scratch/builder-1258/native_mutants.py`.

Every mutant used a fresh archive under the builder's scratch folder, modified both runtime copies, and ran one at a time. Six mutants were killed by behavioral assertions: removing the fork boundary, call-id pairing, latest-final selection, native-root check, child-own settings and notification recipient check. No vendor-drift assertion counted as a kill.

## Safety sweep

- AUTH PASS: the route differential and native launch/root mismatch tests reject unproven parent, call, role, identity and path evidence.
- VAL PASS: native tests cover blank, malformed, duplicate, boundary, unreadable and symlink-escape records; generated path probe is 32/32/0.
- TEST PASS: native stop, attestation, kept-report and delivery assertions reach the real consumers; obsolete categorical Codex guidance tests were updated.
- ERR PASS: malformed or unavailable proof records stay unconfirmed, with no fabricated identity or attestation. Existing hook error handling passed the full suite.
- STATE PASS: native repeated/corrected reports and concurrent delivery use the existing latest-valid store and atomic claims; legacy race cases passed.
- CON PASS: sanitized observed parent/child/notification producer shapes reach the stop and report consumers, including state and turn rows without payload type.
- INF N.A.: no new secret, environment setting, configuration key, entry point, installation or trust operation. Account roots reuse the existing POSIX/Windows account lookup.

## Limits and remaining reviews

Runtime is 3,872 lines: +74 from the 3,798-line parent, within the 111-line item budget and approved 4,000 cap. `git diff --check` passes. Generated agents were built and vendor parity passed.

Independent gates, current-head CI and owner review remain required before readiness. Changed-plugin trust and a fresh native live rehearsal belong to the planner. No approval, old PASS or ledger attestation was imported. The owner-answer bridge is excluded after its separate origin probe found a counterexample. Companion jobs and unsupported transcript roots remain unconfirmed.
