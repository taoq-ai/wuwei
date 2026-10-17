Verdict: PASS
Gate: arch
Item: seat-rules
PR: taoq-ai/wuwei#1111
Head: b823c06225ca4a6af2aeeade199e988d6fab2cdf
Confidence: high
Breaking: no

## Findings
- [low] charters/steward.md:19 blocks: no. "A lesson that fits both is a charter proposal, never a standards line" is a two-way choice, and spec.md Assumptions records it. In a workspace that does not own the plugin, a charter proposal cannot be applied there, so a repository lesson that also concerns seats stays unapplied until the plugin changes. A later retro could add it as a standards line in the meantime.
- [low] blocks: no. Carried from the previous verdict: builder.md:57 (`tests/fixtures/routes.json`) and planner.md:36-37 (`guards.py`, `hook.py`) were already WUWEI-specific on main. This diff does not touch them.

## Probes
- Ran `git diff bec74db b823c06 -- charters tests specs`. The change is limited to _gate.md rules 3 and 4, steward.md rule 4, the matching tests, a spec assumption, and the regenerated and vendored copies.
- Finding 1 from bec74db is closed. _gate.md:26-29 now fires only on "a change to guard parsing ... or rewrites the guard's parser" and glosses door words in place ("the program names and paths a guard matches to refuse a command"). A parser rewrite in an adopter's repository no longer triggers it. `grep -rn "door word" docs skills charters` finds only this glossed line.
- Finding 2 from bec74db is closed. steward.md:17-18 now says "goes in `.wuwei/standards.md` as a line that names that repository", which matches the one standards file per workspace in docs/design.md section 10 and many-repositories.md.
- The rule 3 note is closed. The equivalent-mutant sentence is merged into the differential-probe rule, so there is one standard for "equivalent". Untested is `[low] blocks: no`, which still agrees with "a surviving mutant blocks only when you can name a concrete input". The tie-break note is closed by the new steward line, recorded as an assumption.
- Ran `pytest -q tests/` in a `git archive` copy at b823c06: 1198 passed, 2 skipped. In a second copy committed to a fresh repository, `bin/wuwei agents build` exited 0 and `git status --short` showed no change (acceptance 1).
- Outward contracts: charter text, generated agents and tests only. No CLI, config key or file format change. Breaking: no.
- Confidence is high: the delta is small, wording only, and both fixes match the cited design text exactly.

## Residual risk
Holding all verdicts until the last gate returns makes the builder wait for the slowest gate. The spec bounds that wait; the planner charter does not say so itself.
