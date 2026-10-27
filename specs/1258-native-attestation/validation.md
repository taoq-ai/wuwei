# Builder validation

Final source head: `ea78a08d7939360b053372fdadeeabedd6fc66dc`.
Parent: `b6310c55f20a430110007f3050929881e8b68935`, merged normally before source validation.
Both initial gate findings were corrected in one combined fix round. Further changes to this feature's evidence are prose only; runtime hashes must remain unchanged.

## Tests and producer evidence

- Initial native proof/protection red: 375 failed, 33 passed. The first implementation passed 408 native tests.
- Missing-boundary and strict native-parent-root regressions ran red before their fixes. Broader focused checks exposed initial vendor drift, fixed by generation with supported Python.
- The initial full run at b5fb247c passed 4,350 tests with 7 skips. It missed genuine inherited metadata and sensitive identity cases later found by the gates. It is not evidence that those cases worked.
- The genuine fork-all regression preserves child metadata@0, inherited parent metadata/report/model before boundary45, and the child's own report/settings. It failed before moving extra-metadata rejection after the boundary. Own extra metadata remains rejected.
- Both original identity-disclosure regressions plus two distinct-sensitive-identity consumers ran red: 4 failed, 1 ordinary-identity control passed. Shared stable keys at launch and verified stop then preserved isolated board state, unique filenames and exact notification matching.
- Corrected focused run: `uv run --no-project --with pytest python -m pytest -q tests/test_native_identity_privacy.py tests/test_native_evidence.py tests/test_codex.py tests/test_models.py tests/test_setup.py::test_the_vendored_plugin_matches_the_tree_it_was_copied_from`: 614 passed.
- Final full suite: `uv run --no-project --with pytest python .wuwei/scratch/builder-1258/run_full_private.py` launches `python -m pytest -q`, saves the log and exit status, and returns that status. Actual exec exit was 0. Persisted result: 4,356 passed, 7 skipped in 248.22 seconds at the final source head.
- `uv run --no-project --with pytest python .wuwei/scratch/builder-1258/actual_fork_private.py`: the genuine same-workspace desktop parent/child passes the pure reader. Child has 524 strictly increasing rows, one inherited metadata row before boundary45 and no own extra metadata. First-row digest is `d0116d51ec8faaf9ff35899d208a245de789bc76ddeb45ccc301051be6276895`; latest own final digest is `64015ecc9b7b1909db0d478e49fa928f010357e3efd2f5653ee6837d9d5e6112`. No hook, ruling or attestation was invoked.

The earlier 997a2a75 full run is incomplete: its exec session disappeared when the agent ended, its log stops at 95 percent and its exit is unmeasured. It is not counted. An earlier interrupted pre-root-fix run is also superseded. Final logs, exit JSON and probe records remain under the builder's `builder-1258` scratch evidence. No test used real GitHub credentials; the repository's offline fixture remained active.

## Final test-only coverage completion

The LOW review note requested checked-in coverage for rejected-proof identity privacy. Two token/canary cases now supply a mismatched parent and assert a mapped private seat.unconfirmed identity with no seat.stopped or attest row. `uv run --no-project --with pytest python -m pytest -q tests/test_native_identity_privacy.py`: 7 passed in 0.06 seconds, including the two added cases.

A fresh archive of 0b630d40 received the new test and reversed only the rejected-proof seat_identity call in both runtime copies. The two added cases failed behaviorally (2 failed, 5 deselected, exit1). This proves coverage of that consumer rather than vendor drift. Runtime remains byte-identical to ea78a08d. The actual full result remains 4,356 passed and 7 skipped; the added-test run is reported separately, with no new full-suite claim.

## Route differential

Command: `uv run --no-project --with pytest python .wuwei/scratch/builder-1258/run_differential_private.py`.
The decision-capture plugin runs the repository's route tests in separate archived trees.

Main: `3feedf5ca60ad78ac602cb1a44c165e2aade0263`, 288 routes, passed.
Head: `ea78a08d7939360b053372fdadeeabedd6fc66dc`, 288 routes, passed.
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

Command: `PYTHONPATH=.wuwei/scratch/builder-1258/head-private/cli uv run --no-project --with pytest python .wuwei/scratch/builder-1258/native_root_private_probe.py`.

Generated 32 commands, ran the tee door stub 32 times, found 0 holes. Four path classes (`//`, `%xx`, `/./`, `/../`) crossed direct calls and `cd`, `env -C`, `sudo -D`, with plain and pipeline positions. Bash is real; env/sudo are minimal PATH wrappers executing tee in the requested directory. Eight percent-literal controls pass because percent spelling is a literal filesystem name. No privilege request was made; the shell parser was unchanged.

Tracked native tests also cover existing writer templates, edit tools, Windows spellings and wrapper forms. Native Windows execution remains subject to platform CI; this local run used POSIX.

## Isolated behavioral mutants

Command: `uv run --no-project --with pytest python .wuwei/scratch/builder-1258/native_private_mutants.py`.

Eight fresh archives at the final source head modified both runtime copies and ran serially. Every mutant was killed by behavioral assertions: removing the fork boundary, call-id pairing, latest-final selection, native-root check, child-own settings, sensitive identity mapping, distinct sensitive identity keys and notification recipient check. Vendor drift did not count as a kill. The serialized slot then passed explicitly to the delta reviewers for their independent reversals.

## Identity and report mapping

Ordinary canonical task IDs stay unchanged in launch, stop and attestation rows. Credential/canary-bearing IDs use `sha256-` plus the complete raw identity's SHA256 at both launch and verified stop. Distinct sensitive paths stay distinct; masking cannot collapse them to one seat. Raw UUID/path proof happens before mapping. Kept report filenames hash the persisted identity. Native notifications still require the exact canonical author, recipient, frame, body and timestamp; comparison maps that author through the same identity function before the filename hash.

## Safety sweep

- AUTH PASS: `run_differential_private.py` and native proof tests reject unproven parent, call, role, identity, path and root evidence; ordinary native owner answers remain unconfirmed.
- VAL PASS: native suites cover blank, malformed, duplicate, boundary, unreadable and symlink-escape records. Generated path probe is 32/32/0.
- TEST PASS: stop, attestation, board, kept-report and notification assertions reach real consumers. Genuine desktop producer replay supplements synthetic tests.
- ERR PASS: unavailable or mismatched proof stays unconfirmed. Existing hook error handling passed the final full suite.
- STATE PASS: repeated/corrected reports, concurrent delivery and two sensitive paths use existing latest-valid versions and atomic claims.
- CON PASS: observed parent/child/notification shapes and actual producer files reach the pure reader. State/turn payloads without type and inherited metadata remain covered.
- INF N.A.: no new secret, environment setting, configuration key, entry point, installation or trust operation. Roots reuse POSIX/Windows account lookup.

## Limits and remaining reviews

Runtime is 3,877 lines: +79 from the 3,798-line parent, within the 111-line item budget and approved 4,000 cap. `git diff --check` passes; generated agents were built and vendor parity passed. The cap amendment is dated 2026-10-27 in its owner-authorized commit.

Independent delta gates, current-head CI and owner review remain required before readiness. Changed-plugin trust and a fresh native live rehearsal belong to the planner. No approval, historical PASS or ledger attestation was imported. The owner-answer bridge remains excluded after its separate origin probe found a counterexample. Companion jobs and unsupported transcript roots stay unconfirmed.
