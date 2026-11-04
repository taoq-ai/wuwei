# Spec: redteam-goal

Item: redteam-goal, tier smart, domain complex, promise in doubt, goal G-2.

## Explain-back

The goal gate becomes the team's red team. Before it reads any other verdict or the builder's
account, it names the three likeliest ways the change fails its promise in real use: a runtime the
tests stand in for, a sibling path the diff left alone, and a defect class the repository fixed
before. It runs each as a probe in a `git archive` copy of the head and reports each under Probes.
A probe that runs and breaks a promise line blocks under gate rule 5. A risk it cannot run is a
note that names the probe that would settle it. It keeps its goal duties: trace goal to artifact,
compare the explain-back, check drift both ways, and check counts against their population.

At smart, goal joins the gates when the item is complex, or the diff touches owner or risky paths,
besides a promise in doubt. Full keeps all four. The code (`evidence.needed`), `_common.md` Done,
the lead charter, design section 6 and the evidence page say the same rule. The goal row of the
model table follows the spike.

Acceptance in my words:

1. A smart item in the complex domain, or one whose code touches an owner or risky path, owes goal
   when evidence reads its PR. A clear item off those paths, not in doubt, does not.
2. The generated sentinel-goal agent names the three attack classes, the archive-copy probes, and
   says a failure that runs blocks while an unrun risk is a note.
3. The route differential and the smart tier tests, at main and at head, move only rows where goal
   is added on one of the named triggers.
4. Every generated agent keeps 100 words of room under 2,250, and no charter sentence exceeds 35
   words.
5. The PR body cites the spike's recall and false-blocker numbers.

## User scenarios

- US1 (acceptance 1, 3): a builder opens a draft for a complex item, or for a clear item that
  changes an owner or risky path. `wuwei evidence` names goal among the missing gates until a goal
  PASS lands at the head.
- US2 (acceptance 2): the planner launches sentinel-goal. The agent attacks the change first, runs
  its probes in an archive copy, and blocks only on a probe that runs and breaks a promise line.
- US3 (acceptance 4): the charter fitness tests hold at the head.

## Requirements

- FR-001: `evidence.needed` at smart adds goal for a complex (or unclassified) domain, for owner or
  risky code paths, and for a promise in doubt. Docs alone still need no gate.
- FR-002: `charters/sentinel-goal.md` carries the red-team brief the spike validated, adapted to
  the gate's verdict shape, and keeps rules 1 to 7 of the goal duties.
- FR-003: `_common.md` Done, `lead.md` rule 3, `docs/design.md` section 6 and
  `docs/site/concepts/evidence.md` state the same trigger.
- FR-004: the goal row of `planner.md`, `agents.TABLE` and the models page reads Sonnet 5.5 high,
  and Opus 5.5 high at full or on risky, owner or contract paths.
- FR-005: the generated agents and the vendored `.claude/` copy are rebuilt from the charters.

## Success criteria

- SC-001: the new and updated rows in `tests/test_smart.py` and `tests/test_charters.py` fail at
  main and pass at head.
- SC-002: the route differential moves only the complex, owner and risky hosts, each to a goal gap.
- SC-003: runtime lines change by 0 net (cap +3).

## Clarifications

- Q: does the spike show a narrower trigger? A: no case in it settles that. All six escape heads
  touched owner or risky paths (wuwei #1152 `evidence.py`, #1236 `hook.py`, #1247 `guards.py`,
  all owner paths; taoqi #151 workflows, infra and a Dockerfile, #166 infra, #171 a migration, all
  risky). Owner or risky paths alone would catch the same six, but no case was a complex item off
  those paths, so the sample cannot show the complex trigger adds nothing. The item's acceptance 1
  names both; the build keeps both (Assumptions A1).
- Q: where do Attacks, Blocking and Notes go, since the verdict format is out of scope? A: attacks
  and probes under `## Probes`, a blocking failure as a `blocks: yes` finding, a note as
  `blocks: no`.

## Assumptions:

- A1: the trigger stays as the item states it: complex, owner or risky paths, or in doubt. Why: no
  spike case can tell the complex trigger apart (Clarifications). Overturned by a window where goal
  verdicts on complex items off owner and risky paths find nothing the other gates missed.
- A2: the goal row moves to Opus 5.5 high at full or on risky, owner or contract paths, the shape
  of the quality row. Why: the spike's one model miss (taoqi #166, an infra path) blocked on the
  Opus rerun, and on #1236 (an owner path) the Opus rerun found a second blocker, the repeated
  #1198 class. Off those paths Sonnet 5.5 high stays: the go threshold held on Sonnet alone (4 of
  6) and every control ran on Sonnet. Overturned by Opus false blockers above one on the controls,
  which is unmeasured.
- A3: a limit the change discloses, even in part, is a note. Why: the spike's cost line says the
  disclosure clause hid two half-disclosed defects and asks for advisory rows, not blocks.
  Overturned by a half-disclosed limit that escapes because a note did not hold the merge.
- A4: unclassified and other spellings read as complex (`evidence.cynefin`), so they owe goal too.
  Why: "when unsure, go up" already holds for security and arch. Overturned by an owner ruling to
  treat a missing domain as clear.

## How this fails:

1. False blockers flood the queue. Goal now runs on most of this repository's PRs (its owner paths
   are `evidence.py`, `guards.py` and `hook.py`), and on Opus there. The spike's false-blocker
   count (0 of 3 controls, or 1 discounted) is a Sonnet number. Probe: the steward's goal FIX rate
   and its reversals over the next window.
2. A sibling reader computes the gates its own way and misses goal: the error-budget raise turns
   smart into standard, where goal is not owed. `gates_for` keeps every gate the unraised item
   owed, so goal should survive; `test_an_error_budget_overrun_keeps_every_gate_the_unraised_item_owed`
   holds it, and the route differential reads every door.
3. The red team reads the builder's summary first and anchors on it, since the order is a charter
   rule no hook enforces. Probe: goal verdicts whose three attacks restate the PR's own
   `How this fails` lines.

Rollback: revert the commit.
