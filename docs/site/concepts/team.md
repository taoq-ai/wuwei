# The team and its charters

| Role | Does | Why it is a separate role |
| --- | --- | --- |
| planner | your session: plans with the lead, launches seats, follows the board, asks you what is yours | one place where your attention is spent |
| lead | discovery, readiness, scope, tier, ranking, red-teaming the plan | deciding what to build is a different skill from building it |
| builder | one item, test first, in its own branch and worktree | small, isolated changes are easier to review and undo |
| sentinel-arch | architecture gate | contracts and boundaries break quietly |
| sentinel-quality | quality gate, on a different model | tests that do not test, code that should not exist |
| sentinel-security | security gate | trust boundaries need a reviewer who looks only at them |
| sentinel-goal | goal gate (full tier) | building the wrong thing well is still wrong |
| shepherd | PRs from raise to merge: reviewers, threads, CI, conflicts, the evidence comment | PRs die of neglect, not of bad code |
| steward | the retro at each checkpoint | someone must learn from the day without being in it |

## Charters are the one source

Each role's conduct is a charter in `charters/`: `_common.md` for everyone, `_common-authoring.md`
for roles that write for people, `_gate.md` for the sentinels, and one file per role. The agents
in `agents/` are generated from them (`wuwei agents build`) with a reviewed tool grant per role
(`agents/allowlist.json`), and a test fails if they drift.

**Why:** a rule written in two places drifts. The charter is where a rule lives; the agent is how
the harness receives it.

## Independence

The sentinels review the diff, the requirement and the running code, never the builder's summary.
They run probes and mutants in a scratch copy of the tree at the head they review. Their verdicts
count only when [attested](evidence.md#attested-verdicts).

One gate (quality) runs on a different model than the session's by default, so the reviews do not
share every blind spot. Change it in `cli/wuwei/agents.py` (`MODELS`).

**Why:** a reviewer who shares the author's assumptions finds the author's mistakes only by luck.

## Seats cannot ask you

Seats have no AskUserQuestion tool. Only the planner reaches you, and only with an owner-class
question.

**Why:** one voice, batched, with a recommendation, instead of every agent interrupting you.

## Standards travel with the brief

Seats do not see the session's context, so the planner passes each seat the lines of
`.wuwei/standards.md` for its role: the defects this workspace has seen escape, the rules the retro
promoted.
