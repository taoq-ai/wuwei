# Cross-artifact analysis

2026-10-13, before implementation. Reviewed spec, plan, tasks and constitution.

| Requirements | Tasks | Acceptance |
| --- | --- | --- |
| FR-001, FR-002 | T003, T004 | SC-001, replay and identity tests |
| FR-003 | T005, T006 | SC-002, refused or pending hand-back |
| FR-004 | T005, T006 | SC-004, gap with no owner card |
| FR-005, FR-006 | T007, T008 | SC-003, committed build through checks/gates |
| FR-007 | T009, T010 | importer tests and security/race review |

No uncovered requirements, duplicate behaviors, unresolved placeholders, CRITICAL
or HIGH findings. Completion evidence is explicitly required for automatic recovery; clean HEAD alone
never ends a live task. Recovery never supplies invented result text or usage.
No owner design edits. Combined feature and explicit test selection are user
instructions overriding the default one-issue/full-suite workflow.

## Assumption alignment

| Assumption | Relation | Governing source |
| --- | --- | --- |
| Final text is the hand-back | agrees | design 5.2, 5.3 |
| Transport failure is Gap | clarification proposed | design 5.2 retro note |
| Checks and gates still required | agrees | design 5.3, 5.10 |
| Exact desktop payload unavailable | not covered | compatibility fallback authorized by owner |

## Adversarial review and fix round

The independent review found failed-check feedback overwritten by repeat recovery,
mixed business blockers discarded by tooling classification, resultless owner
blockers bypassed, and non-object transcript rows crashing recovery. It also
identified acceptance gaps for resumed tasks, old tooling events and rejected
stop callbacks. All received failing regressions before fixes in the single fix
round. Explicit reconcile also refuses unresolved business blockers.

Initial reproduction: `10 failed, 1 passed, 35 deselected in 0.83s` for seat cases;
`6 failed, 5 passed, 90 deselected in 8.26s` for build recovery. Initial focused
verification: `147 passed in 45.71s`. Review regressions reproduced seven failures.
The first importer run had 7079 passing tests and three fixture convention failures;
the compatibility fixture now uses neutral paths and does not replace the default
example fixture. Post-review focused validation: `446 passed in 78.56s (0:01:18)`.
Delta review and final verification are recorded below.

## Delta review and design reconsideration

The delta found two remaining gaps: unmeasured first-run builders store agent_id
on the seat, so the stopped-only owner-blocker lookup missed them; and permissive
failure matching could still swallow combined business prose ending in "refused".
The approach leaked because it treated successful result recording as the only
source of blocker identity and used arbitrary prose wildcards as classification.
Replace those assumptions: the shared blocker lookup includes unmeasured seats;
transport classification accepts a bounded grammar of known transport-only
statements, preserving ambiguous prose. Add the exact delta counterexamples as
regressions. This is a documented design reconsideration, not another review loop.
The owner's instruction to resolve assumptions and proceed without questions is
applied; no new owner approval is claimed and no additional delegated review runs.

The exact delta regressions failed before implementation:
`2 failed, 2 passed, 73 deselected in 5.41s`. After the shared lookup and bounded
grammar changes, their focused run passed: `9 passed, 68 deselected in 15.89s`.
The broad run also identified two expectations for intentionally removed behavior:
an unknown-completion seat was expected to receive an automatic stop, and the
event inventory lacked seat.result_gap. Both contracts now match FR-003/FR-004.
Focused verification including those contracts: `243 passed in 20.76s`.

## Final verification

Using the task-prescribed interpreter, `-m pytest -q -p no:cacheprovider -n 4`,
and 97 explicit test files selected by searching tests for all changed module
names (brief, hook, agent_launch, verdict, build, state, dispatch):
`7096 passed in 150.42s (0:02:30)`.

All review counterexamples have passing regression coverage. No unresolved
CRITICAL or HIGH findings. Existing atomic build comparison plus the seat snapshot
protect recovery from concurrent seat changes. Final diff checks pass; no new
runtime module or dependency, owner-design change, or home/temp path literal was
added. Work stays uncommitted on the original branch.

Remaining validation limitation: no exact Claude Code desktop 2.1.295 production
payload was available. Compatibility replay covers the supplied documented fields,
existing repository fixtures, transcript fallback and identity aliases.

## Fresh-context field review

The preceding completion claim was disproved by field evidence. The owner now
explicitly authorized the design reconsideration in spec.md. F1-F3 require direct
fixes, F4-F5 deletion, F6 completion evidence, F7 an existing approval mechanism,
and F8-F9 narrower recovery. Requirements and plan now cover each finding. No
unresolved design-level HIGH finding remains before implementation; runtime fixes
and their acceptance tests are pending below.

Before fixes, the two field scenarios plus manual-report variant reproduced:
`3 failed, 53 deselected in 5.12s`. The first refused a delayed matching text row;
the second returned continue again; the manual variant refused a stopped seat.

Follow-up contract regressions before fixes: `6 failed, 2 passed, 158 deselected in 2.50s`.
These cover real terminal results, parent-transcript refusal, completion requirements,
stale launch blockers and recovery advice. Rebind acceptance before implementation:
`4 failed, 25 deselected in 2.87s`. After fixes, focused field/rebind validation:
`11 passed, 60 deselected in 8.44s`. The earlier explicit-reconcile and alias claims
above are historical and superseded by the rewritten spec and contracts.

Requirements review: FR-001 maps to F1/F5; FR-002 to F2/manual verdict;
FR-003 to F3/F8; FR-004 to F4; FR-005 to F6; FR-006 to F7; FR-007 to F9.
All acceptance paths have tests. No design-level CRITICAL or HIGH finding remains.

## Final field follow-up results

- F1 fixed at commands/build.py:544: bounded rereads match the delayed text row;
  persistent mismatches remain refused and no longer blame payload compatibility.
- F2 fixed through commands/build.py:492/544 and commands/seat.py:142: the bound
  ready/continue agent records a new round without a launch hook. The same
  completion does not record twice. Manual --verdict accepts that continued seat.
- F3 fixed at brief.py:289: real terminal tool results do not need toolUseResult.
- F4 removed the prose classifier and all call sites. The builder charter states
  that refused hand-back tools belong under Gap and final text is the report.
- F5 removed normalize_stop, aliases and parent-transcript fallback. Fixtures now
  carry the field-supported agent transcript and final-message fields.
- F6 removed explicit bypass: unknown completion refuses all reconcile paths.
- F7 uses workspace.adopt_worktree and sessions.needs_owner for a same-repository
  rebind. The card names both paths/HEADs and its exact command. Current item/build
  bind approval, seats/item/build are compared at the atomic write, and old build
  evidence is discarded. Changed HEADs, live seats and foreign repos are tested.
- F8 simplified recovery and doctor to --verdict.
- F9 requires a matching bound seat before consulting a resultless blocker.

Both field repros plus manual-report variant, before fixes:
`3 failed, 53 deselected in 5.12s`.
After fixes, the exact three cases:
`3 passed in 0.36s`.
Delayed final text now records its matching report; SendMessage's next round
advances to check rather than repeating continue; manual verdict is accepted.

All importer verification used the prescribed interpreter, explicit files and
`-m pytest -q -p no:cacheprovider -n 4`. The final run covers 102 files, including
all changed runtime module importers plus agents, charters and fixture consumers:
`7446 passed in 86.20s (0:01:26)`.

The tracked net diff decreased from +460 lines before follow-up to +453 lines.
Shared test setup replaced duplicated coverage; no acceptance was dropped.
Diff whitespace checks pass. The original branch is unchanged, all work is
uncommitted, and the design/constitution are untouched. No new runtime module
or dependency, home/temp path literal or em dash was added.

No finding remains open. Validation limitation: the payload is inferred from the
review's real-day evidence, not a captured raw envelope. The race is replayed
with a patched transcript reader; no live desktop session or owner state was changed.

## Round 2 review

The review confirms all round 1 HIGH/MEDIUM findings closed and identifies N1/N2.
The owner explicitly authorized reconsideration. Updated requirements require
bounded retry of partial JSON and original-transcript manual continuation; no
unresolved design-level HIGH finding remains. Custom checklist criteria were
rechecked without changing reviewer-owned markers.

Before implementation, new regressions reproduce the two torn-row entry points
and acceptance of an arbitrary verdict file:
`3 failed, 1 passed, 42 deselected in 0.94s`.

Missing-old-tree cases reproduced before their fix:
`2 failed, 27 deselected in 1.55s`.
Focused verification after changes:
`189 passed in 12.93s`.

N1 retries initial and subsequent ValueError reads inside the same two-second
budget. N2 refuses verdict files for continued rounds, rejects old completions,
and runs existing guards on the recorded agent transcript rather than synthesizing
identity. The helper eligibility check now uses the incoming ID after mismatch
validation. The import-only hook change is reverted.

LOW decisions: stale stop remains deferred, as permitted, because old manually
recorded completions do not supply a reliable SendMessage delivery boundary.
Rebind retains implement: commands/build.py's reconcile only invokes check setup
for planned/build phases, so raised/delta preservation would skip verifying the
new tree. Missing old trees now use explicit missing evidence on the approval
card, and reappearance invalidates the answer. Planner-main-thread enforcement
is recorded as a separate deferred issue; no GitHub command was run.

Final round 2 importer verification: 102 explicit test files, task-prescribed
interpreter with `-m pytest -q -p no:cacheprovider -n 4`:
`7450 passed in 63.01s (0:01:03)`.
No MEDIUM or HIGH finding remains open. LOW dispositions are stated above.
All edits remain uncommitted on 937-seat-results. The design and constitution
are unchanged; diff whitespace and added-path/style checks pass.
