Verdict: FIX
Gate: security
Item: verdict-bind
PR: taoq-ai/wuwei#1249
Head: 63edbf9f1e3450d0aadb9b75c67ab0c352867eed
Confidence: medium

## Findings
- [high] cli/wuwei/hook.py:248 blocks: yes. Failure: the binding is per seat and path, and _report (hook.py:175) accepts any report the seat's transcript holds, so a seat whose first hand-back was refused for its shape (the charter's own retry flow) and then attested FIX at -2.md can be overturned: the session writes a PASS with Supersedes naming the FIX to the first-named path and replays that earlier real report; it is attested and gate_gaps clears the gate (acceptance 1, CWE-345). Binding per seat (any earlier attest row of this agent with another sha records verdict.rewritten) closes it and keeps test_hook.py green (589 passed).
- [low] cli/wuwei/guards.py:383 blocks: no. The -m refusal reads literal argv only: 142 of 195 generated hook calls that really reach the hook parser still pass at head (classes ifs, var, subst, xargs, module cli.wuwei, dashdash `-m wuwei -- hook`, runpy, env -S, brace, dash-c); the same classes pass for bin/wuwei itself at main (`bin/wuwei -- hook Stop`, `env -S 'bin/wuwei hook Stop'`, `a=hook; bin/wuwei $a Stop`), so they are an existing gap, and SECURITY.md already concedes -c and scripts. The transcript check, not this guard, is the boundary.
- [low] cli/wuwei/guards.py:383 blocks: no. Over-refusal: `echo -m wuwei hook`, `git log -m wuwei hook`, `git commit -am wuwei hook`, `tail -m wuwei hook` are now refused; `git commit -m "wuwei hook"` and `grep -m 1 wuwei hook.log` still pass.
- [low] cli/wuwei/upgrade.py:124 blocks: no. The original plant.py (a workspace with config and plan but no ledger) still imports the planted PASS at head, as the promise scopes; every workspace past one `wuwei init` holds a workspace.init row, so a running workspace is covered.

## Probes
- Trees: git archive of main 8c38073 and head 63edbf9 under my scratch folder; nothing run in the main worktree.
- attack.py (security-handback-transcript) at main and head: 60 cases each, 1 moved: the rewrite case went from attest FIX + attest PASS (counted FIX, PASS) at main to attest FIX only (counted FIX) at head. Fix 1 holds for the reproducer.
- plant.py at main and head: both import the PASS and count it (no ledger in that case, inside the promise's scope); builder's repro with a seat.started row is the covered case and its test fails under mutant m3.
- test_rebind.py (new): seat names arch-ccccccc.md (bad shape, refused: hand-back deny / stop verdict.missing), then attests FIX at arch-aaaaaaa.md; session writes PASS + Supersedes at arch-ccccccc.md and replays the first real report. Main and head identical: attest PASS written, gate_gaps empty, for stop and hand-back. With the per-seat binding applied in a copy: verdict.rewritten, gate still missing.
- Guard probe gen2.py/run2.py: 202 commands generated across 13 classes x 6 positions, run under real bash with a stub python3 and bin/wuwei logging argv; 195 reached the hook parser. Holes at main 195, at head 142. Closed at head: quote 38/38, exec -a 9/9, symlinked interpreter 6/6. Open at head: ifs 18, var 15, subst 18, xargs 17, module 11, dashdash 18, runpy 12, env-S 16, brace 12, dash-c 5.
- Builder's door probe (664 generated, 664 ran, 0 holes at head) not rerun; my classes are new ones beside it.
- Route corpus: tests/fixtures/routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 (same at main and head), 288 routes through guards.bash, planner PreToolUse and sentinel PreToolUse at both trees: 0 moved.
- Mutants (applied to cli/wuwei and the vendored copy, run one at a time): m1 drop the -m regex: 6 tests in test_guards.py fail; m2 drop the per-seat branch: both test_hook rewritten cases fail; m3 fresh = True: the new test_upgrade case fails. All killed.
- Attestation path (#1244 follow-up): this PR adds only a no-attest branch for a seat that already holds an attest row for the path with another sha; it does not touch _report or the first attestation, so it does not make the failed hand-back attestation worse.
- Scanner: not run; the diff adds no dependency, workflow or agent tool. Unmeasured.
- Confidence medium: the second-path replay is shown end to end in the repository's own fixtures; how often a real seat's first report is refused is unmeasured.

## Residual risk
Even with the per-seat binding, a rewrite before a seat's first attestation still counts (documented), and the hook guard stays bypassable by argv shapes beyond literal words, so the transcript check carries the boundary.
