# Learning

At each checkpoint the steward reads the report, the ledger and the verdicts and writes the retro
to `.wuwei/retro/<date>.md`, with at most three proposals. Process rules land in
`.wuwei/standards.md`, which the session reads at start and every seat receives in its brief.
Changes to a repository (its memory or skills) become plan items, built and reviewed like any
change.

**Why:** a process that does not learn repeats its mistakes, and a process that only grows
collapses under its own rules. Both directions are needed.

## Defect vaccines

Every escaped defect (a revert, or a follow-up fix to the same lines) is traced to the merge it
came from and the gates that passed it, with their stated confidence. The steward proposes a
regression test item and one line under the gate that should have caught it:
`quality: an error path that ends a long job on a rate-limit error`. The planner passes those lines
to every brief, and the gates check them first.

**Why:** the cheapest defect to catch is one you have already seen escape.

## Calibration and yield

Builders and gates state their confidence (low, medium, high) on every handoff and verdict. The
report shows each gate's yield (verdicts and how many found something to fix) and the confidence
of the verdicts that passed an escaped change.

**Why:** knowing when you do not know is the core of responsible autonomy. An overconfident gate
gets stricter standards; a gate that never finds anything is a cost to question.

## Error budget

From site reliability engineering: when a repository's change failure rate over 28 days (reverts
and failed production deployments over merges, with at least five merges) goes over 15 percent, every tier in that repository rises
one step until it recovers. Light changes get the full gate set; standard changes get the goal gate.

**Why:** autonomy should be earned by results and lost by escapes, automatically, without anyone
configuring it.

## Skills and memory

When seats keep re-learning a repository fact (how to run its tests, a convention, a trap), the
steward proposes a line for that repository's `CLAUDE.md` or `AGENTS.md`. When the same multi-step
procedure recurs three or more times (a hotfix release, a migration), it proposes a project skill
under `.claude/skills/`. Both land through a PR in that repository. `AGENTS.md` is read by other
harnesses too, so the memory travels. WUWEI never writes your personal memory.

**Why:** an agent that relearns the same fact every session pays for it every session.

## Empty the cup

A rule in `.wuwei/standards.md` that caught nothing in 30 days is proposed for removal. A new rule
starts as a note for its first five days, so its false alarms show before it costs anyone time.

**Why:** rules that never fire still cost attention. A process stays light only if it forgets.

## Questions that become rules

The report counts your prompts and how often you chose the recommendation. A kind of question you
keep answering the same way becomes a proposal that the process decides it.

## The weekly sample

Each week the report picks one merged PR at random as a sample for you. It is not a question: read
its evidence comment if you want to. It is how you audit the auditor.
