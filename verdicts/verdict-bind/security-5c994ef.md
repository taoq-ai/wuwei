Verdict: PASS
Gate: security
Item: verdict-bind
PR: taoq-ai/wuwei#1249
Head: 5c994ef0044d0f627a854056197e9aaaf9b268d7
Confidence: medium
Supersedes: verdict-bind/security-63edbf9.md

## Findings
- [low] cli/wuwei/hook.py:175 blocks: no. A seat's last report that names a path it never got attested (its final verdict refused for its shape) still attests whatever that file holds later; SECURITY.md names this as a rewrite before the seat attests a path.
- [low] cli/wuwei/guards.py:383 blocks: no. Hook calls built at run time still pass (101 of 195 that reach the hook parser: ifs 18, var 15, subst 18, xargs 17, env -S 16, brace 12, -c 5), as SECURITY.md now states; the transcript check is the boundary.
- [low] cli/wuwei/guards.py:383 blocks: no. Over-refusal kept: `echo -m wuwei hook`, `git log -m wuwei hook`, `git commit -am wuwei hook`, `tail -m wuwei hook`; `git commit -m "wuwei hook"` and `grep -m 1 wuwei hook.log` pass.
- [low] cli/wuwei/hook.py:175 blocks: no. Equality with the last report is stricter than membership: a SubagentStop payload that carries an earlier text part (if the harness sends one after a hand-back) now records seat.unconfirmed instead of seat.stopped. Unmeasured on real payloads; the hand-back PreToolUse, where attestation happens, still matches (attack.py real cases unchanged).

## Probes
- closed: [high] hook.py:248 second-path replay of an earlier real report at 5c994ef. test_rebind.py at 5c994ef: the replay of the earlier report records seat.unconfirmed at both doors, attest rows stay [FIX], gate_gaps still owes arch (it was cleared at 63edbf9 and main).
- attack.py at 5c994ef: 60 cases, 1 moved against 63edbf9: the same-path rewrite now records verdict.missing (the seat is told) instead of nothing; still one attest row (FIX), counted FIX. The other 59, real hand-back and stop included, are unchanged.
- Guard probe gen2.py/run2.py (202 generated, 195 reached the hook parser under real bash with stub python3 and bin/wuwei): holes main 195, 63edbf9 142, 5c994ef 101. Closed in this delta: module cli.wuwei 11/11, dashdash (`-m wuwei -- hook`, `bin/wuwei -- hook`) 18/18, runpy 12/12. Quote, exec -a and symlink stay closed.
- Route corpus tests/fixtures/routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 (unchanged), 288 routes x guards.bash, planner and sentinel PreToolUse, main vs 5c994ef: 0 moved.
- Mutant (tree and vendored copy): `text == found` reversed to `text in said` fails test_only_a_seats_latest_report_attests_and_a_resumed_seat_attests_its_new_verdict at stop and hand-back. Earlier mutants on 63edbf9 (the -m regex, the same-path branch, fresh = True) were killed; the same-path and upgrade code is unchanged here apart from the returned message and the empty agent_id guard.
- Attestation path: real hand-back and stop cases in attack.py attest as before, so this delta does not make the #1244 attestation failure worse in the fixtures; real payload shapes are unmeasured.
- Scanner: not run; no dependency, workflow or agent tool in the diff. Unmeasured.
- Confidence medium: the reproducers and probes run on the repository's fixtures; real harness stop payloads after a hand-back are unmeasured.

## Residual risk
A seat steered (by a resume message) to name an unattested path in a new last report would attest that file; the hook guard stays bypassable by run-time-built commands, so the transcript check carries the boundary.
