Verdict: PASS
Gate: security
Item: handback-transcript
PR: taoq-ai/wuwei#1244
Head: 1022b823d9d4c399e5e0d7193db483dc17b85127
Confidence: medium

## Findings
- [low] cli/wuwei/hook.py:175 blocks: no. Mutant MA (`text in said` changed to `any(text in s for s in said)`, a substring match) survives test_hook.py and test_codex.py, run twice in fresh copies. With it, a payload made of one line of a real report (for example only its `Verdict file:` line) would be accepted. That text is still the seat's own, so nothing is attested from outside the seat, but no test pins the exact match. Missing test: a hand-back whose message is one line of the real report records seat.unconfirmed.
- [medium] cli/wuwei/hook.py:248 blocks: no. Existing gap, outside the item and named in SECURITY.md: when a gate seat's real FIX verdict is rewritten to PASS and its real stop is replayed (`python3 -m wuwei hook SubagentStop` with the real payload), a second attest row (PASS) is recorded, and evidence.verdicts counts both FIX and PASS. Head and main behave the same. Proposed follow-up item: the same agent never attests a second sha for a path it already attested.
- [medium] cli/wuwei/upgrade.py:107 blocks: no. Existing gap, outside the item (the builder flagged it): a seat can Write `.wuwei/days/<date>/decisions/gate-quality-<item>.md` and run `wuwei init`, and the guards refuse neither step. upgrade.verdicts then imports the file as an `imported` attest row, and evidence.verdicts counts it as a quality PASS. Reproduced at both trees. Proposed follow-up item: import only on a 0.34 workspace (a config.0x.toml backup), or never at a seat's init.
- [low] cli/wuwei/guards.py:383 blocks: no. Existing gap: guards refuse `wuwei hook` only when the program name is `wuwei`. `python3 -m wuwei hook SubagentStop < p.json` and `PYTHONPATH=cli python3 -m wuwei hook PreToolUse` both pass guards.bash at head. After this item, a forged payload reaching the hook only records seat.unconfirmed, or replays a real seat's own report (the finding above).
- [low] blocks: no. Expected limit: a hard link, or any file written under ws.PROJECTS, is read as the seat's transcript and can still forge a report (probe "hard link in the folder" attests at both trees). The guards refuse ln, cp, mv, tee and Write on projects paths. SECURITY.md names the quoting bypass as residual until the sandbox item lands.

## Probes
- Head confirmed: origin/leone/handback-transcript is 1022b823d9d4c399e5e0d7193db483dc17b85127, and the merge base with origin/main is b9522fc7. The vendored .claude/wuwei/cli/wuwei/hook.py matches cli/wuwei/hook.py (cmp), and test_the_vendored_plugin_matches_the_tree_it_was_copied_from passes.
- Route corpus differential: head's specs/handback-transcript/route_diff.py re-run on git-archive copies of main and head. Corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1, the same file at both trees. 288 routes read through guards.bash, the planner's PreToolUse and a sentinel seat's PreToolUse: 0 moved.
- Builder's hand-back cases (12): 7 moved, each one from attest (or deny) to seat.unconfirmed. Both real flows (PreToolUse and SubagentStop) record the same rows at main and head.
- Own attack probe: 60 cases at both trees (scratch attack.py). Cases that attest at main and record seat.unconfirmed with no attest at head:
  - a forged report at PreToolUse and at SubagentStop;
  - agent_id set to '../X', 'X/../X', '/X', 'x/../../s0/subagents/agent-X', '*', '', None or 7 (PreToolUse; at SubagentStop all were already unconfirmed at main);
  - the agent path spelled with '//' or '/./' carrying a forged report;
  - a session transcript that is the agent transcript or its meta file;
  - forged text held only in a user tool_result row, a user string row or a Bash tool_use command;
  - one line of the real report, the real report plus a newline, or the real report with CRLF;
  - a builder's transcript and meta named for a sentinel;
  - a symlink out of the projects folder, for the transcript or the meta.
  The real report spelled with '//' or '/./' still attests. '/x/../' fails closed.
- Still attesting at both trees, as expected: a hard link staged under the projects folder, and a replay of another session's real report.
- Residual verdict rewrite reproduced at both trees: FIX attested, the file rewritten to PASS, the real stop replayed, then attest PASS, and evidence counts [arch FIX, arch PASS].
- Residual planted import reproduced at both trees (scratch plant.py): the Write guard returns None, `wuwei init` passes guards.bash, and evidence counts quality PASS.
- Mutants, one at a time in fresh git-archive copies with both runtime copies mutated, running pytest tests/test_hook.py tests/test_codex.py:
  - MB (no agent-<id>.jsonl name check) killed, 18 failed;
  - MF (verdict problem for any non-None report) killed, 88 failed;
  - MI (session transcript launch check dropped) killed, 19 failed;
  - MJ (derived path ignores agent_id) killed, 20 failed;
  - MA (substring match) survived, twice.
  The builder's mutants.txt records M1 to M11 (M5 equivalent, M11 surviving, as the builder explains).
- Targeted tests at head: tests/test_hook.py and tests/test_codex.py, 583 passed. The full suite was not run (as briefed).
- Scanner: the repository's CI runs no secret, dependency or static-analysis scanner, so that scan is unmeasured. guards.SECRETS run over the 1,118-line diff found 0 matches. No home paths in the diff. The fixture transcripts are redacted (cwd /repo, no email).
- Supply chain: no new dependency, lockfile, install script or workflow change in the diff.
- Errors fail closed: a crash in _report at a hand-back records hook.error and attests nothing. Unreadable, odd or NUL paths read as None.
- Confidence medium: all attack shapes I could build against both doors fail closed. The real-harness timing of the hand-back row at PreToolUse is measured by the builder only for Bash, not inside a PreToolUse hook. Two existing gaps outside the item still let a seat turn a FIX into a counted PASS.

## Residual risk
The item's promise holds: no forged payload text is attested at either door, and every steered path fails closed. A seat can still get a PASS counted without a gate writing it, either by rewriting a real verdict and replaying its real stop, or by a planted 0.34 decision file imported at `wuwei init`. Both are existing gaps outside this diff, and both need a follow-up item.
