Verdict: PASS
Gate: goal
Item: shell-stdin
PR: taoq-ai/wuwei#1115
Head: f7e30fbfd02531e999589f7cf383310cabb8579d
Confidence: high

## Findings
- [low] blocks: no. docs/design.md changed, though the promise's file list names docs/site/concepts/doors.md. The spec records why under Assumptions: doors.md does not list the unreadable shapes (grep at head finds none), and design.md is the page that does. This is drift toward the requirement, not away from it.
- [low] blocks: no. A shell fed an infra write or a leaking curl on stdin still passes: 3420 of 3840 real-run shapes in probe2 C, the same count on main and head. This is outside the promise, which covers only raw text that names a door program. The spec (How this fails 3) and the PR review notes record it as a candidate item.
- [low] blocks: no. zsh is in SHELLS (guards.py:14) but is not in the probe's shell list. The same _unwrap branch covers it by name, so the probe does not exercise that branch through zsh.

## Probes
- Trees: git archive of f7e30fb (head) and 86135fa (base) into scratchpad/goal-shell-stdin/{head,base}. PR read once through gh api: draft true, head.sha f7e30fbf...
- Acceptance 1 (l1.py, stub git on PATH, bash -c): at head all 6 commands logged 'push origin main' and guards.bash refused each one. At base all 6 also logged the push, and guards.bash passed all 6.
- Acceptance 2: copied the builder's genprobe.py into my scratch and ran it. Head: 912 generated, 803 ran the push, 0 holes. Base: 912, 803, 586 holes. probe2.py at head: A push through fed shells 4032/3840/0 holes; B infra after fd 576/467/0; B leak after fd 576/468/0. At base: 3420, 300 and 300 holes.
- Acceptance 3: bash run.sh, echo hi | bash, bash -c 'echo hi', echo {a,b}>x and diff <(sort a) <(sort b) all pass at head (and at base).
- Acceptance 4: pytest -q gave 1238 passed, 2 skipped at head and 1204 passed, 2 skipped at base, each with the builder's route dump test added. The 168-route dumps are byte-identical between head and base (cmp). tests/fixtures/routes.json is unchanged. The corpus/seat tests (-k "corpus or seat") gave 30 passed at head.
- Scope: git diff --stat 86135fa f7e30fb shows only guards.py and its vendored copy (cmp identical), tests/test_guards.py (additions only), docs/design.md and specs/shell-stdin/*. Runtime is 2976 lines on both trees, within the +2 budget.
- Spec: the explain-back in spec.md matches the promise's two parts, all 4 acceptance lines, the Outside list, Rollback and the corpus assumption. The PR body's numbers match my reruns.
- Confidence high: I re-ran every acceptance line on both trees and got the same results. A corpus row moving from pass to refuse in real seat use would change it.

## Residual risk
Real seats may chain a script run with a door command (accepted false refusal). A shell fed an infra write or a leak on stdin is still open, the same as on main.
